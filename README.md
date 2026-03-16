# Exodus — University Attendance System

A full-stack Django web application for managing university attendance with GPS-based verification, QR code check-ins, two-factor authentication, role-based dashboards, and real-time notifications.

[![CI](https://github.com/Larry-007-del/Exodus/actions/workflows/ci.yml/badge.svg)](https://github.com/Larry-007-del/Exodus/actions/workflows/ci.yml)

**Live:** [https://exodus-nsji.onrender.com](https://exodus-nsji.onrender.com)

---

## Features

- **GPS-Based Attendance** — Students submit their location; the system verifies they are within range of the lecturer
- **QR Code Check-In** — Lecturers generate time-limited attendance tokens with scannable QR codes
- **Two-Factor Authentication** — WebAuthn (fingerprint/biometric) and TOTP (authenticator app) support for attendance verification
- **Role-Based Access** — Admin, Lecturer, and Student roles with tailored dashboards, sidebars, and permissions
- **Streamlined Admin Provisioning** — Admin can create Student profile + linked User credentials (including password validation) in one form
- **Real-Time Notifications** — Email and SMS alerts for attendance sessions (configurable per-student)
- **Welcome Onboarding Email** — Automatically emails new Student/Lecturer accounts with sign-in guidance
- **Reports & Analytics** — Attendance trends, per-course statistics, weekly charts, CSV/Excel exports
- **Password Reset** — Full email-based password reset flow with branded templates
- **Backup & Restore** — Database backup (`dbbackup`) and safe recovery (`dbrestore`) management commands
- **REST API** — DRF-powered API with Swagger/OpenAPI documentation and token authentication
- **Health Check** — `/health/` endpoint with DB and cache connectivity monitoring (used by Render)
- **Responsive UI** — Tailwind CSS + Alpine.js + HTMX + Flowbite — all assets served locally (no CDN)
- **Accessibility** — Skip-nav link, ARIA landmarks, live regions, semantic HTML
- **Security Hardened** — HSTS, secure cookies, CSRF protection, rate limiting on login and registration, scoped access control

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.2, Django REST Framework 3.16 |
| Frontend | Tailwind CSS 3.4, Alpine.js 3.15, HTMX 2.0, Flowbite 4.0 |
| Database | SQLite (dev), PostgreSQL (production) |
| Auth | Token auth, session auth, WebAuthn 2FA, TOTP 2FA |
| Media | Cloudinary (production), local storage (dev) |
| Static Files | WhiteNoise, PostCSS/Tailwind build pipeline |
| Deployment | Render (Gunicorn + health check), GitHub Actions CI |
| Monitoring | Sentry error tracking |

---

## Project Structure

```
attendance_system_master/
├── attendance/              # Core app — models, REST API, serializers
│   ├── models.py            # Lecturer, Student, Course, Attendance, WebAuthnCredential, etc.
│   ├── views.py             # DRF ViewSets and API views
│   ├── serializers.py       # REST serializers with schema annotations
│   ├── urls.py              # API URL routing
│   ├── notification_service.py  # Email + SMS notification helpers
│   ├── tasks.py             # Background task helpers (attendance notifications)
│   └── tests.py             # Model, API, serializer, and permission tests
├── frontend/                # Web UI app — server-rendered templates
│   ├── views.py             # All page views (dashboard, CRUD, reports, 2FA, auth)
│   ├── urls.py              # Frontend URL routing (incl. password reset)
│   ├── forms.py             # Django forms
│   └── tests.py             # View, access control, rate limit, and integration tests
├── attendance_system/       # Django project settings
│   ├── settings.py          # Configuration (security, DB, email, cache, etc.)
│   └── urls.py              # Root URLs (health check, favicon, admin, API)
├── templates/               # Django templates
│   ├── base.html            # Main layout (nav, sidebar, footer, a11y landmarks)
│   ├── dashboard.html       # Role-aware dashboard
│   ├── attendance/          # Attendance management + 2FA challenge pages
│   ├── courses/             # Course CRUD pages
│   ├── students/            # Student management pages
│   ├── lecturers/           # Lecturer management pages
│   ├── reports/             # Analytics and export pages
│   ├── registration/        # Password reset templates + email
│   ├── frontend/            # Login, register pages
│   └── errors/              # Custom 404/500 error pages
├── static/                  # Built frontend assets (committed)
│   ├── css/styles.css       # Compiled & minified Tailwind CSS
│   └── js/                  # Alpine.js, HTMX, Flowbite (local copies)
├── .github/workflows/ci.yml # GitHub Actions CI pipeline
├── build.sh                 # Render build script
├── entrypoint.sh            # Render start script (migrate, superuser, gunicorn)
├── render.yaml              # Render deployment config (with health check)
├── package.json             # Node.js — Tailwind/PostCSS build
├── tailwind.config.js       # Tailwind configuration
└── requirements.txt         # Python dependencies (28 packages)
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend asset builds)
- Git

### Local Setup

```bash
# Clone the repository
git clone https://github.com/Larry-007-del/Exodus.git
cd Exodus/attendance_system_master

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies & build frontend assets
npm install
npm run build

# Apply database migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Visit `http://localhost:8000` — you'll be redirected to the login page.

### Docker Setup (Recommended)

If you have Docker and Docker Compose installed, you can spin up the entire application (including a PostgreSQL database) with a single command:

```bash
# Clone the repository
git clone https://github.com/Larry-007-del/Exodus.git
cd Exodus/attendance_system_master

# Build and start the containers
docker-compose up --build -d

# Visit http://localhost:8000
```

To run Django management commands inside the Docker container (like creating a superuser):
```bash
docker-compose exec web python manage.py createsuperuser
```

### Testing Password Reset Locally

In `DEBUG` mode, the email backend is set to `console` — password reset emails will print directly to the terminal. Click "Forgot password?" on the login page, enter an email, and check the terminal output for the reset link.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | insecure dev key | Secret key for production |
| `DJANGO_DEBUG` | `True` | Set `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | PostgreSQL URL for production |
| `DJANGO_SUPERUSER_USERNAME` | — | Auto-create superuser on deploy |
| `DJANGO_SUPERUSER_PASSWORD` | — | Superuser password |
| `DJANGO_SUPERUSER_EMAIL` | — | Superuser email |
| `CLOUDINARY_CLOUD_NAME` | — | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | — | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | — | Cloudinary API secret |
| `EMAIL_HOST_USER` | — | SMTP email address |
| `EMAIL_HOST_PASSWORD` | — | SMTP app password |
| `SENTRY_DSN` | — | Sentry error tracking DSN |
| `TWILIO_ACCOUNT_SID` | — | Twilio SMS SID |
| `TWILIO_AUTH_TOKEN` | — | Twilio SMS auth token |
| `TWILIO_PHONE_NUMBER` | — | Twilio sender number |
| `CACHE_BACKEND` | `FileBasedCache` | Cache backend class |
| `CACHE_LOCATION` | `.cache/` | Cache directory or URL |
| `CORS_ALLOWED_ORIGINS` | — | Comma-separated CORS origins |

---

## API Reference

The API is served under `/api/` with interactive Swagger docs at `/api/docs/`.

### Authentication

All API endpoints require token authentication. Obtain a token via:

```
POST /api/login/student/    { username, password, student_id }
POST /api/login/staff/      { username, password, staff_id }
```

Include the token in subsequent requests:

```
Authorization: Token <your-token>
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lecturers/` | List all lecturers |
| GET | `/api/students/` | List students (filtered by role) |
| GET | `/api/courses/` | List all courses |
| GET | `/api/attendances/` | List attendance records |
| GET | `/api/attendance-tokens/` | List attendance tokens |
| GET | `/api/lecturers/my-courses/` | Lecturer's own courses |
| POST | `/api/submit-location/` | Student submits GPS for check-in |
| POST | `/api/logout/` | Invalidate auth token |
| GET | `/api/student-attendance-history/` | Student's attendance history |
| GET | `/api/lecturer-attendance-history/` | Lecturer's attendance history |
| POST | `/api/lecturer-location/` | Get lecturer coordinates by token |

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health/` | Health check (DB + cache status, used by Render) |
| GET | `/favicon.ico` | SVG favicon (24h cache) |
| GET | `/api/schema/` | OpenAPI schema (JSON) |
| GET | `/api/docs/` | Swagger UI |

---

## Testing

The project has **279 tests** covering models, API endpoints, serializers, views, access control, rate limiting, 2FA flows, management commands, and integration scenarios.

```bash
# Run all tests
python manage.py test

# Run with parallel workers (faster)
python manage.py test --parallel

# Run with verbose output
python manage.py test --verbosity=2

# Run specific app tests
python manage.py test attendance
python manage.py test frontend

# Run with coverage
coverage run manage.py test
coverage report
```

Tests run automatically on every push/PR via GitHub Actions CI.

---

## Backup & Restore

Use built-in management commands for operational recovery:

```bash
# Create backup (JSON by default)
python manage.py dbbackup

# Create named XML backup
python manage.py dbbackup --format xml --output backup_manual.xml

# Restore safely (recommended): flush then restore
python manage.py dbrestore --input backup_YYYYMMDD_HHMMSS.json --flush --force

# Validate restore plan without writing
python manage.py dbrestore --input backup_YYYYMMDD_HHMMSS.json --dry-run
```

Safety behavior:
- `dbrestore` blocks restore when existing data is detected unless `--flush` or `--force` is provided.
- `--flush --force` is recommended for full-environment recovery.

---

## Frontend Asset Pipeline

Frontend assets are built locally and committed to the repo. No CDN dependencies at runtime.

```bash
# Install Node dependencies
npm install

# Build Tailwind CSS (minified) + copy JS vendor assets
npm run build

# Watch mode for development (Tailwind CSS only)
npm run watch
```

**Assets:**
- `static/css/styles.css` — Compiled Tailwind CSS (purged and minified)
- `static/js/alpine.min.js` — Alpine.js 3.15
- `static/js/htmx.min.js` — HTMX 2.0
- `static/js/flowbite.min.js` — Flowbite 4.0

---

## Deployment (Render)

The project is configured for [Render](https://render.com) deployment via `render.yaml`:

1. Connect your GitHub repo to Render
2. Set environment variables — at minimum `DJANGO_SECRET_KEY`, `DATABASE_URL`, and superuser credentials
3. Render will use `build.sh` (install deps, build assets, migrate) and `entrypoint.sh` (collectstatic, safe superuser creation, Gunicorn)

### Deployment Features

- **Gunicorn** with 2 workers bound to `0.0.0.0:${PORT}`
- **Health check** at `/health/` (configured in `render.yaml`)
- **Cron session cleanup** — `close_expired_sessions --notify` runs every 30 minutes
- **WhiteNoise** for static file serving with compression
- **PostgreSQL** via `DATABASE_URL`
- **Environment-aware media storage** — local filesystem in dev/tests, Cloudinary in production
- **Safe superuser creation** — checks if user exists before creating (no crash on redeploy)
- **HSTS**, secure cookies, SSL redirect, CSRF trusted origins in production
- **Sentry** error tracking (if `SENTRY_DSN` is set)

---

## Security

Production mode (`DJANGO_DEBUG=False`) automatically enables:

- HTTPS redirect (`SECURE_SSL_REDIRECT`)
- Secure session and CSRF cookies
- HSTS headers (1 year, include subdomains, preload)
- XSS and content-type sniffing protection
- API rate limiting (10/min anonymous, 1000/day authenticated)
- Dedicated API login throttling (5/min per scope for student/staff token login)
- Standardized API error payloads (`error`, `code`, optional `details`) on auth/location workflows
- Login rate limiting (5 attempts per 5 minutes per IP)
- Registration rate limiting (5 attempts per hour per IP)
- Scoped access control on student detail views
- POST-only logout with CSRF protection

---

## License

This project is licensed under the ISC License.
