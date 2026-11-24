# config/urls.py
from django.contrib import admin
from django.urls import include, path

from auth_service.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health_check, name="health"),
    path("api/v1/health", health_check, name="api-v1-health"),
    path("api/v1/auth/", include("auth_service.urls")),
]
