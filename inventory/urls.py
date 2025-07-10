# inventory/urls.py
# Location: bps_inventory/apps/inventory/urls.py

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
    path('devices/add/', views.device_create, name='device_create'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<str:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<str:device_id>/qr/', views.device_qr_code, name='device_qr_code'),
    path('devices/<str:device_id>/history/', views.device_history, name='device_history'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/add/', views.assignment_create, name='assignment_create'),
    path('assignments/<str:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<str:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<str:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<str:assignment_id>/extend/', views.assignment_extend, name='assignment_extend'),
    path('assignments/<str:assignment_id>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/bulk/create/', views.bulk_assignment_create, name='bulk_assignment_create'),
    path('assignments/overdue/', views.overdue_assignments_list, name='overdue_assignments_list'),
    
    # ================================
    # PERSONAL ASSIGNMENT VIEWS
    # ================================
    path('my-assignments/', views.my_assignments, name='my_assignments'),
    path('my-assignments/<str:assignment_id>/', views.my_assignment_detail, name='my_assignment_detail'),

    # ================================
    # STAFF MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_create'),
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
    # LOCATION MANAGEMENT - ENHANCED WITH BLOCK SUPPORT
    # ================================
    path('locations/', views.location_list, name='location_list'),
    path('locations/add/', views.location_create, name='location_add'),
    path('locations/<str:location_id>/', views.location_detail, name='location_detail'),
    path('locations/<str:location_id>/edit/', views.location_edit, name='location_edit'),
    path('locations/<str:location_id>/delete/', views.location_delete, name='location_delete'),

    # ================================
    # BUILDING MANAGEMENT
    # ================================
    path('buildings/', views.building_list, name='building_list'),
    path('buildings/add/', views.building_create, name='building_add'),
    path('buildings/<str:building_id>/', views.building_detail, name='building_detail'),
    path('buildings/<str:building_id>/edit/', views.building_edit, name='building_edit'),
    path('buildings/<str:building_id>/delete/', views.building_delete, name='building_delete'),

    # ================================
    # BLOCK MANAGEMENT
    # ================================
    path('blocks/', views.block_list, name='block_list'),
    path('blocks/add/', views.block_create, name='block_add'),
    path('blocks/<str:block_id>/', views.block_detail, name='block_detail'),
    path('blocks/<str:block_id>/edit/', views.block_edit, name='block_edit'),
    path('blocks/<str:block_id>/delete/', views.block_delete, name='block_delete'),

    # ================================
    # FLOOR MANAGEMENT
    # ================================
    path('floors/', views.floor_list, name='floor_list'),
    path('floors/add/', views.floor_create, name='floor_add'),
    path('floors/<str:floor_id>/', views.floor_detail, name='floor_detail'),
    path('floors/<str:floor_id>/edit/', views.floor_edit, name='floor_edit'),
    path('floors/<str:floor_id>/delete/', views.floor_delete, name='floor_delete'),

    # ================================
    # ROOM MANAGEMENT
    # ================================
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/add/', views.room_create, name='room_add'),
    path('rooms/<str:room_id>/', views.room_detail, name='room_detail'),
    path('rooms/<str:room_id>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<str:room_id>/delete/', views.room_delete, name='room_delete'),
    
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
    # AJAX ENDPOINTS - ENHANCED WITH LOCATION HIERARCHY SUPPORT
    # ================================
    path('ajax/get-subcategories/', views.ajax_subcategories_by_category, name='ajax_get_subcategories'), 
    path('ajax/get-device-types/', views.ajax_device_types_by_subcategory, name='ajax_get_device_types'),  
    path('ajax/device-stats/<str:device_id>/', views.ajax_device_stats, name='ajax_device_stats'),
    path('ajax/assignment-quick-actions/<str:assignment_id>/', views.ajax_assignment_quick_actions, name='ajax_assignment_quick_actions'),
    path('ajax/staff-search/', views.ajax_staff_search, name='ajax_staff_search'),
    path('ajax/location-search/', views.ajax_location_search, name='ajax_location_search'),
    
    # Location Hierarchy Cascade AJAX Endpoints
    path('ajax/get-blocks/', views.ajax_get_blocks, name='ajax_get_blocks'),
    path('ajax/get-floors/', views.ajax_get_floors, name='ajax_get_floors'),
    path('ajax/get-departments/', views.ajax_get_departments, name='ajax_get_departments'),
    path('ajax/get-rooms/', views.ajax_get_rooms, name='ajax_get_rooms'),
    
    # Hierarchy Validation and Utilities
    path('ajax/validate-hierarchy/', views.ajax_validate_hierarchy, name='ajax_validate_hierarchy'),
    path('ajax/suggest-block-code/', views.ajax_suggest_block_code, name='ajax_suggest_block_code'),
    path('ajax/location-breadcrumb/', views.ajax_location_breadcrumb, name='ajax_location_breadcrumb'),

    # ================================
    # ORGANIZATION HIERARCHY UTILITIES
    # ================================
    path('hierarchy/', views.hierarchy_overview, name='hierarchy_overview'),
    path('hierarchy/tree/', views.hierarchy_tree_view, name='hierarchy_tree'),
    path('hierarchy/map/', views.hierarchy_map_view, name='hierarchy_map'),
    path('hierarchy/export/', views.hierarchy_export, name='hierarchy_export'),

    # ================================
    # LOCATION-SPECIFIC REPORTS
    # ================================
    path('reports/location-utilization/', views.location_utilization_report, name='location_utilization_report'),
    path('reports/hierarchy-breakdown/', views.hierarchy_breakdown_report, name='hierarchy_breakdown_report'),
    path('reports/space-analysis/', views.space_analysis_report, name='space_analysis_report'),

    # ================================
    # BULK LOCATION OPERATIONS
    # ================================
    path('bulk/locations/create/', views.bulk_location_create, name='bulk_location_create'),
    path('bulk/locations/update/', views.bulk_location_update, name='bulk_location_update'),
    path('bulk/locations/export/', views.bulk_location_export, name='bulk_location_export'),
    path('bulk/locations/import/', views.bulk_location_import, name='bulk_location_import'),
    
    # ================================
    # SYSTEM UTILITIES - CONFIRMED EXISTS
    # ================================
    path('system/statistics/', views.system_statistics, name='system_statistics'),
    path('audit/logs/', views.audit_log_list, name='audit_log_list'),

    # ================================
    # API ENDPOINTS FOR MOBILE/EXTERNAL INTEGRATION
    # ================================
    path('api/locations/search/', views.api_location_search, name='api_location_search'),
    path('api/hierarchy/validate/', views.api_hierarchy_validate, name='api_hierarchy_validate'),
    path('api/blocks/by-building/<str:building_id>/', views.api_blocks_by_building, name='api_blocks_by_building'),
    path('api/floors/by-block/<str:block_id>/', views.api_floors_by_block, name='api_floors_by_block'),
    path('api/departments/by-floor/<str:floor_id>/', views.api_departments_by_floor, name='api_departments_by_floor'),
    path('api/rooms/by-department/<str:department_id>/', views.api_rooms_by_department, name='api_rooms_by_department'),
]