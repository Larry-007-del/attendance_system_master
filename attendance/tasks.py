"""
Task scheduling for attendance notifications
Supports both Celery (for production) and simple time-based scheduling (for development)
"""
import threading
from datetime import timedelta
from django.utils import timezone
from .notification_service import send_attendance_expiring_notifications
from .models import Attendance


def schedule_attendance_expiration_reminder(attendance, token):
    """
    Schedule a reminder to be sent 15 minutes before the attendance session expires
    """
    # Calculate when to send the reminder (15 minutes before expiry)
    duration_hours = attendance.duration_hours or 2
    reminder_time = attendance.created_at + timedelta(hours=duration_hours) - timedelta(minutes=15)
    time_until_reminder = (reminder_time - timezone.now()).total_seconds()
    
    if time_until_reminder > 0:
        # Create a timer to send the reminder
        timer = threading.Timer(
            time_until_reminder,
            send_attendance_expiring_notifications,
            args=[attendance, token]
        )
        timer.daemon = True
        timer.start()
        return True
    else:
        # Session already expired or close to expiring
        return False


def send_attendance_started_notifications(attendance, token):
    """
    Send notifications to students when attendance session starts
    This should be called when the session begins
    """
    from .notification_service import send_attendance_started_notifications
    send_attendance_started_notifications(attendance, token)


def send_missed_attendance_notifications(attendance):
    """
    Send notifications to students who missed the attendance session
    This should be called when the session ends
    """
    from .notification_service import send_attendance_missed_notifications
    send_attendance_missed_notifications(attendance)


try:
    # Try to import Celery for production usage
    from celery import shared_task
    
    @shared_task(bind=True, max_retries=3)
    def celery_send_attendance_expiring_notifications(self, attendance_id, token):
        """
        Celery task to send attendance expiration reminders with retry logic
        """
        try:
            attendance = Attendance.objects.get(id=attendance_id)
            send_attendance_expiring_notifications(attendance, token)
            return True
        except Attendance.DoesNotExist:
            return False
        except Exception as e:
            self.retry(exc=e, countdown=60)  # Retry in 60 seconds
    
    @shared_task(bind=True, max_retries=3)
    def celery_send_attendance_started_notifications(self, attendance_id, token):
        """
        Celery task to send attendance started notifications with retry logic
        """
        try:
            attendance = Attendance.objects.get(id=attendance_id)
            send_attendance_started_notifications(attendance, token)
            return True
        except Attendance.DoesNotExist:
            return False
        except Exception as e:
            self.retry(exc=e, countdown=60)  # Retry in 60 seconds
    
    @shared_task(bind=True, max_retries=3)
    def celery_send_missed_attendance_notifications(self, attendance_id):
        """
        Celery task to send missed attendance notifications with retry logic
        """
        try:
            attendance = Attendance.objects.get(id=attendance_id)
            send_attendance_missed_notifications(attendance)
            return True
        except Attendance.DoesNotExist:
            return False
        except Exception as e:
            self.retry(exc=e, countdown=60)  # Retry in 60 seconds
    
    def schedule_attendance_expiration_reminder(attendance, token):
        """
        Celery version of the reminder scheduler
        """
        duration_hours = attendance.duration_hours or 2
        reminder_time = attendance.created_at + timedelta(hours=duration_hours) - timedelta(minutes=15)
        celery_send_attendance_expiring_notifications.apply_async(
            args=[attendance.id, token],
            eta=reminder_time
        )
        return True
        
except ImportError:
    # Celery not available, falling back to basic timer implementation
    pass