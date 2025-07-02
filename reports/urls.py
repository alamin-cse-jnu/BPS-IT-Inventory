# reports/urls.py
# Location: bps_inventory/apps/reports/urls.py
# COMPLETE: All views verified to exist in reports/views.py

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # ================================
    # MAIN REPORTS DASHBOARD - CONFIRMED EXISTS
    # ================================
    path('', views.reports_dashboard, name='dashboard'),
    
    # ================================
    # STANDARD REPORTS - CONFIRMED EXISTS
    # ================================
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('assignments/', views.assignment_report, name='assignment_report'),
    path('maintenance/', views.maintenance_report, name='maintenance_report'),
    path('audit/', views.audit_report, name='audit_report'),
    path('warranty/', views.warranty_report, name='warranty_report'),
    path('department-utilization/', views.department_utilization_report, name='department_utilization'),
    
    # ================================
    # CUSTOM REPORT GENERATION - CONFIRMED EXISTS
    # ================================
    path('custom/', views.generate_custom_report, name='generate_custom_report'),
    
    # ================================
    # AJAX ENDPOINTS - CONFIRMED EXISTS
    # ================================
    path('ajax/progress/<str:report_id>/', views.ajax_report_progress, name='ajax_report_progress'),
]
