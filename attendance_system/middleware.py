from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class InactivityLogoutMiddleware:
    """Log out authenticated users after a period of inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timeout_minutes = getattr(settings, 'SESSION_INACTIVITY_TIMEOUT_MINUTES', None)
        if timeout_minutes and request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = timezone.now()

            if last_activity:
                try:
                    last_activity_dt = timezone.datetime.fromisoformat(last_activity)
                except ValueError:
                    last_activity_dt = None

                if last_activity_dt:
                    if timezone.is_naive(last_activity_dt):
                        last_activity_dt = timezone.make_aware(
                            last_activity_dt,
                            timezone.get_current_timezone(),
                        )

                    if now - last_activity_dt > timedelta(minutes=timeout_minutes):
                        logout(request)
                        request.session.flush()
                        if hasattr(request, '_messages'):
                            messages.info(request, "You have been logged out due to inactivity.")
                        return redirect('frontend:login')

            request.session['last_activity'] = now.isoformat()

        return self.get_response(request)
