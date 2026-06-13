"""
Task scheduling for attendance notifications and bulk processing.
Uses Celery for asynchronous background processing with:
- Exponential backoff retries
- Failure email notifications for upload tasks
- Structured logging
"""
import logging
import secrets
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.core.mail import send_mail, EmailMessage
from django.utils import timezone

from .models import Attendance, Course, CourseEnrollment, Student
from .notification_service import (
    send_attendance_expiring_notifications as _send_expiring,
    send_attendance_missed_notifications as _send_missed,
    send_attendance_started_notifications as _send_started,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification tasks — lightweight, use autoretry with exponential backoff
# ---------------------------------------------------------------------------

@shared_task(
    bind=True, max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60, retry_backoff_max=600, retry_jitter=True,
)
def send_attendance_expiring_notifications(self, attendance_id, token):
    """Send attendance expiration reminders."""
    try:
        attendance = Attendance.objects.get(id=attendance_id)
    except Attendance.DoesNotExist:
        logger.warning('Attendance %s not found — skipping expiration notification.', attendance_id)
        return False
    _send_expiring(attendance, token)
    logger.info('Sent expiration notification for attendance %s.', attendance_id)
    return True


@shared_task(
    bind=True, max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60, retry_backoff_max=600, retry_jitter=True,
)
def send_attendance_started_notifications(self, attendance_id, token):
    """Send attendance started notifications."""
    try:
        attendance = Attendance.objects.get(id=attendance_id)
    except Attendance.DoesNotExist:
        logger.warning('Attendance %s not found — skipping started notification.', attendance_id)
        return False
    _send_started(attendance, token)
    logger.info('Sent started notification for attendance %s.', attendance_id)
    return True


@shared_task(
    bind=True, max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60, retry_backoff_max=600, retry_jitter=True,
)
def send_missed_attendance_notifications(self, attendance_id):
    """Send missed attendance notifications."""
    try:
        attendance = Attendance.objects.get(id=attendance_id)
    except Attendance.DoesNotExist:
        logger.warning('Attendance %s not found — skipping missed notification.', attendance_id)
        return False
    _send_missed(attendance)
    logger.info('Sent missed notification for attendance %s.', attendance_id)
    return True


def schedule_attendance_expiration_reminder(attendance, token):
    """Helper to schedule the expiration reminder at the right time."""
    duration_hours = attendance.duration_hours or 2
    reminder_time = attendance.created_at + timedelta(hours=duration_hours) - timedelta(minutes=15)

    if reminder_time > timezone.now():
        send_attendance_expiring_notifications.apply_async(
            args=[attendance.id, token],
            eta=reminder_time,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Helper: notify uploader on permanent failure
# ---------------------------------------------------------------------------

def _notify_upload_failure(uploader_email, task_name, error_msg):
    """Send a failure email when an upload task exhausts all retries."""
    if not uploader_email:
        return
    send_mail(
        subject=f'{task_name} Failed',
        message=(
            f'Your background upload task could not be completed after multiple attempts.\n\n'
            f'Error: {error_msg}\n\n'
            f'Please try uploading the file again. If the problem persists, contact support.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[uploader_email],
        fail_silently=True,
    )


# ---------------------------------------------------------------------------
# Bulk upload tasks — progress tracking + failure notifications
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, retry_backoff=60, retry_backoff_max=600, retry_jitter=True)
def process_student_upload(self, student_data_list, uploader_email):
    """
    Process bulk student CSV uploads.
    Reports progress via update_state() and emails uploader on completion or failure.
    """
    total = len(student_data_list)
    logger.info('Starting student upload: %d rows, uploader=%s', total, uploader_email)

    try:
        count = 0
        skipped = 0
        failed_rows = []
        from django.http import HttpRequest

        # Build a dummy request with the real production hostname so that
        # password-reset links in emails point to the live site, not localhost.
        _render_host = getattr(settings, 'RENDER_EXTERNAL_HOSTNAME', None)
        _allowed = [h for h in settings.ALLOWED_HOSTS if h not in ('*', 'localhost', '127.0.0.1', '')]
        if _render_host:
            _host, _port, _https = _render_host, '443', True
        elif _allowed:
            _host, _port, _https = _allowed[0], '443', True
        else:
            _host, _port, _https = 'localhost', '8000', False

        dummy_request = HttpRequest()
        dummy_request.META['SERVER_NAME'] = _host
        dummy_request.META['SERVER_PORT'] = _port

        for i, row in enumerate(student_data_list):
            self.update_state(state='PROGRESS', meta={
                'current': i + 1, 'total': total,
                'status': f'Processing student {i + 1} of {total}...',
            })

            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            email = row.get('email', '').strip()
            student_id = row.get('student_id', '').strip()

            if not all([first_name, last_name, email, student_id]):
                missing = [f for f, v in [('first_name', first_name), ('last_name', last_name), ('email', email), ('student_id', student_id)] if not v]
                failed_rows.append({'row': i + 1, 'student_id': student_id or '—', 'reason': f'Missing fields: {", ".join(missing)}'})
                continue

            if not User.objects.filter(username=student_id).exists():
                try:
                    random_password = secrets.token_urlsafe(12)
                    user = User.objects.create_user(
                        username=student_id,
                        email=email,
                        password=random_password,
                        first_name=first_name,
                        last_name=last_name,
                    )

                    Student.objects.create(
                        user=user,
                        student_id=student_id,
                        name=f'{first_name} {last_name}',
                    )

                    reset_form = PasswordResetForm({'email': user.email})
                    if reset_form.is_valid():
                        reset_form.save(
                            request=dummy_request,
                            use_https=_https,
                            email_template_name='registration/password_reset_email.html',
                        )

                    count += 1
                except Exception as row_exc:
                    logger.warning('Failed to create student for row %d (%s): %s', i + 1, student_id, row_exc)
                    failed_rows.append({'row': i + 1, 'student_id': student_id, 'reason': str(row_exc)})
            else:
                skipped += 1

        logger.info('Student upload complete: %d created, %d skipped, %d failed, %d total.', count, skipped, len(failed_rows), total)

        if uploader_email:
            body = f'Your CSV upload has finished processing.\n\n✅ Created: {count}\n⏭ Skipped (already exists): {skipped}\n❌ Failed: {len(failed_rows)}\n\nTotal rows: {total}'
            if failed_rows:
                body += '\n\nFailed rows:\n' + '\n'.join(
                    f'  Row {r["row"]} ({r["student_id"]}): {r["reason"]}' for r in failed_rows
                )
            send_mail(
                subject='Student Bulk Upload Complete',
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[uploader_email],
                fail_silently=True,
            )

        return {'created': count, 'skipped': skipped, 'failed': len(failed_rows), 'failed_rows': failed_rows, 'total': total}

    except Exception as exc:
        logger.exception('Student upload failed (attempt %d/%d): %s', self.request.retries + 1, self.max_retries + 1, exc)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error('Student upload permanently failed after %d retries.', self.max_retries)
            _notify_upload_failure(uploader_email, 'Student Bulk Upload', str(exc))
            raise


@shared_task(bind=True, max_retries=3, retry_backoff=60, retry_backoff_max=600, retry_jitter=True)
def process_enrollment_upload(self, student_ids, course_id, uploader_email):
    """
    Process bulk course enrollment CSV uploads.
    Reports progress via update_state() and emails uploader on completion or failure.
    """
    total = len(student_ids)
    logger.info('Starting enrollment upload: %d IDs, course=%s, uploader=%s', total, course_id, uploader_email)

    try:
        course = Course.objects.get(id=course_id)

        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': total,
            'status': 'Looking up students...',
        })

        students = Student.objects.filter(student_id__in=student_ids)
        existing_enrollments = set(
            CourseEnrollment.objects.filter(course=course).values_list('student_id', flat=True)
        )

        enrollments = []
        count = 0
        skipped = 0
        for i, student in enumerate(students):
            self.update_state(state='PROGRESS', meta={
                'current': i + 1, 'total': total,
                'status': f'Enrolling student {i + 1} of {total}...',
            })
            if student.id not in existing_enrollments:
                enrollments.append(CourseEnrollment(course=course, student_id=student.id))
                count += 1
            else:
                skipped += 1

        CourseEnrollment.objects.bulk_create(enrollments, ignore_conflicts=True)

        logger.info('Enrollment upload complete: %d enrolled, %d skipped in %s.', count, skipped, course.course_code)

        if uploader_email:
            send_mail(
                subject='Course Enrollment Bulk Upload Complete',
                message=f'Your CSV upload has finished processing. {count} students were successfully enrolled in {course.course_code} ({skipped} skipped).',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[uploader_email],
                fail_silently=True,
            )

        return {'enrolled': count, 'skipped': skipped, 'total': total, 'course': course.course_code}

    except Course.DoesNotExist:
        logger.error('Enrollment upload failed: course %s not found.', course_id)
        return {'error': 'Course not found.'}
    except Exception as exc:
        logger.exception('Enrollment upload failed (attempt %d/%d): %s', self.request.retries + 1, self.max_retries + 1, exc)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _notify_upload_failure(uploader_email, 'Course Enrollment Upload', str(exc))
            raise


