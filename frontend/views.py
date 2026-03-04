from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
import secrets
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timedelta
import csv
import io
import openpyxl
from openpyxl import Workbook

from attendance.models import Lecturer, Student, Course, Attendance, AttendanceToken, CourseEnrollment, AttendanceStudent
from django.contrib.auth.models import User
from .forms import LecturerForm, StudentForm, CourseForm, StudentUploadForm


# ==================== Authentication ====================

def login_view(request):
    """View for user login"""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.POST.get('next') or 'frontend:dashboard'
            return redirect(next_url)
        else:
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

        if len(new_password) < 8:
            messages.error(request, 'New password must be at least 8 characters.')
            return redirect('frontend:change_password')

        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('frontend:change_password')

        request.user.set_password(new_password)
        request.user.save()

        # Keep the user logged in after password change
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password changed successfully!')
        return redirect('frontend:profile')

    return render(request, 'frontend/change_password.html')


@login_required
def ajax_dashboard_stats(request):
    """HTMX endpoint for dashboard statistics"""
    stats = {
        'total_lecturers': Lecturer.objects.count(),
        'total_students': Student.objects.count(),
        'total_courses': Course.objects.count(),
        'active_courses': Course.objects.filter(is_active=True).count(),
        'today_attendance': Attendance.objects.filter(date=timezone.localdate()).count(),
    }
    return JsonResponse(stats)


# ==================== Lecturers ====================

@login_required
def lecturer_list(request):
    """List all lecturers"""
    query = request.GET.get('q')
    if query:
        lecturers = Lecturer.objects.select_related('user').filter(
            Q(name__icontains=query) | Q(staff_id__icontains=query) | Q(department__icontains=query)
        ).order_by('name')
    else:
        lecturers = Lecturer.objects.select_related('user').all().order_by('name')
    
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
    }
    return render(request, 'lecturers/list.html', context)


@login_required
def lecturer_create(request):
    """Create new lecturer"""
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
                
                # Validate lecturer fields
                form = LecturerForm(request.POST, instance=lecturer)
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
    courses = Course.objects.filter(lecturer=lecturer)
    
    context = {
        'lecturer': lecturer,
        'courses': courses,
    }
    return render(request, 'lecturers/detail.html', context)


@login_required
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


@login_required
def lecturer_edit(request, pk):
    """Edit lecturer"""
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
        
        lecturer.save()
        messages.success(request, f'Lecturer {lecturer.name} updated successfully!')
        return redirect('frontend:lecturer_detail', pk=pk)
    
    context = {'lecturer': lecturer}
    return render(request, 'lecturers/edit.html', context)


@login_required
def lecturer_delete(request, pk):
    """Delete lecturer"""
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

@login_required
def student_list(request):
    """List all students"""
    query = request.GET.get('q')
    year_filter = request.GET.get('year')
    programme_filter = request.GET.get('programme')
    
    students = Student.objects.select_related('user').all().order_by('name')
    
    if query:
        students = students.filter(
            Q(name__icontains=query) | Q(student_id__icontains=query)
        )
    if year_filter:
        students = students.filter(year=year_filter)
    if programme_filter:
        students = students.filter(programme_of_study=programme_filter)
    
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
        'years': Student.objects.values_list('year', flat=True).distinct(),
        'programmes': Student.objects.values_list('programme_of_study', flat=True).distinct(),
    }
    return render(request, 'students/list.html', context)


@login_required
def student_create(request):
    """Create new student"""
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
                
                user = User.objects.create_user(username=username, email=email, password=password)
                
                student = Student(
                    user=user,
                    student_id=request.POST.get('student_id'),
                    name=request.POST.get('name'),
                    programme_of_study=request.POST.get('programme_of_study'),
                    year=request.POST.get('year'),
                    phone_number=request.POST.get('phone_number'),
                )
                
                # Validate student fields
                form = StudentForm(request.POST, instance=student)
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


@login_required
def upload_students(request):
    """Bulk upload students from CSV file"""
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
                
                count = 0
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

                    if not User.objects.filter(username=student_id).exists():
                        random_password = secrets.token_urlsafe(12)
                        user = User.objects.create_user(
                            username=student_id, 
                            email=email, 
                            password=random_password,
                            first_name=first_name,
                            last_name=last_name
                        )
                        
                        Student.objects.create(
                            user=user, 
                            student_id=student_id, 
                            name=f"{first_name} {last_name}"
                        )
                        
                        reset_form = PasswordResetForm({'email': user.email})
                        if reset_form.is_valid():
                            reset_form.save(request=request, use_https=request.is_secure())
                            
                        count += 1
                
                messages.success(request, f'{count} students uploaded successfully!')
                return redirect('frontend:dashboard')
                
            except UnicodeDecodeError:
                messages.error(request, "Invalid file encoding. Please ensure the CSV is saved as UTF-8.")
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    
    else:
        form = StudentUploadForm()
    
    return render(request, 'students/upload.html', {'form': form})


