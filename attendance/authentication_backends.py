from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from attendance.models import Student, Lecturer
import logging

logger = logging.getLogger(__name__)


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.filter(email=username).first()
            if user and user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        except Exception:
            logger.exception("Unexpected error in EmailBackend.authenticate")
            return None

class StudentBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, student_id=None, **kwargs):
        try:
            student = Student.objects.select_related('user').get(user__username=username, student_id=student_id)
        except Student.DoesNotExist:
            return None

        if student.user.check_password(password):
            return student.user
        return None

class StaffBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, staff_id=None, **kwargs):
        try:
            lecturer = Lecturer.objects.select_related('user').get(user__username=username, staff_id=staff_id)
        except Lecturer.DoesNotExist:
            return None

        if lecturer.user.check_password(password):
            return lecturer.user
        return None
