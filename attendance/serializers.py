from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Lecturer, Student, Course, CourseEnrollment, Attendance, AttendanceToken
from django.contrib.auth.models import User

# User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

# Lecturer serializer
class LecturerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    courses = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    profile_picture = serializers.SerializerMethodField()  # Use SerializerMethodField

    class Meta:
        model = Lecturer
        fields = ['id', 'user', 'staff_id', 'name', 'profile_picture', 'courses', 'department', 'phone_number', 'latitude', 'longitude']

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return None

# Student serializer
class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    courses = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='enrolled_courses')
    profile_picture = serializers.SerializerMethodField()  # Use SerializerMethodField

    class Meta:
        model = Student
        fields = ['id', 'user', 'student_id', 'name', 'courses', 'profile_picture', 'programme_of_study', 'year', 'phone_number']

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return None

# Course serializer
class CourseSerializer(serializers.ModelSerializer):
    lecturer = LecturerSerializer(read_only=True)  # Use nested LecturerSerializer
    students = StudentSerializer(many=True, read_only=True)  # Use nested StudentSerializer

    class Meta:
        model = Course
        fields = ['id', 'name', 'course_code', 'lecturer', 'students']

# Course Enrollment serializer
class CourseEnrollmentSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    course = CourseSerializer(read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = ['course', 'student', 'enrolled_at']

# Attendance serializer
class AttendanceSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    present_students = StudentSerializer(many=True, read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'course', 'date', 'present_students', 'lecturer_latitude', 'lecturer_longitude', 'is_active', 'ended_at']

# Attendance token serializer
class AttendanceTokenSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    qr_code = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceToken
        fields = ['id', 'course', 'token', 'generated_at', 'expires_at', 'is_active', 'qr_code']

    def to_representation(self, instance):
        """Hide token value from non-staff users (students)."""
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            if not (user.is_superuser or hasattr(user, 'lecturer')):
                data.pop('token', None)
                data.pop('qr_code', None)
        return data

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_qr_code(self, obj):
        request = self.context.get('request')
        if obj.qr_code and request:
            return request.build_absolute_uri(obj.qr_code.url)
        return None

# Logout serializer
class LogoutSerializer(serializers.Serializer):
    pass

# Submit Location serializer
class SubmitLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    attendance_token = serializers.CharField(max_length=10)
