

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # ================================
    # MAIN DASHBOARD
    # ================================
    path('', views.dashboard, name='dashboard'),
    
    # ================================
    # DEVICE MANAGEMENT
    # ================================
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_add'),
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<int:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<int:device_id>/qr/', views.device_qr_code, name='device_qr_code'),
    path('devices/<int:device_id>/history/', views.device_history, name='device_history'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/add/', views.assignment_create, name='assignment_add'),
    path('assignments/<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<int:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<int:assignment_id>/extend/', views.assignment_extend, name='assignment_extend'),
    path('assignments/<int:assignment_id>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/bulk/create/', views.bulk_assignment_create, name='bulk_assignment_create'),
    path('assignments/overdue/', views.overdue_assignments_list, name='overdue_assignments_list'),
    
    # ================================
    # STAFF MANAGEMENT
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_add'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:staff_id>/delete/', views.staff_delete, name='staff_delete'),
    path('staff/<int:staff_id>/assignments/', views.staff_assignments, name='staff_assignments'),
    
    # ================================
    # DEPARTMENT MANAGEMENT
    # ================================
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_add'),
    path('departments/<int:department_id>/', views.department_detail, name='department_detail'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:department_id>/assignments/', views.department_assignments, name='department_assignments'),
    
    # ================================
    # LOCATION MANAGEMENT
    # ================================
    path('locations/', views.location_list, name='location_list'),
    path('locations/add/', views.location_create, name='location_add'),
    path('locations/<int:location_id>/', views.location_detail, name='location_detail'),
    path('locations/<int:location_id>/edit/', views.location_edit, name='location_edit'),
    path('locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),
    
    # ================================
    # VENDOR MANAGEMENT
    # ================================
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/add/', views.vendor_create, name='vendor_add'),
    path('vendors/<int:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<int:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    
    # ================================
    # MAINTENANCE MANAGEMENT
    # ================================
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.maintenance_create, name='maintenance_add'),
    path('maintenance/<int:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<int:maintenance_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<int:maintenance_id>/complete/', views.maintenance_complete, name='maintenance_complete'),
    
    # ================================
    # DEVICE TYPE MANAGEMENT
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/add/', views.device_type_create, name='device_type_add'),
    path('device-types/<int:type_id>/', views.device_type_detail, name='device_type_detail'),
    path('device-types/<int:type_id>/edit/', views.device_type_edit, name='device_type_edit'),
    path('device-types/<int:type_id>/delete/', views.device_type_delete, name='device_type_delete'),
    
    # ================================
    # IMPORT/EXPORT
    # ================================
    path('import/', views.bulk_import, name='bulk_import'),
    path('import/devices/', views.import_devices_csv, name='import_devices_csv'),
    path('import/staff/', views.import_staff_csv, name='import_staff_csv'),
    path('export/', views.bulk_export, name='bulk_export'),
    path('export/devices/', views.export_devices_csv, name='export_devices_csv'),
    path('export/assignments/', views.export_assignments_csv, name='export_assignments_csv'),
    path('export/maintenance/', views.export_maintenance_csv, name='export_maintenance_csv'),
    path('import/template/', views.import_template, name='import_template'),
    
    # ================================
    # SEARCH AND FILTERS
    # ================================
    path('search/', views.global_search, name='global_search'),
    path('search/advanced/', views.advanced_search, name='advanced_search'),
    path('api/search/', views.global_search_api, name='global_search_api'),
    
    # ================================
    # DASHBOARD ANALYTICS API
    # ================================
    path('api/dashboard/stats/', views.ajax_dashboard_stats, name='ajax_dashboard_stats'),
    path('api/notifications/', views.ajax_notification_list, name='ajax_notification_list'),
    path('api/device-stats/', views.ajax_device_stats, name='ajax_device_stats'),
    
    # ================================
    # AJAX ENDPOINTS FOR DYNAMIC FORMS
    # ================================
    path('api/subcategories/', views.ajax_subcategories_by_category, name='ajax_subcategories_by_category'),
    path('api/device-types/', views.ajax_device_types_by_subcategory, name='ajax_device_types_by_subcategory'),
    path('api/device/<str:device_id>/info/', views.get_device_info, name='get_device_info'),
    path('api/device/assign/', views.quick_assign_device, name='quick_assign_device'),
    path('api/search/suggestions/', views.search_suggestions, name='search_suggestions'),
    path('api/device/availability/', views.device_availability_check, name='device_availability_check'),
    path('api/staff/department/<int:department_id>/', views.get_staff_by_department, name='get_staff_by_department'),
    path('api/rooms/building/<int:building_id>/', views.get_rooms_by_building, name='get_rooms_by_building'),
    path('api/locations/room/<int:room_id>/', views.get_locations_by_room, name='get_locations_by_room'),
]