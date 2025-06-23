# reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Main reports dashboard
    path('', views.reports_dashboard, name='dashboard'),
    
    # Standard reports
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('assignments/', views.assignment_report, name='assignment_report'),
    path('maintenance/', views.maintenance_report, name='maintenance_report'),
    path('audit/', views.audit_report, name='audit_report'),
    path('warranty/', views.warranty_report, name='warranty_report'),
    path('department-utilization/', views.department_utilization_report, name='department_utilization'),
    
    # Custom report generation
    path('custom/', views.generate_custom_report, name='generate_custom_report'),
    
    # AJAX endpoints
    path('ajax/progress/<int:report_id>/', views.ajax_report_progress, name='ajax_report_progress'),
]