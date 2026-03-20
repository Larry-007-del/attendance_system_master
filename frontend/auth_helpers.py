"""
Phase 3: Authentication & Authorization Helpers

This module provides custom decorators, permission utilities, and role-based access control
for the Exodus attendance system.
"""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth.models import Permission, Group
from django.core.cache import cache
from datetime import timedelta


# ==================== Role-Based Decorators ====================

def student_required(view_func):
    """Restrict view to students only."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'student'):
            messages.error(request, "This area is reserved for students only.")
            return redirect('frontend:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def lecturer_required(view_func):
    """Restrict view to lecturers only."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'lecturer'):
            messages.error(request, "This area is reserved for lecturers only.")
            return redirect('frontend:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_or_lecturer_required(view_func):
    """Restrict view to admins or lecturers."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_superuser or hasattr(request.user, 'lecturer')):
            messages.error(request, "You do not have permission to access this page.")
            return redirect('frontend:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def two_factor_required(view_func):
    """Ensure user has completed 2FA verification (if enabled)."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # Check if user has 2FA enabled
        if hasattr(request.user, 'lecturer') and request.user.lecturer.is_two_factor_enabled:
            # Check if 2FA was completed in this session
            if not request.session.get('2fa_verified'):
                messages.warning(request, "Please complete 2-factor authentication.")
                return redirect('frontend:verify_2fa')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== Rate Limiting ====================

class RateLimiter:
    """Helper class for rate limiting by IP address or user."""
    
    def __init__(self, attempts_max=5, window_seconds=300):
        self.attempts_max = attempts_max
        self.window_seconds = window_seconds
    
    def get_identifier(self, request, user_based=False):
        """Get rate limit identifier (IP or user ID)."""
        if user_based and request.user.is_authenticated:
            return f"rate_limit_user_{request.user.id}"
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        return f"rate_limit_ip_{ip}"
    
    def is_rate_limited(self, request, user_based=False):
        """Check if request is rate limited."""
        identifier = self.get_identifier(request, user_based)
        attempts = cache.get(identifier, 0)
        return attempts >= self.attempts_max
    
    def increment(self, request, user_based=False):
        """Increment rate limit counter."""
        identifier = self.get_identifier(request, user_based)
        attempts = cache.get(identifier, 0)
        cache.set(identifier, attempts + 1, self.window_seconds)
    
    def reset(self, request, user_based=False):
        """Reset rate limit counter."""
        identifier = self.get_identifier(request, user_based)
        cache.delete(identifier)


# ==================== Permission Utilities ====================

def create_default_groups():
    """Create default user groups with permissions."""
    from django.contrib.auth.models import Permission, Group
    from django.contrib.contenttypes.models import ContentType
    from attendance.models import Student, Lecturer, Course, Attendance
    
    # Admin group (superusers)
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    
    # Lecturer group
    lecturer_group, _ = Group.objects.get_or_create(name='Lecturer')
    lecturer_permissions = Permission.objects.filter(
        content_type__app_label='attendance',
        codename__in=['view_attendance', 'add_attendance', 'change_attendance', 'view_student', 'view_course']
    )
    lecturer_group.permissions.set(lecturer_permissions)
    
    # Student group
    student_group, _ = Group.objects.get_or_create(name='Student')
    student_permissions = Permission.objects.filter(
        content_type__app_label='attendance',
        codename__in=['view_attendance', 'view_course']
    )
    student_group.permissions.set(student_permissions)


def assign_user_group(user, role='student'):
    """Assign user to appropriate group based on role."""
    from django.contrib.auth.models import Group
    
    # Remove from all groups first
    user.groups.clear()
    
    # Assign new group
    if role == 'lecturer':
        group = Group.objects.get_or_create(name='Lecturer')[0]
    elif role == 'admin':
        group = Group.objects.get_or_create(name='Admin')[0]
    else:  # student
        group = Group.objects.get_or_create(name='Student')[0]
    
    user.groups.add(group)


# ==================== Session Security ====================

def mark_2fa_verified(request):
    """Mark that user has completed 2FA in current session."""
    request.session['2fa_verified'] = True
    request.session['2fa_verified_at'] = __import__('time').time()
    request.session.set_expiry(minutes=30)  # Require re-verification after 30 minutes


def is_2fa_valid(request, max_age_seconds=1800):
    """Check if 2FA verification is still valid (default 30 minutes)."""
    if not request.session.get('2fa_verified'):
        return False
    
    verified_at = request.session.get('2fa_verified_at', 0)
    return (__import__('time').time() - verified_at) < max_age_seconds


# ==================== Mobile API Authentication ====================

def api_token_required(view_func):
    """
    Decorator for API endpoints that require token authentication.
    Token should be passed as Bearer token in Authorization header.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return HttpResponseForbidden(json.dumps({'error': 'Missing or invalid authorization'}),
                                        content_type='application/json')
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Token validation would happen here (check against database)
        # For now, this is a placeholder
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== Permission Checkers ====================

def user_can_edit_course(user, course):
    """Check if user can edit a course."""
    if user.is_superuser:
        return True
    if hasattr(user, 'lecturer') and user.lecturer == course.lecturer:
        return True
    return False


def user_can_view_attendance(user, attendance):
    """Check if user can view attendance record."""
    if user.is_superuser:
        return True
    if hasattr(user, 'lecturer') and user.lecturer == attendance.created_by:
        return True
    if hasattr(user, 'student') and user.student in attendance.students.all():
        return True
    return False


def user_can_edit_student(user, student):
    """Check if user can edit student record."""
    if user.is_superuser:
        return True
    if hasattr(user, 'student') and user.student == student:
        return True
    return False
