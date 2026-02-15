from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Swagger and ReDoc schema view
schema_view = get_schema_view(
    openapi.Info(
        title="Attendance System API",
        default_version='v1',
        description="API documentation for the Attendance System",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # 1. The Real Django Admin (Restore this!)
    path('admin/', admin.site.urls),

    # 2. Your API
    path('api/', include('attendance.urls')),

    # 3. Your Frontend (Move to root, so it becomes /login/, /dashboard/)
    path('', include('frontend.urls')),
    
    # 4. Auth URLs
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    
    # 5. Swagger Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
