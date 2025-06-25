from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('devices/', views.device_list, name='device_list'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('departments/<int:department_id>/assignments/', views.department_assignments, name='department_assignments'),
]