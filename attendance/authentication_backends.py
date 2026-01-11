from django.contrib.auth.backends import ModelBackend
from attendance.models import Student, Lecturer

class StudentBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, student_id=None, **kwargs):
        try:
            student = Student.objects.get(user__username=username, student_id=student_id)
        except Student.DoesNotExist:
            return None

        if student.user.check_password(password):
            return student.user
        return None

class StaffBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, staff_id=None, **kwargs):
        try:
            lecturer = Lecturer.objects.get(user__username=username, staff_id=staff_id)
        except Lecturer.DoesNotExist:
            return None

        if lecturer.user.check_password(password):
            return lecturer.user
        return None
