from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'frontend'

urlpatterns = [
    # Redirect root to dashboard
    path('', RedirectView.as_view(pattern_name='frontend:dashboard', permanent=False)),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Lecturers
    path('lecturers/', views.lecturer_list, name='lecturer_list'),
    path('lecturers/create/', views.lecturer_create, name='lecturer_create'),
    path('lecturers/<int:pk>/', views.lecturer_detail, name='lecturer_detail'),
    path('lecturers/<int:pk>/edit/', views.lecturer_edit, name='lecturer_edit'),
    path('lecturers/<int:pk>/delete/', views.lecturer_delete, name='lecturer_delete'),
    
    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    
    # Courses
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    
    # Attendance
    path('attendance/', views.attendance_index, name='attendance_index'),
    path('attendance/take/', views.attendance_take, name='attendance_take'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    path('attendance/mark/', views.attendance_mark, name='attendance_mark'),
    path('attendance/<int:pk>/', views.attendance_detail, name='attendance_detail'),
    
    # Reports
    path('reports/', views.reports_index, name='reports_index'),
    path('reports/export/', views.reports_export, name='reports_export'),
    
    # API endpoints for HTMX
    path('api/search/students/', views.ajax_search_students, name='ajax_search_students'),
    path('api/search/lecturers/', views.ajax_search_lecturers, name='ajax_search_lecturers'),
    path('api/search/courses/', views.ajax_search_courses, name='ajax_search_courses'),
    path('api/dashboard/stats/', views.ajax_dashboard_stats, name='ajax_dashboard_stats'),
]
