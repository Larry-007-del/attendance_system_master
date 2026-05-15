import logging
import secrets
import string

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from geopy.distance import geodesic
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='lecturer_pictures/', blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)  # Added field
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    require_two_factor_auth = models.BooleanField(default=False)  # 2FA setting
    two_factor_secret = models.CharField(max_length=100, blank=True, null=True)
    is_two_factor_enabled = models.BooleanField(default=False)
    fcm_token = models.CharField(max_length=255, blank=True, null=True, help_text="Firebase Notification Token")

    def __str__(self):
        return f"{self.name} ({self.staff_id})"

    def validate_coordinates(self):
        if self.latitude is not None and self.longitude is not None:
            if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
                raise ValidationError("Invalid latitude or longitude.")

    class Meta:
        indexes = [
            models.Index(fields=['department']),
        ]

    def clean(self):
        self.validate_coordinates()
        super().clean()

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='student_pictures/', blank=True, null=True)
    programme_of_study = models.CharField(max_length=255, blank=True, null=True)  # Added field
    year = models.CharField(max_length=2, blank=True, null=True)  # Added field
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    require_two_factor_auth = models.BooleanField(default=False)  # 2FA setting
    two_factor_secret = models.CharField(max_length=100, blank=True, null=True)
    is_two_factor_enabled = models.BooleanField(default=False)
    fcm_token = models.CharField(max_length=255, blank=True, null=True, help_text="Firebase Notification Token")
    
    NOTIFICATION_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('both', 'Both Email and SMS'),
        ('none', 'None')
    ]
    notification_preference = models.CharField(
        max_length=10,
        choices=NOTIFICATION_CHOICES,
        default='both'
    )
    is_notifications_enabled = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['programme_of_study']),
            models.Index(fields=['year']),
        ]

    def __str__(self):
        return f"{self.name} ({self.student_id})"

    def get_full_name(self):
        return f"{self.name} ({self.student_id})"

    def should_send_email_notifications(self):
        """Check if student should receive email notifications"""
        return self.is_notifications_enabled and (self.notification_preference in ['email', 'both'])

    def should_send_sms_notifications(self):
        """Check if student should receive SMS notifications"""
        return self.is_notifications_enabled and (self.notification_preference in ['sms', 'both']) and self.phone_number


