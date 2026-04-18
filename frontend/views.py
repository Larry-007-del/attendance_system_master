from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.utils.http import url_has_allowed_host_and_scheme
import secrets
from functools import wraps
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timedelta
import csv
import io
import openpyxl
from openpyxl import Workbook

from attendance.models import Lecturer, Student, Course, Attendance, AttendanceToken, CourseEnrollment, AttendanceStudent, WebAuthnCredential
from django.contrib.auth.models import User
from .forms import LecturerForm, StudentForm, CourseForm, StudentUploadForm, CourseEnrollmentUploadForm


def admin_required(view_func):
    """Restrict view to superusers only. Redirects others to dashboard with error."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('frontend:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_required(view_func):
    """Restrict view to superusers or lecturers. Redirects students to dashboard."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_superuser or hasattr(request.user, 'lecturer')):
            messages.error(request, "You do not have permission to access this page.")
            return redirect('frontend:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== Authentication ====================

def login_view(request):
    """View for user login with brute-force rate limiting"""
    if request.method == "POST":
        # Rate limiting: max 5 attempts per IP per 5 minutes
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        cache_key = f'login_attempts_{ip}'
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            messages.error(request, "Too many login attempts. Please try again in a few minutes.")
            return render(request, 'frontend/login.html', {'form': AuthenticationForm()})

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            cache.delete(cache_key)  # Reset on successful login
            next_url = request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect('frontend:dashboard')
        else:
            cache.set(cache_key, attempts + 1, 300)  # 5-minute window
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'frontend/login.html', {'form': form})


from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect

@ensure_csrf_cookie
@csrf_protect
def logout_view(request):
    """View for user logout - POST only for CSRF safety"""
    if request.method == 'POST':
        logout(request)
        return redirect('frontend:login')
    # GET requests should not log out (CSRF protection)
    return redirect('frontend:dashboard')


def register_view(request):
    """Self-registration for new students."""
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')

    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')
        cache_key = f'register_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, "Too many registration attempts. Please try again later.")
            return render(request, 'frontend/register.html')

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # Validation
        errors = []
        if not username or not email or not password1:
            errors.append('All fields are required.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.objects.filter(username=username).exists():
            errors.append('Username is already taken.')
        if User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists.')

        if errors:
            cache.set(cache_key, attempts + 1, 300)
            for error in errors:
                messages.error(request, error)
            return render(request, 'frontend/register.html')

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=username,
        )

        # Auto-generate student_id (STU + zero-padded pk)
        student_id = f'STU{user.pk:05d}'
        Student.objects.create(
            user=user,
            student_id=student_id,
            name=username,
        )

        cache.delete(cache_key)
        # Auto-login after registration
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome to Exodus! Your Student ID is {student_id}.')
        return redirect('frontend:dashboard')

    return render(request, 'frontend/register.html')


# ==================== Dashboard ====================

@login_required
def dashboard(request):
    """Main dashboard view - safe for all user types"""
    context = {
        'role_label': 'User',
        'attendance_rate': 0,
        'next_class': 'No upcoming sessions',
        'is_student': False,
        'is_lecturer': False,
        'is_admin': request.user.is_superuser,
    }

    # Safely determine user role
    if request.user.is_superuser:
        context['role_label'] = 'Administrator'
        # Admin stats
        context['total_students'] = Student.objects.count()
        context['total_lecturers'] = Lecturer.objects.count()
        context['total_courses'] = Course.objects.count()
        context['active_sessions'] = Attendance.objects.filter(is_active=True, date=timezone.localdate()).count()
        context['recent_activity'] = Attendance.objects.select_related('course').order_by('-date', '-created_at')[:6]
    elif hasattr(request.user, 'lecturer'):
        try:
            if request.user.lecturer:
                lecturer = request.user.lecturer
                context['is_lecturer'] = True
                context['role_label'] = 'Lecturer'
                taught_courses = Course.objects.filter(lecturer=lecturer).annotate(
                    enrolled_count=Count('students')
                )
                context['taught_courses'] = taught_courses

                # Compute lecturer stats
                context['total_sessions'] = Attendance.objects.filter(course__lecturer=lecturer).count()
                active_session = Attendance.objects.filter(
                    course__lecturer=lecturer, is_active=True, date=timezone.localdate()
                ).select_related('course').first()
                if active_session:
                    context['next_class'] = f"{active_session.course.name} (Live now)"
                    context['active_session'] = active_session
                else:
                    context['next_class'] = f"{taught_courses.count()} course{'s' if taught_courses.count() != 1 else ''} assigned"
        except Lecturer.DoesNotExist:
            pass
    elif hasattr(request.user, 'student'):
        try:
            if request.user.student:
                student = request.user.student
                context['is_student'] = True
                context['role_label'] = 'Student'

                enrolled_courses = Course.objects.filter(students=student).select_related('lecturer')
                context['enrolled_courses'] = enrolled_courses

                # Compute real attendance rate
                total_sessions = Attendance.objects.filter(course__students=student).distinct().count()
                attended_sessions = Attendance.objects.filter(present_students=student).distinct().count()
                if total_sessions > 0:
                    context['attendance_rate'] = round((attended_sessions / total_sessions) * 100)
                else:
                    context['attendance_rate'] = 0

                # Find next active session the student can join
                active_session = Attendance.objects.filter(
                    course__students=student, is_active=True, date=timezone.localdate()
                ).select_related('course').first()
                if active_session:
                    context['next_class'] = f"{active_session.course.name} (Live now)"
        except Student.DoesNotExist:
            pass

    return render(request, 'dashboard.html', context)


@login_required
def checkin_view(request):
    """Check-in page with GPS pulsing button"""
    return render(request, 'frontend/checkin.html')


@login_required
def profile_view(request):
    """View and edit user profile for students and lecturers"""
    user = request.user
    profile = None
    profile_type = None

    if hasattr(user, 'lecturer'):
        profile = user.lecturer
        profile_type = 'lecturer'
    elif hasattr(user, 'student'):
        profile = user.student
        profile_type = 'student'

    if request.method == 'POST' and profile:
        # Update common user fields
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'That email is already in use.')
                return redirect('frontend:profile')

        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email
        user.save()

        # Update profile-specific fields
        profile.name = request.POST.get('name', profile.name)
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)

        if profile_type == 'student':
            profile.programme_of_study = request.POST.get('programme_of_study', profile.programme_of_study)
            profile.year = request.POST.get('year', profile.year)
            profile.notification_preference = request.POST.get('notification_preference', profile.notification_preference)
            profile.is_notifications_enabled = request.POST.get('is_notifications_enabled') == 'on'
        elif profile_type == 'lecturer':
            profile.department = request.POST.get('department', profile.department)

        profile.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('frontend:profile')

    # Compute stats for display
    stats = {}
    if profile_type == 'student':
        total = Attendance.objects.filter(course__students=profile).distinct().count()
        attended = Attendance.objects.filter(present_students=profile).distinct().count()
        stats['total_sessions'] = total
        stats['attended_sessions'] = attended
        stats['attendance_rate'] = round((attended / total) * 100) if total > 0 else 0
        stats['enrolled_courses'] = Course.objects.filter(students=profile).count()
    elif profile_type == 'lecturer':
        stats['total_sessions'] = Attendance.objects.filter(course__lecturer=profile).count()
        stats['total_courses'] = Course.objects.filter(lecturer=profile).count()
        stats['total_students'] = Student.objects.filter(
            enrolled_courses__lecturer=profile
        ).distinct().count()

    context = {
        'profile': profile,
        'profile_type': profile_type,
        'stats': stats,
    }
    return render(request, 'frontend/profile.html', context)


