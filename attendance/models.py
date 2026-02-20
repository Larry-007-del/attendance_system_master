from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from geopy.distance import geodesic
from datetime import timedelta
from django.utils import timezone


class ActiveCourseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='lecturer_pictures/', blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)  # Added field
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.staff_id})"

    def validate_coordinates(self):
        if self.latitude is not None and self.longitude is not None:
            if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
                raise ValidationError("Invalid latitude or longitude.")

    def clean(self):
        self.validate_coordinates()
        super().clean()

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='student_pictures/', blank=True, null=True)
    programme_of_study = models.CharField(max_length=255, blank=True, null=True)  # Added field
    year = models.CharField(max_length=2, blank=True, null=True)  # Added field
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['programme_of_study']),
        ]

    def __str__(self):
        return f"{self.name} ({self.student_id})"

    def get_full_name(self):
        return f"{self.name} ({self.student_id})"

class Course(models.Model):
    name = models.CharField(max_length=100)
    course_code = models.CharField(max_length=10, unique=True)
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name='courses')
    students = models.ManyToManyField(Student, through='CourseEnrollment', related_name='enrolled_courses', blank=True)
    is_active = models.BooleanField(default=False)  # Added field

    def __str__(self):
        return f"{self.name} ({self.course_code})"

    def clean(self):
        if not Lecturer.objects.filter(id=self.lecturer_id).exists():
            raise ValidationError("Lecturer does not exist.")
        super().clean()

class CourseEnrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('course', 'student')

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

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['course', 'date']),
            models.Index(fields=['is_active']),
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
        """Returns True only if the session is active AND created less than 4 hours ago"""
        if not self.is_active:
            return False
        
        # Hard limit: 4 hours (adjust as needed)
        time_limit = self.created_at + timedelta(hours=4)
        return timezone.now() < time_limit

    def is_within_radius(self, student_lat, student_lon, radius_meters=50):
        """Check if student is within radius of lecturer's location"""
        if not self.lecturer_latitude or not self.lecturer_longitude:
            return True  # Fallback or deny depending on policy

        lecturer_coords = (self.lecturer_latitude, self.lecturer_longitude)
        student_coords = (student_lat, student_lon)
        distance = geodesic(lecturer_coords, student_coords).meters
        return distance <= radius_meters


# M2M Signal for Attendance Audit Logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

@receiver(m2m_changed, sender=Attendance.present_students.through)
def log_attendance_change(sender, instance, action, pk_set, **kwargs):
    """
    Logs when a student is manually added/removed from attendance.
    """
    if action in ["post_add", "post_remove"]:
        verb = "Added" if action == "post_add" else "Removed"
        students = ", ".join([str(pk) for pk in pk_set])
        print(f"AUDIT LOG: Students {students} were {verb} from Attendance ID {instance.id}")


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
        if self.generated_at is None:
            self.generated_at = timezone.now()

        if self.expires_at is None:
            self.expires_at = self.generated_at + timedelta(hours=4)

        if self.expires_at <= timezone.now():
            self.is_active = False

        # Generate QR code if it doesn't exist
        if not self.qr_code:
            qr_buffer = self.generate_qr_code()
            filename = f"qr_{self.token}.png"
            self.qr_code = SimpleUploadedFile(filename, qr_buffer.read(), content_type='image/png')

        super().save(*args, **kwargs)
