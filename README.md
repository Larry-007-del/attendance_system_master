# Attendance System

A Django REST Framework-based attendance management system with geolocation-based tracking capabilities.

## Features

✅ **Authentication System**
- Token-based authentication for both students and lecturers
- Separate login endpoints for students and staff
- Secure session management

✅ **Attendance Management**
- Geolocation-based attendance tracking
- Attendance token generation and validation
- Time-based attendance sessions (default 4 hours)
- Attendance history tracking and reporting

✅ **Course Management**
- Course creation and management
- Student enrollment in courses
- Lecturer-course associations
- Active course status tracking

✅ **Location Tracking**
- Real-time geolocation capture
- Distance-based attendance verification
- Lecturer location updates

✅ **Reporting & Export**
- Excel export of attendance records
- Student attendance history
- Lecturer-specific attendance records
- Date-based filtering

✅ **API Documentation**
- Swagger UI integration
- ReDoc documentation
- Comprehensive API endpoints

## Technology Stack

- **Backend**: Django 5.0.7
- **API Framework**: Django REST Framework 3.15.2
- **Authentication**: Token Authentication
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Geolocation**: GeoPy 2.4.1
- **Documentation**: drf-yasg (Swagger/ReDoc)
- **Server**: Gunicorn
- **Deployment**: Render.com compatible

## Quick Start

### Prerequisites
- Python 3.12+
- pip
- Virtual environment

### Installation

```bash
# Clone repository
git clone <repository-url>
cd attendance_system-master

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

Access the application at: `http://localhost:8000`

## API Endpoints

### Authentication
```
POST   /api/login/student/      - Student login
POST   /api/login/staff/        - Staff/Lecturer login  
POST   /api/logout/             - User logout
GET    /api-token-auth/         - Token authentication
```

### Courses
```
GET    /api/courses/                           - List all courses
POST   /api/courses/                           - Create course
GET    /api/courses/{id}/                      - Course details
POST   /api/courses/{id}/generate_attendance_token/ - Generate attendance token
POST   /api/courses/take_attendance/           - Record attendance via token
```

### Attendance
```
GET    /api/attendances/                       - List attendance records
POST   /api/attendances/end_attendance/        - End attendance session
GET    /api/attendances/generate_excel/       - Export to Excel
POST   /api/submit-location/                   - Location-based check-in
GET    /api/student-attendance-history/       - Student history
GET    /api/lecturer-attendance-history/      - Lecturer history
```

### Users
```
GET    /api/lecturers/                         - List lecturers
GET    /api/students/                          - List students
GET    /api/studentenrolledcourses/            - Student's enrolled courses
GET    /api/lecturer-location/                 - Lecturer location
```

## Environment Variables

```env
# Required
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Optional
GDAL_LIBRARY_PATH=path-to-gdal-library
DATABASE_URL=postgresql://user:password@host/db
```

## Database Models

### Core Models
- **User**: Django's built-in user model
- **Lecturer**: Staff members teaching courses
- **Student**: Students enrolled in courses
- **Course**: Academic courses
- **CourseEnrollment**: Many-to-many relationship with enrollment tracking
- **Attendance**: Attendance records per course per date
- **AttendanceToken**: Time-limited tokens for attendance marking

## Documentation

- **API Docs (Swagger)**: `/swagger/`
- **API Docs (ReDoc)**: `/redoc/`
- **Admin Panel**: `/admin/`
- **Deployment Guide**: See `DEPLOYMENT_GUIDE.md`

## Deployment

### Deploy to Render

1. Push code to GitHub
2. Connect repository to Render
3. Configure environment variables
4. Deploy automatically on push

See `DEPLOYMENT_GUIDE.md` for detailed instructions.

## Project Structure

```
attendance_system-master/
├── attendance/              # Main Django app
│   ├── models.py           # Database models
│   ├── views.py            # API views
│   ├── serializers.py      # DRF serializers
│   ├── urls.py             # App URL routing
│   └── migrations/         # Database migrations
├── attendance_system/       # Project configuration
│   ├── settings.py         # Django settings
│   ├── urls.py             # Main URL routing
│   └── wsgi.py             # WSGI configuration
├── staticfiles/            # Collected static files
├── requirements.txt        # Python dependencies
├── Procfile               # Deployment configuration
├── render.yaml            # Render service config
└── manage.py              # Django management script
```

## Key Features Implementation

### Geolocation-Based Attendance
The system verifies student location against lecturer location within a configurable radius (default: 100 meters).

```python
# Check if student is within range
attendance.is_within_radius(student_lat, student_lon, radius_km=0.1)
```

### Attendance Tokens
Time-limited tokens (default 4 hours) generated by lecturers for attendance sessions.

### Excel Export
Attendance records can be exported to Excel with student details and attendance status.

## Security Features

- Token-based authentication
- CORS headers support
- HTTPS enforcement in production
- CSRF protection
- Secure cookie handling
- Input validation
- Custom authentication backends

## Error Handling

The API provides clear error responses with appropriate HTTP status codes:
- `200 OK`: Successful request
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `500 Server Error`: Internal error

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues, questions, or suggestions, please create an issue in the repository.

## Changelog

### Version 1.0.0 (Current)
- Initial release
- Core attendance system functionality
- Geolocation-based tracking
- Token authentication
- API documentation with Swagger/ReDoc
- Production-ready deployment configuration

---

**Last Updated**: January 2026
**Status**: ✅ Production Ready
