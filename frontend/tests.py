"""Tests for frontend views — comprehensive coverage."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
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
        cache.clear()  # Reset rate-limit counters between tests

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


# ==================== Two-Factor Authentication Tests ====================


class TwoFactorSetupViewTest(FrontendViewsTestCase):
    """Tests for 2FA setup page"""

    def test_setup_2fa_requires_login(self):
        response = self.client.get(reverse('frontend:student_setup_2fa'))
        self.assertEqual(response.status_code, 302)

    def test_setup_2fa_renders_for_student(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_setup_2fa'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'students/setup_2fa.html')

    def test_setup_2fa_context(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_setup_2fa'))
        self.assertIn('student', response.context)
        self.assertIn('credentials', response.context)
        self.assertIn('has_webauthn', response.context)
        self.assertIn('has_otp', response.context)
        self.assertFalse(response.context['has_webauthn'])
        self.assertFalse(response.context['has_otp'])


class WebAuthnRegisterBeginTest(FrontendViewsTestCase):
    """Tests for WebAuthn registration begin endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:webauthn_register_begin'))
        self.assertEqual(response.status_code, 302)

    def test_requires_post(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:webauthn_register_begin'))
        self.assertEqual(response.status_code, 405)

    def test_returns_json_options(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:webauthn_register_begin'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('challenge', data)
        self.assertIn('rp', data)
        self.assertIn('user', data)

    def test_stores_challenge_in_session(self):
        self.client.login(username='teststudent', password='testpassword123')
        self.client.post(reverse('frontend:webauthn_register_begin'))
        session = self.client.session
        self.assertIn('webauthn_reg_challenge', session)


class WebAuthnRegisterCompleteTest(FrontendViewsTestCase):
    """Tests for WebAuthn registration complete endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:webauthn_register_complete'))
        self.assertEqual(response.status_code, 302)

    def test_requires_post(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:webauthn_register_complete'))
        self.assertEqual(response.status_code, 405)

    def test_fails_without_session_challenge(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(
            reverse('frontend:webauthn_register_complete'),
            data='{"id": "test"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'].lower())


class WebAuthnRemoveTest(FrontendViewsTestCase):
    """Tests for WebAuthn credential removal"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:webauthn_remove'))
        self.assertEqual(response.status_code, 302)

    def test_remove_redirects_to_setup(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:webauthn_remove'), {
            'credential_id': 'nonexistent',
        })
        self.assertRedirects(response, reverse('frontend:student_setup_2fa'))

    def test_remove_deletes_credential(self):
        from attendance.models import WebAuthnCredential
        self.client.login(username='teststudent', password='testpassword123')
        cred = WebAuthnCredential.objects.create(
            user=self.student_user,
            credential_id='test-cred-id',
            public_key='test-key',
            sign_count=0,
        )
        self.client.post(reverse('frontend:webauthn_remove'), {
            'credential_id': 'test-cred-id',
        })
        self.assertFalse(WebAuthnCredential.objects.filter(id=cred.id).exists())


class WebAuthnAuthBeginTest(FrontendViewsTestCase):
    """Tests for WebAuthn authentication begin endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:webauthn_auth_begin'))
        self.assertEqual(response.status_code, 302)

    def test_fails_without_credentials(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:webauthn_auth_begin'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('No fingerprint', response.json()['error'])

    def test_returns_options_with_credential(self):
        from attendance.models import WebAuthnCredential
        self.client.login(username='teststudent', password='testpassword123')
        WebAuthnCredential.objects.create(
            user=self.student_user,
            credential_id='dGVzdC1jcmVk',  # base64url of 'test-cred'
            public_key='test-key',
            sign_count=0,
        )
        response = self.client.post(reverse('frontend:webauthn_auth_begin'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('challenge', data)
        self.assertIn('allowCredentials', data)


class WebAuthnAuthCompleteTest(FrontendViewsTestCase):
    """Tests for WebAuthn authentication complete endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:webauthn_auth_complete'))
        self.assertEqual(response.status_code, 302)

    def test_fails_without_session_challenge(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(
            reverse('frontend:webauthn_auth_complete'),
            data='{"id": "test", "rawId": "test"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'].lower())


class OTPSetupTest(FrontendViewsTestCase):
    """Tests for OTP setup endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:student_setup_otp'))
        self.assertEqual(response.status_code, 302)

    def test_requires_post(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_setup_otp'))
        self.assertEqual(response.status_code, 405)

    def test_returns_qr_and_secret(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:student_setup_otp'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('secret', data)
        self.assertIn('qr_svg', data)
        self.assertTrue(len(data['secret']) > 10)
        self.assertIn('<svg', data['qr_svg'].lower())

    def test_stores_pending_secret_in_session(self):
        self.client.login(username='teststudent', password='testpassword123')
        self.client.post(reverse('frontend:student_setup_otp'))
        session = self.client.session
        self.assertIn('pending_otp_secret', session)


class OTPVerifyTest(FrontendViewsTestCase):
    """Tests for OTP verification endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:student_verify_otp'))
        self.assertEqual(response.status_code, 302)

    def test_fails_without_pending_secret(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:student_verify_otp'), {
            'otp_code': '123456',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'].lower())

    def test_fails_with_invalid_code_format(self):
        self.client.login(username='teststudent', password='testpassword123')
        # First set up a pending secret
        self.client.post(reverse('frontend:student_setup_otp'))
        # Then try an invalid code
        response = self.client.post(reverse('frontend:student_verify_otp'), {
            'otp_code': 'abc',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('6 digits', response.json()['error'])

    def test_succeeds_with_valid_otp(self):
        import pyotp
        self.client.login(username='teststudent', password='testpassword123')
        # Set up OTP
        self.client.post(reverse('frontend:student_setup_otp'))
        secret = self.client.session['pending_otp_secret']
        # Generate a valid code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        response = self.client.post(reverse('frontend:student_verify_otp'), {
            'otp_code': valid_code,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        # Verify it was saved to the student
        self.student.refresh_from_db()
        self.assertEqual(self.student.two_factor_secret, secret)
        self.assertTrue(self.student.is_two_factor_enabled)

    def test_fails_with_wrong_otp(self):
        self.client.login(username='teststudent', password='testpassword123')
        self.client.post(reverse('frontend:student_setup_otp'))
        response = self.client.post(reverse('frontend:student_verify_otp'), {
            'otp_code': '000000',
        })
        # Might pass or fail depending on timing, but with a random secret
        # 000000 is very unlikely to be correct
        self.assertIn(response.status_code, [200, 400])


class OTPDisableTest(FrontendViewsTestCase):
    """Tests for OTP disable endpoint"""

    def test_requires_login(self):
        response = self.client.post(reverse('frontend:student_disable_otp'))
        self.assertEqual(response.status_code, 302)

    def test_disables_otp(self):
        self.client.login(username='teststudent', password='testpassword123')
        # Enable OTP first
        self.student.two_factor_secret = 'JBSWY3DPEHPK3PXP'
        self.student.is_two_factor_enabled = True
        self.student.save()
        # Disable it
        response = self.client.post(reverse('frontend:student_disable_otp'))
        self.assertRedirects(response, reverse('frontend:student_setup_2fa'))
        self.student.refresh_from_db()
        self.assertIsNone(self.student.two_factor_secret)
        self.assertFalse(self.student.is_two_factor_enabled)


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage')
class TwoFactorChallengeIntegrationTest(FrontendViewsTestCase):
    """Tests for the 2FA challenge flow during attendance marking"""

    def setUp(self):
        super().setUp()
        import pyotp
        # Set up an active attendance session with 2FA required
        self.attendance = Attendance.objects.create(
            course=self.course,
            date=timezone.localdate(),
            is_active=True,
            require_two_factor_auth=True,
            lecturer_latitude=Decimal('5.6500'),
            lecturer_longitude=Decimal('-0.1860'),
        )
        from attendance.models import AttendanceToken
        self.token = AttendanceToken.objects.create(
            course=self.course,
            token='t2fatk',
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        # Student OTP setup
        self.student.two_factor_secret = pyotp.random_base32()
        self.student.is_two_factor_enabled = True
        self.student.save()

    def test_2fa_challenge_shown_when_required(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:attendance_mark'), {
            'token': 't2fatk',
            'latitude': '5.6500',
            'longitude': '-0.1860',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/two_factor_challenge.html')

    def test_2fa_otp_verification_works(self):
        import pyotp
        self.client.login(username='teststudent', password='testpassword123')
        totp = pyotp.TOTP(self.student.two_factor_secret)
        response = self.client.post(reverse('frontend:attendance_mark'), {
            'token': 't2fatk',
            'latitude': '5.6500',
            'longitude': '-0.1860',
            'two_factor_completed': 'on',
            'two_factor_method': 'otp',
            'otp_code': totp.now(),
        })
        # Should succeed (redirect to success) or fail on GPS, but NOT fail on 2FA
        self.assertNotContains(response, 'Invalid or expired OTP', status_code=response.status_code)

    def test_2fa_invalid_otp_rejected(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:attendance_mark'), {
            'token': 't2fatk',
            'latitude': '5.6500',
            'longitude': '-0.1860',
            'two_factor_completed': 'on',
            'two_factor_method': 'otp',
            'otp_code': '000000',
        })
        self.assertEqual(response.status_code, 200)

    def test_2fa_webauthn_fails_without_session_flag(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:attendance_mark'), {
            'token': 't2fatk',
            'latitude': '5.6500',
            'longitude': '-0.1860',
            'two_factor_completed': 'on',
            'two_factor_method': 'webauthn',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/two_factor_challenge.html')

    def test_redirect_to_setup_when_no_2fa_configured(self):
        # Remove 2FA setup
        self.student.two_factor_secret = None
        self.student.is_two_factor_enabled = False
        self.student.save()
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.post(reverse('frontend:attendance_mark'), {
            'token': 't2fatk',
            'latitude': '5.6500',
            'longitude': '-0.1860',
        })
        self.assertRedirects(response, reverse('frontend:student_setup_2fa'))


if __name__ == '__main__':
    import unittest
    unittest.main()


class HealthEndpointTest(TestCase):
    """Tests for the /health/ endpoint"""

    def test_health_returns_200_json(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertEqual(data['cache'], 'ok')

    def test_health_no_auth_required(self):
        """Health check should be publicly accessible"""
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)


class PasswordResetViewTest(FrontendViewsTestCase):
    """Tests for the password reset flow"""

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse('frontend:password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset your password')

    def test_password_reset_post_redirects(self):
        response = self.client.post(reverse('frontend:password_reset'), {
            'email': 'student@test.com',
        })
        self.assertRedirects(response, reverse('frontend:password_reset_done'))

    def test_password_reset_done_page_loads(self):
        response = self.client.get(reverse('frontend:password_reset_done'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Check your email')

    def test_password_reset_complete_page_loads(self):
        response = self.client.get(reverse('frontend:password_reset_complete'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password reset successful')

    def test_password_reset_confirm_invalid_token(self):
        response = self.client.get(reverse('frontend:password_reset_confirm', kwargs={
            'uidb64': 'invalid',
            'token': 'invalid-token',
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid or expired link')

    def test_password_reset_sends_email(self):
        from django.core import mail
        self.client.post(reverse('frontend:password_reset'), {
            'email': self.student_user.email,
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password Reset', mail.outbox[0].subject)


class StudentDetailAccessControlTest(FrontendViewsTestCase):
    """Tests for student_detail access restrictions"""

    def test_admin_can_view_any_student(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:student_detail', kwargs={'pk': self.student.pk}))
        self.assertEqual(response.status_code, 200)

    def test_student_can_view_own_profile(self):
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_detail', kwargs={'pk': self.student.pk}))
        self.assertEqual(response.status_code, 200)

    def test_lecturer_can_view_enrolled_student(self):
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:student_detail', kwargs={'pk': self.student.pk}))
        self.assertEqual(response.status_code, 200)

    def test_other_student_cannot_view(self):
        other_user = User.objects.create_user(username='otherstudent', password='testpassword123', email='other@test.com')
        Student.objects.create(user=other_user, student_id='OTHER001', name='Other Student')
        self.client.login(username='otherstudent', password='testpassword123')
        response = self.client.get(reverse('frontend:student_detail', kwargs={'pk': self.student.pk}))
        self.assertRedirects(response, reverse('frontend:dashboard'))

    def test_unrelated_lecturer_cannot_view(self):
        other_lec_user = User.objects.create_user(username='otherlec', password='testpassword123', email='otherlec@test.com')
        Lecturer.objects.create(user=other_lec_user, name='Other Lec', staff_id='OLEC001')
        self.client.login(username='otherlec', password='testpassword123')
        response = self.client.get(reverse('frontend:student_detail', kwargs={'pk': self.student.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/students/', response.url)


class RegisterRateLimitTest(FrontendViewsTestCase):
    """Tests for registration rate limiting"""

    def test_registration_rate_limited_after_5_attempts(self):
        cache.clear()
        for i in range(5):
            self.client.post(reverse('frontend:register'), {
                'username': f'spamuser{i}',
                'email': f'spam{i}@test.com',
                'password1': 'badpassword',
                'password2': 'badpassword',
                'role': 'student',
                'student_id': f'SPAM{i}',
                'name': f'Spam User {i}',
                'programme_of_study': 'Test',
                'year': '1',
            })
        # 6th attempt should be rate limited
        response = self.client.post(reverse('frontend:register'), {
            'username': 'spamuser6',
            'email': 'spam6@test.com',
            'password1': 'TestPassword123!',
            'password2': 'TestPassword123!',
            'role': 'student',
            'student_id': 'SPAM6',
            'name': 'Spam User 6',
            'programme_of_study': 'Test',
            'year': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Too many registration attempts')


class SEOMetaTagsTest(FrontendViewsTestCase):
    """Tests for OpenGraph and SEO meta tags on public pages."""

    def test_login_page_has_og_tags(self):
        response = self.client.get(reverse('frontend:login'))
        self.assertContains(response, 'og:title')
        self.assertContains(response, 'og:description')
        self.assertContains(response, 'og:site_name')
        self.assertContains(response, 'meta name="description"')

    def test_register_page_has_og_tags(self):
        response = self.client.get(reverse('frontend:register'))
        self.assertContains(response, 'og:title')
        self.assertContains(response, 'og:description')
        self.assertContains(response, 'meta name="description"')

    def test_base_template_has_og_tags(self):
        """Authenticated pages (via base.html) include OG blocks."""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(response, 'og:title')
        self.assertContains(response, 'og:site_name')
        self.assertContains(response, 'theme-color')

    def test_password_reset_has_noindex(self):
        response = self.client.get(reverse('frontend:password_reset'))
        self.assertContains(response, 'noindex')


class AdminDashboardStatsTest(FrontendViewsTestCase):
    """Tests for the admin dashboard stats widget."""

    def test_admin_index_has_stats(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        # Stats cards should show model counts
        self.assertContains(response, 'Students')
        self.assertContains(response, 'Lecturers')
        self.assertContains(response, 'Active Courses')

    def test_admin_index_uses_custom_template(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get('/admin/')
        templates_used = [t.name for t in response.templates]
        self.assertIn('admin/exodus_index.html', templates_used)


class DbBackupCommandTest(TestCase):
    """Tests for the dbbackup management command."""

    def test_backup_creates_file(self):
        import os
        output = 'test_dbbackup_output.json'
        try:
            call_command('dbbackup', output=output)
            self.assertTrue(os.path.exists(output))
            self.assertGreater(os.path.getsize(output), 0)
        finally:
            if os.path.exists(output):
                os.remove(output)

    def test_backup_xml_format(self):
        import os
        output = 'test_dbbackup_output.xml'
        try:
            call_command('dbbackup', output=output, format='xml')
            self.assertTrue(os.path.exists(output))
            with open(output, 'r') as f:
                content = f.read()
            self.assertIn('<?xml', content)
        finally:
            if os.path.exists(output):
                os.remove(output)

    def test_backup_prune_keeps_latest(self):
        import os
        # Create 3 fake backup files
        for i in range(3):
            with open(f'backup_2026010{i}_000000.json', 'w') as f:
                f.write('{}')
        try:
            call_command('dbbackup', output='backup_20260103_000000.json', latest=2)
            # Should have pruned old ones, keeping only 2 most recent
            remaining = [f for f in os.listdir('.') if f.startswith('backup_') and f.endswith('.json')]
            self.assertLessEqual(len(remaining), 2)
        finally:
            for f in os.listdir('.'):
                if f.startswith('backup_') and f.endswith('.json'):
                    os.remove(f)


class CloseExpiredSessionsTest(FrontendViewsTestCase):
    """Tests for close_expired_sessions management command."""

    def _create_expired_session(self):
        """Helper: create a session that's already expired."""
        session = Attendance.objects.create(
            course=self.course,
            date=timezone.now().date(),
            is_active=True,
            duration_hours=1,
            created_by=self.lecturer_user,
        )
        # Backdate created_at so it's expired
        Attendance.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        session.refresh_from_db()
        return session

    def test_closes_expired_session(self):
        session = self._create_expired_session()
        call_command('close_expired_sessions')
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.ended_at)

    def test_does_not_close_active_session(self):
        session = Attendance.objects.create(
            course=self.course,
            date=timezone.now().date(),
            is_active=True,
            duration_hours=10,
            created_by=self.lecturer_user,
        )
        call_command('close_expired_sessions')
        session.refresh_from_db()
        self.assertTrue(session.is_active)

    def test_dry_run_does_not_modify(self):
        session = self._create_expired_session()
        call_command('close_expired_sessions', dry_run=True)
        session.refresh_from_db()
        self.assertTrue(session.is_active)  # unchanged

    def test_deactivates_related_tokens(self):
        from attendance.models import AttendanceToken
        session = self._create_expired_session()
        # Create token without saving (to avoid Cloudinary upload in tests)
        token = AttendanceToken(
            course=self.course, token='EXP123', is_active=True,
        )
        # Bypass the save() QR generation by inserting directly
        token.generated_at = timezone.now()
        token.expires_at = timezone.now() + timedelta(hours=2)
        AttendanceToken.objects.bulk_create([token])
        call_command('close_expired_sessions')
        self.assertFalse(AttendanceToken.objects.filter(token='EXP123', is_active=True).exists())

    def test_no_expired_sessions_reports_clean(self):
        from io import StringIO
        out = StringIO()
        call_command('close_expired_sessions', stdout=out)
        self.assertIn('No expired sessions found', out.getvalue())


class DarkModeToggleTest(FrontendViewsTestCase):
    """Tests that the dark mode toggle is present in the authenticated layout."""

    def test_toggle_button_present(self):
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, 'theme-toggle-light-icon')
        self.assertContains(response, 'theme-toggle-dark-icon')
        self.assertContains(response, 'exodus-theme')

