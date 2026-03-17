"""
Task scheduling for attendance notifications
Uses Celery for asynchronous background processing
"""
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .notification_service import (
    send_attendance_expiring_notifications as _send_expiring,
    send_attendance_started_notifications as _send_started,
    send_attendance_missed_notifications as _send_missed
)
from .models import Attendance, Student, Course, CourseEnrollment
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.conf import settings
import secrets


@shared_task(bind=True, max_retries=3)
def send_attendance_expiring_notifications(self, attendance_id, token):
    """
    Celery task to send attendance expiration reminders with retry logic
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        _send_expiring(attendance, token)
        return True
    except Attendance.DoesNotExist:
        return False
    except Exception as e:
        self.retry(exc=e, countdown=60)  # Retry in 60 seconds


@shared_task(bind=True, max_retries=3)
def send_attendance_started_notifications(self, attendance_id, token):
    """
    Celery task to send attendance started notifications with retry logic
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        _send_started(attendance, token)
        return True
    except Attendance.DoesNotExist:
        return False
    except Exception as e:
        self.retry(exc=e, countdown=60)  # Retry in 60 seconds


@shared_task(bind=True, max_retries=3)
def send_missed_attendance_notifications(self, attendance_id):
    """
    Celery task to send missed attendance notifications with retry logic
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        _send_missed(attendance)
        return True
    except Attendance.DoesNotExist:
        return False
    except Exception as e:
        self.retry(exc=e, countdown=60)  # Retry in 60 seconds


def schedule_attendance_expiration_reminder(attendance, token):
    """
    Helper function to schedule the expiration reminder
    """
    duration_hours = attendance.duration_hours or 2
    reminder_time = attendance.created_at + timedelta(hours=duration_hours) - timedelta(minutes=15)
    
    # Only schedule if the reminder time is in the future
    if reminder_time > timezone.now():
        send_attendance_expiring_notifications.apply_async(
            args=[attendance.id, token],
            eta=reminder_time
        )
        return True
    return False


@shared_task(bind=True, max_retries=3)
def process_student_upload(self, student_data_list, uploader_email):
    """
    Celery task to handle processing of bulk student CSV uploads.
    Accepts a list of dictionaries representing the parsed CSV rows.
    """
    total = len(student_data_list)
    try:
        count = 0
        skipped = 0
        from django.http import HttpRequest
        
        dummy_request = HttpRequest()
        dummy_request.META['SERVER_NAME'] = 'localhost'
        dummy_request.META['SERVER_PORT'] = '8000'
        
        for i, row in enumerate(student_data_list):
            self.update_state(state='PROGRESS', meta={
                'current': i + 1, 'total': total,
                'status': f'Processing student {i + 1} of {total}...'
            })

            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            email = row.get('email', '').strip()
            student_id = row.get('student_id', '').strip()

            if not all([first_name, last_name, email, student_id]):
                skipped += 1
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
                    reset_form.save(
                        request=dummy_request, 
                        use_https=True,
                        email_template_name='registration/password_reset_email.html'
                    )
                    
                count += 1
            else:
                skipped += 1

        if uploader_email:
            send_mail(
                subject='Student Bulk Upload Complete',
                message=f'Your CSV upload has finished processing. {count} new students were successfully registered.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[uploader_email],
                fail_silently=True,
            )
            
        return {'created': count, 'skipped': skipped, 'total': total}
        
    except Exception as e:
        self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_enrollment_upload(self, student_ids, course_id, uploader_email):
    """
    Celery task to handle processing of bulk course enrollment CSV uploads.
    Accepts a list of student IDs and the course ID.
    """
    total = len(student_ids)
    try:
        course = Course.objects.get(id=course_id)
        
        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': total,
            'status': 'Looking up students...'
        })

        students = Student.objects.filter(student_id__in=student_ids)
        existing_enrollments = CourseEnrollment.objects.filter(course=course).values_list('student_id', flat=True)
        
        enrollments = []
        count = 0
        skipped = 0
        for i, student in enumerate(students):
            self.update_state(state='PROGRESS', meta={
                'current': i + 1, 'total': total,
                'status': f'Enrolling student {i + 1} of {total}...'
            })
            if student.id not in existing_enrollments:
                enrollments.append(CourseEnrollment(course=course, student_id=student.id))
                count += 1
            else:
                skipped += 1
        
        CourseEnrollment.objects.bulk_create(enrollments, ignore_conflicts=True)
        
        if uploader_email:
            send_mail(
                subject='Course Enrollment Bulk Upload Complete',
                message=f'Your CSV upload has finished processing. {count} students were successfully enrolled in {course.course_code}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[uploader_email],
                fail_silently=True,
            )
            
        return {'enrolled': count, 'skipped': skipped, 'total': total, 'course': course.course_code}
        
    except Course.DoesNotExist:
        return {'error': 'Course not found.'}
    except Exception as e:
        self.retry(exc=e, countdown=60)