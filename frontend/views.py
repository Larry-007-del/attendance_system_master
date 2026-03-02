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
from datetime import timedelta
import csv
import io
import openpyxl
from openpyxl import Workbook

from attendance.models import Lecturer, Student, Course, Attendance, AttendanceToken, CourseEnrollment
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
    """View for user logout - handles both GET and POST with proper CSRF handling"""
    if request.method == 'POST':
        logout(request)
        return redirect('frontend:login')
    # For GET requests, still log out and redirect
    logout(request)
    return redirect('frontend:login')


# ==================== Dashboard ====================

@login_required
def dashboard(request):
    """Main dashboard view - safe for all user types"""
    context = {
        'role_label': 'User',
        'attendance_rate': 0,
        'next_class': 'No classes scheduled',
        'is_student': False,
        'is_lecturer': False,
        'is_admin': request.user.is_superuser,
    }

    # Safely determine user role
    if request.user.is_superuser:
        context['role_label'] = 'Administrator'
    elif hasattr(request.user, 'lecturer'):
        try:
            if request.user.lecturer:
                context['is_lecturer'] = True
                context['role_label'] = 'Lecturer'
                # Get courses taught by lecturer with enrollment count
                context['taught_courses'] = Course.objects.filter(lecturer=request.user.lecturer).annotate(
                    enrolled_count=Count('students')
                )
        except Lecturer.DoesNotExist:
            pass
    elif hasattr(request.user, 'student'):
        try:
            if request.user.student:
                context['is_student'] = True
                context['role_label'] = 'Student'
                # Get attendance rate with fallback
                context['attendance_rate'] = getattr(request.user.student, 'attendance_rate', 0)
                # Get enrolled courses with lecturer information
                context['enrolled_courses'] = Course.objects.filter(students=request.user.student).select_related('lecturer')
        except Student.DoesNotExist:
            pass

    return render(request, 'dashboard.html', context)


@login_required
def checkin_view(request):
    """Check-in page with GPS pulsing button"""
    return render(request, 'frontend/checkin.html')


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
        lecturers = Lecturer.objects.filter(
            Q(name__icontains=query) | Q(staff_id__icontains=query) | Q(department__icontains=query)
        )
    else:
        lecturers = Lecturer.objects.all()
    
    context = {
        'lecturers': lecturers,
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
                    return redirect('frontend:lecturer_create')
                
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists')
                    return redirect('frontend:lecturer_create')
                
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
                    messages.error(request, f'{error}')
            return redirect('frontend:lecturer_create')
    
    return render(request, 'lecturers/create.html')


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


def ajax_search_lecturers(request):
    """Search lecturers for HTMX"""
    query = request.GET.get('q', '')
    lecturers = Lecturer.objects.filter(
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
    
    students = Student.objects.all()
    
    if query:
        students = students.filter(
            Q(name__icontains=query) | Q(student_id__icontains=query)
        )
    if year_filter:
        students = students.filter(year=year_filter)
    if programme_filter:
        students = students.filter(programme_of_study=programme_filter)
    
    context = {
        'students': students,
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
                for column in csv.reader(io_string, delimiter=',', quotechar='|'):
                    first_name = column[0]
                    last_name = column[1]
                    email = column[2]
                    student_id = column[3]

                    if not User.objects.filter(username=student_id).exists():
                        random_password = secrets.token_urlsafe(12)
                        user = User.objects.create_user(
                            username=student_id, 
                            email=email, 
                            password=random_password,
                            first_name=first_name,
                            last_name=last_name
                        )
                        
                        Student.objects.create(user=user, student_id=student_id)
                        
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
    
    if request.method == 'POST':
        user = student.user
        student.delete()
        user.delete()
        messages.success(request, 'Student deleted successfully!')
        return redirect('frontend:student_list')
    
    context = {'student': student}
    return render(request, 'students/delete.html', context)


def ajax_search_students(request):
    """Search students for HTMX"""
    query = request.GET.get('q', '')
    students = Student.objects.filter(
        Q(name__icontains=query) | Q(student_id__icontains=query)
    )[:10]
    
    return render(request, 'partials/student_rows.html', {'students': students})


# ==================== Courses ====================

@login_required
def course_list(request):
    """List all courses"""
    query = request.GET.get('q')
    active_filter = request.GET.get('active')
    
    courses = Course.objects.all().select_related('lecturer').annotate(
        enrolled_count=Count('students')
    )
    
    if query:
        courses = courses.filter(
            Q(name__icontains=query) | Q(course_code__icontains=query)
        )
    if active_filter is not None:
        courses = courses.filter(is_active=active_filter == 'true')
    
    context = {
        'courses': courses,
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
    lecturers = Lecturer.objects.all()
    students = Student.objects.all()
    context = {
        'lecturers': lecturers,
        'students': students,
        'form': form if 'form' in locals() else CourseForm(),
    }
    return render(request, 'courses/create.html', context)
    
    lecturers = Lecturer.objects.all()
    students = Student.objects.all()
    context = {
        'lecturers': lecturers,
        'students': students,
    }
    return render(request, 'courses/create.html', context)


@login_required
def course_detail(request, pk):
    """View course details"""
    course = get_object_or_404(Course, pk=pk)
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')
    attendances = Attendance.objects.filter(course=course)
    
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
    
    lecturers = Lecturer.objects.all()
    students = Student.objects.all()
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
        token_value = request.POST.get('token')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        require_two_factor_auth = request.POST.get('require_two_factor_auth') == 'on'
        
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
            lecturer_latitude=latitude or None,
            lecturer_longitude=longitude or None,
            is_active=True,
            created_by=request.user,
            require_two_factor_auth=require_two_factor_auth,
        )
        
        # Generate token
        att_token = AttendanceToken.objects.create(
            course=course,
            token=token_value,
            is_active=True,
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
    try:
        lecturer = Lecturer.objects.get(user=request.user)
        courses = Course.objects.filter(lecturer=lecturer)
    except Lecturer.DoesNotExist:
        courses = Course.objects.all()
    
    context = {
        'courses': courses,
        'active_session': active_session,
        'lecturer': Lecturer.objects.get(user=request.user) if hasattr(request.user, 'lecturer') else None
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
                attendance, created = Attendance.objects.get_or_create(
                    course=course,
                    date=timezone.now().date()
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
                            # Verify OTP code (simplified example - should check against real OTP system)
                            otp_code = request.POST.get('otp_code', '')
                            if len(otp_code) != 6 or not otp_code.isdigit():
                                messages.error(request, 'Invalid OTP code')
                                return render(request, 'attendance/two_factor_challenge.html', context)
                
                # Mark attendance with location coordinates
                AttendanceStudent.objects.get_or_create(
                    attendance=attendance,
                    student=student,
                    defaults={
                        'latitude': latitude,
                        'longitude': longitude
                    }
                )
                
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
    
    attendances = Attendance.objects.all().select_related('course')
    
    if course_filter:
        attendances = attendances.filter(course_id=course_filter)
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    
    courses = Course.objects.all()
    
    context = {
        'attendances': attendances.order_by('-date'),
        'courses': courses,
        'course_filter': course_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'attendance/history.html', context)


# ==================== Reports ====================

@login_required
def reports_index(request):
    """Reports dashboard"""
    return render(request, 'reports/index.html')


@login_required
def reports_export(request):
    """Export attendance data"""
    course_id = request.GET.get('course')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    export_format = request.GET.get('format', 'csv')
    
    attendances = Attendance.objects.all().select_related('course')
    
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
