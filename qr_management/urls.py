
from django.urls import path
from . import views

app_name = 'qr_management'

urlpatterns = [
    # ================================
    # MAIN QR MANAGEMENT - CONFIRMED EXISTS
    # ================================
    path('', views.qr_index, name='index'),
    
    # ================================
    # QR CODE GENERATION - CONFIRMED EXISTS
    # ================================
    path('generate/<str:device_id>/', views.qr_generate, name='qr_generate'),
    path('bulk-generate/', views.qr_bulk_generate, name='qr_bulk_generate'),
    path('print-labels/', views.qr_print_labels, name='qr_print_labels'),
    
    # ================================
    # QR CODE VERIFICATION AND SCANNING - CONFIRMED EXISTS
    # ================================
    path('verify/<str:device_id>/', views.qr_verify, name='qr_verify'),
    path('scan/mobile/', views.qr_scan_mobile, name='qr_scan_mobile'),
    path('scan/history/', views.qr_scan_history, name='scan_history'),
    path('scan/<str:scan_id>/', views.qr_scan_detail, name='qr_scan_detail'),
    path('batch-verify/', views.qr_batch_verify, name='qr_batch_verify'),
    
    # ================================
    # ANALYTICS AND REPORTING - CONFIRMED EXISTS
    # ================================
    path('analytics/', views.qr_analytics, name='qr_analytics'),
]