@login_required
def change_password(request):
    """Change the logged-in user's password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('frontend:change_password')

        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('frontend:change_password')

        # Validate using Django's built-in password validators
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(new_password, user=request.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('frontend:change_password')

        request.user.set_password(new_password)
        request.user.save()

        # Keep the user logged in after password change
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password changed successfully!')
        return redirect('frontend:profile')

    return render(request, 'frontend/change_password.html')


@staff_required
def ajax_dashboard_stats(request):
    """HTMX endpoint for dashboard statistics — admin/lecturer only (cached 60s)"""
    cache_key = 'dashboard_stats'
    stats = cache.get(cache_key)
    if stats is None:
        stats = {
            'total_lecturers': Lecturer.objects.count(),
            'total_students': Student.objects.count(),
            'total_courses': Course.objects.count(),
            'active_courses': Course.objects.filter(is_active=True).count(),
            'today_attendance': Attendance.objects.filter(date=timezone.localdate()).count(),
        }
        cache.set(cache_key, stats, 60)
        
    if request.headers.get('HX-Request'):
        return render(request, 'partials/admin_stats.html', stats)
    return JsonResponse(stats)


@staff_required
def chart_weekly_attendance(request):
    """Returns attendance sessions over the last 7 days"""
    today = timezone.localdate()
    start_date = today - timedelta(days=6)
    
    records = Attendance.objects.filter(date__gte=start_date, date__lte=today).values('date').annotate(
        sessions=Count('id')
    ).order_by('date')
    
    date_list = [(start_date + timedelta(days=i)) for i in range(7)]
    labels = [d.strftime('%a') for d in date_list]
    data = [0] * 7
    
    for r in records:
        if r['date'] in date_list:
            idx = date_list.index(r['date'])
            data[idx] = r['sessions']
            
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Live Sessions',
            'data': data,
            'backgroundColor': 'rgba(79, 70, 229, 0.2)',
            'borderColor': 'rgba(79, 70, 229, 1)',
            'borderWidth': 2,
            'tension': 0.4,
            'fill': True
        }]
    })


@staff_required
def chart_course_enrollment(request):
    """Returns top courses by enrollment"""
    courses = Course.objects.annotate(enrolled=Count('students')).order_by('-enrolled')[:5]
    labels = [c.name for c in courses]
    data = [c.enrolled for c in courses]
    
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': [
                '#4f46e5', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'
            ]
        }]
    })


@staff_required
def chart_department_stats(request):
    """Returns distribution of lecturers by department"""
    depts = Lecturer.objects.values('department').annotate(count=Count('id')).order_by('-count')
    labels = [d['department'] if d['department'] else 'Other' for d in depts]
    data = [d['count'] for d in depts]
    
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Lecturers per Dept',
            'data': data,
            'backgroundColor': 'rgba(59, 130, 246, 0.8)'
        }]
    })

@login_required
def chart_lecturer_course_stats(request):
    """Returns average attendance percentage per course taught by lecturer.

    Uses a single aggregated query instead of N+1 per-session loops.
    """
    if not hasattr(request.user, 'lecturer'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    lecturer = request.user.lecturer

    # Annotate each course with session count and enrolled count in one pass
    courses = (
        Course.objects.filter(lecturer=lecturer)
        .annotate(
            total_sessions=Count('attendance', distinct=True),
            enrolled_count=Count('students', distinct=True),
        )
    )

    # Aggregate actual attendances per course in a single query
    # AttendanceStudent links each marked attendance to a student
    actual_counts = (
        AttendanceStudent.objects
        .filter(attendance__course__lecturer=lecturer)
        .values('attendance__course_id')
        .annotate(actual=Count('id'))
    )
    actual_by_course = {row['attendance__course_id']: row['actual'] for row in actual_counts}

    labels = []
    rates = []

    for course in courses:
        labels.append(course.course_code)
        total_sessions = course.total_sessions
        enrolled_students = course.enrolled_count

        if total_sessions == 0 or enrolled_students == 0:
            rates.append(0)
            continue

        total_possible = total_sessions * enrolled_students
        total_actual = actual_by_course.get(course.pk, 0)
        rates.append(round((total_actual / total_possible) * 100))

    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Average Attendance (%)',
            'data': rates,
            'backgroundColor': 'rgba(139, 92, 246, 0.5)',  # Violet
            'borderColor': '#8b5cf6',
            'borderWidth': 1,
            'borderRadius': 4
        }]
    })

@login_required
def chart_student_history(request):
    """Returns student's attendance sessions over the last 30 days"""
    if not hasattr(request.user, 'student'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    student = request.user.student
    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    
    records = Attendance.objects.filter(
        present_students=student,
        date__gte=start_date,
        date__lte=today
    ).values('date').annotate(
        sessions=Count('id')
    ).order_by('date')
    
    # We will aggregate by week to keep it clean, or just plot individual days that had attendance
    date_list = [(start_date + timedelta(days=i)) for i in range(30)]
    labels = [d.strftime('%b %d') for d in date_list]
    data = [0] * 30
    
    for r in records:
        if r['date'] in date_list:
            idx = date_list.index(r['date'])
            data[idx] = r['sessions']
            
    # Filter out empty past dates at start to make chart nicer (optional)
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Classes Attended',
            'data': data,
            'backgroundColor': 'rgba(99, 102, 241, 0.2)',
            'borderColor': '#6366f1',
            'borderWidth': 2,
            'fill': True,
            'tension': 0.4
        }]
    })

@login_required
def chart_student_course_breakdown(request):
    """Returns attended vs missed sessions per enrolled course for a student"""
    if not hasattr(request.user, 'student'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    student = request.user.student
    courses = Course.objects.filter(students=student)
    
    labels = []
    attended_data = []
    missed_data = []
    
    for course in courses:
        labels.append(course.course_code)
        
        # Get count of total distinct sessions for this course
        total_sessions = Attendance.objects.filter(course=course).count()
        attended_sessions = Attendance.objects.filter(course=course, present_students=student).count()
        
        attended_data.append(attended_sessions)
        missed_data.append(max(0, total_sessions - attended_sessions))
        
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Attended',
                'data': attended_data,
                'backgroundColor': '#10b981', # Emerald
                'borderRadius': 4
            },
            {
                'label': 'Missed',
                'data': missed_data,
                'backgroundColor': '#ef4444', # Red
                'borderRadius': 4
            }
        ]
    })


# ==================== Lecturers ====================

@admin_required
def lecturer_list(request):
    """List all lecturers (admin only) with HTMX sort & search"""
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'name')
    
    lecturers = Lecturer.objects.select_related('user').all()
    
    if query:
        lecturers = lecturers.filter(
            Q(name__icontains=query) | Q(staff_id__icontains=query) | Q(department__icontains=query)
        )
        
    allowed_sorts = ['name', '-name', 'staff_id', '-staff_id', 'department', '-department']
    if sort in allowed_sorts:
        lecturers = lecturers.order_by(sort)
    else:
        lecturers = lecturers.order_by('name')
        sort = 'name'
    
    paginator = Paginator(lecturers, 20)
    page = request.GET.get('page')
    try:
        lecturers_page = paginator.page(page)
    except PageNotAnInteger:
        lecturers_page = paginator.page(1)
    except EmptyPage:
        lecturers_page = paginator.page(paginator.num_pages)
    
    context = {
        'lecturers': lecturers_page,
        'query': query,
        'sort': sort,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'partials/lecturer_list_content.html', context)
    return render(request, 'lecturers/list.html', context)


