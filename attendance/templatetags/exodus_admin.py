from django import template
from django.utils import timezone

register = template.Library()


@register.inclusion_tag('admin/exodus_stats.html')
def exodus_dashboard_stats():
    """Render attendance system stats cards on the admin dashboard."""
    from attendance.models import Student, Lecturer, Course, Attendance, AttendanceStudent

    today = timezone.now().date()
    return {
        'total_students': Student.objects.count(),
        'total_lecturers': Lecturer.objects.count(),
        'active_courses': Course.objects.filter(is_active=True).count(),
        'total_checkins': AttendanceStudent.objects.count(),
        'active_sessions': Attendance.objects.filter(is_active=True).count(),
        'today_sessions': Attendance.objects.filter(date=today).count(),
    }
