from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction
from datetime import timedelta
import csv
import openpyxl
from openpyxl import Workbook

from attendance.models import Lecturer, Student, Course, Attendance, AttendanceToken, CourseEnrollment
from django.contrib.auth.models import User
from .forms import LecturerForm, StudentForm, CourseForm


# ==================== Authentication ====================

def login_view(request):
    """HTMX-powered login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirect admins/superusers to Django admin
            if user.is_superuser or user.is_staff:
                return redirect('/admin/')
            # Redirect lecturers and students to dashboard
            if hasattr(user, 'lecturer'):
                return redirect('dashboard')
            elif hasattr(user, 'student'):
                return redirect('dashboard')
            # Default redirect
            next_url = request.GET.get('next', '/dashboard/')
            if request.htmx:
                return render(request, 'partials/login-success.html', {'next': next_url})
            return redirect(next_url)
        else:
            if request.htmx:
                return render(request, 'partials/login-error.html', {'error': 'Invalid username or password'})
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'registration/login.html')


def logout_view(request):
    """Logout view"""
    logout(request)
    return redirect('login')


# ==================== Dashboard ====================

@login_required
def dashboard(request):
    # Fix: Redirect Superusers to the backend Admin panel
    if request.user.is_superuser:
        return redirect('/admin/')
        
    # ... rest of your existing logic for Students/Lecturers ...
    context = {
        'total_lecturers': Lecturer.objects.count(),
        'total_students': Student.objects.count(),
        'total_courses': Course.objects.count(),
        'active_courses': Course.objects.filter(is_active=True).count(),
        'today': timezone.now().date(),
        'today_attendance': Attendance.objects.filter(date=timezone.now().date()).count(),
        'recent_attendances': Attendance.objects.order_by('-created_at')[:5],
    }
    return render(request, 'dashboard.html', context)


def ajax_dashboard_stats(request):
    """HTMX endpoint for dashboard statistics"""
    stats = {
        'total_lecturers': Lecturer.objects.count(),
        'total_students': Student.objects.count(),
        'total_courses': Course.objects.count(),
        'active_courses': Course.objects.filter(is_active=True).count(),
        'today_attendance': Attendance.objects.filter(date=timezone.now().date()).count(),
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
                    return redirect('lecturer_create')
                
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists')
                    return redirect('lecturer_create')
                
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
                    return redirect('lecturer_list')
                else:
                    # Transaction will rollback automatically
                    raise ValueError("Form Invalid")
        except ValueError:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
            return redirect('lecturer_create')
    
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
        return redirect('lecturer_detail', pk=pk)
    
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
        return redirect('lecturer_list')
    
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
                    return redirect('student_create')
                
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists')
                    return redirect('student_create')
                
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
                    return redirect('student_list')
                else:
                    # Transaction will rollback automatically
                    raise ValueError("Form Invalid")
        except ValueError:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
            return redirect('student_create')
    
    return render(request, 'students/create.html')


@login_required
def student_detail(request, pk):
    """View student details"""
    student = get_object_or_404(Student, pk=pk)
    enrollments = CourseEnrollment.objects.filter(student=student)
    attendances = Attendance.objects.filter(present_students=student)
    
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
        student.save()
        
        messages.success(request, f'Student {student.name} updated successfully!')
        return redirect('student_detail', pk=pk)
    
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
        return redirect('student_list')
    
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
    
    courses = Course.objects.all().select_related('lecturer')
    
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
            return redirect('course_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
            return redirect('course_list')
    
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
        return redirect('course_detail', pk=pk)
    
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
    
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted successfully!')
        return redirect('course_list')
    
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
    today = timezone.now().date()
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
    if request.method == 'POST':
        course_id = request.POST.get('course')
        token_value = request.POST.get('token')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        course = get_object_or_404(Course, pk=course_id)
        
        # Create attendance session
        attendance = Attendance.objects.create(
            course=course,
            date=timezone.now().date(),
            lecturer_latitude=latitude or None,
            lecturer_longitude=longitude or None,
            is_active=True,
            created_by=request.user,
        )
        
        # Generate token
        att_token = AttendanceToken.objects.create(
            course=course,
            token=token_value,
            is_active=True,
        )
        
        # Update course status
        course.is_active = True
        course.save()
        
        messages.success(request, f'Attendance session started for {course.name}!')
        return redirect('attendance_detail', pk=attendance.pk)
    
    # Get lecturer's courses
    try:
        lecturer = Lecturer.objects.get(user=request.user)
        courses = Course.objects.filter(lecturer=lecturer)
    except Lecturer.DoesNotExist:
        courses = Course.objects.all()
    
    context = {'courses': courses}
    return render(request, 'attendance/take.html', context)


@login_required
def attendance_mark(request):
    """Mark attendance - student view"""
    if request.method == 'POST':
        token = request.POST.get('token')
        
        try:
            att_token = AttendanceToken.objects.get(token=token, is_active=True)
            course = att_token.course
            
            # Check if student is enrolled
            try:
                student = Student.objects.get(user=request.user)
                if student not in course.students.all():
                    messages.error(request, 'You are not enrolled in this course!')
                    return render(request, 'attendance/mark.html')
                
                # Mark attendance
                attendance, created = Attendance.objects.get_or_create(
                    course=course,
                    date=timezone.now().date()
                )
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
    present_ids = attendance.present_students.values_list('id', flat=True)
    
    context = {
        'attendance': attendance,
        'course': course,
        'all_students': all_students,
        'present_ids': list(present_ids),
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
    
    # Security check
    if attendance.course.lecturer != request.user.lecturer:
        return HttpResponse("Unauthorized", status=403)
        
    student = get_object_or_404(Student, id=student_id)
    
    # Add to ManyToMany field
    attendance.present_students.add(student)
    
    return redirect('attendance_detail', pk=attendance_id)


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