@admin_required
def lecturer_create(request):
    """Create new lecturer (admin only)"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get user data
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                
                # Validate required fields
                if not username or not password:
                    messages.error(request, 'Username and password are required')
                    form = LecturerForm(request.POST)
                    return render(request, 'lecturers/create.html', {'form': form})
                
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists')
                    form = LecturerForm(request.POST)
                    return render(request, 'lecturers/create.html', {'form': form})
                
                # Check password strength
                try:
                    from django.contrib.auth.password_validation import validate_password
                    validate_password(password)
                except ValidationError as e:
                    for error in e.messages:
                        messages.error(request, error)
                    form = LecturerForm(request.POST)
                    return render(request, 'lecturers/create.html', {'form': form})
                
                user = User.objects.create_user(username=username, email=email, password=password)
                
                # Create lecturer profile
                lecturer = Lecturer(
                    user=user,
                    staff_id=request.POST.get('staff_id'),
                    name=request.POST.get('name'),
                    department=request.POST.get('department'),
                    phone_number=request.POST.get('phone_number'),
                    latitude=request.POST.get('latitude') or None,
                    longitude=request.POST.get('longitude') or None,
                )
                
                if 'profile_picture' in request.FILES:
                    lecturer.profile_picture = request.FILES['profile_picture']
                
                # Validate lecturer fields
                form = LecturerForm(request.POST, request.FILES, instance=lecturer)
                if form.is_valid():
                    form.save()
                    messages.success(request, f'Lecturer {lecturer.name} created successfully!')
                    return redirect('frontend:lecturer_list')
                else:
                    # Transaction will rollback automatically
                    raise ValueError("Form Invalid")
        except ValueError:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.replace("_", " ").title()}: {error}')
            return render(request, 'lecturers/create.html', {'form': form})
    
    # GET request: render empty form
    return render(request, 'lecturers/create.html', {'form': LecturerForm()})


@login_required
def lecturer_detail(request, pk):
    """View lecturer details"""
    lecturer = get_object_or_404(Lecturer, pk=pk)
    
    # Access control: admin, the lecturer themselves, or a student enrolled in their courses
    if not request.user.is_superuser:
        if hasattr(request.user, 'lecturer') and request.user.lecturer.pk == lecturer.pk:
            pass  # Lecturer can view their own profile
        elif hasattr(request.user, 'student'):
            # Only students in their courses can view
            if not CourseEnrollment.objects.filter(student=request.user.student, course__lecturer=lecturer).exists():
                 messages.error(request, 'You do not have permission to view this profile.')
                 return redirect('frontend:dashboard')
        else:
            messages.error(request, 'You do not have permission to view this profile.')
            return redirect('frontend:dashboard')

    courses = Course.objects.filter(lecturer=lecturer)
    
    context = {
        'lecturer': lecturer,
        'courses': courses,
    }
    return render(request, 'lecturers/detail.html', context)


@admin_required
def lecturer_two_factor_settings(request, pk):
    """Manage lecturer 2FA settings"""
    lecturer = get_object_or_404(Lecturer, pk=pk)
    
    if request.method == 'POST':
        lecturer.require_two_factor_auth = request.POST.get('require_two_factor_auth') == 'on'
        lecturer.save()
        messages.success(request, '2FA settings updated successfully!')
        return redirect('frontend:lecturer_detail', pk=pk)
    
    context = {
        'lecturer': lecturer,
    }
    return render(request, 'lecturers/two_factor_settings.html', context)


@admin_required
def lecturer_edit(request, pk):
    """Edit lecturer (admin only)"""
    lecturer = get_object_or_404(Lecturer, pk=pk)
    
    if request.method == 'POST':
        lecturer.name = request.POST.get('name')
        lecturer.department = request.POST.get('department')
        lecturer.phone_number = request.POST.get('phone_number')
        
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        try:
            lecturer.latitude = float(lat) if lat else None
        except (ValueError, TypeError):
            lecturer.latitude = None
        try:
            lecturer.longitude = float(lon) if lon else None
        except (ValueError, TypeError):
            lecturer.longitude = None
            
        if 'profile_picture' in request.FILES:
            lecturer.profile_picture = request.FILES['profile_picture']
        
        lecturer.save()
        messages.success(request, f'Lecturer {lecturer.name} updated successfully!')
        return redirect('frontend:lecturer_detail', pk=pk)
    
    context = {'lecturer': lecturer}
    return render(request, 'lecturers/edit.html', context)


@admin_required
def lecturer_delete(request, pk):
    """Delete lecturer (admin only)"""
    lecturer = get_object_or_404(Lecturer, pk=pk)
    
    if request.method == 'POST':
        user = lecturer.user
        lecturer.delete()
        user.delete()
        messages.success(request, 'Lecturer deleted successfully!')
        return redirect('frontend:lecturer_list')
    
    context = {'lecturer': lecturer}
    return render(request, 'lecturers/delete.html', context)


@login_required
def ajax_search_lecturers(request):
    """Search lecturers for HTMX"""
    query = request.GET.get('q', '')
    lecturers = Lecturer.objects.select_related('user').filter(
        Q(name__icontains=query) | Q(staff_id__icontains=query)
    )[:10]
    
    return render(request, 'partials/lecturer_rows.html', {'lecturers': lecturers})


# ==================== Students ====================

@admin_required
def student_list(request):
    """List all students (admin only) with HTMX sort & search"""
    query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')
    programme_filter = request.GET.get('programme', '')
    sort = request.GET.get('sort', 'name')
    
    students = Student.objects.select_related('user').all()
    
    if query:
        students = students.filter(
            Q(name__icontains=query) | Q(student_id__icontains=query)
        )
    if year_filter:
        students = students.filter(year=year_filter)
    if programme_filter:
        students = students.filter(programme_of_study=programme_filter)
        
    allowed_sorts = ['name', '-name', 'student_id', '-student_id', 'year', '-year', 'programme_of_study', '-programme_of_study']
    if sort in allowed_sorts:
        students = students.order_by(sort)
    else:
        students = students.order_by('name')
        sort = 'name'
    
    paginator = Paginator(students, 20)
    page = request.GET.get('page')
    try:
        students_page = paginator.page(page)
    except PageNotAnInteger:
        students_page = paginator.page(1)
    except EmptyPage:
        students_page = paginator.page(paginator.num_pages)
    
    context = {
        'students': students_page,
        'query': query,
        'year_filter': year_filter,
        'programme_filter': programme_filter,
        'sort': sort,
        'years': Student.objects.values_list('year', flat=True).distinct(),
        'programmes': Student.objects.values_list('programme_of_study', flat=True).distinct(),
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'partials/student_list_content.html', context)
    return render(request, 'students/list.html', context)


@admin_required
def student_create(request):
    """Create new student (admin only)"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                
                # Validate required fields
                if not username or not password:
                    messages.error(request, 'Username and password are required')
                    form = StudentForm(request.POST)
                    return render(request, 'students/create.html', {'form': form})
                
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists')
                    form = StudentForm(request.POST)
                    return render(request, 'students/create.html', {'form': form})
                
                # Check password strength
                try:
                    from django.contrib.auth.password_validation import validate_password
                    validate_password(password)
                except ValidationError as e:
                    for error in e.messages:
                        messages.error(request, error)
                    form = StudentForm(request.POST)
                    return render(request, 'students/create.html', {'form': form})
                
                user = User.objects.create_user(username=username, email=email, password=password)
                
                student = Student(
                    user=user,
                    student_id=request.POST.get('student_id'),
                    name=request.POST.get('name'),
                    programme_of_study=request.POST.get('programme_of_study'),
                    year=request.POST.get('year'),
                    phone_number=request.POST.get('phone_number'),
                )
                
                if 'profile_picture' in request.FILES:
                    student.profile_picture = request.FILES['profile_picture']
                
                # Validate student fields
                form = StudentForm(request.POST, request.FILES, instance=student)
                if form.is_valid():
                    form.save()
                    messages.success(request, f'Student {student.name} created successfully!')
                    return redirect('frontend:student_list')
                else:
                    # Transaction will rollback automatically
                    raise ValueError("Form Invalid")
        except ValueError:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.replace("_", " ").title()}: {error}')
            return render(request, 'students/create.html', {'form': form})
    
    # GET request: render empty form
    return render(request, 'students/create.html', {'form': StudentForm()})


@admin_required
def upload_students(request):
    """Bulk upload students from CSV file (admin only)"""
    task_id = None
    if request.method == 'POST':
        form = StudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            
            try:
                data_set = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(data_set)
                
                header = next(io_string, None)
                if not header:
                    raise ValueError("The uploaded CSV file is empty.")
                
                student_data_list = []
                for i, column in enumerate(csv.reader(io_string, delimiter=',', quotechar='"')):
                    # Skip empty lines
                    if not column or all(cell.strip() == '' for cell in column):
                        continue
                    
                    # Check if row has all required columns
                    if len(column) < 4:
                        messages.warning(request, f"Row {i+2} has only {len(column)} columns. Skipping.")
                        continue
                    
                    first_name = column[0].strip()
                    last_name = column[1].strip()
                    email = column[2].strip()
                    student_id = column[3].strip()
                    
                    # Skip row if any required field is empty
                    if not all([first_name, last_name, email, student_id]):
                        messages.warning(request, f"Row {i+2} has empty fields. Skipping.")
                        continue
                    
                    student_data_list.append({
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email,
                        'student_id': student_id
                    })

                if student_data_list:
                    from attendance.tasks import process_student_upload
                    result = process_student_upload.delay(student_data_list, request.user.email)
                    task_id = result.id
                    messages.info(request, f'{len(student_data_list)} students are being processed...')
                else:
                    messages.warning(request, "No valid students found in the CSV file.")

            except UnicodeDecodeError:
                messages.error(request, "Invalid file encoding. Please ensure the CSV is saved as UTF-8.")
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    
    else:
        form = StudentUploadForm()
    
    return render(request, 'students/upload.html', {'form': form, 'task_id': task_id})


