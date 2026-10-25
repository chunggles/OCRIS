from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# Uploaded scans are not served from /media/; they go through /api/ocr/scans/<id>/file/, which checks access.
# The site itself (FRONTEND_DIST) is served by WhiteNoise before a request reaches these routes.
urlpatterns = [
    path('api/', include('api.urls')),
]
if settings.ENABLE_DJANGO_ADMIN:
    urlpatterns.append(path('admin/', admin.site.urls))