@login_required
def student_detail(request, pk):
    """View student details"""
    student = get_object_or_404(Student, pk=pk)
    enrollments = CourseEnrollment.objects.filter(student=student).select_related('course')
    attendances = Attendance.objects.filter(present_students=student).select_related('course').order_by('-date')
    
    context = {
        'student': student,
        'enrollments': enrollments,
        'attendances': attendances,
    }
    return render(request, 'students/detail.html', context)


@login_required
def student_edit(request, pk):
    """Edit student"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        student.name = request.POST.get('name')
        student.programme_of_study = request.POST.get('programme_of_study')
        student.year = request.POST.get('year')
        student.phone_number = request.POST.get('phone_number')
        student.notification_preference = request.POST.get('notification_preference', 'both')
        student.is_notifications_enabled = request.POST.get('is_notifications_enabled') == 'on'
        student.save()
        
        messages.success(request, f'Student {student.name} updated successfully!')
        return redirect('frontend:student_detail', pk=pk)
    
    context = {'student': student}
    return render(request, 'students/edit.html', context)


@login_required
def student_delete(request, pk):
    """Delete student"""
    student = get_object_or_404(Student, pk=pk)
    
    # Security check: Only superusers can delete students
    if not request.user.is_superuser:
        if request.headers.get('HX-Request'):
            return HttpResponse('Unauthorized', status=403)
        messages.error(request, "You do not have permission to delete this student.")
        return redirect('frontend:student_list')
    
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
        courses = Course.objects.filter(students=student).select_related('lecturer').annotate(
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
        courses = Course.objects.filter(lecturer=lecturer).select_related('lecturer').annotate(
            enrolled_count=Count('students')
        )
        context = {
            'courses': courses,
            'is_student': False,
            'page_title': 'Courses I Teach'
        }
    else:
        # Other users: show all courses (admin)
        courses = Course.objects.all().select_related('lecturer').annotate(
            enrolled_count=Count('students')
        )
        context = {
            'courses': courses,
            'is_student': False,
            'page_title': 'All Courses'
        }
    
    return render(request, 'courses/my_courses.html', context)

@login_required
def course_list(request):
    """List all courses"""
    query = request.GET.get('q')
    active_filter = request.GET.get('active')
    
    courses = Course.objects.all().select_related('lecturer').annotate(
        enrolled_count=Count('students')
    ).order_by('name')
    
    if query:
        courses = courses.filter(
            Q(name__icontains=query) | Q(course_code__icontains=query)
        )
    if active_filter is not None:
        courses = courses.filter(is_active=active_filter == 'true')
    
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
    }
    return render(request, 'courses/list.html', context)


@login_required
def course_create(request):
    """Create new course"""
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
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')
    attendances = Attendance.objects.filter(course=course).select_related('course').prefetch_related('present_students')
    
    context = {
        'course': course,
        'enrollments': enrollments,
        'attendances': attendances,
        'enrolled_count': enrollments.count(),
    }
    return render(request, 'courses/detail.html', context)


@login_required
def course_edit(request, pk):
    """Edit course"""
    course = get_object_or_404(Course, pk=pk)
    
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


@login_required
def course_delete(request, pk):
    """Delete course"""
    course = get_object_or_404(Course, pk=pk)
    
    # Security check: Only superusers or the course's lecturer can delete
    if not (request.user.is_superuser or (hasattr(request.user, 'lecturer') and course.lecturer == request.user.lecturer)):
        if request.headers.get('HX-Request'):
            return HttpResponse('Unauthorized', status=403)
        messages.error(request, "You do not have permission to delete this course.")
        return redirect('frontend:course_list')

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

@login_required
def attendance_index(request):
    """Attendance dashboard"""
    today = timezone.localdate()
    attendances = Attendance.objects.filter(date=today).select_related('course').prefetch_related('present_students')
    active_tokens = AttendanceToken.objects.filter(is_active=True)
    
    context = {
        'today': today,
        'attendances': attendances,
        'active_tokens': active_tokens,
    }
    return render(request, 'attendance/index.html', context)


@login_required
def attendance_take(request):
    """Take attendance - generate token"""
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
            
            # Security check: Only the course's lecturer can end the session
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
                if student not in course.students.all():
                    messages.error(request, 'You are not enrolled in this course!')
                    return render(request, 'attendance/mark.html')
                
                # Get attendance session
                attendance = Attendance.objects.get(
                    course=course, 
                    date=timezone.localdate(),
                    is_active=True
                )
                
                # Check if 2FA is required
                if attendance.require_two_factor_auth:
                    # Check if student has completed 2FA
                    has_completed_two_factor = request.POST.get('two_factor_completed') == 'on'
                    
                    if not has_completed_two_factor:
                        # Render 2FA challenge page
                        context = {
                            'token': token,
                            'course': course,
                            'latitude': latitude,
                            'longitude': longitude
                        }
                        return render(request, 'attendance/two_factor_challenge.html', context)
                    else:
                        # Verify 2FA method
                        two_factor_method = request.POST.get('two_factor_method', 'biometric')
                        if two_factor_method == 'otp':
                            # Verify OTP code using pyotp
                            import pyotp
                            otp_code = request.POST.get('otp_code', '')
                            if len(otp_code) != 6 or not otp_code.isdigit():
                                messages.error(request, 'Invalid OTP code')
                                return render(request, 'attendance/two_factor_challenge.html', context)
                            
                            # Check if student has a valid secret key
                            if not hasattr(student.user, 'student') or not student.user.student.two_factor_secret:
                                messages.error(request, 'Two-factor authentication not properly configured')
                                return render(request, 'attendance/two_factor_challenge.html', context)
                            
                            # Verify OTP code against the secret key
                            totp = pyotp.TOTP(student.user.student.two_factor_secret)
                            if not totp.verify(otp_code):
                                messages.error(request, 'Invalid OTP code')
                                return render(request, 'attendance/two_factor_challenge.html', context)
                
                # Parse latitude and longitude
                try:
                    lat_float = float(latitude) if latitude else 0.0
                    lon_float = float(longitude) if longitude else 0.0
                except ValueError:
                    messages.error(request, 'Invalid GPS coordinates provided.')
                    return render(request, 'attendance/mark.html')

                # Check if student is within valid GPS radius
                if not attendance.is_within_radius(lat_float, lon_float):
                    messages.error(request, 'You are too far from the classroom to check in.')
                    return render(request, 'attendance/mark.html')
                
                # Mark attendance with location coordinates
                AttendanceStudent.objects.get_or_create(
                    attendance=attendance,
                    student=student,
                    defaults={
                        'latitude': lat_float if latitude else None,
                        'longitude': lon_float if longitude else None
                    }
                )
                
                # CRITICAL FIX: Add student to present_students M2M field
                attendance.present_students.add(student)
                
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
    
    # Security check - only lecturer can export
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
    
    # Security check: Only lecturers can manually mark attendance
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
    if hasattr(request.user, 'lecturer'):
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
    """Reports dashboard with real analytics"""
    from django.db.models import Avg, F
    from collections import defaultdict
    import json
    
    # ---- Role-scoped base querysets ----
    if hasattr(request.user, 'lecturer'):
        courses = Course.objects.filter(lecturer=request.user.lecturer)
        attendances = Attendance.objects.filter(course__lecturer=request.user.lecturer)
    elif hasattr(request.user, 'student'):
        courses = Course.objects.filter(students=request.user.student)
        attendances = Attendance.objects.filter(course__in=courses)
    elif request.user.is_superuser:
        courses = Course.objects.all()
        attendances = Attendance.objects.all()
    else:
        courses = Course.objects.none()
        attendances = Attendance.objects.none()
    
    attendances = attendances.select_related('course').prefetch_related('present_students')
    
    # ---- Summary stats ----
    total_records = attendances.count()
    total_courses = courses.count()
    total_students = Student.objects.filter(enrolled_courses__in=courses).distinct().count()
    active_sessions = attendances.filter(is_active=True).count()
    
    # ---- Per-course attendance rates ----
    course_stats = []
    for course in courses.select_related('lecturer').prefetch_related('students'):
        enrolled = course.students.count()
        sessions = attendances.filter(course=course)
        session_count = sessions.count()
        if session_count > 0 and enrolled > 0:
            total_marks = sum(s.present_students.count() for s in sessions)
            rate = round((total_marks / (session_count * enrolled)) * 100)
        else:
            rate = 0
        course_stats.append({
            'name': course.name,
            'code': course.course_code,
            'sessions': session_count,
            'enrolled': enrolled,
            'rate': rate,
        })
    course_stats.sort(key=lambda c: c['rate'], reverse=True)
    
    # ---- Weekly trend (last 8 weeks) ----
    today = timezone.localdate()
    week_labels = []
    week_counts = []
    for i in range(7, -1, -1):
        start = today - timedelta(weeks=i+1)
        end = today - timedelta(weeks=i)
        label = end.strftime('%b %d')
        count = attendances.filter(date__gte=start, date__lt=end).count()
        week_labels.append(label)
        week_counts.append(count)
    
    # ---- Recent sessions ----
    recent_sessions = attendances.order_by('-date', '-created_at')[:10]
    
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
    if hasattr(request.user, 'lecturer'):
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
        
        for att in attendances:
            ws.append([
                att.course.name,
                str(att.date),
                att.present_students.count(),
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
        
        for att in attendances:
            writer.writerow([
                att.course.name,
                att.date,
                att.present_students.count(),
                'Yes' if att.is_active else 'No',
                att.created_at,
            ])
        
        return response
  


def register_view(request):
    """View for user registration"""
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        role = request.POST.get('role')
        
        # Validate role
        if role not in ['lecturer', 'student']:
            messages.error(request, "Invalid role selected. Please choose either Student or Lecturer.")
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
                
                # Create profile based on role
                if role == 'lecturer':
                    Lecturer.objects.create(
                        user=user,
                        staff_id=request.POST.get('staff_id'),
                        name=request.POST.get('name'),
                        department=request.POST.get('department'),
                        phone_number=request.POST.get('phone_number')
                    )
                elif role == 'student':
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


# ==================== Error Handlers ====================

def error_404(request, exception):
    """Custom 404 page"""
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    """Custom 500 page"""
    return render(request, 'errors/500.html', status=500)
