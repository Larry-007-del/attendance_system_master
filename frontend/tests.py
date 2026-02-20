"""Tests for frontend views"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from attendance.models import Lecturer, Student, Course

class FrontendViewsTestCase(TestCase):
    """Base test case with test data setup"""
    
    def setUp(self):
        """Setup test data"""
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
            year=2
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
            lecturer=self.lecturer
        )
        self.course.students.add(self.student)

class LoginViewTest(FrontendViewsTestCase):
    """Tests for login view"""
    
    def test_login_view_get(self):
        """Test GET request to login page"""
        response = self.client.get(reverse('frontend:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/login.html')
    
    def test_login_view_post_valid(self):
        """Test valid login credentials"""
        response = self.client.post(reverse('frontend:login'), {
            'username': 'testadmin',
            'password': 'testpassword123'
        })
        self.assertRedirects(response, reverse('frontend:dashboard'))
    
    def test_login_view_post_invalid(self):
        """Test invalid login credentials"""
        response = self.client.post(reverse('frontend:login'), {
            'username': 'invaliduser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/login.html')

class LogoutViewTest(FrontendViewsTestCase):
    """Tests for logout view"""
    
    def test_logout_view_post(self):
        """Test logout functionality"""
        # Login first
        self.client.login(username='testadmin', password='testpassword123')
        
        # Test logout without following redirect
        response = self.client.post(reverse('frontend:logout'), follow=False)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/login/', response.url)
    
    def test_logout_view_get(self):
        """Test logout with GET request"""
        # Login first
        self.client.login(username='testadmin', password='testpassword123')
        
        # Test logout without following redirect
        response = self.client.get(reverse('frontend:logout'), follow=False)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/login/', response.url)

class DashboardViewTest(FrontendViewsTestCase):
    """Tests for dashboard view"""
    
    def test_dashboard_admin(self):
        """Test dashboard for admin user"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Administrator')
    
    def test_dashboard_student(self):
        """Test dashboard for student user"""
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Student')
    
    def test_dashboard_lecturer(self):
        """Test dashboard for lecturer user"""
        self.client.login(username='testlecturer', password='testpassword123')
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Lecturer')
    
    def test_dashboard_redirect_unauthenticated(self):
        """Test dashboard redirects unauthenticated users to login"""
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertRedirects(response, reverse('frontend:login') + '?next=/dashboard/')

class CheckinViewTest(FrontendViewsTestCase):
    """Tests for checkin view"""
    
    def test_checkin_view_authenticated(self):
        """Test checkin view is accessible to authenticated users"""
        self.client.login(username='teststudent', password='testpassword123')
        response = self.client.get(reverse('frontend:checkin'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/checkin.html')
    
    def test_checkin_view_unauthenticated(self):
        """Test checkin view redirects unauthenticated users"""
        response = self.client.get(reverse('frontend:checkin'))
        self.assertRedirects(response, reverse('frontend:login') + '?next=/attendance/checkin/')

class AJAXViewsTest(FrontendViewsTestCase):
    """Tests for AJAX views"""
    
    def test_ajax_dashboard_stats(self):
        """Test dashboard stats AJAX endpoint"""
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

class LecturerViewsTest(FrontendViewsTestCase):
    """Tests for lecturer management views"""
    
    def test_lecturer_list_view(self):
        """Test lecturer list view"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:lecturer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lecturers/list.html')
    
    def test_lecturer_create_view(self):
        """Test lecturer creation"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:lecturer_create'), {
            'user-username': 'newlecturer',
            'user-email': 'newlecturer@example.com',
            'user-password1': 'testpassword123',
            'user-password2': 'testpassword123',
            'staff_id': 'L002',
            'name': 'New Lecturer',
            'department': 'Electrical Engineering'
        })
        self.assertEqual(response.status_code, 302)

class StudentViewsTest(FrontendViewsTestCase):
    """Tests for student management views"""
    
    def test_student_list_view(self):
        """Test student list view"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'students/list.html')
    
    def test_student_create_view(self):
        """Test student creation"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:student_create'), {
            'user-username': 'newstudent',
            'user-email': 'newstudent@example.com',
            'user-password1': 'testpassword123',
            'user-password2': 'testpassword123',
            'student_id': 'ST124',
            'name': 'New Student',
            'programme_of_study': 'Mechanical Engineering',
            'year': 1
        })
        self.assertEqual(response.status_code, 302)

class CourseViewsTest(FrontendViewsTestCase):
    """Tests for course management views"""
    
    def test_course_list_view(self):
        """Test course list view"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:course_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/list.html')
    
    def test_course_create_view(self):
        """Test course creation"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.post(reverse('frontend:course_create'), {
            'name': 'Data Structures',
            'course_code': 'CS201',
            'lecturer': self.lecturer.id,
            'is_active': True
        })
        self.assertEqual(response.status_code, 302)

class AttendanceViewsTest(FrontendViewsTestCase):
    """Tests for attendance views"""
    
    def test_attendance_index_view(self):
        """Test attendance index view"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/index.html')
    
    def test_attendance_history_view(self):
        """Test attendance history view"""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('frontend:attendance_history'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'attendance/history.html')

if __name__ == '__main__':
    import unittest
    unittest.main()
