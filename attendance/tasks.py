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
from .models import Attendance


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