@login_required
def student_detail(request, pk):
    """View student details — restricted to admins, the student's lecturers, or the student themselves."""
    student = get_object_or_404(Student, pk=pk)

    # Access control: admin, the student themselves, or a lecturer who teaches them
    if not request.user.is_superuser:
        if hasattr(request.user, 'student') and request.user.student.pk == student.pk:
            pass  # Students can view their own profile
        elif hasattr(request.user, 'lecturer'):
            teaches_student = Course.objects.filter(
                lecturer=request.user.lecturer, students=student
            ).exists()
            if not teaches_student:
                messages.error(request, "You do not have permission to view this student.")
                return redirect('frontend:student_list')
        else:
            messages.error(request, "You do not have permission to view this student.")
            return redirect('frontend:dashboard')

    enrollments = CourseEnrollment.objects.filter(student=student).select_related('course')
    attendances = Attendance.objects.filter(present_students=student).select_related('course').order_by('-date')
    
    context = {
        'student': student,
        'enrollments': enrollments,
        'attendances': attendances,
    }
    return render(request, 'students/detail.html', context)


@admin_required
def student_edit(request, pk):
    """Edit student (admin only)"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        student.name = request.POST.get('name')
        student.programme_of_study = request.POST.get('programme_of_study')
        student.year = request.POST.get('year')
        student.phone_number = request.POST.get('phone_number')
        student.notification_preference = request.POST.get('notification_preference', 'both')
        student.is_notifications_enabled = request.POST.get('is_notifications_enabled') == 'on'
        
        if 'profile_picture' in request.FILES:
            student.profile_picture = request.FILES['profile_picture']
            
        student.save()
        
        messages.success(request, f'Student {student.name} updated successfully!')
        return redirect('frontend:student_detail', pk=pk)
    
    context = {'student': student}
    return render(request, 'students/edit.html', context)


@admin_required
def student_delete(request, pk):
    """Delete student"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        user = student.user
        student.delete()
        user.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse('')  # Return empty response for HTMX to remove row
        messages.success(request, 'Student deleted successfully!')
        return redirect('frontend:student_list')
    
    if request.headers.get('HX-Request'):
        return render(request, 'partials/student_delete_confirm.html', {'student': student})
    
    context = {'student': student}
    return render(request, 'students/delete.html', context)


@login_required
def ajax_search_students(request):
    """Search students for HTMX"""
    query = request.GET.get('q', '')
    students = Student.objects.select_related('user').filter(
        Q(name__icontains=query) | Q(student_id__icontains=query)
    )[:10]
    
    return render(request, 'partials/student_rows.html', {'students': students})


# ==================== Courses ====================

@login_required
def my_courses(request):
    """List courses for the current user (enrolled for students, taught for lecturers)"""
    if hasattr(request.user, 'student'):
        # Student: show enrolled courses
        student = request.user.student
        courses = Course.objects.filter(students=student).select_related('lecturer', 'lecturer__user').annotate(
            enrolled_count=Count('students')
        )
        context = {
            'courses': courses,
            'is_student': True,
            'page_title': 'My Enrolled Courses'
        }
    elif hasattr(request.user, 'lecturer'):
        # Lecturer: show taught courses
        lecturer = request.user.lecturer
        courses = Course.objects.filter(lecturer=lecturer).select_related('lecturer', 'lecturer__user').annotate(
            enrolled_count=Count('students')
        )
        context = {
            'courses': courses,
            'is_student': False,
            'page_title': 'Courses I Teach'
        }
    else:
        # Other users: show all courses (admin)
        courses = Course.objects.all().select_related('lecturer', 'lecturer__user').annotate(
            enrolled_count=Count('students')
        )
        context = {
            'courses': courses,
            'is_student': False,
            'page_title': 'All Courses'
        }
    
    return render(request, 'courses/my_courses.html', context)

@staff_required
def course_list(request):
    """List all courses (admin/lecturer only) with HTMX"""
    query = request.GET.get('q', '')
    active_filter = request.GET.get('active', '')
    sort = request.GET.get('sort', 'name')
    
    courses = Course.objects.all().select_related('lecturer').annotate(
        enrolled_count=Count('students')
    )
    
    if query:
        courses = courses.filter(
            Q(name__icontains=query) | Q(course_code__icontains=query)
        )
    if active_filter in ['true', 'false']:
        courses = courses.filter(is_active=active_filter == 'true')
        
    allowed_sorts = ['name', '-name', 'course_code', '-course_code']
    if sort in allowed_sorts:
        courses = courses.order_by(sort)
    else:
        courses = courses.order_by('name')
        sort = 'name'
    
    paginator = Paginator(courses, 12)
    page = request.GET.get('page')
    try:
        courses_page = paginator.page(page)
    except PageNotAnInteger:
        courses_page = paginator.page(1)
    except EmptyPage:
        courses_page = paginator.page(paginator.num_pages)
    
    context = {
        'courses': courses_page,
        'query': query,
        'active_filter': active_filter,
        'sort': sort,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'partials/course_list_content.html', context)
    return render(request, 'courses/list.html', context)


@staff_required
def course_create(request):
    """Create new course (admin or lecturer)"""
    if request.method == 'POST':
        course = Course(
            name=request.POST.get('name'),
            course_code=request.POST.get('course_code'),
            lecturer_id=request.POST.get('lecturer'),
            is_active=request.POST.get('is_active') == 'on',
        )
        
        # Validate course fields
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            
            # Enroll selected students
            student_ids = request.POST.getlist('students')
            enrollments = [
                CourseEnrollment(course=course, student_id=s_id) 
                for s_id in student_ids
            ]
            CourseEnrollment.objects.bulk_create(enrollments, ignore_conflicts=True)
            
            messages.success(request, f'Course {course.name} created successfully!')
            return redirect('frontend:course_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.replace("_", " ").title()}: {error}')
    
    # GET request or validation error: render form
    lecturers = Lecturer.objects.select_related('user').all()
    students = Student.objects.select_related('user').all()
    context = {
        'lecturers': lecturers,
        'students': students,
        'form': form if 'form' in locals() else CourseForm(),
    }
    return render(request, 'courses/create.html', context)


@login_required
def course_detail(request, pk):
    """View course details"""
    course = get_object_or_404(Course, pk=pk)
    
    # Access control: admin, the course's lecturer, or an enrolled student
    if not request.user.is_superuser:
        if hasattr(request.user, 'lecturer') and course.lecturer.pk != request.user.lecturer.pk:
            messages.error(request, 'You do not have permission to view this course.')
            return redirect('frontend:dashboard')
        elif hasattr(request.user, 'student') and not course.students.filter(pk=request.user.student.pk).exists():
            messages.error(request, 'You do not have permission to view this course.')
            return redirect('frontend:dashboard')

    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')
    attendances = Attendance.objects.filter(course=course).select_related('course').prefetch_related('present_students')
    
    context = {
        'course': course,
        'enrollments': enrollments,
        'attendances': attendances,
        'enrolled_count': enrollments.count(),
    }
    return render(request, 'courses/detail.html', context)


@staff_required
def course_edit(request, pk):
    """Edit course (admin or own lecturer only)"""
    course = get_object_or_404(Course, pk=pk)
    
    # Ownership check: only admin or the course's own lecturer can edit
    if not request.user.is_superuser:
        if not hasattr(request.user, 'lecturer') or course.lecturer != request.user.lecturer:
            messages.error(request, 'You do not have permission to edit this course.')
            return redirect('frontend:dashboard')
    
    if request.method == 'POST':
        course.name = request.POST.get('name')
        course.course_code = request.POST.get('course_code')
        course.lecturer_id = request.POST.get('lecturer')
        course.is_active = request.POST.get('is_active') == 'on'
        course.save()
        
        # Update enrollments
        student_ids = request.POST.getlist('students')
        CourseEnrollment.objects.filter(course=course).exclude(student_id__in=student_ids).delete()
        enrollments = [
            CourseEnrollment(course=course, student_id=s_id) 
            for s_id in student_ids
        ]
        CourseEnrollment.objects.bulk_create(enrollments, ignore_conflicts=True)
        
        messages.success(request, f'Course {course.name} updated successfully!')
        return redirect('frontend:course_detail', pk=pk)
    
    lecturers = Lecturer.objects.select_related('user').all()
    students = Student.objects.select_related('user').all()
    current_enrollments = CourseEnrollment.objects.filter(course=course).values_list('student_id', flat=True)
    
    context = {
        'course': course,
        'lecturers': lecturers,
        'students': students,
        'current_enrollments': list(current_enrollments),
    }
    return render(request, 'courses/edit.html', context)


