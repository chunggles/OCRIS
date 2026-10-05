from django.contrib import admin
from django.urls import include, path

# Uploaded scans are not served from /media/; they go through /api/ocr/scans/<id>/file/, which checks access.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]
