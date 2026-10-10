from django.urls import path

from .views import analytics, audit, auth, ocr, records, sections, users

urlpatterns = [
    # Auth
    path('auth/login/',  auth.login_view,  name='login'),
    path('auth/logout/', auth.logout_view, name='logout'),
    path('auth/me/',     auth.me_view,     name='me'),
    path('auth/change-password/', auth.change_password_view, name='change-password'),

    # Records ("create", "search" and "options" must come before the <record_id> routes)
    path('records/',                        records.records_list,    name='records-list'),
    path('records/create/',                 records.record_create,   name='record-create'),
    path('records/search/',                 records.records_search,  name='records-search'),
    path('records/options/',                records.records_options, name='records-options'),
    path('records/<str:record_id>/',        records.record_detail,  name='record-detail'),
    path('records/<str:record_id>/update/', records.record_update,  name='record-update'),
    path('records/<str:record_id>/delete/', records.record_delete,  name='record-delete'),

    # OCR pipeline
    path('ocr/quality/',                  ocr.ocr_quality,  name='ocr-quality'),
    path('ocr/upload/',                   ocr.ocr_upload,   name='ocr-upload'),
    path('ocr/validate/',                 ocr.ocr_validate, name='ocr-validate'),
    path('ocr/scans/<str:scan_id>/file/', ocr.scan_file,    name='scan-file'),
    path('ocr/history/',                  ocr.scan_history, name='scan-history'),

    # Analytics
    path('analytics/', analytics.analytics_dashboard, name='analytics'),

    # Sections ("create" must come before the <section_id> route)
    path('sections/',                  sections.sections_list,   name='sections-list'),
    path('sections/create/',           sections.sections_create, name='sections-create'),
    path('sections/<str:section_id>/', sections.section_detail,  name='section-detail'),

    # Users & audit
    path('users/',               users.users_list,   name='users-list'),
    path('users/create/',        users.users_create, name='users-create'),
    path('users/<int:user_id>/', users.user_detail,  name='user-detail'),
    path('audit/',               audit.audit_log,    name='audit-log'),
]
