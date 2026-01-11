from django.contrib import admin
from .models import Lecturer, Student, Course, CourseEnrollment, Attendance, AttendanceToken

admin.site.register(Course)
admin.site.register(Attendance)
admin.site.register(Student)
admin.site.register(Lecturer)
admin.site.register(CourseEnrollment)
admin.site.register(AttendanceToken)
