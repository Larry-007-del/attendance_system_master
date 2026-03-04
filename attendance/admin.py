from django.contrib import admin
from .models import Lecturer, Student, Course, CourseEnrollment, Attendance, AttendanceToken, AttendanceStudent


@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('name', 'staff_id', 'department', 'phone_number', 'is_two_factor_enabled')
    search_fields = ('name', 'staff_id', 'user__email', 'department')
    list_filter = ('department', 'is_two_factor_enabled', 'require_two_factor_auth')
    readonly_fields = ('two_factor_secret',)
    raw_id_fields = ('user',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'student_id', 'programme_of_study', 'year', 'notification_preference', 'is_notifications_enabled')
    search_fields = ('name', 'student_id', 'user__email', 'programme_of_study')
    list_filter = ('programme_of_study', 'year', 'notification_preference', 'is_notifications_enabled', 'is_two_factor_enabled')
    readonly_fields = ('two_factor_secret',)
    raw_id_fields = ('user',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_code', 'lecturer', 'is_active', 'require_two_factor_auth')
    search_fields = ('name', 'course_code', 'lecturer__name')
    list_filter = ('is_active', 'require_two_factor_auth')
    raw_id_fields = ('lecturer',)


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('course', 'student', 'enrolled_at')
    search_fields = ('course__name', 'course__course_code', 'student__name', 'student__student_id')
    list_filter = ('enrolled_at',)
    raw_id_fields = ('course', 'student')


class AttendanceStudentInline(admin.TabularInline):
    model = AttendanceStudent
    extra = 0
    readonly_fields = ('marked_at',)
    raw_id_fields = ('student',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'is_active', 'duration_hours', 'require_two_factor_auth', 'created_at')
    search_fields = ('course__name', 'course__course_code')
    list_filter = ('is_active', 'date', 'require_two_factor_auth', 'duration_hours')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('course', 'created_by', 'updated_by')
    date_hierarchy = 'date'
    inlines = [AttendanceStudentInline]


@admin.register(AttendanceStudent)
class AttendanceStudentAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'student', 'latitude', 'longitude', 'marked_at')
    search_fields = ('student__name', 'student__student_id', 'attendance__course__name')
    list_filter = ('marked_at',)
    readonly_fields = ('marked_at',)
    raw_id_fields = ('attendance', 'student')


@admin.register(AttendanceToken)
class AttendanceTokenAdmin(admin.ModelAdmin):
    list_display = ('course', 'token', 'is_active', 'generated_at', 'expires_at')
    search_fields = ('course__name', 'course__course_code', 'token')
    list_filter = ('is_active', 'generated_at')
    readonly_fields = ('generated_at', 'qr_code')
