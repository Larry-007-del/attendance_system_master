from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from . import views

app_name = 'frontend'

urlpatterns = [
    # Redirect root to dashboard
    path('', RedirectView.as_view(pattern_name='frontend:dashboard', permanent=False)),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url=reverse_lazy('frontend:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('frontend:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Lecturers
    path('lecturers/', views.lecturer_list, name='lecturer_list'),
    path('lecturers/create/', views.lecturer_create, name='lecturer_create'),
    path('lecturers/<int:pk>/', views.lecturer_detail, name='lecturer_detail'),
    path('lecturers/<int:pk>/edit/', views.lecturer_edit, name='lecturer_edit'),
    path('lecturers/<int:pk>/delete/', views.lecturer_delete, name='lecturer_delete'),
    path('lecturers/<int:pk>/two-factor-settings/', views.lecturer_two_factor_settings, name='lecturer_two_factor_settings'),
    
    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/upload/', views.upload_students, name='upload_students'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    
    # Courses
    path('courses/', views.course_list, name='course_list'),
    path('courses/my/', views.my_courses, name='my_courses'),
    path('courses/upload-enrollments/', views.upload_enrollments, name='upload_enrollments'),
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    
    # Attendance
    path('attendance/', views.attendance_index, name='attendance_index'),
    path('attendance/checkin/', views.checkin_view, name='checkin'),
    path('attendance/take/', views.attendance_take, name='attendance_take'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    path('attendance/mark/', views.attendance_mark, name='attendance_mark'),
    path('attendance/<int:pk>/', views.attendance_detail, name='attendance_detail'),
    path('attendance/<int:attendance_id>/export/', views.export_attendance_csv, name='export_attendance_csv'),
    path('attendance/<int:attendance_id>/mark-present/<int:student_id>/', views.manual_mark_present, name='manual_mark_present'),
    path('attendance/end/', views.end_attendance, name='end_attendance'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.change_password, name='change_password'),
    
    # Reports
    path('reports/', views.reports_index, name='reports_index'),
    path('reports/export/', views.reports_export, name='reports_export'),
    
    # API endpoints for HTMX
    path('api/search/students/', views.ajax_search_students, name='ajax_search_students'),
    path('api/search/lecturers/', views.ajax_search_lecturers, name='ajax_search_lecturers'),
    path('api/search/courses/', views.ajax_search_courses, name='ajax_search_courses'),
    path('api/dashboard/stats/', views.ajax_dashboard_stats, name='ajax_dashboard_stats'),
    path('api/task-status/<str:task_id>/', views.task_status, name='task_status'),
    
    # Two-Factor Authentication
    path('2fa/setup/', views.student_setup_2fa, name='student_setup_2fa'),
    path('2fa/webauthn/register/begin/', views.webauthn_register_begin, name='webauthn_register_begin'),
    path('2fa/webauthn/register/complete/', views.webauthn_register_complete, name='webauthn_register_complete'),
    path('2fa/webauthn/remove/', views.webauthn_remove, name='webauthn_remove'),
    path('2fa/webauthn/auth/begin/', views.webauthn_auth_begin, name='webauthn_auth_begin'),
    path('2fa/webauthn/auth/complete/', views.webauthn_auth_complete, name='webauthn_auth_complete'),
    path('2fa/otp/setup/', views.student_setup_otp, name='student_setup_otp'),
    path('2fa/otp/verify/', views.student_verify_otp, name='student_verify_otp'),
    path('2fa/otp/disable/', views.student_disable_otp, name='student_disable_otp'),
]
