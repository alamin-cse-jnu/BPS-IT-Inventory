

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # ================================
    # MAIN DASHBOARD
    # ================================
    path('', views.dashboard, name='dashboard'),
    
    # ================================
    # DEVICE MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_add'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<str:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<str:device_id>/qr/', views.device_qr_code, name='device_qr_code'),
    path('devices/<str:device_id>/history/', views.device_history, name='device_history'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/add/', views.assignment_create, name='assignment_add'),
    path('assignments/<str:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<str:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<str:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<str:assignment_id>/extend/', views.assignment_extend, name='assignment_extend'),
    path('assignments/<str:assignment_id>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/bulk/create/', views.bulk_assignment_create, name='bulk_assignment_create'),
    path('assignments/overdue/', views.overdue_assignments_list, name='overdue_assignments_list'),
    
    # ================================
    # STAFF MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_add'),
    path('staff/<str:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<str:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<str:staff_id>/delete/', views.staff_delete, name='staff_delete'),
    path('staff/<str:staff_id>/assignments/', views.staff_assignments, name='staff_assignments'),
    
    # ================================
    # DEPARTMENT MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_add'),
    path('departments/<str:department_id>/', views.department_detail, name='department_detail'),
    path('departments/<str:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<str:department_id>/assignments/', views.department_assignments, name='department_assignments'),
    
    # ================================
    # LOCATION MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('locations/', views.location_list, name='location_list'),
    path('locations/add/', views.location_create, name='location_add'),
    path('locations/<str:location_id>/', views.location_detail, name='location_detail'),
    path('locations/<str:location_id>/edit/', views.location_edit, name='location_edit'),
    path('locations/<str:location_id>/delete/', views.location_delete, name='location_delete'),
    
    # ================================
    # VENDOR MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/add/', views.vendor_create, name='vendor_add'),
    path('vendors/<str:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<str:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    path('vendors/<str:vendor_id>/delete/', views.vendor_delete, name='vendor_delete'),
    
    # ================================
    # MAINTENANCE MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.maintenance_create, name='maintenance_add'),
    path('maintenance/<str:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<str:maintenance_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<str:maintenance_id>/complete/', views.maintenance_complete, name='maintenance_complete'),
    path('maintenance/schedule/', views.maintenance_schedule, name='maintenance_schedule'),
    
    # ================================
    # DEVICE TYPE MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/add/', views.device_type_create, name='device_type_add'),
    path('device-types/<str:type_id>/', views.device_type_detail, name='device_type_detail'),
    path('device-types/<str:type_id>/edit/', views.device_type_edit, name='device_type_edit'),
    path('device-types/<str:type_id>/delete/', views.device_type_delete, name='device_type_delete'),
    
    # ================================
    # BULK OPERATIONS - CONFIRMED EXISTS
    # ================================
    path('bulk/actions/', views.bulk_actions, name='bulk_actions'),
    path('bulk/import/', views.bulk_import, name='bulk_import'),
    path('bulk/export/', views.bulk_export, name='bulk_export'),
    path('bulk/assignment/', views.bulk_assignment, name='bulk_assignment'),
    path('bulk/qr-generate/', views.bulk_qr_generate, name='bulk_qr_generate'),
    
    # ================================
    # IMPORT/EXPORT - CONFIRMED EXISTS
    # ================================
    path('import/', views.bulk_import, name='bulk_import_main'),
    path('import/devices/', views.import_devices_csv, name='import_devices_csv'),
    path('import/staff/', views.import_staff_csv, name='import_staff_csv'),
    path('export/', views.bulk_export, name='bulk_export_main'),
    path('export/devices/', views.export_devices_csv, name='export_devices_csv'),
    path('export/assignments/', views.export_assignments_csv, name='export_assignments_csv'),
    path('export/maintenance/', views.export_maintenance_csv, name='export_maintenance_csv'),
    
    # ================================
    # SEARCH AND FILTERING - CONFIRMED EXISTS
    # ================================
    path('search/', views.global_search, name='global_search'),
    path('search/devices/', views.device_search, name='device_search'),
    path('search/assignments/', views.assignment_search, name='assignment_search'),
    path('advanced-search/', views.advanced_search, name='advanced_search'),
    
    # ================================
    # REPORTING VIEWS - CONFIRMED EXISTS IN INVENTORY
    # ================================
    path('reports/warranty/', views.warranty_report, name='warranty_report'),
    path('reports/assignment/', views.assignment_report, name='assignment_report'),
    path('reports/audit/', views.audit_report, name='audit_report'),
    
    # ================================
    # AJAX ENDPOINTS - CONFIRMED EXISTS
    # ================================
    path('ajax/get-subcategories/', views.ajax_subcategories_by_category, name='ajax_get_subcategories'), 
    path('ajax/get-device-types/', views.ajax_device_types_by_subcategory, name='ajax_get_device_types'),  
    path('ajax/device-stats/<str:device_id>/', views.ajax_device_stats, name='ajax_device_stats'),
    path('ajax/assignment-quick-actions/<str:assignment_id>/', views.ajax_assignment_quick_actions, name='ajax_assignment_quick_actions'),
    path('ajax/staff-search/', views.ajax_staff_search, name='ajax_staff_search'),
    path('ajax/location-search/', views.ajax_location_search, name='ajax_location_search'),
    
    # ================================
    # SYSTEM UTILITIES - CONFIRMED EXISTS
    # ================================
    path('system/statistics/', views.system_statistics, name='system_statistics'),
    path('audit/logs/', views.audit_log_list, name='audit_log_list'),
]