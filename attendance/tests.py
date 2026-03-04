"""
Comprehensive tests for attendance app models, serializers, and API views.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    Attendance,
    AttendanceStudent,
    AttendanceToken,
    Course,
    CourseEnrollment,
    Lecturer,
    Student,
)


# ==================== Model Tests ====================


class LecturerModelTest(TestCase):
    """Tests for the Lecturer model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='lecturer1', email='lec@test.com', password='pass1234'
        )
        self.lecturer = Lecturer.objects.create(
            user=self.user,
            staff_id='L001',
            name='Dr. Smith',
            department='Computer Science',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.lecturer), 'Dr. Smith (L001)')

    def test_valid_coordinates(self):
        self.lecturer.latitude = Decimal('5.650000')
        self.lecturer.longitude = Decimal('-0.187000')
        self.lecturer.clean()  # Should not raise

    def test_invalid_latitude(self):
        self.lecturer.latitude = Decimal('100.000000')
        self.lecturer.longitude = Decimal('0.000000')
        with self.assertRaises(ValidationError):
            self.lecturer.clean()

    def test_invalid_longitude(self):
        self.lecturer.latitude = Decimal('0.000000')
        self.lecturer.longitude = Decimal('200.000000')
        with self.assertRaises(ValidationError):
            self.lecturer.clean()

    def test_null_coordinates_valid(self):
        self.lecturer.latitude = None
        self.lecturer.longitude = None
        self.lecturer.clean()  # Should not raise

    def test_one_to_one_user_relationship(self):
        self.assertEqual(self.user.lecturer, self.lecturer)

    def test_default_two_factor_fields(self):
        self.assertFalse(self.lecturer.require_two_factor_auth)
        self.assertFalse(self.lecturer.is_two_factor_enabled)
        self.assertIsNone(self.lecturer.two_factor_secret)


