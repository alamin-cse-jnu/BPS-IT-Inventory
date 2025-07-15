# inventory/urls.py
# Location: bps_inventory/apps/inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # ================================
    # DASHBOARD AND HOME
    # ================================
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # ================================
    # DEVICE MANAGEMENT
    # ================================
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_create'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<str:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<str:device_id>/qr-code/', views.device_qr_code, name='device_qr_code'),
    path('devices/<str:device_id>/history/', views.device_history, name='device_history'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/add/', views.assignment_create, name='assignment_create'),
    path('assignments/<str:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<str:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<str:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<str:assignment_id>/delete/', views.assignment_delete, name='assignment_delete'),
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
    # STAFF MANAGEMENT
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_create'),
    path('staff/<str:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<str:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<str:staff_id>/delete/', views.staff_delete, name='staff_delete'),
    path('staff/<str:staff_id>/assignments/', views.staff_assignments, name='staff_assignments'),
    
    # Staff Management AJAX endpoints
    path('ajax/generate-employee-id/', views.ajax_generate_employee_id, name='ajax_generate_employee_id'),
    path('ajax/check-employee-id/', views.ajax_check_employee_id, name='ajax_check_employee_id'),
    path('ajax/staff-search/', views.ajax_staff_search, name='ajax_staff_search'),

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
    # DEPARTMENT MANAGEMENT
    # ================================
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_add'),
    path('departments/<str:department_id>/', views.department_detail, name='department_detail'),
    path('departments/<str:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<str:department_id>/delete/', views.department_delete, name='department_delete'),
    path('departments/<str:department_id>/assignments/', views.department_assignments, name='department_assignments'),
    
    # ================================
    # ROOM MANAGEMENT
    # ================================
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/add/', views.room_create, name='room_add'),
    path('rooms/<str:room_id>/', views.room_detail, name='room_detail'),
    path('rooms/<str:room_id>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<str:room_id>/delete/', views.room_delete, name='room_delete'),
    
    # ================================
    # LOCATION MANAGEMENT
    # ================================
    path('locations/', views.location_list, name='location_list'),
    path('locations/add/', views.location_create, name='location_add'),
    path('locations/<str:location_id>/', views.location_detail, name='location_detail'),
    path('locations/<str:location_id>/edit/', views.location_edit, name='location_edit'),
    path('locations/<str:location_id>/delete/', views.location_delete, name='location_delete'),
    
    # ================================
    # DEVICE TYPES MANAGEMENT
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/add/', views.device_type_create, name='device_type_create'),
    path('device-types/<str:type_id>/', views.device_type_detail, name='device_type_detail'),
    path('device-types/<str:type_id>/edit/', views.device_type_edit, name='device_type_edit'),
    path('device-types/<str:type_id>/delete/', views.device_type_delete, name='device_type_delete'),
    
    # ================================
    # VENDOR MANAGEMENT
    # ================================
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/add/', views.vendor_create, name='vendor_create'),
    path('vendors/<str:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<str:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    path('vendors/<str:vendor_id>/delete/', views.vendor_delete, name='vendor_delete'),
    
    # ================================
    # MAINTENANCE MANAGEMENT
    # ================================
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.maintenance_create, name='maintenance_create'),
    path('maintenance/<str:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<str:maintenance_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<str:maintenance_id>/delete/', views.maintenance_delete, name='maintenance_delete'),
    
    # ================================
    # BULK OPERATIONS
    # ================================
    path('bulk/actions/', views.bulk_actions, name='bulk_actions'),
    path('bulk/import/', views.bulk_import, name='bulk_import'),
    path('bulk/export/', views.bulk_export, name='bulk_export'),
    path('bulk/assignment/', views.bulk_assignment, name='bulk_assignment'),
    path('bulk/qr-generate/', views.bulk_qr_generate, name='bulk_qr_generate'),
    
    # ================================
    # SEARCH FUNCTIONALITY
    # ================================
    path('search/', views.global_search, name='global_search'),
    path('search/devices/', views.device_search, name='device_search'),
    path('search/assignments/', views.assignment_search, name='assignment_search'),
    path('search/advanced/', views.advanced_search, name='advanced_search'),
    
    # ================================
    # CASCADE API ENDPOINTS
    # ================================
    path('api/blocks/by-building/<str:building_id>/', views.api_blocks_by_building, name='api_blocks_by_building'),
    path('api/floors/by-block/<str:block_id>/', views.api_floors_by_block, name='api_floors_by_block'),
    path('api/floors/by-building/<str:building_id>/', views.api_floors_by_building, name='api_floors_by_building'),
    path('api/departments/by-floor/<str:floor_id>/', views.api_departments_by_floor, name='api_departments_by_floor'),
    path('api/departments/by-building/<str:building_id>/', views.api_departments_by_building, name='api_departments_by_building'),
    path('api/departments/by-block/<str:block_id>/', views.api_departments_by_block, name='api_departments_by_block'),
    path('api/rooms/by-department/<str:department_id>/', views.api_rooms_by_department, name='api_rooms_by_department'),
    path('api/rooms/by-floor/<str:floor_id>/', views.api_rooms_by_floor, name='api_rooms_by_floor'),
    path('api/rooms/by-building/<str:building_id>/', views.api_rooms_by_building, name='api_rooms_by_building'),
    path('api/locations/by-building/<str:building_id>/', views.api_locations_by_building, name='api_locations_by_building'),
    path('api/locations/by-department/<str:department_id>/', views.api_locations_by_department, name='api_locations_by_department'),
    
    # ================================
    # VALIDATION AND SEARCH APIs
    # ================================
    path('api/hierarchy/validate/', views.api_validate_hierarchy, name='api_hierarchy_validate'),
    path('api/locations/search/', views.api_location_search, name='api_location_search'),
    path('api/hierarchy/stats/', views.api_hierarchy_stats, name='api_hierarchy_stats'),
    
    # ================================
    # AJAX ENDPOINTS
    # ================================
    path('ajax/get-subcategories/', views.ajax_subcategories_by_category, name='ajax_get_subcategories'), 
    path('ajax/get-device-types/', views.ajax_device_types_by_subcategory, name='ajax_get_device_types'),  
    path('ajax/device-stats/<str:device_id>/', views.ajax_device_stats, name='ajax_device_stats'),
    path('ajax/assignment-quick-actions/<str:assignment_id>/', views.ajax_assignment_quick_actions, name='ajax_assignment_quick_actions'),
    path('ajax/validate-hierarchy/', views.api_validate_hierarchy, name='ajax_validate_hierarchy'),
    # path('ajax/suggest-block-code/', views.ajax_suggest_block_code, name='ajax_suggest_block_code'),
    # path('ajax/location-breadcrumb/', views.ajax_location_breadcrumb, name='ajax_location_breadcrumb'),
    
    # ================================
    # LOCATION-SPECIFIC REPORTS
    # ================================
    #path('reports/location-utilization/', views.location_utilization_report, name='location_utilization_report'),
    #path('reports/hierarchy-breakdown/', views.hierarchy_breakdown_report, name='hierarchy_breakdown_report'),
    #path('reports/space-analysis/', views.space_analysis_report, name='space_analysis_report'),
    
    # ================================
    # HIERARCHY OVERVIEW
    # ================================
    path('hierarchy/overview/', views.location_hierarchy_overview, name='hierarchy_overview'),

    # ================================
    # SYSTEM UTILITIES
    # ================================
    path('system/statistics/', views.system_statistics, name='system_statistics'),
    path('audit/logs/', views.audit_log_list, name='audit_log_list'),
]