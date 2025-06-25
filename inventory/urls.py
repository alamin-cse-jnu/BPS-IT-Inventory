from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard and main pages
    path('', views.dashboard, name='dashboard'),
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_add, name='device_add'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/edit/', views.device_edit, name='device_edit'),
    path('devices/<str:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/bulk/actions/', views.device_bulk_actions, name='device_bulk_actions'),
    path('devices/export/csv/', views.device_export_csv, name='device_export_csv'),
    
    # Assignment URLs
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/<str:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/create/<str:device_id>/', views.assignment_create, name='assignment_create_device'),
    path('assignments/<str:assignment_id>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/<str:assignment_id>/return/', views.assignment_return, name='assignment_return'),
    path('assignments/bulk/create/', views.bulk_assignment, name='bulk_assignment'),
    path('assignments/overdue/', views.overdue_assignments, name='overdue_assignments'),
    
    # Staff and Department assignments
    path('staff/<str:staff_id>/assignments/', views.staff_assignments, name='staff_assignments'),
    path('departments/<int:department_id>/assignments/', views.department_assignments, name='department_assignments'),
    
    # Device Types
    path('device-types/', views.device_type_list, name='device_type_list'),
    path('device-types/add/', views.device_type_create, name='device_type_create'),
    
    # AJAX endpoints
    path('ajax/subcategories/', views.ajax_get_subcategories, name='ajax_subcategories'),
    path('ajax/device-types/', views.ajax_get_device_types, name='ajax_device_types'),
    path('ajax/device/<str:device_id>/info/', views.ajax_device_quick_info, name='ajax_device_info'),
    path('ajax/locations/by-room/', views.ajax_get_locations_by_room, name='ajax_locations_by_room'),
    path('ajax/assignments/<str:assignment_id>/actions/', views.ajax_assignment_quick_actions, name='ajax_assignment_actions'),
    
    # API endpoints
    path('api/device/<str:device_id>/info/', views.get_device_info, name='get_device_info'),
    path('api/assign/', views.quick_assign_device, name='quick_assign_device'),
]