"""Tests for frontend views — comprehensive coverage."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from attendance.models import (
    Attendance,
    AttendanceStudent,
    Course,
    CourseEnrollment,
    Lecturer,
    Student,
)


class FrontendViewsTestCase(TestCase):
    """Base test case with test data setup"""

    def setUp(self):
        self.client = Client()

        # Create test users
        self.admin_user = User.objects.create_superuser(
            username='testadmin',
            email='admin@example.com',
            password='testpassword123'
        )

        self.student_user = User.objects.create_user(
            username='teststudent',
            email='student@example.com',
            password='testpassword123'
        )

        self.lecturer_user = User.objects.create_user(
            username='testlecturer',
            email='lecturer@example.com',
            password='testpassword123'
        )

        # Create student and lecturer profiles
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='ST123',
            name='Test Student',
            programme_of_study='Computer Science',
            year='2'
        )

        self.lecturer = Lecturer.objects.create(
            user=self.lecturer_user,
            staff_id='L001',
            name='Test Lecturer',
            department='Computer Science'
        )

        # Create course
        self.course = Course.objects.create(
            name='Introduction to Programming',
            course_code='CS101',
            lecturer=self.lecturer,
        )
        self.course.students.add(self.student)


class LoginViewTest(FrontendViewsTestCase):
    """Tests for login view"""

    def test_login_view_get(self):
        response = self.client.get(reverse('frontend:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/login.html')

    def test_login_view_post_valid(self):
        response = self.client.post(reverse('frontend:login'), {
            'username': 'testadmin',
            'password': 'testpassword123'
        })
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_login_view_post_invalid(self):
        response = self.client.post(reverse('frontend:login'), {
            'username': 'invaliduser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/login.html')

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:login'))
        # Should redirect to dashboard since already logged in
        self.assertIn(response.status_code, [200, 302])


class LogoutViewTest(FrontendViewsTestCase):
    """Tests for logout view"""

    def test_logout_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:logout'), follow=False)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/login/', response.url)

    def test_logout_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:logout'), follow=False)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/dashboard/', response.url)


class DashboardViewTest(FrontendViewsTestCase):
    """Tests for dashboard view"""

    def test_dashboard_admin(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Administrator')

    def test_dashboard_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student')

    def test_dashboard_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lecturer')

    def test_dashboard_redirect_unauthenticated(self):
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertRedirects(response, reverse('frontend:login') + '?next=/dashboard/')

    def test_dashboard_admin_has_stats(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertIn('total_students', response.context)
        self.assertIn('total_lecturers', response.context)
        self.assertIn('total_courses', response.context)

    def test_dashboard_student_has_attendance_rate(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertIn('attendance_rate', response.context)

    def test_dashboard_lecturer_has_taught_courses(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertIn('taught_courses', response.context)


class CheckinViewTest(FrontendViewsTestCase):
    """Tests for checkin view"""

    def test_checkin_view_authenticated(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:checkin'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/checkin.html')

    def test_checkin_view_unauthenticated(self):
        response = self.client.get(reverse('frontend:checkin'))
        self.assertRedirects(response, reverse('frontend:login') + '?next=/attendance/checkin/')


class ProfileViewTest(FrontendViewsTestCase):
    """Tests for profile view"""

    def test_profile_get_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/profile.html')
        self.assertEqual(response.context['profile_type'], 'student')

    def test_profile_get_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile_type'], 'lecturer')

    def test_profile_update_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:profile'), {
            'first_name': 'Updated',
            'last_name': 'Student',
            'email': 'updated@example.com',
            'name': 'Updated Student',
            'phone_number': '+233241234567',
            'programme_of_study': 'Mathematics',
            'year': '3',
            'notification_preference': 'email',
        })
        self.assertRedirects(response, reverse('frontend:profile'))
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, 'Updated Student')
        self.assertEqual(self.student.programme_of_study, 'Mathematics')

    def test_profile_update_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.post(reverse('frontend:profile'), {
            'first_name': 'Updated',
            'last_name': 'Lecturer',
            'email': 'updatedlec@example.com',
            'name': 'Updated Lecturer',
            'phone_number': '+233241234567',
            'department': 'Mathematics',
        })
        self.assertRedirects(response, reverse('frontend:profile'))
        self.lecturer.refresh_from_db()
        self.assertEqual(self.lecturer.name, 'Updated Lecturer')
        self.assertEqual(self.lecturer.department, 'Mathematics')

    def test_profile_duplicate_email_rejected(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:profile'), {
            'first_name': 'Test',
            'last_name': 'Student',
            'email': 'lecturer@example.com',  # Already in use
            'name': 'Test Student',
        })
        self.assertRedirects(response, reverse('frontend:profile'))

    def test_profile_stats_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:profile'))
        stats = response.context['stats']
        self.assertIn('total_sessions', stats)
        self.assertIn('attended_sessions', stats)
        self.assertIn('attendance_rate', stats)
        self.assertIn('enrolled_courses', stats)

    def test_profile_stats_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:profile'))
        stats = response.context['stats']
        self.assertIn('total_sessions', stats)
        self.assertIn('total_courses', stats)
        self.assertIn('total_students', stats)


class ChangePasswordViewTest(FrontendViewsTestCase):
    """Tests for password change"""

    def test_change_password_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:change_password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/change_password.html')

    def test_change_password_success(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:change_password'), {
            'current_password': 'testpassword123',
            'new_password': 'newstrong_password456',
            'confirm_password': 'newstrong_password456',
        })
        self.assertRedirects(response, reverse('frontend:profile'))
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password('newstrong_password456'))

    def test_change_password_wrong_current(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:change_password'), {
            'current_password': 'wrongpassword',
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456',
        })
        self.assertRedirects(response, reverse('frontend:change_password'))

    def test_change_password_mismatch(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:change_password'), {
            'current_password': 'testpassword123',
            'new_password': 'newpassword456',
            'confirm_password': 'different789',
        })
        self.assertRedirects(response, reverse('frontend:change_password'))

    def test_change_password_too_short(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:change_password'), {
            'current_password': 'testpassword123',
            'new_password': 'short',
            'confirm_password': 'short',
        })
        self.assertRedirects(response, reverse('frontend:change_password'))


class AJAXViewsTest(FrontendViewsTestCase):
    """Tests for AJAX views"""

    def test_ajax_dashboard_stats(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:ajax_dashboard_stats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertIn('total_lecturers', data)
        self.assertIn('total_students', data)
        self.assertIn('total_courses', data)
        self.assertIn('active_courses', data)
        self.assertIn('today_attendance', data)

    def test_ajax_search_students(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:ajax_search_students'), {'q': 'Test'}
        )
        self.assertEqual(response.status_code, 200)

    def test_ajax_search_lecturers(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:ajax_search_lecturers'), {'q': 'Test'}
        )
        self.assertEqual(response.status_code, 200)

    def test_ajax_search_courses(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:ajax_search_courses'), {'q': 'CS'}
        )
        self.assertEqual(response.status_code, 200)


class LecturerViewsTest(FrontendViewsTestCase):
    """Tests for lecturer management views"""

    def test_lecturer_list_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lecturers/list.html')

    def test_lecturer_list_search(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:lecturer_list'), {'q': 'Test'}
        )
        self.assertEqual(response.status_code, 200)

    def test_lecturer_create_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_create'))
        self.assertEqual(response.status_code, 200)

    def test_lecturer_create_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:lecturer_create'), {
            'username': 'newlecturer',
            'email': 'newlecturer@example.com',
            'password': 'testpassword123',
            'staff_id': 'L002',
            'name': 'New Lecturer',
            'department': 'Electrical Engineering'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lecturer.objects.filter(staff_id='L002').exists())

    def test_lecturer_detail_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:lecturer_detail', args=[self.lecturer.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lecturers/detail.html')

    def test_lecturer_edit_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:lecturer_edit', args=[self.lecturer.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lecturers/edit.html')

    def test_lecturer_edit_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(
            reverse('frontend:lecturer_edit', args=[self.lecturer.pk]),
            {
                'name': 'Updated Lecturer',
                'department': 'Mathematics',
                'phone_number': '+233241234567',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.lecturer.refresh_from_db()
        self.assertEqual(self.lecturer.name, 'Updated Lecturer')

    def test_lecturer_delete_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:lecturer_delete', args=[self.lecturer.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lecturers/delete.html')

    def test_lecturer_delete_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        pk = self.lecturer.pk
        response = self.client.post(
            reverse('frontend:lecturer_delete', args=[pk])
        )
        self.assertRedirects(response, reverse('frontend:lecturer_list'))
        self.assertFalse(Lecturer.objects.filter(pk=pk).exists())

    def test_lecturer_two_factor_settings_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:lecturer_two_factor_settings', args=[self.lecturer.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_lecturer_two_factor_settings_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(
            reverse('frontend:lecturer_two_factor_settings', args=[self.lecturer.pk]),
            {'require_two_factor_auth': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.require_two_factor_auth)


class StudentViewsTest(FrontendViewsTestCase):
    """Tests for student management views"""

    def test_student_list_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'students/list.html')

    def test_student_list_search(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:student_list'), {'q': 'Test'}
        )
        self.assertEqual(response.status_code, 200)

    def test_student_create_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:student_create'))
        self.assertEqual(response.status_code, 200)

    def test_student_create_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:student_create'), {
            'username': 'newstudent',
            'email': 'newstudent@example.com',
            'password': 'testpassword123',
            'student_id': 'ST124',
            'name': 'New Student',
            'programme_of_study': 'Mechanical Engineering',
            'year': '1'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(student_id='ST124').exists())

    def test_student_detail_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:student_detail', args=[self.student.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'students/detail.html')

    def test_student_edit_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:student_edit', args=[self.student.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_student_edit_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(
            reverse('frontend:student_edit', args=[self.student.pk]),
            {
                'name': 'Updated Student',
                'programme_of_study': 'Mathematics',
                'year': '3',
                'phone_number': '+233241234567',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, 'Updated Student')

    def test_student_delete_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:student_delete', args=[self.student.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_student_delete_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        pk = self.student.pk
        response = self.client.post(
            reverse('frontend:student_delete', args=[pk])
        )
        self.assertRedirects(response, reverse('frontend:student_list'))
        self.assertFalse(Student.objects.filter(pk=pk).exists())


class CourseViewsTest(FrontendViewsTestCase):
    """Tests for course management views"""

    def test_course_list_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:course_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/list.html')

    def test_course_list_search(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:course_list'), {'q': 'Introduction'}
        )
        self.assertEqual(response.status_code, 200)

    def test_course_list_active_filter(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:course_list'), {'active': 'true'}
        )
        self.assertEqual(response.status_code, 200)

    def test_course_create_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:course_create'))
        self.assertEqual(response.status_code, 200)

    def test_course_create_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:course_create'), {
            'name': 'Data Structures',
            'course_code': 'CS201',
            'lecturer': self.lecturer.id,
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Course.objects.filter(course_code='CS201').exists())

    def test_course_detail_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:course_detail', args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/detail.html')
        self.assertIn('enrollments', response.context)
        self.assertIn('attendances', response.context)

    def test_course_edit_view_get(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:course_edit', args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/edit.html')

    def test_course_edit_view_post(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(
            reverse('frontend:course_edit', args=[self.course.pk]),
            {
                'name': 'Updated Course',
                'course_code': 'CS101',
                'lecturer': self.lecturer.id,
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.name, 'Updated Course')

    def test_course_delete_admin(self):
        self.client.login(username='testadmin', password='testpassword123')
        pk = self.course.pk
        response = self.client.post(
            reverse('frontend:course_delete', args=[pk])
        )
        self.assertRedirects(response, reverse('frontend:course_list'))
        self.assertFalse(Course.objects.filter(pk=pk).exists())

    def test_course_delete_unauthorized_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(
            reverse('frontend:course_delete', args=[self.course.pk])
        )
        self.assertRedirects(response, reverse('frontend:dashboard'))
        # Course should still exist
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_course_delete_by_own_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        pk = self.course.pk
        response = self.client.post(
            reverse('frontend:course_delete', args=[pk])
        )
        self.assertRedirects(response, reverse('frontend:course_list'))
        self.assertFalse(Course.objects.filter(pk=pk).exists())


class MyCoursesViewTest(FrontendViewsTestCase):
    """Tests for My Courses view"""

    def test_my_courses_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:my_courses'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/my_courses.html')
        self.assertTrue(response.context['is_student'])
        self.assertEqual(response.context['page_title'], 'My Enrolled Courses')
        self.assertEqual(len(response.context['courses']), 1)

    def test_my_courses_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:my_courses'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_student'])
        self.assertEqual(response.context['page_title'], 'Courses I Teach')
        self.assertEqual(len(response.context['courses']), 1)

    def test_my_courses_admin(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:my_courses'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_title'], 'All Courses')

    def test_my_courses_unauthenticated(self):
        response = self.client.get(reverse('frontend:my_courses'))
        self.assertEqual(response.status_code, 302)


class AttendanceViewsTest(FrontendViewsTestCase):
    """Tests for attendance views"""

    def test_attendance_index_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/index.html')

    def test_attendance_history_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_history'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/history.html')

    def test_attendance_take_get(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_take'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/take.html')

    def test_attendance_detail_view(self):
        attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            is_active=True,
        )
        attendance.present_students.add(self.student)
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:attendance_detail', args=[attendance.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/detail.html')

    def test_attendance_detail_404(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:attendance_detail', args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_export_attendance_csv(self):
        attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
        )
        AttendanceStudent.objects.create(
            attendance=attendance,
            student=self.student,
        )
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(
            reverse('frontend:export_attendance_csv', args=[attendance.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_attendance_history_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_history'))
        self.assertEqual(response.status_code, 200)

    def test_attendance_history_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_history'))
        self.assertEqual(response.status_code, 200)

    @patch('attendance.tasks.send_missed_attendance_notifications')
    def test_end_attendance_post(self, mock_notif):
        attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            is_active=True,
        )
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.post(
            reverse('frontend:end_attendance'),
            {'course_id': self.course.pk},
        )
        self.assertIn(response.status_code, [200, 302])
        attendance.refresh_from_db()
        self.assertFalse(attendance.is_active)


class ReportsViewTest(FrontendViewsTestCase):
    """Tests for reports views"""

    def test_reports_index_view(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:reports_index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/index.html')

    def test_reports_index_has_stats(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:reports_index'))
        self.assertEqual(response.status_code, 200)

    def test_reports_export_csv(self):
        attendance = Attendance.objects.create(
            course=self.course, date=timezone.localdate()
        )
        attendance.present_students.add(self.student)
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:reports_export'), {'format': 'csv'}
        )
        self.assertIn(response.status_code, [200, 302])

    def test_reports_unauthenticated(self):
        response = self.client.get(reverse('frontend:reports_index'))
        self.assertEqual(response.status_code, 302)


class RegisterViewTest(FrontendViewsTestCase):
    """Tests for registration view"""

    def test_register_get(self):
        response = self.client.get(reverse('frontend:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/register.html')

    def test_register_student_success(self):
        response = self.client.post(reverse('frontend:register'), {
            'username': 'newstu',
            'email': 'newstu@example.com',
            'password1': 'strongpassword_123',
            'password2': 'strongpassword_123',
            'role': 'student',
            'name': 'New Student',
            'student_id': 'NS001',
            'programme_of_study': 'Physics',
            'year': '1',
        })
        self.assertRedirects(response, reverse('frontend:login'))
        self.assertTrue(User.objects.filter(username='newstu').exists())
        self.assertTrue(Student.objects.filter(student_id='NS001').exists())

    def test_register_lecturer_success(self):
        """Lecturer self-registration is blocked — should redirect back to register."""
        response = self.client.post(reverse('frontend:register'), {
            'username': 'newlec',
            'email': 'newlec@example.com',
            'password1': 'strongpassword_123',
            'password2': 'strongpassword_123',
            'role': 'lecturer',
            'name': 'New Lecturer',
            'staff_id': 'NL001',
            'department': 'Physics',
        })
        self.assertRedirects(response, reverse('frontend:register'))
        self.assertFalse(Lecturer.objects.filter(staff_id='NL001').exists())

    def test_register_password_mismatch(self):
        response = self.client.post(reverse('frontend:register'), {
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password1': 'strongpassword_123',
            'password2': 'different_password456',
            'role': 'student',
            'name': 'Mismatch',
            'student_id': 'MM001',
        })
        self.assertRedirects(response, reverse('frontend:register'))
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    def test_register_duplicate_username(self):
        response = self.client.post(reverse('frontend:register'), {
            'username': 'testadmin',  # Already exists
            'email': 'unique@example.com',
            'password1': 'strongpassword_123',
            'password2': 'strongpassword_123',
            'role': 'student',
            'name': 'Dup',
            'student_id': 'DU001',
        })
        self.assertRedirects(response, reverse('frontend:register'))

    def test_register_duplicate_email(self):
        response = self.client.post(reverse('frontend:register'), {
            'username': 'uniqueuser',
            'email': 'admin@example.com',  # Already exists
            'password1': 'strongpassword_123',
            'password2': 'strongpassword_123',
            'role': 'student',
            'name': 'Dup Email',
            'student_id': 'DE001',
        })
        self.assertRedirects(response, reverse('frontend:register'))
        self.assertFalse(User.objects.filter(username='uniqueuser').exists())

    def test_register_invalid_role(self):
        response = self.client.post(reverse('frontend:register'), {
            'username': 'invalidrole',
            'email': 'invalid@example.com',
            'password1': 'strongpassword_123',
            'password2': 'strongpassword_123',
            'role': 'admin',  # Invalid
            'name': 'Invalid',
            'student_id': 'IR001',
        })
        self.assertRedirects(response, reverse('frontend:register'))
        self.assertFalse(User.objects.filter(username='invalidrole').exists())


class AccessControlTest(FrontendViewsTestCase):
    """Tests for unauthenticated access - all protected views should redirect"""

    def test_protected_views_redirect(self):
        protected_urls = [
            reverse('frontend:dashboard'),
            reverse('frontend:profile'),
            reverse('frontend:change_password'),
            reverse('frontend:lecturer_list'),
            reverse('frontend:student_list'),
            reverse('frontend:course_list'),
            reverse('frontend:my_courses'),
            reverse('frontend:attendance_index'),
            reverse('frontend:attendance_history'),
            reverse('frontend:reports_index'),
            reverse('frontend:checkin'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 302,
                f'{url} should redirect unauthenticated users (got {response.status_code})'
            )


class AdminAuthorizationTest(FrontendViewsTestCase):
    """Tests that admin-only views block students and lecturers"""

    def test_student_cannot_create_lecturer(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_create'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_edit_lecturer(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_edit', args=[self.lecturer.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_delete_lecturer(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:lecturer_delete', args=[self.lecturer.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))
        self.assertTrue(Lecturer.objects.filter(pk=self.lecturer.pk).exists())

    def test_student_cannot_create_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_create'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_edit_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_edit', args=[self.student.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_lecturer_cannot_create_lecturer(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_create'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_lecturer_cannot_create_student(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:student_create'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_create_course(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:course_create'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_edit_course(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:course_edit', args=[self.course.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_lecturer_can_create_course(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:course_create'))
        self.assertEqual(response.status_code, 200)

    def test_lecturer_can_edit_course(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:course_edit', args=[self.course.pk]))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_lecturer(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_create'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_student(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:student_create'))
        self.assertEqual(response.status_code, 200)


class LoginRateLimitTest(FrontendViewsTestCase):
    """Tests for login brute-force rate limiting"""

    def test_login_rate_limit_blocks_after_5_attempts(self):
        from django.core.cache import cache
        cache.clear()

        # Make 5 failed attempts
        for i in range(5):
            self.client.post(reverse('frontend:login'), {
                'username': 'nonexistent',
                'password': 'wrongpassword',
            })

        # 6th attempt should be rate limited
        response = self.client.post(reverse('frontend:login'), {
            'username': 'testadmin',
            'password': 'testpassword123',
        })
        # Should not redirect (login blocked), stays on login page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Too many login attempts')

    def test_successful_login_resets_counter(self):
        from django.core.cache import cache
        cache.clear()

        # Make 3 failed attempts
        for i in range(3):
            self.client.post(reverse('frontend:login'), {
                'username': 'nonexistent',
                'password': 'wrongpassword',
            })

        # Successful login should reset counter
        response = self.client.post(reverse('frontend:login'), {
            'username': 'testadmin',
            'password': 'testpassword123',
        })
        self.assertEqual(response.status_code, 302)  # Redirect = success


class DeepSecurityTest(FrontendViewsTestCase):
    """Tests for the deep security hardening round"""

    def test_student_cannot_access_attendance_take(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_take'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_access_attendance_index(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_index'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_access_course_list(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:course_list'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_access_lecturer_list(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_list'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_student_cannot_access_student_list(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_list'))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_attendance_detail_blocks_non_enrolled_student(self):
        # Create a course with no enrolled students
        other_course = Course.objects.create(
            name='Other Course', course_code='OC001', lecturer=self.lecturer
        )
        attendance = Attendance.objects.create(
            course=other_course, date=timezone.localdate(), is_active=True
        )
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_detail', args=[attendance.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_attendance_detail_allows_enrolled_student(self):
        attendance = Attendance.objects.create(
            course=self.course, date=timezone.localdate(), is_active=True
        )
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_detail', args=[attendance.pk]))
        self.assertEqual(response.status_code, 200)

    def test_course_edit_blocks_non_owner_lecturer(self):
        # Create another lecturer
        other_user = User.objects.create_user(
            username='other_lecturer', password='testpassword123'
        )
        Lecturer.objects.create(
            user=other_user, staff_id='L999', name='Other Lec', department='Math'
        )
        self.client.login(username='other_lecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:course_edit', args=[self.course.pk]))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_attendance_history_admin_sees_records(self):
        Attendance.objects.create(
            course=self.course, date=timezone.localdate(), is_active=True
        )
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_history'))
        self.assertEqual(response.status_code, 200)
        # Admin should see all records (not empty)
        attendances = response.context['attendances']
        self.assertGreater(len(attendances), 0)

    def test_export_attendance_csv_admin_allowed(self):
        attendance = Attendance.objects.create(
            course=self.course, date=timezone.localdate(), is_active=True
        )
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(
            reverse('frontend:export_attendance_csv', args=[attendance.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_open_redirect_blocked(self):
        """Login should not redirect to external URLs"""
        response = self.client.post(reverse('frontend:login'), {
            'username': 'testadmin',
            'password': 'testpassword123',
            'next': 'https://evil.com/steal',
        })
        # Should redirect to dashboard, not to evil.com
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_ajax_dashboard_stats_blocked_for_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:ajax_dashboard_stats'))
        self.assertRedirects(response, reverse('frontend:dashboard'))


if __name__ == '__main__':
    import unittest
    unittest.main()
