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
    path('devices/add/', views.device_add, name='device_add'),
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<int:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<int:device_id>/qr/', views.device_qr_code, name='device_qr_code'),
    path('devices/<int:device_id>/history/', views.device_history, name='device_history'),
    
    # ================================
    # ASSIGNMENT MANAGEMENT
    # ================================
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/add/', views.assignment_add, name='assignment_add'),
    path('assignments/<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<int:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/<int:assignment_id>/extend/', views.assignment_extend, name='assignment_extend'),
    
    # ================================
    # STAFF MANAGEMENT
    # ================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_add, name='staff_add'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:staff_id>/delete/', views.staff_delete, name='staff_delete'),
    
    # ================================
    # VENDOR MANAGEMENT
    # ================================
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/add/', views.vendor_add, name='vendor_add'),
    path('vendors/<int:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<int:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    
    # ================================
    # MAINTENANCE MANAGEMENT
    # ================================
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/<int:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<int:maintenance_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<int:maintenance_id>/complete/', views.maintenance_complete, name='maintenance_complete'),
    
    # ================================
    # DEVICE TYPE MANAGEMENT
    # ================================
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/add/', views.device_type_add, name='device_type_add'),
    path('device-types/<int:type_id>/edit/', views.device_type_edit, name='device_type_edit'),
    
    # ================================
    # IMPORT/EXPORT
    # ================================
    path('import/', views.bulk_import, name='bulk_import'),
    path('export/', views.bulk_export, name='bulk_export'),
    path('import/template/', views.import_template, name='import_template'),
    
    # ================================
    # SEARCH AND FILTERS
    # ================================
    path('search/', views.global_search, name='global_search'),
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
    
    # ================================
    # BACKUP & RECOVERY
    # ================================
    path('backup/', views.database_backup, name='database_backup'),
    path('restore/', views.database_restore, name='database_restore'),
    path('backup/delete/<str:backup_filename>/', views.delete_backup, name='delete_backup'),
    
    # ================================
    # INVENTORY SPECIFIC REPORTS (NOT MAINTENANCE REPORT)
    # ================================
    path('reports/summary/', views.inventory_summary_report, name='inventory_summary_report'),
    path('reports/utilization/', views.asset_utilization_report, name='asset_utilization_report'),
    path('reports/lifecycle/', views.device_lifecycle_report, name='device_lifecycle_report'),
    path('reports/warranty/', views.warranty_report, name='warranty_report'),
    path('reports/assignment/', views.assignment_report, name='assignment_report'),
    path('reports/audit/', views.audit_report, name='audit_report'),
    
    # NOTE: maintenance_report is handled by the reports app, not inventory app
]