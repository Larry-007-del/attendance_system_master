from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Course

def course_ics_calendar(request, course_id):
    """Generates an ICS calendar file for a given course allowing easy imports."""
    course = get_object_or_404(Course, id=course_id)
    
    # Mocking standard weekly recurrences based on course creation or today
    now = timezone.now()
    # Snap to the upcoming Monday 9 AM as a mock standard starting layout
    days_ahead = 0 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    start_time = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=2)
    
    dtstamp = now.strftime('%Y%m%dT%H%M%SZ')
    dtstart = start_time.strftime('%Y%m%dT%H%M%SZ')
    dtend = end_time.strftime('%Y%m%dT%H%M%SZ')
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Exodus Attendance System//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:course_{course.id}@exodus.com
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR
SUMMARY:{course.name} ({course.course_code})
DESCRIPTION:Lecturer: {course.lecturer.name}
END:VEVENT
END:VCALENDAR"""

    response = HttpResponse(ics_content.replace('\n', '\r\n'), content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="course_{course.course_code}.ics"'
    return response