@staff_required
def upload_enrollments(request):
    """Bulk upload course enrollments from CSV file"""
    task_id = None
    if request.method == 'POST':
        form = CourseEnrollmentUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            course = form.cleaned_data['course']
            csv_file = request.FILES['file']
            
            try:
                data_set = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(data_set)
                
                header = next(io_string, None)
                if not header:
                    raise ValueError("The uploaded CSV file is empty.")
                
                student_ids = []
                for i, column in enumerate(csv.reader(io_string, delimiter=',', quotechar='"')):
                    if not column or all(cell.strip() == '' for cell in column):
                        continue
                        
                    student_id = column[0].strip()
                    if student_id:
                        student_ids.append(student_id)
                
                if student_ids:
                    from attendance.tasks import process_enrollment_upload
                    result = process_enrollment_upload.delay(student_ids, course.id, request.user.email)
                    task_id = result.id
                    messages.info(request, f'{len(student_ids)} students are being enrolled into {course.course_code}...')
                else:
                    messages.warning(request, "No valid students found in the CSV file.")
                
            except UnicodeDecodeError:
                messages.error(request, "Invalid file encoding. Please ensure the CSV is saved as UTF-8.")
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    
    else:
        form = CourseEnrollmentUploadForm(user=request.user)
    
    return render(request, 'courses/upload_enrollments.html', {'form': form, 'task_id': task_id})


@login_required
def join_course(request):
    """Student view to join a course using a code"""
    if not hasattr(request.user, 'student'):
        messages.error(request, "Only students can join courses via code.")
        return redirect('frontend:dashboard')

    if request.method == 'POST':
        join_code = request.POST.get('join_code', '').strip().upper()
        if not join_code:
            messages.error(request, "Please enter a valid join code.")
            return redirect('frontend:join_course')

        try:
            course = Course.objects.get(join_code=join_code)
            
            # Check if active
            if not course.is_active:
                messages.warning(request, "This course is currently inactive.")
                return redirect('frontend:join_course')

            # Check if already enrolled
            if CourseEnrollment.objects.filter(course=course, student=request.user.student).exists():
                messages.info(request, f"You are already enrolled in {course.course_code}.")
                return redirect('frontend:my_courses')

            # Enroll
            CourseEnrollment.objects.create(course=course, student=request.user.student)
            messages.success(request, f"Successfully enrolled in {course.name} ({course.course_code})!")
            return redirect('frontend:my_courses')

        except Course.DoesNotExist:
            messages.error(request, "Invalid join code. Please try again.")
            return redirect('frontend:join_course')

    return render(request, 'courses/join.html')


@login_required
def task_status(request, task_id):
    """Return the status of a Celery task as JSON for polling."""
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    response = {'state': result.state}

    if result.state == 'PROGRESS':
        info = result.info or {}
        response.update({
            'current': info.get('current', 0),
            'total': info.get('total', 1),
            'status': info.get('status', 'Processing...'),
        })
    elif result.state == 'SUCCESS':
        response['result'] = result.result
    elif result.state == 'FAILURE':
        response['error'] = str(result.result)

    return JsonResponse(response)


@admin_required
def course_delete(request, pk):
    """Delete course"""
    course = get_object_or_404(Course, pk=pk)
    
    if request.method == 'POST':
        course.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse('')  # Return empty response for HTMX to remove row
        messages.success(request, 'Course deleted successfully!')
        return redirect('frontend:course_list')
    
    if request.headers.get('HX-Request'):
        return render(request, 'partials/course_delete_confirm.html', {'course': course})

    context = {'course': course}
    return render(request, 'courses/delete.html', context)


@login_required
def ajax_search_courses(request):
    """Search courses for HTMX"""
    query = request.GET.get('q', '')
    courses = Course.objects.filter(
        Q(name__icontains=query) | Q(course_code__icontains=query)
    )[:10]
    
    return render(request, 'partials/course_rows.html', {'courses': courses})


# ==================== Attendance ====================

@staff_required
def attendance_index(request):
    """Attendance dashboard (admin/lecturer only)"""
    today = timezone.localdate()
    attendances = Attendance.objects.filter(date=today).select_related('course').prefetch_related('present_students')
    active_tokens = AttendanceToken.objects.filter(is_active=True)
    
    context = {
        'today': today,
        'attendances': attendances,
        'active_tokens': active_tokens,
    }
    return render(request, 'attendance/index.html', context)


@staff_required
def attendance_take(request):
    """Take attendance - generate token (lecturer/admin only)"""
    # Get active attendance session if it exists
    active_session = None
    try:
        lecturer = Lecturer.objects.get(user=request.user)
        active_attendance = Attendance.objects.filter(
            course__lecturer=lecturer,
            date=timezone.localdate(),
            is_active=True
        ).first()
        
        if active_attendance:
            active_session = AttendanceToken.objects.filter(
                course__lecturer=lecturer,
                is_active=True
            ).first()
    except Lecturer.DoesNotExist:
        pass
    
    if request.method == 'POST' and not active_session:
        course_id = request.POST.get('course')
        token_value = request.POST.get('token', '').strip()
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        require_two_factor_auth = request.POST.get('require_two_factor_auth') == 'on'
        try:
            duration_hours = int(request.POST.get('duration_hours', 2))
            if duration_hours < 1 or duration_hours > 12:
                duration_hours = 2
        except (ValueError, TypeError):
            duration_hours = 2
        
        # Validate token length
        if len(token_value) != 6:
            messages.error(request, "Attendance token must be exactly 6 characters.")
            return redirect('frontend:attendance_take')
        
        # Validate coordinates
        if not latitude or not longitude:
            messages.error(request, "Location coordinates must be provided. Please ensure location services are enabled.")
            return redirect('frontend:attendance_take')
        
        try:
            lat = float(latitude)
            lng = float(longitude)
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise ValueError("Invalid coordinate values")
        except (ValueError, TypeError):
            messages.error(request, "Invalid location coordinates. Please refresh your location.")
            return redirect('frontend:attendance_take')
        
        course = get_object_or_404(Course, pk=course_id)
        
        # Check if lecturer has global 2FA setting enabled
        try:
            lecturer = Lecturer.objects.get(user=request.user)
            if lecturer.require_two_factor_auth and not require_two_factor_auth:
                require_two_factor_auth = True
        except Lecturer.DoesNotExist:
            pass
        
        # Create attendance session
        attendance = Attendance.objects.create(
            course=course,
            date=timezone.localdate(),
            lecturer_latitude=lat,
            lecturer_longitude=lng,
            is_active=True,
            created_by=request.user,
            require_two_factor_auth=require_two_factor_auth,
            duration_hours=duration_hours,
        )
        
        # Generate token with expiration based on attendance duration
        att_token = AttendanceToken.objects.create(
            course=course,
            token=token_value,
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=duration_hours),
        )
        
        # Generate and save QR code
        qr_buffer = att_token.generate_qr_code()
        filename = f"qr_{att_token.token}.png"
        att_token.qr_code = SimpleUploadedFile(filename, qr_buffer.read(), content_type='image/png')
        att_token.save()
        

        
        # Update course status
        course.is_active = True
        course.save()
        
        messages.success(request, f'Attendance session started for {course.name}!')
        return redirect('frontend:attendance_take')
    
    # Get lecturer's courses
    lecturer = None
    try:
        lecturer = Lecturer.objects.get(user=request.user)
        courses = Course.objects.filter(lecturer=lecturer)
    except Lecturer.DoesNotExist:
        courses = Course.objects.all()
    
    context = {
        'courses': courses,
        'active_session': active_session,
        'lecturer': lecturer,
    }
    return render(request, 'attendance/take.html', context)


@login_required
def end_attendance(request):
    """End active attendance session"""
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        
        try:
            # Find active attendance for the course
            attendance = Attendance.objects.get(
                course_id=course_id,
                date=timezone.localdate(),
                is_active=True
            )
            
            # Security check: Admins or the course's lecturer can end the session
            if not request.user.is_superuser:
                if not hasattr(request.user, 'lecturer') or attendance.course.lecturer != request.user.lecturer:
                    messages.error(request, 'Unauthorized to end this session.')
                    return redirect('frontend:attendance_take')
            
            # End attendance
            attendance.is_active = False
            attendance.ended_at = timezone.now()
            attendance.save()
            
            # Deactivate token
            AttendanceToken.objects.filter(
                course_id=course_id,
                is_active=True
            ).update(is_active=False)
            
            # Update course status
            course = attendance.course
            course.is_active = False
            course.save()
            
            # Send missed attendance notifications
            from attendance.tasks import send_missed_attendance_notifications
            send_missed_attendance_notifications(attendance)
            
            messages.success(request, 'Attendance session ended successfully!')
        except Attendance.DoesNotExist:
            messages.error(request, 'No active attendance session found!')
        except Exception as e:
            messages.error(request, f'Error ending attendance session: {str(e)}')
    
    return redirect('frontend:attendance_take')


