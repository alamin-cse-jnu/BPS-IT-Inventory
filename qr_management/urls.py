# qr_management/urls.py
from django.urls import path
from . import views

app_name = 'qr_management'

urlpatterns = [
    # QR Code generation
    path('generate/<str:device_id>/', views.qr_generate, name='qr_generate'),
    path('bulk-generate/', views.qr_bulk_generate, name='qr_bulk_generate'),
    path('print-labels/', views.qr_print_labels, name='qr_print_labels'),
    
    # QR Code verification and scanning
    path('verify/<str:device_id>/', views.qr_verify, name='qr_verify'),
    path('scan/mobile/', views.qr_scan_mobile, name='qr_scan_mobile'),
    path('scan/history/', views.qr_scan_history, name='qr_scan_history'),
    path('scan/<int:scan_id>/', views.qr_scan_detail, name='qr_scan_detail'),
    path('batch-verify/', views.qr_batch_verify, name='qr_batch_verify'),
    
    # Analytics and reporting
    path('analytics/', views.qr_analytics, name='qr_analytics'),
    
    # Main QR management page
    path('', views.qr_index, name='index'),
]