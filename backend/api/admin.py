from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import OCRISUser

OCRIS_FIELDSET = ('OCRIS Role', {'fields': ('role', 'employee_id', 'assigned_grade', 'assigned_section')})


@admin.register(OCRISUser)
class OCRISUserAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'role', 'employee_id', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = UserAdmin.fieldsets + (OCRIS_FIELDSET,)
    add_fieldsets = UserAdmin.add_fieldsets + (OCRIS_FIELDSET,)
