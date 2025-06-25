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
    # DEVICE TYPE MANAGEMENT
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/create/', views.device_type_create, name='device_type_create'),
    
    # ================================
    # REPORTING VIEWS
    # ================================
    path('reports/summary/', views.inventory_summary_report, name='inventory_summary_report'),
    path('reports/utilization/', views.asset_utilization_report, name='asset_utilization_report'),
    path('reports/lifecycle/', views.device_lifecycle_report, name='device_lifecycle_report'),
    path('reports/warranty/', views.warranty_management_report, name='warranty_management_report'),
    
    # ================================
    # SYSTEM ADMINISTRATION
    # ================================
    path('admin/statistics/', views.system_statistics, name='system_statistics'),
    path('admin/audit-logs/', views.audit_log_list, name='audit_log_list'),
    path('admin/data-cleanup/', views.data_cleanup_tools, name='data_cleanup_tools'),
    
    # ================================
    # AJAX ENDPOINTS
    # ================================
    path('ajax/device-info/<str:device_id>/', views.get_device_info, name='get_device_info'),
    path('ajax/quick-assign/', views.quick_assign_device, name='quick_assign_device'),
    path('ajax/search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('ajax/device-availability/', views.device_availability_check, name='device_availability_check'),
    path('ajax/staff-by-department/<int:department_id>/', views.get_staff_by_department, name='get_staff_by_department'),
    path('ajax/rooms-by-building/<int:building_id>/', views.get_rooms_by_building, name='get_rooms_by_building'),
    path('ajax/locations-by-room/<int:room_id>/', views.get_locations_by_room, name='get_locations_by_room'),
    path('ajax/subcategories/', views.ajax_get_subcategories, name='ajax_get_subcategories'),
    path('ajax/device-types/', views.ajax_get_device_types, name='ajax_get_device_types'),
    path('ajax/device-quick-info/<str:device_id>/', views.ajax_device_quick_info, name='ajax_device_quick_info'),
    path('ajax/assignment-actions/<str:assignment_id>/', views.ajax_assignment_quick_actions, name='ajax_assignment_quick_actions'),
]