@login_required
def attendance_mark(request):
    """Mark attendance - student view"""
    if request.method == 'POST':
        token = request.POST.get('token')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        try:
            att_token = AttendanceToken.objects.get(token=token, is_active=True)
            course = att_token.course
            
            # Check if student is enrolled
            try:
                student = Student.objects.get(user=request.user)
                if not course.students.filter(pk=student.pk).exists():
                    messages.error(request, 'You are not enrolled in this course!')
                    return render(request, 'attendance/mark.html')
                
                # Get active attendance session
                attendance = Attendance.objects.filter(
                    course=course, 
                    is_active=True
                ).first()
                
                if not attendance:
                    messages.error(request, 'No active attendance session found for this course today.')
                    return render(request, 'attendance/mark.html')
                
                # Check if 2FA is required
                if attendance.require_two_factor_auth:
                    # Build 2FA context (needed in both branches)
                    two_fa_context = {
                        'token': token,
                        'course': course,
                        'latitude': latitude,
                        'longitude': longitude,
                        'has_webauthn': WebAuthnCredential.objects.filter(user=request.user).exists(),
                        'has_otp': bool(getattr(student, 'two_factor_secret', None)),
                    }
                    
                    # Check if student has completed 2FA
                    has_completed_two_factor = request.POST.get('two_factor_completed') == 'on'
                    
                    if not has_completed_two_factor:
                        # Check if student has any 2FA method configured
                        if not two_fa_context['has_webauthn'] and not two_fa_context['has_otp']:
                            messages.warning(request, 'This session requires 2FA. Please set up fingerprint or OTP first.')
                            return redirect('frontend:student_setup_2fa')
                        # Render 2FA challenge page
                        return render(request, 'attendance/two_factor_challenge.html', two_fa_context)
                    else:
                        # Verify 2FA method
                        two_factor_method = request.POST.get('two_factor_method', '')
                        
                        if two_factor_method == 'webauthn':
                            # Verify WebAuthn was completed via session flag
                            if not request.session.pop('webauthn_2fa_verified', False):
                                messages.error(request, 'Biometric verification failed. Please try again.')
                                return render(request, 'attendance/two_factor_challenge.html', two_fa_context)
                        elif two_factor_method == 'otp':
                            # Verify OTP code using pyotp
                            otp_code = request.POST.get('otp_code', '')
                            if len(otp_code) != 6 or not otp_code.isdigit():
                                messages.error(request, 'Invalid OTP code. Must be 6 digits.')
                                return render(request, 'attendance/two_factor_challenge.html', two_fa_context)
                            
                            if not student.two_factor_secret:
                                messages.error(request, 'OTP not configured. Please set up 2FA first.')
                                return redirect('frontend:student_setup_2fa')
                            
                            totp = pyotp.TOTP(student.two_factor_secret)
                            if not totp.verify(otp_code, valid_window=1):
                                messages.error(request, 'Invalid or expired OTP code.')
                                return render(request, 'attendance/two_factor_challenge.html', two_fa_context)
                        else:
                            messages.error(request, 'Invalid 2FA method.')
                            return render(request, 'attendance/two_factor_challenge.html', two_fa_context)
                
                # Parse latitude and longitude — reject missing coords instead of defaulting
                if not latitude or not longitude:
                    messages.error(request, 'Location coordinates are required. Please enable location services.')
                    return render(request, 'attendance/mark.html')
                try:
                    lat_float = float(latitude)
                    lon_float = float(longitude)
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid GPS coordinates provided.')
                    return render(request, 'attendance/mark.html')

                # Check if student is within valid GPS radius
                if not attendance.is_within_radius(lat_float, lon_float):
                    messages.error(request, 'You are too far from the classroom to check in.')
                    return render(request, 'attendance/mark.html')
                
                from django.db import transaction
                with transaction.atomic():
                    locked_attendance = Attendance.objects.select_for_update().get(pk=attendance.pk)
                    # Mark attendance with location coordinates
                    AttendanceStudent.objects.get_or_create(
                        attendance=locked_attendance,
                        student=student,
                        defaults={
                            'latitude': lat_float if latitude else None,
                            'longitude': lon_float if longitude else None
                        }
                    )
                    
                    # CRITICAL FIX: Add student to present_students M2M field
                    locked_attendance.present_students.add(student)
                
                messages.success(request, f'Attendance marked for {course.name}!')
            except Student.DoesNotExist:
                messages.error(request, 'Student profile not found!')
                
        except AttendanceToken.DoesNotExist:
            messages.error(request, 'Invalid or expired token!')
    
    return render(request, 'attendance/mark.html')


@login_required
def attendance_detail(request, pk):
    """View attendance session details"""
    attendance = get_object_or_404(Attendance, pk=pk)
    course = attendance.course
    
    # Authorization: admin, the course lecturer, or an enrolled student
    if not request.user.is_superuser:
        if hasattr(request.user, 'lecturer'):
            if course.lecturer != request.user.lecturer:
                messages.error(request, 'You do not have permission to view this session.')
                return redirect('frontend:dashboard')
        elif hasattr(request.user, 'student'):
            if not course.students.filter(pk=request.user.student.pk).exists():
                messages.error(request, 'You are not enrolled in this course.')
                return redirect('frontend:dashboard')
        else:
            messages.error(request, 'You do not have permission to view this session.')
            return redirect('frontend:dashboard')
    
    all_students = course.students.all()
    
    # Get present students with their location information
    attendance_students = AttendanceStudent.objects.filter(attendance=attendance).select_related('student')
    present_students_with_location = []
    for as_obj in attendance_students:
        present_students_with_location.append({
            'student': as_obj.student,
            'is_within_perimeter': as_obj.is_within_valid_perimeter(),
            'distance': as_obj.get_distance_from_lecturer(),
            'marked_at': as_obj.marked_at
        })
    
    # Get all students and prepare present/absent data
    present_ids = [as_obj['student'].id for as_obj in present_students_with_location]
    absent_students = [student for student in all_students if student.id not in present_ids]
    
    # Get attendance token for this course and date
    token = None
    qr_code = None
    try:
        att_token = AttendanceToken.objects.get(
            course=course,
            is_active=True,
            generated_at__date=attendance.date
        )
        token = att_token.token
        if att_token.qr_code:
            qr_code = att_token.qr_code.url
    except AttendanceToken.DoesNotExist:
        pass
    
    context = {
        'attendance': attendance,
        'course': course,
        'all_students': all_students,
        'present_students_with_location': present_students_with_location,
        'absent_students': absent_students,
        'present_ids': present_ids,
        'token': token,
        'qr_code': qr_code,
        'require_two_factor_auth': attendance.require_two_factor_auth,
    }
    return render(request, 'attendance/detail.html', context)


@login_required
def export_attendance_csv(request, attendance_id):
    """Export attendance as CSV"""
    attendance = get_object_or_404(Attendance, id=attendance_id)
    
    # Security check - only the course lecturer or admin can export
    if not request.user.is_superuser:
        if not hasattr(request.user, 'lecturer') or attendance.course.lecturer != request.user.lecturer:
            return HttpResponse("Unauthorized", status=403)

    # Create the CSV response
    filename = f"attendance_{attendance.course.course_code}_{attendance.date}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Full Name', 'Programme', 'Status', 'Date'])

    # Fetch all enrolled students
    enrolled_students = attendance.course.students.all()
    present_ids = attendance.present_students.values_list('id', flat=True)

    for student in enrolled_students:
        status = 'Present' if student.id in present_ids else 'Absent'
        writer.writerow([
            student.student_id, 
            student.name, 
            student.programme_of_study, 
            status, 
            attendance.date
        ])

    return response


@login_required
def manual_mark_present(request, attendance_id, student_id):
    """Manually mark a student as present"""
    attendance = get_object_or_404(Attendance, id=attendance_id)
    
    # Security check: Only the course lecturer or admin can manually mark attendance
    if not request.user.is_superuser:
        if not hasattr(request.user, 'lecturer') or attendance.course.lecturer != request.user.lecturer:
            return HttpResponse("Unauthorized", status=403)
        
    student = get_object_or_404(Student, id=student_id)
    
    # Add to ManyToMany field
    attendance.present_students.add(student)
    
    return redirect('frontend:attendance_detail', pk=attendance_id)


