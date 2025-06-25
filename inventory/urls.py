# inventory/urls.py - Updated with new views
# Location: inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # ================================
    # DASHBOARD
    # ================================
    path('', views.dashboard, name='dashboard'),
    
    # ================================
    # DEVICE MANAGEMENT
    # ================================
    path('devices/', views.device_list, name='device_list'),
    path('devices/create/', views.device_create, name='device_create'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<str:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/export/csv/', views.export_devices_csv, name='export_devices_csv'),
    path('devices/bulk/update/', views.bulk_device_update, name='bulk_device_update'),
    path('devices/qr/bulk-generate/', views.generate_qr_codes_bulk, name='generate_qr_codes_bulk'),
    
    # ================================
    # IMPORT/EXPORT - HIGH PRIORITY
    # ================================
    path('import/devices/', views.import_devices_csv, name='import_devices_csv'),
    path('import/staff/', views.import_staff_csv, name='import_staff_csv'),
    path('export/maintenance/', views.export_maintenance_csv, name='export_maintenance_csv'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/bulk/create/', views.bulk_assignment_create, name='bulk_assignment_create'),
    path('assignments/<str:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<str:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<str:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<str:assignment_id>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/<str:assignment_id>/extend/', views.assignment_extend, name='assignment_extend'),
    path('assignments/overdue/', views.overdue_assignments_list, name='overdue_assignments_list'),
    path('assignments/export/csv/', views.export_assignments_csv, name='export_assignments_csv'),
    path('assignments/bulk/return/', views.bulk_assignment_return, name='bulk_assignment_return'),
    
    # ================================
    # STAFF MANAGEMENT
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:staff_id>/assignments/', views.staff_assignments, name='staff_assignments'),
    
    # ================================
    # DEPARTMENT MANAGEMENT
    # ================================
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:department_id>/', views.department_detail, name='department_detail'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:department_id>/assignments/', views.department_assignments, name='department_assignments'),
    
    # ================================
    # LOCATION MANAGEMENT
    # ================================
    path('locations/', views.location_list, name='location_list'),
    path('locations/create/', views.location_create, name='location_create'),
    path('locations/<int:location_id>/', views.location_detail, name='location_detail'),
    
    # ================================
    # VENDOR MANAGEMENT
    # ================================
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/create/', views.vendor_create, name='vendor_create'),
    path('vendors/<int:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<int:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    
    # ================================
    # MAINTENANCE MANAGEMENT
    # ================================
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/create/', views.maintenance_create, name='maintenance_create'),
    path('maintenance/<int:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<int:maintenance_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<int:maintenance_id>/complete/', views.maintenance_complete, name='maintenance_complete'),
    
    # ================================
    # DEVICE TYPE MANAGEMENT - MEDIUM PRIORITY
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/create/', views.device_type_create, name='device_type_create'),
    path('device-types/<int:type_id>/', views.device_type_detail, name='device_type_detail'),
    path('device-types/<int:type_id>/edit/', views.device_type_edit, name='device_type_edit'),
    path('device-types/<int:type_id>/delete/', views.device_type_delete, name='device_type_delete'),
    
    # ================================
    # ADVANCED SEARCH - MEDIUM PRIORITY
    # ================================
    path('search/', views.advanced_search, name='advanced_search'),
    path('api/search/', views.global_search_api, name='global_search_api'),
    
    # ================================
    # DASHBOARD ANALYTICS API - MEDIUM PRIORITY
    # ================================
    path('api/dashboard/stats/', views.ajax_dashboard_stats, name='ajax_dashboard_stats'),
    path('api/notifications/', views.ajax_notification_list, name='ajax_notification_list'),
    path('api/device-stats/', views.ajax_device_stats, name='ajax_device_stats'),
    
    # ================================
    # AJAX ENDPOINTS FOR DYNAMIC FORMS
    # ================================
    path('api/subcategories/', views.ajax_subcategories_by_category, name='ajax_subcategories_by_category'),
    path('api/device-types/', views.ajax_device_types_by_subcategory, name='ajax_device_types_by_subcategory'),
    
    # ================================
    # BACKUP & RECOVERY - LOW PRIORITY
    # ================================
    path('backup/', views.database_backup, name='database_backup'),
    path('restore/', views.database_restore, name='database_restore'),
    path('backup/delete/<str:backup_filename>/', views.delete_backup, name='delete_backup'),
    
    # ================================
    # REPORTING VIEWS
    # ================================
    path('reports/summary/', views.inventory_summary_report, name='inventory_summary_report'),
    path('reports/utilization/', views.asset_utilization_report, name='asset_utilization_report'),
    path('reports/lifecycle/', views.device_lifecycle_report, name='device_lifecycle_report'),
    path('reports/maintenance/', views.maintenance_report, name='maintenance_report'),
    path('reports/warranty/', views.warranty_report, name='warranty_report'),
    path('reports/assignment/', views.assignment_report, name='assignment_report'),
    path('reports/audit/', views.audit_report, name='audit_report'),
]