class StudentModelTest(TestCase):
    """Tests for the Student model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='student1', email='stu@test.com', password='pass1234'
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='ST001',
            name='Jane Doe',
            programme_of_study='Computer Science',
            year='2',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.student), 'Jane Doe (ST001)')

    def test_get_full_name(self):
        self.assertEqual(self.student.get_full_name(), 'Jane Doe (ST001)')

    def test_default_notification_preference(self):
        self.assertEqual(self.student.notification_preference, 'both')
        self.assertTrue(self.student.is_notifications_enabled)

    def test_should_send_email_notifications_both(self):
        self.student.notification_preference = 'both'
        self.assertTrue(self.student.should_send_email_notifications())

    def test_should_send_email_notifications_email_only(self):
        self.student.notification_preference = 'email'
        self.assertTrue(self.student.should_send_email_notifications())

    def test_should_not_send_email_notifications_sms_only(self):
        self.student.notification_preference = 'sms'
        self.assertFalse(self.student.should_send_email_notifications())

    def test_should_not_send_email_notifications_none(self):
        self.student.notification_preference = 'none'
        self.assertFalse(self.student.should_send_email_notifications())

    def test_should_not_send_email_when_disabled(self):
        self.student.is_notifications_enabled = False
        self.student.notification_preference = 'both'
        self.assertFalse(self.student.should_send_email_notifications())

    def test_should_send_sms_notifications_with_phone(self):
        self.student.notification_preference = 'sms'
        self.student.phone_number = '+233241234567'
        self.assertTrue(self.student.should_send_sms_notifications())

    def test_should_not_send_sms_without_phone(self):
        self.student.notification_preference = 'sms'
        self.student.phone_number = ''
        self.assertFalse(self.student.should_send_sms_notifications())

    def test_should_not_send_sms_none_phone(self):
        self.student.notification_preference = 'sms'
        self.student.phone_number = None
        self.assertFalse(self.student.should_send_sms_notifications())


class CourseModelTest(TestCase):
    """Tests for the Course model"""

    def setUp(self):
        self.user = User.objects.create_user(username='lec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.user, staff_id='L001', name='Dr. Smith'
        )
        self.course = Course.objects.create(
            name='Intro to CS',
            course_code='CS101',
            lecturer=self.lecturer,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.course), 'Intro to CS (CS101)')

    def test_default_is_active(self):
        self.assertFalse(self.course.is_active)

    def test_default_require_two_factor(self):
        self.assertFalse(self.course.require_two_factor_auth)

    def test_unique_course_code(self):
        with self.assertRaises(Exception):
            Course.objects.create(
                name='Duplicate Course',
                course_code='CS101',
                lecturer=self.lecturer,
            )

    def test_lecturer_relationship(self):
        self.assertEqual(self.course.lecturer, self.lecturer)
        self.assertIn(self.course, self.lecturer.courses.all())


class CourseEnrollmentTest(TestCase):
    """Tests for the CourseEnrollment model (M2M through table)"""

    def setUp(self):
        self.lec_user = User.objects.create_user(username='lec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.lec_user, staff_id='L001', name='Dr. Smith'
        )
        self.stu_user = User.objects.create_user(username='stu', password='pass1234')
        self.student = Student.objects.create(
            user=self.stu_user, student_id='ST001', name='Jane Doe'
        )
        self.course = Course.objects.create(
            name='Intro to CS',
            course_code='CS101',
            lecturer=self.lecturer,
        )

    def test_enroll_student(self):
        self.course.students.add(self.student)
        self.assertIn(self.student, self.course.students.all())

    def test_enrollment_creates_through_record(self):
        self.course.students.add(self.student)
        self.assertTrue(
            CourseEnrollment.objects.filter(
                course=self.course, student=self.student
            ).exists()
        )

    def test_duplicate_enrollment_prevented(self):
        CourseEnrollment.objects.create(course=self.course, student=self.student)
        with self.assertRaises(Exception):
            CourseEnrollment.objects.create(course=self.course, student=self.student)

    def test_unenroll_student(self):
        self.course.students.add(self.student)
        self.course.students.remove(self.student)
        self.assertNotIn(self.student, self.course.students.all())


class AttendanceModelTest(TestCase):
    """Tests for the Attendance model"""

    def setUp(self):
        self.lec_user = User.objects.create_user(username='lec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.lec_user, staff_id='L001', name='Dr. Smith'
        )
        self.stu_user = User.objects.create_user(username='stu', password='pass1234')
        self.student = Student.objects.create(
            user=self.stu_user, student_id='ST001', name='Jane Doe'
        )
        self.course = Course.objects.create(
            name='Intro to CS', course_code='CS101', lecturer=self.lecturer
        )
        self.course.students.add(self.student)
        self.attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            lecturer_latitude=Decimal('5.650000'),
            lecturer_longitude=Decimal('-0.187000'),
        )

    def test_str_representation(self):
        s = str(self.attendance)
        self.assertIn('Intro to CS', s)
        self.assertIn('Active: True', s)

    def test_is_open_when_active(self):
        self.assertTrue(self.attendance.is_open())

    def test_is_not_open_when_ended(self):
        self.attendance.ended_at = timezone.now() - timedelta(minutes=5)
        self.attendance.save()
        self.assertFalse(self.attendance.is_open())

    def test_is_session_valid_within_duration(self):
        self.assertTrue(self.attendance.is_session_valid)

    def test_is_session_invalid_after_duration(self):
        Attendance.objects.filter(pk=self.attendance.pk).update(
            created_at=timezone.now() - timedelta(hours=3)
        )
        self.attendance.refresh_from_db()
        self.assertFalse(self.attendance.is_session_valid)

    def test_is_session_invalid_when_not_active(self):
        self.attendance.is_active = False
        self.attendance.save()
        self.assertFalse(self.attendance.is_session_valid)

    def test_save_sets_course_active_when_attendance_active(self):
        self.course.is_active = False
        self.course.save()
        self.attendance.is_active = True
        self.attendance.save()
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_active)

    def test_save_deactivates_when_ended(self):
        self.attendance.ended_at = timezone.now()
        self.attendance.save()
        self.assertFalse(self.attendance.is_active)

    def test_is_within_radius_same_location(self):
        result = self.attendance.is_within_radius(
            Decimal('5.650000'), Decimal('-0.187000')
        )
        self.assertTrue(result)

    def test_is_not_within_radius_far_location(self):
        result = self.attendance.is_within_radius(
            Decimal('6.000000'), Decimal('1.000000')
        )
        self.assertFalse(result)

    def test_is_within_radius_no_lecturer_coords(self):
        self.attendance.lecturer_latitude = None
        self.attendance.lecturer_longitude = None
        result = self.attendance.is_within_radius(Decimal('5.650000'), Decimal('-0.187000'))
        self.assertTrue(result)

    def test_ordering(self):
        yesterday = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate() - timedelta(days=1),
        )
        records = list(Attendance.objects.all())
        self.assertEqual(records[0], self.attendance)
        self.assertEqual(records[1], yesterday)

    def test_mark_student_present(self):
        self.attendance.present_students.add(self.student)
        self.assertIn(self.student, self.attendance.present_students.all())

    def test_default_duration_hours(self):
        self.assertEqual(self.attendance.duration_hours, 2)


class AttendanceStudentModelTest(TestCase):
    """Tests for the AttendanceStudent through model"""

    def setUp(self):
        self.lec_user = User.objects.create_user(username='lec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.lec_user, staff_id='L001', name='Dr. Smith'
        )
        self.stu_user = User.objects.create_user(username='stu', password='pass1234')
        self.student = Student.objects.create(
            user=self.stu_user, student_id='ST001', name='Jane Doe'
        )
        self.course = Course.objects.create(
            name='Intro to CS', course_code='CS101', lecturer=self.lecturer
        )
        self.attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            lecturer_latitude=Decimal('5.650000'),
            lecturer_longitude=Decimal('-0.187000'),
        )
        self.att_student = AttendanceStudent.objects.create(
            attendance=self.attendance,
            student=self.student,
            latitude=Decimal('5.650010'),
            longitude=Decimal('-0.187010'),
        )

    def test_is_within_valid_perimeter_close(self):
        self.assertTrue(self.att_student.is_within_valid_perimeter(radius_meters=50))

    def test_is_not_within_valid_perimeter_far(self):
        self.att_student.latitude = Decimal('6.000000')
        self.att_student.longitude = Decimal('1.000000')
        self.assertFalse(self.att_student.is_within_valid_perimeter(radius_meters=50))

    def test_get_distance_from_lecturer(self):
        distance = self.att_student.get_distance_from_lecturer()
        self.assertIsNotNone(distance)
        self.assertGreaterEqual(distance, 0)

    def test_distance_none_when_no_student_coords(self):
        self.att_student.latitude = None
        self.att_student.longitude = None
        self.assertIsNone(self.att_student.get_distance_from_lecturer())

    def test_distance_none_when_no_lecturer_coords(self):
        self.attendance.lecturer_latitude = None
        self.attendance.lecturer_longitude = None
        self.attendance.save()
        self.assertIsNone(self.att_student.get_distance_from_lecturer())

    def test_unique_together_attendance_student(self):
        with self.assertRaises(Exception):
            AttendanceStudent.objects.create(
                attendance=self.attendance,
                student=self.student,
                latitude=Decimal('5.650010'),
                longitude=Decimal('-0.187010'),
            )


class AttendanceTokenModelTest(TestCase):
    """Tests for the AttendanceToken model"""

    def setUp(self):
        self.lec_user = User.objects.create_user(username='lec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.lec_user, staff_id='L001', name='Dr. Smith'
        )
        self.course = Course.objects.create(
            name='Intro to CS', course_code='CS101', lecturer=self.lecturer
        )

    def test_str_representation(self):
        token = AttendanceToken(course=self.course, token='ABC123')
        self.assertEqual(str(token), 'Intro to CS - ABC123')

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_save_sets_expiry_default(self):
        token = AttendanceToken.objects.create(
            course=self.course,
            token='TOK123',
        )
        self.assertIsNotNone(token.expires_at)
        diff = token.expires_at - token.generated_at
        self.assertAlmostEqual(diff.total_seconds(), 7200, delta=5)

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_save_generates_qr_code(self):
        token = AttendanceToken.objects.create(
            course=self.course,
            token='QR0001',
        )
        self.assertTrue(bool(token.qr_code))

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_expired_token_deactivated(self):
        token = AttendanceToken(
            course=self.course,
            token='EXP001',
            generated_at=timezone.now() - timedelta(hours=3),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        token.save()
        self.assertFalse(token.is_active)

    def test_generate_qr_code_returns_buffer(self):
        token = AttendanceToken(course=self.course, token='BUF001')
        buf = token.generate_qr_code()
        data = buf.read()
        self.assertTrue(data[:4] == b'\x89PNG')


# ==================== API View Tests ====================


from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token


class APIAuthTestCase(APITestCase):
    """Base test case for API tests with authentication setup"""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='apiadmin', email='apiadmin@test.com', password='pass1234'
        )
        self.lec_user = User.objects.create_user(
            username='apilec', email='apilec@test.com', password='pass1234'
        )
        self.stu_user = User.objects.create_user(
            username='apistu', email='apistu@test.com', password='pass1234'
        )
        self.lecturer = Lecturer.objects.create(
            user=self.lec_user, staff_id='AL01', name='API Lecturer'
        )
        self.student = Student.objects.create(
            user=self.stu_user, student_id='AS01', name='API Student'
        )
        self.course = Course.objects.create(
            name='API Course', course_code='API1', lecturer=self.lecturer
        )
        self.course.students.add(self.student)

        self.admin_token = Token.objects.create(user=self.admin_user)
        self.lec_token = Token.objects.create(user=self.lec_user)
        self.stu_token = Token.objects.create(user=self.stu_user)

    def auth_as(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')


class LecturerAPITest(APIAuthTestCase):
    """Tests for Lecturer API endpoints"""

    def test_list_lecturers_authenticated(self):
        self.auth_as(self.admin_token)
        response = self.client.get('/api/lecturers/')
        self.assertEqual(response.status_code, 200)

    def test_list_lecturers_unauthenticated(self):
        response = self.client.get('/api/lecturers/')
        self.assertEqual(response.status_code, 401)

    def test_retrieve_lecturer(self):
        self.auth_as(self.admin_token)
        response = self.client.get(f'/api/lecturers/{self.lecturer.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['staff_id'], 'AL01')

    def test_my_courses_for_lecturer(self):
        self.auth_as(self.lec_token)
        response = self.client.get('/api/lecturers/my-courses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['course_code'], 'API1')


class StudentAPITest(APIAuthTestCase):
    """Tests for Student API endpoints"""

    def test_list_students_as_lecturer(self):
        self.auth_as(self.lec_token)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_students_as_student(self):
        self.auth_as(self.stu_token)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['student_id'], 'AS01')


class CourseAPITest(APIAuthTestCase):
    """Tests for Course API endpoints"""

    def test_list_courses(self):
        self.auth_as(self.admin_token)
        response = self.client.get('/api/courses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_course(self):
        self.auth_as(self.admin_token)
        response = self.client.get(f'/api/courses/{self.course.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['course_code'], 'API1')


class AttendanceAPITest(APIAuthTestCase):
    """Tests for Attendance API endpoints"""

    def test_list_attendance(self):
        self.auth_as(self.admin_token)
        Attendance.objects.create(course=self.course, date=timezone.localdate())
        response = self.client.get('/api/attendances/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    @patch('attendance.tasks.schedule_attendance_expiration_reminder')
    @patch('attendance.tasks.send_attendance_started_notifications')
    def test_generate_attendance_token(self, mock_notif, mock_sched):
        self.auth_as(self.lec_token)
        response = self.client.post(
            f'/api/courses/{self.course.pk}/generate_attendance_token/',
            {'token': 'TK1234', 'latitude': '5.650000', 'longitude': '-0.187000'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AttendanceToken.objects.filter(token='TK1234').exists())
        self.assertTrue(
            Attendance.objects.filter(course=self.course, date=timezone.localdate()).exists()
        )

    def test_generate_attendance_token_missing_fields(self):
        self.auth_as(self.lec_token)
        response = self.client.post(
            f'/api/courses/{self.course.pk}/generate_attendance_token/',
            {'token': 'TK9999'},
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_take_attendance_valid(self):
        self.auth_as(self.stu_token)
        Attendance.objects.create(
            course=self.course, date=timezone.localdate(), is_active=True
        )
        AttendanceToken.objects.create(
            course=self.course, token='VALID1', is_active=True
        )
        response = self.client.post(
            '/api/courses/take_attendance/', {'token': 'VALID1'},
        )
        self.assertEqual(response.status_code, 200)

    def test_take_attendance_invalid_token(self):
        self.auth_as(self.stu_token)
        response = self.client.post(
            '/api/courses/take_attendance/', {'token': 'NOPE'},
        )
        self.assertEqual(response.status_code, 400)

    @patch('attendance.tasks.send_missed_attendance_notifications')
    def test_end_attendance(self, mock_notif):
        self.auth_as(self.lec_token)
        att = Attendance.objects.create(
            course=self.course, date=timezone.localdate(), is_active=True
        )
        response = self.client.post(
            '/api/attendances/end_attendance/', {'course_id': self.course.pk},
        )
        self.assertEqual(response.status_code, 200)
        att.refresh_from_db()
        self.assertFalse(att.is_active)

    def test_end_attendance_no_active_session(self):
        self.auth_as(self.lec_token)
        response = self.client.post(
            '/api/attendances/end_attendance/', {'course_id': self.course.pk},
        )
        self.assertEqual(response.status_code, 404)


class SubmitLocationAPITest(APIAuthTestCase):
    """Tests for the location-based attendance submission"""

    def setUp(self):
        super().setUp()
        self.attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            lecturer_latitude=Decimal('5.650000'),
            lecturer_longitude=Decimal('-0.187000'),
            is_active=True,
        )

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_submit_location_within_radius(self):
        self.auth_as(self.stu_token)
        AttendanceToken.objects.create(
            course=self.course, token='LOC123', is_active=True
        )
        response = self.client.post(
            '/api/api/submit-location/',
            {'latitude': '5.650010', 'longitude': '-0.187010', 'attendance_token': 'LOC123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AttendanceStudent.objects.filter(
                attendance=self.attendance, student=self.student
            ).exists()
        )

    @override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
    def test_submit_location_out_of_range(self):
        self.auth_as(self.stu_token)
        AttendanceToken.objects.create(
            course=self.course, token='LOC456', is_active=True
        )
        response = self.client.post(
            '/api/api/submit-location/',
            {'latitude': '6.500000', 'longitude': '1.500000', 'attendance_token': 'LOC456'},
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_location_invalid_token(self):
        self.auth_as(self.stu_token)
        response = self.client.post(
            '/api/api/submit-location/',
            {'latitude': '5.650010', 'longitude': '-0.187010', 'attendance_token': 'INVALID'},
        )
        self.assertEqual(response.status_code, 400)


class StudentLoginAPITest(TestCase):
    """Tests for student login endpoint"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='stulogin', password='pass1234'
        )
        self.student = Student.objects.create(
            user=self.user, student_id='SL01', name='Login Student'
        )

    def test_student_login_valid(self):
        response = self.client_api.post(
            '/api/api/login/student/',
            {'username': 'stulogin', 'password': 'pass1234', 'student_id': 'SL01'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_student_login_wrong_student_id(self):
        response = self.client_api.post(
            '/api/api/login/student/',
            {'username': 'stulogin', 'password': 'pass1234', 'student_id': 'WRONG'},
        )
        self.assertEqual(response.status_code, 400)

    def test_student_login_invalid_credentials(self):
        response = self.client_api.post(
            '/api/api/login/student/',
            {'username': 'stulogin', 'password': 'wrongpass', 'student_id': 'SL01'},
        )
        self.assertEqual(response.status_code, 400)


class StaffLoginAPITest(TestCase):
    """Tests for staff/lecturer login endpoint"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='leclogin', password='pass1234'
        )
        self.lecturer = Lecturer.objects.create(
            user=self.user, staff_id='LL01', name='Login Lecturer'
        )

    def test_staff_login_valid(self):
        response = self.client_api.post(
            '/api/api/login/staff/',
            {'username': 'leclogin', 'password': 'pass1234', 'staff_id': 'LL01'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_staff_login_wrong_staff_id(self):
        response = self.client_api.post(
            '/api/api/login/staff/',
            {'username': 'leclogin', 'password': 'pass1234', 'staff_id': 'WRONG'},
        )
        self.assertEqual(response.status_code, 400)


class LogoutAPITest(APIAuthTestCase):
    """Tests for API logout"""

    def test_logout_deletes_token(self):
        self.auth_as(self.admin_token)
        response = self.client.post('/api/api/logout/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(user=self.admin_user).exists())


# ==================== Serializer Tests ====================

from .serializers import (
    LecturerSerializer,
    StudentSerializer,
    CourseSerializer,
    AttendanceSerializer,
    SubmitLocationSerializer,
)


class LecturerSerializerTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='serlec', password='pass1234')
        self.lecturer = Lecturer.objects.create(
            user=self.user, staff_id='SL01', name='Serializer Lec',
            department='Engineering'
        )

    def test_serializer_contains_expected_fields(self):
        serializer = LecturerSerializer(self.lecturer)
        expected = {'id', 'user', 'staff_id', 'name', 'profile_picture',
                    'courses', 'department', 'phone_number', 'latitude', 'longitude'}
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_profile_picture_none_without_request(self):
        serializer = LecturerSerializer(self.lecturer)
        self.assertIsNone(serializer.data['profile_picture'])


class StudentSerializerTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='serstu', password='pass1234')
        self.student = Student.objects.create(
            user=self.user, student_id='SS01', name='Serializer Stu'
        )

    def test_serializer_contains_expected_fields(self):
        serializer = StudentSerializer(self.student)
        expected = {'id', 'user', 'student_id', 'name',
                    'profile_picture', 'programme_of_study', 'year', 'phone_number'}
        self.assertEqual(set(serializer.data.keys()), expected)


class SubmitLocationSerializerTest(TestCase):

    def test_valid_data(self):
        serializer = SubmitLocationSerializer(data={
            'latitude': 5.65,
            'longitude': -0.187,
            'attendance_token': 'ABC123',
        })
        self.assertTrue(serializer.is_valid())

    def test_missing_fields(self):
        serializer = SubmitLocationSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('latitude', serializer.errors)
        self.assertIn('longitude', serializer.errors)
        self.assertIn('attendance_token', serializer.errors)