@login_required
def attendance_history(request):
    """View attendance history"""
    course_filter = request.GET.get('course')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base query - restrict based on user role
    if request.user.is_superuser:
        attendances = Attendance.objects.all().select_related('course').prefetch_related('present_students')
    elif hasattr(request.user, 'lecturer'):
        attendances = Attendance.objects.filter(course__lecturer=request.user.lecturer).select_related('course').prefetch_related('present_students')
    elif hasattr(request.user, 'student'):
        attendances = Attendance.objects.filter(present_students=request.user.student).select_related('course').prefetch_related('present_students')
    else:
        attendances = Attendance.objects.none()
    
    if course_filter:
        attendances = attendances.filter(course_id=course_filter)
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
        
    if request.GET.get('export_csv') == 'true':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="attendance_history.csv"'
        writer = csv.writer(response)
        writer.writerow(['Course', 'Course Code', 'Date', 'Present Count', 'Status'])
        for att in attendances.order_by('-date'):
            writer.writerow([
                att.course.name,
                att.course.course_code,
                att.date,
                att.present_students.count(),
                'Active' if att.is_active else 'Ended'
            ])
        return response
    
    courses = Course.objects.all()
    
    paginator = Paginator(attendances.order_by('-date'), 25)
    page = request.GET.get('page')
    try:
        attendances_page = paginator.page(page)
    except PageNotAnInteger:
        attendances_page = paginator.page(1)
    except EmptyPage:
        attendances_page = paginator.page(paginator.num_pages)
    
    context = {
        'attendances': attendances_page,
        'courses': courses,
        'course_filter': course_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'attendance/history.html', context)


# ==================== Reports ====================

@login_required
def reports_index(request):
    """Reports dashboard with real analytics — O(1) DB queries regardless of scale."""
    import json

    # ---- Role-scoped base querysets ----
    if hasattr(request.user, 'lecturer'):
        courses = Course.objects.filter(lecturer=request.user.lecturer)
        attendances_qs = Attendance.objects.filter(course__lecturer=request.user.lecturer)
    elif hasattr(request.user, 'student'):
        courses = Course.objects.filter(students=request.user.student)
        attendances_qs = Attendance.objects.filter(course__in=courses)
    elif request.user.is_superuser:
        courses = Course.objects.all()
        attendances_qs = Attendance.objects.all()
    else:
        courses = Course.objects.none()
        attendances_qs = Attendance.objects.none()

    # ---- Summary stats (4 single-query counts) ----
    total_records = attendances_qs.count()
    total_courses = courses.count()
    
    if request.user.is_superuser:
        total_students = Student.objects.count()
    else:
        total_students = Student.objects.filter(enrolled_courses__in=courses).distinct().count()
    active_sessions = attendances_qs.filter(is_active=True).count()

    # ---- Per-course attendance rates — O(3) queries total ----
    # 1. Session count + enrolled count per course (one aggregated query)
    from django.db.models import Count as _Count
    course_session_counts = {
        row['id']: row['session_count']
        for row in courses.annotate(session_count=_Count('attendance', distinct=True)).values('id', 'session_count')
    }
    course_enrolled_counts = {
        row['id']: row['enrolled_count']
        for row in courses.annotate(enrolled_count=_Count('students', distinct=True)).values('id', 'enrolled_count')
    }
    # 2. Total present marks per course (one aggregated query across all sessions)
    from attendance.models import AttendanceStudent
    course_present_totals = {
        row['attendance__course_id']: row['total']
        for row in AttendanceStudent.objects.filter(
            attendance__in=attendances_qs
        ).values('attendance__course_id').annotate(total=_Count('id'))
    }

    course_stats = []
    for course in courses.only('id', 'name', 'course_code'):
        sessions = course_session_counts.get(course.id, 0)
        enrolled = course_enrolled_counts.get(course.id, 0)
        total_marks = course_present_totals.get(course.id, 0)
        if sessions > 0 and enrolled > 0:
            rate = round((total_marks / (sessions * enrolled)) * 100)
        else:
            rate = 0
        course_stats.append({
            'name': course.name,
            'code': course.course_code,
            'sessions': sessions,
            'enrolled': enrolled,
            'rate': rate,
        })
    course_stats.sort(key=lambda c: c['rate'], reverse=True)

    # ---- Weekly trend (last 8 weeks) — single annotated date-range query ----
    today = timezone.localdate()
    week_start = today - timedelta(weeks=8)
    # Pull all session dates in the range in one query
    session_dates = list(
        attendances_qs.filter(date__gte=week_start)
        .values_list('date', flat=True)
    )
    week_labels = []
    week_counts = []
    for i in range(7, -1, -1):
        start = today - timedelta(weeks=i + 1)
        end = today - timedelta(weeks=i)
        week_labels.append(end.strftime('%b %d'))
        week_counts.append(sum(1 for d in session_dates if start <= d < end))

    # ---- Recent sessions (prefetched to avoid per-row count queries) ----
    recent_sessions = (
        attendances_qs
        .select_related('course')
        .prefetch_related('present_students')
        .order_by('-date', '-created_at')[:10]
    )

    context = {
        'total_records': total_records,
        'total_courses': total_courses,
        'total_students': total_students,
        'active_sessions': active_sessions,
        'course_stats': course_stats,
        'week_labels': json.dumps(week_labels),
        'week_counts': json.dumps(week_counts),
        'recent_sessions': recent_sessions,
        'courses': courses,
    }
    return render(request, 'reports/index.html', context)



@login_required
def reports_export(request):
    """Export attendance data"""
    course_id = request.GET.get('course')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    export_format = request.GET.get('format', 'csv')
    
    # Base query - restrict based on user role
    if request.user.is_superuser:
        attendances = Attendance.objects.all().select_related('course').prefetch_related('present_students')
    elif hasattr(request.user, 'lecturer'):
        attendances = Attendance.objects.filter(course__lecturer=request.user.lecturer).select_related('course').prefetch_related('present_students')
    elif hasattr(request.user, 'student'):
        attendances = Attendance.objects.filter(present_students=request.user.student).select_related('course').prefetch_related('present_students')
    else:
        attendances = Attendance.objects.none()
    
    if course_id:
        attendances = attendances.filter(course_id=course_id)
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    
    if export_format == 'xlsx':
        wb = Workbook()
        ws = wb.active
        ws.append(['Course', 'Date', 'Present Count', 'Active', 'Created At'])
        
        for att in attendances.annotate(present_count=Count('present_students')):
            ws.append([
                att.course.name,
                str(att.date),
                att.present_count,
                'Yes' if att.is_active else 'No',
                str(att.created_at),
            ])
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=attendance_report.xlsx'
        wb.save(response)
        return response
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=attendance_report.csv'
        
        writer = csv.writer(response)
        writer.writerow(['Course', 'Date', 'Present Count', 'Active', 'Created At'])
        
        for att in attendances.annotate(present_count=Count('present_students')):
            writer.writerow([
                att.course.name,
                att.date,
                att.present_count,
                'Yes' if att.is_active else 'No',
                att.created_at,
            ])
        
        return response
  


def disabled_register_view_duplicate(request):
    """View for user registration with rate limiting"""
    if request.method == "POST":
        # Rate limiting: max 5 registrations per IP per hour
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        cache_key = f'register_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            messages.error(request, "Too many registration attempts. Please try again later.")
            return render(request, 'frontend/register.html')
        cache.set(cache_key, attempts + 1, 3600)  # 1-hour window

        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        role = request.POST.get('role')
        
        # Validate role — only students can self-register; lecturers must be created by admin
        if role != 'student':
            messages.error(request, "Only student registration is allowed. Lecturer accounts must be created by an administrator.")
            return redirect('frontend:register')
        
        # Validate passwords
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect('frontend:register')
        
        # Validate password strength
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password1)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('frontend:register')
        
        # Check if username or email exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('frontend:register')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('frontend:register')
            
        try:
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1
                )
                
                # Create student profile (lecturer path is unreachable — blocked above)
                if role == 'student':
                    Student.objects.create(
                        user=user,
                        student_id=request.POST.get('student_id'),
                        name=request.POST.get('name'),
                        programme_of_study=request.POST.get('programme_of_study'),
                        year=request.POST.get('year'),
                        phone_number=request.POST.get('phone_number')
                    )
                
                messages.success(request, "Registration successful! Please login.")
                return redirect('frontend:login')
                
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect('frontend:register')
            
    return render(request, 'frontend/register.html')


