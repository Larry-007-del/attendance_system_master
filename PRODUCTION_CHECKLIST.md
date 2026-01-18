# Production Deployment Checklist

Use this checklist before deploying to production.

## Pre-Deployment Review

### Code Quality
- [ ] All Django system checks pass: `python manage.py check`
- [ ] No pending migrations: `python manage.py makemigrations --check`
- [ ] Code follows PEP 8 guidelines
- [ ] All imports are used
- [ ] No debug print statements in code
- [ ] No hardcoded sensitive information
- [ ] All endpoints have proper error handling

### Testing
- [ ] Unit tests pass (if any exist)
- [ ] Integration tests pass
- [ ] API endpoints tested manually
- [ ] Authentication flows tested
- [ ] Error responses verified

### Security
- [ ] `DEBUG = False` in production settings
- [ ] `SECRET_KEY` is unique and strong
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] `CORS_ALLOWED_ORIGINS` restricted to expected domains
- [ ] SSL/HTTPS enabled
- [ ] CSRF protection enabled
- [ ] XSS protection enabled
- [ ] No sensitive data in logs
- [ ] Database credentials not in version control

### Database
- [ ] All migrations applied
- [ ] Database backed up (if migrating from old system)
- [ ] Database user has minimal required permissions
- [ ] Connection pooling configured (if using PostgreSQL)
- [ ] Database indices created for frequently queried fields

### Static Files & Media
- [ ] Static files collected: `python manage.py collectstatic --noinput`
- [ ] Static files served via CDN or web server (not Django)
- [ ] Media files directory exists and is writable
- [ ] Static/media paths correct in settings

### Environment Variables
- [ ] `.env.example` file exists and documented
- [ ] All required environment variables documented
- [ ] Environment variables set in deployment platform
- [ ] No environment variables committed to version control
- [ ] Default values are safe for development

### Dependencies
- [ ] `requirements.txt` up to date
- [ ] All dependencies are pinned to specific versions
- [ ] No unnecessary dependencies
- [ ] All security patches applied
- [ ] Python version specified in `runtime.txt`

### Documentation
- [ ] README.md is complete and accurate
- [ ] DEPLOYMENT_GUIDE.md is up to date
- [ ] API documentation generated and accessible
- [ ] Environment setup instructions clear
- [ ] Known issues and limitations documented

## Render Deployment Specific

### Repository
- [ ] Code committed and pushed to GitHub
- [ ] Repository is public (or Render has access if private)
- [ ] Main branch is stable and ready for deployment
- [ ] No large binary files in repository
- [ ] `.gitignore` prevents unnecessary files from being committed

### Render Configuration
- [ ] `render.yaml` or Procfile is correct
- [ ] Build command will succeed
- [ ] Start command is correct
- [ ] Static file path correct
- [ ] Database is configured (if needed)

### Environment Setup in Render
- [ ] `DJANGO_SECRET_KEY` set to unique value
- [ ] `DJANGO_DEBUG` set to `False`
- [ ] `DJANGO_ALLOWED_HOSTS` set correctly
- [ ] Any other required environment variables set
- [ ] Variables are marked as synced to the correct instances

### Testing After Deployment
- [ ] Application starts without errors
- [ ] Home page loads successfully
- [ ] Swagger documentation accessible
- [ ] Admin panel accessible
- [ ] API endpoints responding
- [ ] Static files loading correctly
- [ ] CORS requests working
- [ ] Database migrations applied automatically
- [ ] Error pages working correctly
- [ ] Logs show no critical errors

## Post-Deployment

### Monitoring
- [ ] Error logging configured
- [ ] Performance monitoring enabled
- [ ] Uptime monitoring configured
- [ ] Log aggregation (if applicable)
- [ ] Alerts configured for critical errors

### Backups
- [ ] Database backup scheduled
- [ ] Media files backup configured
- [ ] Backup recovery tested
- [ ] Retention policy defined

### Performance
- [ ] Response times acceptable
- [ ] Database queries optimized
- [ ] Caching configured (if needed)
- [ ] Static file compression enabled
- [ ] Load testing completed (if applicable)

### User Communication
- [ ] Users notified of deployment
- [ ] Known issues communicated
- [ ] Support contact information provided
- [ ] Documentation updated for users

## Rollback Plan

- [ ] Previous version identified
- [ ] Rollback procedure documented
- [ ] Database migration rollback plan created
- [ ] Communication plan for rollback ready

## Post-Launch Monitoring (First 24 Hours)

- [ ] Check error logs hourly
- [ ] Monitor application performance
- [ ] Verify user functionality
- [ ] Check for any data corruption
- [ ] Verify all scheduled tasks running
- [ ] Monitor server resource usage
- [ ] Check for any security issues

## Sign-Off

- [ ] Code Review: _________________ Date: _______
- [ ] QA Testing: _________________ Date: _______
- [ ] Security Review: _________________ Date: _______
- [ ] Deployment Approved: _________________ Date: _______

---

**Remember**: A rushed deployment can cause significant downtime and data loss. Take time to verify each item on this checklist.

For issues or questions, see `DEPLOYMENT_GUIDE.md` or `DEBUG_AND_DEPLOY_SUMMARY.md`.
