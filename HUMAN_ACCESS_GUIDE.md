# 🎓 Attendance System - Human Access Guide

## ✅ Your Server is Ready!

The Django development server is **running and accessible** on your local machine.

---

## 🌐 Access Points

### 1. **Interactive API Documentation (Swagger UI)** ⭐ START HERE
**URL:** `http://127.0.0.1:8000/swagger/`

- **Best for:** Testing API endpoints, seeing request/response examples
- **Features:** 
  - Click on each endpoint to expand it
  - Try it out buttons to make real requests
  - See authentication requirements
  - View example responses

### 2. **Alternative API Docs (ReDoc)**
**URL:** `http://127.0.0.1:8000/redoc/`

- **Best for:** Reading API documentation in a clean, searchable format
- **Features:**
  - Beautiful sidebar navigation
  - Full endpoint descriptions
  - Request/response schemas
  - Authentication documentation

### 3. **Admin Panel**
**URL:** `http://127.0.0.1:8000/admin/`

- **Best for:** Managing data - users, lecturers, students, courses, attendance records
- **Requirements:**
  - Need a superuser account to access
  - **Default credentials:** (if you created them)
    - Username: `admin`
    - Password: (whatever you set during setup)
  - To create a superuser, run:
    ```bash
    python manage.py createsuperuser
    ```

### 4. **Raw API Endpoints**
**URL:** `http://127.0.0.1:8000/api/`

- **Best for:** Direct API calls from applications
- **Usage:** See Swagger UI or ReDoc for endpoint details

---

## 📋 Important Endpoints to Know

### Authentication
- **Login:** `POST /api/login/` - Get authentication token
- **Logout:** `POST /api/logout/` - Revoke token

### Lecturers
- **List/Create:** `GET/POST /api/lecturers/`
- **Detail:** `GET /api/lecturers/{id}/`

### Students
- **List/Create:** `GET/POST /api/students/`
- **Detail:** `GET /api/students/{id}/`

### Courses
- **List/Create:** `GET/POST /api/courses/`
- **Detail:** `GET /api/courses/{id}/`

### Attendance
- **List/Create:** `GET/POST /api/attendance/`
- **Check In:** `POST /api/attendance/check-in/`

> For complete endpoint list, visit the Swagger UI!

---

## 🔑 Getting Your First API Token

### Option 1: Using Swagger UI (Recommended)
1. Go to `http://127.0.0.1:8000/swagger/`
2. Find the **Login** endpoint
3. Click "Try it out"
4. Enter your credentials (username/password)
5. Click "Execute"
6. Copy the `token` from the response

### Option 2: Using curl
```bash
curl -X POST http://127.0.0.1:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

### Using the Token
Add it to your requests:
```bash
curl -H "Authorization: Token YOUR_TOKEN_HERE" \
  http://127.0.0.1:8000/api/students/
```

---

## 🧪 Quick Test Steps

### 1. **Test the Server** (2 minutes)
- [ ] Open browser to `http://127.0.0.1:8000/swagger/`
- [ ] Confirm you see the Swagger UI with API documentation
- [ ] Try clicking on an endpoint to expand it

### 2. **Create Test Data** (5 minutes)
- [ ] Go to `http://127.0.0.1:8000/admin/`
- [ ] Create a lecturer
- [ ] Create a student
- [ ] Create a course

### 3. **Test an API Endpoint** (5 minutes)
- [ ] Go to `http://127.0.0.1:8000/swagger/`
- [ ] Find the endpoint you want to test
- [ ] Click "Try it out"
- [ ] Fill in any required fields
- [ ] Click "Execute"
- [ ] See the response

---

## ⚠️ Important Notes

### HTTP vs HTTPS
- **Development Server:** Uses **HTTP only** (not HTTPS)
- **Use:** `http://127.0.0.1:8000` (NOT `https://`)
- **Browsers:** Use regular browser (Chrome, Firefox, Edge, Safari)
- **VS Code Simple Browser:** May not work (enforce HTTPS automatically)

### Server URL Variations (All work the same)
- `http://127.0.0.1:8000/` - Localhost IP
- `http://localhost:8000/` - Hostname

### If You Get "Cannot Connect"
1. Check if the terminal shows `Starting development server at http://127.0.0.1:8000/`
2. Verify the server terminal is still running (no errors)
3. Try refreshing the page (Ctrl+R or Cmd+R)
4. Make sure you're using HTTP, not HTTPS

---

## 📚 System Information

| Item | Value |
|------|-------|
| **Server** | http://127.0.0.1:8000 |
| **Framework** | Django 5.0.7 |
| **API** | Django REST Framework 3.15.2 |
| **Database** | SQLite3 (db.sqlite3) |
| **Python** | 3.12.7 |
| **Mode** | Development (HTTP) |
| **Authentication** | Token-based |

---

## 🚀 Next Steps (After Testing)

1. **Create Test Data**
   - Go to admin panel and create a few test users
   - Create courses and link them to lecturers

2. **Test Attendance Flow**
   - Use API to create an attendance session
   - Test check-in with location verification

3. **Deployment (When Ready)**
   - See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
   - Follow [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for quick deployment

4. **Customization**
   - Modify models in `attendance/models.py`
   - Add custom endpoints in `attendance/views.py`
   - Update serializers in `attendance/serializers.py`

---

## 🎯 Troubleshooting

### "Connection refused"
- Make sure server is running (check terminal)
- Wait 5 seconds, then refresh page
- Make sure you're using `http://`, not `https://`

### "Forbidden" or "Authentication required"
- Most endpoints require a token
- Get a token from the login endpoint first
- Add `Authorization: Token YOUR_TOKEN` header to requests

### "Not Found" (404)
- Check the endpoint URL in Swagger UI
- Make sure it's spelled correctly
- Verify you're using the right HTTP method (GET, POST, etc.)

### Server won't start
- Ensure you activated the virtual environment: `.\venv\Scripts\Activate.ps1`
- Check Python path: `python --version` should show 3.12.7
- Check database: `python manage.py migrate`

---

## 📖 Documentation Files

- **[README.md](README.md)** - Project overview and features
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Fast deployment guide
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment to production
- **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - All documentation files indexed
- **[AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md)** - Documentation automation setup

---

## ❓ Questions?

1. **API Questions?** → Check Swagger UI at `http://127.0.0.1:8000/swagger/`
2. **Deployment Questions?** → See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
3. **Bug Issues?** → Check [DEBUG_AND_DEPLOY_SUMMARY.md](DEBUG_AND_DEPLOY_SUMMARY.md)
4. **Setup Issues?** → Review [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

---

**Last Updated:** January 18, 2026  
**Status:** ✅ Development Server Ready for Testing
