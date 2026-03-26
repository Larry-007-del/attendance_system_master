from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from . import webauthn_views
from . import calendar_views

router = DefaultRouter()
router.register(r'lecturers', views.LecturerViewSet, basename='lecturer')
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'attendances', views.AttendanceViewSet, basename='attendance')
router.register(r'attendance-tokens', views.AttendanceTokenViewSet, basename='attendance-token')

urlpatterns = [
    path('', include(router.urls)),
    path('studentenrolledcourses/', views.StudentEnrolledCoursesView.as_view(), name='student_enrolled_courses'),
    path('login/student/', views.StudentLoginView.as_view(), name='student_login'),
    path('login/staff/', views.StaffLoginView.as_view(), name='staff_login'),
    path('logout/', views.LogoutView.as_view(), name='api_logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('submit-location/', views.SubmitLocationView.as_view(), name='submit_location'),
    path('student-attendance-history/', views.StudentAttendanceHistoryView.as_view(), name='student_attendance_history'),
    path('lecturer-attendance-history/', views.LecturerAttendanceHistoryView.as_view(), name='lecturer_attendance_history'),
    path('lecturer-location/', views.LecturerLocationView.as_view(), name='lecturer_location'),
    
    # WebAuthn Fingerprint endpoints
    path('webauthn/register/begin/', webauthn_views.register_begin, name='webauthn_register_begin'),
    path('webauthn/register/complete/', webauthn_views.register_complete, name='webauthn_register_complete'),
    path('webauthn/authenticate/begin/', webauthn_views.authenticate_begin, name='webauthn_authenticate_begin'),
    path('webauthn/authenticate/complete/', webauthn_views.authenticate_complete, name='webauthn_authenticate_complete'),
    
    # Calendar Export
    path('courses/<int:course_id>/calendar.ics', calendar_views.course_ics_calendar, name='course_calendar'),
]