class WebAuthnCredential(models.Model):
    """Stores WebAuthn (FIDO2) credentials for biometric authentication"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webauthn_credentials')
    credential_id = models.TextField(unique=True)    # base64url-encoded
    public_key = models.TextField()                   # base64url-encoded
    sign_count = models.IntegerField(default=0)
    name = models.CharField(max_length=100, default='Fingerprint')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

class Course(models.Model):
    JOIN_CODE_LENGTH = 6
    JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits

    name = models.CharField(max_length=100)
    course_code = models.CharField(max_length=10, unique=True)
    join_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name='courses')
    students = models.ManyToManyField(Student, through='CourseEnrollment', related_name='enrolled_courses', blank=True)
    is_active = models.BooleanField(default=False)
    require_two_factor_auth = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['lecturer', 'is_active']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.course_code})"

    @classmethod
    def generate_unique_join_code(cls, max_attempts=20):
        for _ in range(max_attempts):
            code = ''.join(
                secrets.choice(cls.JOIN_CODE_ALPHABET)
                for _ in range(cls.JOIN_CODE_LENGTH)
            )
            if not cls.objects.filter(
                models.Q(join_code=code) | models.Q(course_code=code)
            ).exists():
                return code
        raise ValidationError("Unable to generate a unique join code.")

    def save(self, *args, **kwargs):
        if self.join_code:
            self.join_code = self.join_code.strip().upper()
            conflict = self.__class__.objects.filter(
                models.Q(join_code=self.join_code) | models.Q(course_code=self.join_code)
            ).exclude(pk=self.pk).exists()
            if conflict:
                self.join_code = None
        if not self.join_code:
            self.join_code = self.generate_unique_join_code()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

class CourseEnrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('course', 'student')
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['course']),
        ]

class AttendanceStudent(models.Model):
    attendance = models.ForeignKey('Attendance', on_delete=models.CASCADE, db_index=True)
    student = models.ForeignKey('Student', on_delete=models.CASCADE, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    marked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('attendance', 'student')
        indexes = [
            models.Index(fields=['attendance', 'student']),
            models.Index(fields=['marked_at']),
        ]
    
    def is_within_valid_perimeter(self, radius_meters=50):
        """Check if student's location is within valid radius of lecturer's location"""
        if self.latitude is None or self.longitude is None or \
           self.attendance.lecturer_latitude is None or self.attendance.lecturer_longitude is None:
            return False
        
        lecturer_coords = (self.attendance.lecturer_latitude, self.attendance.lecturer_longitude)
        student_coords = (self.latitude, self.longitude)
        distance = geodesic(lecturer_coords, student_coords).meters
        return distance <= radius_meters
    
    def get_distance_from_lecturer(self):
        """Get distance between student and lecturer in meters"""
        if self.latitude is None or self.longitude is None or \
           self.attendance.lecturer_latitude is None or self.attendance.lecturer_longitude is None:
            return None
        
        lecturer_coords = (self.attendance.lecturer_latitude, self.attendance.lecturer_longitude)
        student_coords = (self.latitude, self.longitude)
        return geodesic(lecturer_coords, student_coords).meters


class Attendance(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date = models.DateField()
    present_students = models.ManyToManyField(Student, related_name='attended_classes')
    lecturer_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lecturer_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, related_name='created_attendances', on_delete=models.SET_NULL, null=True)
    updated_by = models.ForeignKey(User, related_name='updated_attendances', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    require_two_factor_auth = models.BooleanField(default=False)
    duration_hours = models.IntegerField(default=2)
    radius_meters = models.PositiveIntegerField(default=50, help_text="Geofencing radius in meters for this session")

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['course', 'date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['ended_at']),
        ]

    def __str__(self):
        return f"{self.course.name} - {self.date} (Active: {self.is_active})"

    def save(self, *args, **kwargs):
        if self.is_active:
            self.course.is_active = True
            self.course.save()
        if self.ended_at is not None:
            self.is_active = False
        super().save(*args, **kwargs)


    def is_open(self):
        return self.is_active and (self.ended_at is None or self.ended_at > timezone.now())

    @property
    def is_session_valid(self):
        """Returns True only if the session is active AND not expired"""
        if not self.is_active:
            return False
        
        time_limit = self.created_at + timedelta(hours=self.duration_hours)
        return timezone.now() < time_limit

    def is_within_radius(self, student_lat, student_lon, radius_meters=None):
        """Check if student is within radius of lecturer's location."""
        if not self.lecturer_latitude or not self.lecturer_longitude:
            logger.warning(
                "Attendance %s has no lecturer GPS — check-in denied for safety.", self.pk
            )
            return False  # Deny if lecturer location was never captured
        radius = radius_meters if radius_meters is not None else self.radius_meters
        lecturer_coords = (self.lecturer_latitude, self.lecturer_longitude)
        student_coords = (student_lat, student_lon)
        distance = geodesic(lecturer_coords, student_coords).meters
        return distance <= radius


# M2M Signal for Attendance Audit Logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

@receiver(m2m_changed, sender=Attendance.present_students.through)
def log_attendance_change(sender, instance, action, pk_set, **kwargs):
    """
    Logs when a student is manually added/removed from attendance.
    Also creates/removes AttendanceStudent records so timestamp and audit data stays in sync.
    """
    if action == "post_add" and pk_set:
        for student_pk in pk_set:
            AttendanceStudent.objects.get_or_create(
                attendance=instance,
                student_id=student_pk,
            )
        students = ", ".join([str(pk) for pk in pk_set])
        logger.info("AUDIT: Students %s were Added to Attendance ID %s", students, instance.id)
    elif action == "post_remove" and pk_set:
        AttendanceStudent.objects.filter(
            attendance=instance,
            student_id__in=pk_set,
        ).delete()
        students = ", ".join([str(pk) for pk in pk_set])
        logger.info("AUDIT: Students %s were Removed from Attendance ID %s", students, instance.id)


import qrcode
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models

class AttendanceToken(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    token = models.CharField(max_length=6, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['course', 'is_active']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.course.name} - {self.token}"

    def generate_qr_code(self):
        """Generate QR code for the attendance token"""
        # Create QR code with token information
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"attendance_token:{self.token}")
        qr.make(fit=True)

        img = qr.make_image(fill_color='black', back_color='white')
        
        # Save to in-memory file
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer

    def save(self, *args, **kwargs):
        if self.token:
            self.token = self.token.strip().upper()

        if self.generated_at is None:
            self.generated_at = timezone.now()

        if self.expires_at is None:
            # Default: 2 hours if not specified
            self.expires_at = self.generated_at + timedelta(hours=2)

        if self.expires_at <= timezone.now():
            self.is_active = False

        # Generate QR code if it doesn't exist
        if not self.qr_code:
            qr_buffer = self.generate_qr_code()
            filename = f"qr_{self.token}.png"
            self.qr_code = SimpleUploadedFile(filename, qr_buffer.read(), content_type='image/png')

        super().save(*args, **kwargs)
