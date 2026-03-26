"""
Notification Service for Attendance System
Handles email and SMS notifications for students
"""
import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import Attendance, Student

logger = logging.getLogger(__name__)


def send_welcome_account_email(user, role='student'):
    """Send onboarding email when a Student/Lecturer profile is created."""
    if not user or not user.email:
        return False

    role_label = 'Lecturer' if role == 'lecturer' else 'Student'
    subject = f"Welcome to Exodus - {role_label} Account"
    context = {
        'user': user,
        'role': role_label,
        'login_url': '/login/',
    }
    html_message = render_to_string('emails/welcome_account.html', context)
    plain_message = (
        f"Welcome to Exodus, {user.username}! "
        f"Your {role_label.lower()} account is ready. "
        f"Sign in at {context['login_url']} to get started."
    )

    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error("Failed to send welcome email to %s: %s", user.email, e)
        return False


def send_attendance_started_notifications(attendance, token):
    """
    Send notifications to students when an attendance session starts
    """
    course = attendance.course
    students = course.students.select_related('user').all()
    
    for student in students:
        # Send email notification if student wants it
        if student.should_send_email_notifications():
            send_attendance_started_email(student, course, token)
        
        # Send SMS notification if student wants it and has a phone number
        if student.should_send_sms_notifications():
            send_attendance_started_sms(student, course, token)


def send_attendance_started_email(student, course, token):
    """
    Send email notification for started attendance session
    """
    subject = f"Attendance Session Started - {course.name}"
    context = {
        'student': student,
        'course': course,
        'token': token,
    }
    
    html_message = render_to_string('emails/attendance_started.html', context)
    plain_message = f"Attendance session started for {course.name} ({course.course_code}). Token: {token}"
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [student.user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", student.user.email, e)
        return False


def send_attendance_started_sms(student, course, token):
    """
    Send SMS notification for started attendance session
    """
    message = f"Attendance session started for {course.course_code}. Token: {token}"
    phone_number = student.phone_number
    
    try:
        # Try to send SMS using Twilio if configured
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
        # Try to send SMS using Africa's Talking if configured
        elif settings.AFRICAS_TALKING_USERNAME and settings.AFRICAS_TALKING_API_KEY:
            import africastalking
            africastalking.initialize(settings.AFRICAS_TALKING_USERNAME, settings.AFRICAS_TALKING_API_KEY)
            sms = africastalking.SMS
            sms.send(message, [phone_number])
        else:
            # Fallback to simulation if no SMS service configured
            logger.info("Simulating SMS to %s: %s", phone_number, message)
        return True
    except ImportError as e:
        logger.warning("SMS package not installed (pip install twilio / africastalking): %s", e)
        return False
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", phone_number, e)
        return False


def send_attendance_expiring_notifications(attendance, token):
    """
    Send notifications to students when an attendance session is about to expire
    """
    course = attendance.course
    students = course.students.select_related('user').all()
    present_ids = set(attendance.present_students.values_list('id', flat=True))
    
    for student in students:
        if student.id not in present_ids:
            if student.should_send_email_notifications():
                send_attendance_expiring_email(student, course, token, attendance)
            
            if student.should_send_sms_notifications():
                send_attendance_expiring_sms(student, course, token, attendance)


def send_attendance_expiring_email(student, course, token, attendance):
    """
    Send email notification for expiring attendance session
    """
    subject = f"Attendance Session Expiring Soon - {course.name}"
    duration_hours = attendance.duration_hours or 2
    expiration_time = attendance.created_at + timedelta(hours=duration_hours)
    context = {
        'student': student,
        'course': course,
        'token': token,
        'expiration_time': expiration_time.strftime('%H:%M:%S')
    }
    
    html_message = render_to_string('emails/attendance_expiring.html', context)
    plain_message = f"Attendance session for {course.course_code} expires in 15 minutes. Token: {token}"
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [student.user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error("Failed to send expiring email to %s: %s", student.user.email, e)
        return False


def send_attendance_expiring_sms(student, course, token, attendance):
    """
    Send SMS notification for expiring attendance session
    """
    duration_hours = attendance.duration_hours or 2
    expiration_time = attendance.created_at + timedelta(hours=duration_hours)
    message = f"Attendance for {course.course_code} expires in 15 minutes. Token: {token}"
    phone_number = student.phone_number
    
    try:
        # Try to send SMS using Twilio if configured
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
        # Try to send SMS using Africa's Talking if configured
        elif settings.AFRICAS_TALKING_USERNAME and settings.AFRICAS_TALKING_API_KEY:
            import africastalking
            africastalking.initialize(settings.AFRICAS_TALKING_USERNAME, settings.AFRICAS_TALKING_API_KEY)
            sms = africastalking.SMS
            sms.send(message, [phone_number])
        else:
            # Fallback to simulation if no SMS service configured
            logger.info("Simulating SMS to %s: %s", phone_number, message)
        return True
    except ImportError as e:
        logger.warning("SMS package not installed (pip install twilio / africastalking): %s", e)
        return False
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", phone_number, e)
        return False


def send_attendance_missed_notifications(attendance):
    """
    Send notifications to students who missed an attendance session
    """
    course = attendance.course
    present_ids = set(attendance.present_students.values_list('id', flat=True))
    all_students = course.students.select_related('user').all()
    
    missed_students = [student for student in all_students if student.id not in present_ids]
    
    for student in missed_students:
        if student.should_send_email_notifications():
            send_attendance_missed_email(student, course, attendance)
        
        if student.should_send_sms_notifications():
            send_attendance_missed_sms(student, course, attendance)


def send_attendance_missed_email(student, course, attendance):
    """
    Send email notification for missed attendance session
    """
    subject = f"You Missed Attendance - {course.name}"
    context = {
        'student': student,
        'course': course,
        'session_date': attendance.date.strftime('%Y-%m-%d')
    }
    
    html_message = render_to_string('emails/attendance_missed.html', context)
    plain_message = f"You missed the attendance session for {course.course_code} on {attendance.date}"
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [student.user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error("Failed to send missed email to %s: %s", student.user.email, e)
        return False


def send_attendance_missed_sms(student, course, attendance):
    """
    Send SMS notification for missed attendance session
    """
    message = f"You missed the attendance session for {course.course_code} on {attendance.date}"
    phone_number = student.phone_number
    
    try:
        # Try to send SMS using Twilio if configured
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
        # Try to send SMS using Africa's Talking if configured
        elif settings.AFRICAS_TALKING_USERNAME and settings.AFRICAS_TALKING_API_KEY:
            import africastalking
            africastalking.initialize(settings.AFRICAS_TALKING_USERNAME, settings.AFRICAS_TALKING_API_KEY)
            sms = africastalking.SMS
            sms.send(message, [phone_number])
        else:
            # Fallback to simulation if no SMS service configured
            logger.info("Simulating SMS to %s: %s", phone_number, message)
        return True
    except ImportError as e:
        logger.warning("SMS package not installed (pip install twilio / africastalking): %s", e)
        return False
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", phone_number, e)
        return False