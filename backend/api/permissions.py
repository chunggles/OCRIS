from rest_framework.permissions import BasePermission

from .models import OCRISUser


class IsOIC(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == OCRISUser.OIC


class IsOICOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (OCRISUser.OIC, OCRISUser.ADMIN)
