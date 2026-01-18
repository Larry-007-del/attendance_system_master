# Attendance System - Deployment Guide

## Overview
This is a Django REST Framework-based attendance management system with location-based check-in capabilities.

## Project Structure
- **attendance_system/**: Django project configuration
- **attendance/**: Main application with models, views, and serializers
- **staticfiles/**: Static files (CSS, JS, images)
- **requirements.txt**: Python dependencies
- **Procfile**: Heroku/Render deployment configuration
- **render.yaml**: Render service configuration
- **runtime.txt**: Python version specification

## Features
- Token-based authentication for students and lecturers
- Geolocation-based attendance tracking
- Course enrollment management
- Attendance history and reporting
- Excel export functionality
- REST API with Swagger/ReDoc documentation

## Local Development Setup

### Prerequisites
- Python 3.12+
- pip
- Virtual environment

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd attendance_system-master
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

The application will be available at `http://localhost:8000`

## API Documentation
- Swagger UI: `http://localhost:8000/swagger/`
- ReDoc: `http://localhost:8000/redoc/`

## Deployment to Render

### Prerequisites
- Render account (https://render.com)
- GitHub repository with the code

### Steps

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Deploy to Render"
   git push origin main
   ```

2. **Connect to Render**
   - Log in to Render dashboard
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository with the attendance system

3. **Configure Build and Start Commands**
   - Build Command: `pip install -r requirements.txt && bash build.sh`
   - Start Command: `gunicorn attendance_system.wsgi:application --bind 0.0.0.0:$PORT`

4. **Set Environment Variables in Render**
   - `DJANGO_SECRET_KEY`: Generate a strong secret key
   - `DJANGO_DEBUG`: Set to `False`
   - `DJANGO_ALLOWED_HOSTS`: Your Render domain (e.g., `attendance-system-xxxx.onrender.com`)

5. **Deploy**
   - Render will automatically deploy when you push to the main branch

### Monitoring
- Check deployment logs in Render dashboard
- Monitor application health and performance metrics

## Environment Variables

Required variables for production:
```
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.onrender.com
```

Optional variables:
```
GDAL_LIBRARY_PATH=path-to-gdal-library (for Windows GIS features)
DATABASE_URL=postgresql://user:password@host/db (for PostgreSQL)
```

## Database

### Local Development
Uses SQLite by default (`db.sqlite3`)

### Production
- SQLite for free tier Render deployments
- PostgreSQL recommended for production (configure via `DATABASE_URL`)

## Security Checklist

- [x] DEBUG is set to False in production
- [x] SECRET_KEY is not hardcoded
- [x] ALLOWED_HOSTS is properly configured
- [x] CSRF protection enabled
- [x] HTTPS redirect enabled for production
- [x] CORS headers properly configured
- [x] Token-based authentication used for API

## Troubleshooting

### Migrations not applied
```bash
python manage.py migrate
```

### Static files not loading
```bash
python manage.py collectstatic --noinput
```

### Database issues
- For SQLite: Delete `db.sqlite3` and run migrations again
- For PostgreSQL: Check DATABASE_URL environment variable

### Port already in use
```bash
python manage.py runserver 0.0.0.0:8001
```

## API Endpoints

### Authentication
- `POST /api/login/student/` - Student login
- `POST /api/login/staff/` - Staff/Lecturer login
- `POST /api/logout/` - Logout

### Attendance
- `POST /api/courses/{id}/generate_attendance_token/` - Generate attendance token
- `POST /api/courses/take_attendance/` - Record attendance
- `POST /api/submit-location/` - Location-based attendance
- `POST /api/attendances/end_attendance/` - End attendance session
- `GET /api/attendances/generate_excel/` - Export attendance to Excel

### Data Retrieval
- `GET /api/lecturers/` - List lecturers
- `GET /api/students/` - List students
- `GET /api/courses/` - List courses
- `GET /api/studentenrolledcourses/` - Get student's enrolled courses
- `GET /api/student-attendance-history/` - Student attendance history
- `GET /api/lecturer-attendance-history/` - Lecturer attendance history

## License
This project is licensed under the MIT License.

## Support
For issues or questions, please create an issue in the repository or contact the development team.
