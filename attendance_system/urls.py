from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.db import connection
from django.core.cache import cache
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Custom admin index template (extends Jazzmin's with stats widget)
admin.site.index_template = 'admin/exodus_index.html'


def health_view(request):
    """Health check endpoint for Render / uptime monitors."""
    status = {'status': 'ok'}
    http_status = 200

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        status['database'] = 'ok'
    except Exception as e:
        status['database'] = str(e)
        status['status'] = 'degraded'
        http_status = 503

    # Check cache connectivity
    try:
        cache.set('_health_check', '1', 10)
        if cache.get('_health_check') == '1':
            status['cache'] = 'ok'
        else:
            status['cache'] = 'unreachable'
            status['status'] = 'degraded'
    except Exception as e:
        status['cache'] = str(e)
        status['status'] = 'degraded'

    return JsonResponse(status, status=http_status)


@cache_control(max_age=86400, public=True)
def favicon_view(request):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#4f46e5"/>'
        '<text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" '
        'fill="white" font-size="20" font-weight="bold">E</text></svg>'
    )
    return HttpResponse(svg, content_type='image/svg+xml')


urlpatterns = [
    # Favicon
    path('favicon.ico', favicon_view, name='favicon'),

    # Health check
    path('health/', health_view, name='health'),

    # Django Admin Obfuscation (Prevents vulnerability scanners)
    path('exodus-manage/', admin.site.urls),

    # Frontend URLs (including login/logout)
    path('', include('frontend.urls')),
    
    # API endpoints
    path('api/', include('attendance.urls')),
    
    # API documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = 'frontend.views.error_404'
handler500 = 'frontend.views.error_500'