# ==================== Two-Factor Authentication (WebAuthn + OTP) ====================

import json
import base64
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from django.views.decorators.http import require_POST


def _get_rp_id(request):
    """Get the Relying Party ID (domain without port)."""
    return request.get_host().split(':')[0]


def _get_origin(request):
    """Get the full origin for WebAuthn verification."""
    scheme = 'https' if request.is_secure() else 'http'
    return f"{scheme}://{request.get_host()}"


@login_required
def student_setup_2fa(request):
    """2FA setup page — students configure fingerprint and/or OTP."""
    student = get_object_or_404(Student, user=request.user)
    credentials = WebAuthnCredential.objects.filter(user=request.user)
    has_otp = bool(student.two_factor_secret)

    context = {
        'student': student,
        'credentials': credentials,
        'has_webauthn': credentials.exists(),
        'has_otp': has_otp,
    }
    return render(request, 'students/setup_2fa.html', context)


@login_required
@require_POST
def webauthn_register_begin(request):
    """Generate WebAuthn registration options (AJAX)."""
    rp_id = _get_rp_id(request)
    user = request.user

    # Exclude already-registered credentials
    existing = WebAuthnCredential.objects.filter(user=user)
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
        for c in existing
    ]

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name="Exodus Attendance",
        user_id=str(user.id).encode(),
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.DISCOURAGED,
        ),
        exclude_credentials=exclude_credentials,
    )

    # Store challenge in session for verification
    request.session['webauthn_reg_challenge'] = bytes_to_base64url(options.challenge)

    return JsonResponse(json.loads(options_to_json(options)), safe=False)


@login_required
@require_POST
def webauthn_register_complete(request):
    """Verify WebAuthn registration response and store credential (AJAX)."""
    try:
        body = json.loads(request.body)
        challenge_b64 = request.session.pop('webauthn_reg_challenge', None)
        if not challenge_b64:
            return JsonResponse({'error': 'Registration session expired. Please try again.'}, status=400)

        rp_id = _get_rp_id(request)
        origin = _get_origin(request)

        verification = verify_registration_response(
            credential=body,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=rp_id,
            expected_origin=origin,
        )

        # Store the credential
        WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            name=body.get('name', 'Fingerprint'),
        )

        return JsonResponse({'success': True, 'message': 'Fingerprint registered successfully!'})

    except Exception as e:
        return JsonResponse({'error': f'Registration failed: {str(e)}'}, status=400)


@login_required
@require_POST
def webauthn_remove(request):
    """Remove a registered WebAuthn credential."""
    cred_id = request.POST.get('credential_id')
    if cred_id:
        WebAuthnCredential.objects.filter(user=request.user, credential_id=cred_id).delete()
        messages.success(request, 'Fingerprint credential removed.')
    return redirect('frontend:student_setup_2fa')


@login_required
@require_POST
def webauthn_auth_begin(request):
    """Generate WebAuthn authentication options (AJAX) — used during attendance 2FA."""
    rp_id = _get_rp_id(request)
    credentials = WebAuthnCredential.objects.filter(user=request.user)

    if not credentials.exists():
        return JsonResponse({'error': 'No fingerprint credentials registered.'}, status=400)

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
        for c in credentials
    ]

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    request.session['webauthn_auth_challenge'] = bytes_to_base64url(options.challenge)

    return JsonResponse(json.loads(options_to_json(options)), safe=False)


@login_required
@require_POST
def webauthn_auth_complete(request):
    """Verify WebAuthn authentication response (AJAX) — sets session flag for attendance."""
    try:
        body = json.loads(request.body)
        challenge_b64 = request.session.pop('webauthn_auth_challenge', None)
        if not challenge_b64:
            return JsonResponse({'error': 'Authentication session expired.'}, status=400)

        rp_id = _get_rp_id(request)
        origin = _get_origin(request)

        # Find the credential
        raw_id = body.get('rawId', body.get('id', ''))
        try:
            stored_cred = WebAuthnCredential.objects.get(
                user=request.user,
                credential_id=raw_id,
            )
        except WebAuthnCredential.DoesNotExist:
            return JsonResponse({'error': 'Unknown credential.'}, status=400)

        verification = verify_authentication_response(
            credential=body,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=base64url_to_bytes(stored_cred.public_key),
            credential_current_sign_count=stored_cred.sign_count,
        )

        # Update sign count
        stored_cred.sign_count = verification.new_sign_count
        stored_cred.save(update_fields=['sign_count'])

        # Set session flag so attendance_mark knows 2FA passed
        request.session['webauthn_2fa_verified'] = True

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': f'Authentication failed: {str(e)}'}, status=400)


@login_required
@require_POST
def student_setup_otp(request):
    """Generate OTP secret and return QR code (AJAX)."""
    student = get_object_or_404(Student, user=request.user)

    # Generate a new secret if one doesn't exist, or regenerate on request
    secret = pyotp.random_base32()
    # Don't save yet — only save after verification
    request.session['pending_otp_secret'] = secret

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=request.user.username,
        issuer_name="Exodus Attendance",
    )

    # Generate QR code as SVG
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(provisioning_uri, image_factory=factory)
    buf = BytesIO()
    img.save(buf)
    svg_data = buf.getvalue().decode('utf-8')

    return JsonResponse({
        'secret': secret,
        'qr_svg': svg_data,
    })


@login_required
@require_POST
def student_verify_otp(request):
    """Verify initial OTP code to confirm setup (AJAX)."""
    student = get_object_or_404(Student, user=request.user)
    otp_code = request.POST.get('otp_code', '').strip()
    secret = request.session.get('pending_otp_secret')

    if not secret:
        return JsonResponse({'error': 'OTP setup session expired. Please start again.'}, status=400)

    if len(otp_code) != 6 or not otp_code.isdigit():
        return JsonResponse({'error': 'OTP must be exactly 6 digits.'}, status=400)

    totp = pyotp.TOTP(secret)
    if not totp.verify(otp_code, valid_window=1):
        return JsonResponse({'error': 'Invalid OTP code. Please try again.'}, status=400)

    # OTP verified — save the secret
    student.two_factor_secret = secret
    student.is_two_factor_enabled = True
    student.save(update_fields=['two_factor_secret', 'is_two_factor_enabled'])
    request.session.pop('pending_otp_secret', None)

    return JsonResponse({'success': True, 'message': 'OTP configured successfully!'})


@login_required
@require_POST
def student_disable_otp(request):
    """Disable OTP for the current student."""
    student = get_object_or_404(Student, user=request.user)
    student.two_factor_secret = None
    student.is_two_factor_enabled = False
    student.save(update_fields=['two_factor_secret', 'is_two_factor_enabled'])
    messages.success(request, 'OTP authentication disabled.')
    return redirect('frontend:student_setup_2fa')


# ==================== Error Handlers ====================

def error_404(request, exception):
    """Custom 404 page"""
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    """Custom 500 page"""
    return render(request, 'errors/500.html', status=500)

@require_POST
@login_required
def save_fcm_token(request):
    """Save the Firebase Cloud Messaging (FCM) device token for the current user.

    Validates that the token is a non-empty string within the FCM spec length
    limit (4096 characters) before persisting it.
    """
    import json
    import re

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'detail': 'Invalid JSON body.'}, status=400)

    token = data.get('token', '')

    # Basic format validation
    if not token or not isinstance(token, str):
        return JsonResponse({'status': 'error', 'detail': 'Token is required.'}, status=400)

    token = token.strip()

    # FCM tokens are alphanumeric + dashes/underscores/colons, max ~4096 chars
    if len(token) > 4096:
        return JsonResponse({'status': 'error', 'detail': 'Token too long.'}, status=400)

    if not re.match(r'^[A-Za-z0-9_:.\-]+$', token):
        return JsonResponse({'status': 'error', 'detail': 'Invalid token format.'}, status=400)

    try:
        if hasattr(request.user, 'student'):
            request.user.student.fcm_token = token
            request.user.student.save(update_fields=['fcm_token'])
        elif hasattr(request.user, 'lecturer'):
            request.user.lecturer.fcm_token = token
            request.user.lecturer.save(update_fields=['fcm_token'])
        else:
            return JsonResponse({'status': 'error', 'detail': 'No profile found.'}, status=400)
        return JsonResponse({'status': 'success'})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("save_fcm_token failed for user %s: %s", request.user.pk, exc)
        return JsonResponse({'status': 'error', 'detail': 'Server error.'}, status=500)