@shared_task
def send_weekly_attendance_reports():
    """Celery Beat task to email weekly attendance summaries to all lecturers"""
    one_week_ago = timezone.now() - timedelta(days=7)
    active_courses = Course.objects.filter(is_active=True).select_related('lecturer__user')
    
    count = 0
    for course in active_courses:
        lecturer_email = course.lecturer.user.email
        if not lecturer_email:
            continue
            
        recent_sessions = Attendance.objects.filter(course=course, date__gte=one_week_ago)
        if not recent_sessions.exists():
            continue
            
        subject = f"Weekly Attendance Report: {course.name} ({course.course_code})"
        body = f"Hello {course.lecturer.name},\n\nHere is your weekly summary for {course.name}:\n\n"
        
        for session in recent_sessions:
            present = session.attendancestudent_set.count()
            body += f"- {session.date.strftime('%Y-%m-%d')}: {present} students attended.\n"
            
        body += "\nLog into the Exodus Dashboard to download full CSV/Excel exports.\n\nBest,\nExodus System"
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[lecturer_email],
        )
        email.send(fail_silently=True)
        count += 1
        
    logger.info("Weekly attendance reports dispatched successfully. Sent %d emails.", count)
    return f"Sent {count} weekly reports."

@shared_task
def close_expired_sessions_task():
    """Celery Beat task to automatically close expired attendance sessions"""
    from django.core.management import call_command
    try:
        call_command('close_expired_sessions', '--notify')
        return "Successfully ran close_expired_sessions command."
    except Exception as exc:
        logger.exception("Failed to run close_expired_sessions: %s", exc)
        raise