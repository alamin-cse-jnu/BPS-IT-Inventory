# bps_inventory/urls.py - Updated Main URL Configuration
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, date

@login_required
def home_view(request):
    """Enhanced home view with quick stats"""
    try:
        from inventory.models import Device, Assignment
        from inventory.utils import get_device_assignment_summary, get_warranty_alerts
        
        # Get quick statistics with error handling
        try:
            summary = get_device_assignment_summary()
        except Exception as e:
            print(f"Error getting device assignment summary: {e}")
            # Fallback summary calculation
            summary = {
                'total_devices': Device.objects.count(),
                'active_assignments': Assignment.objects.filter(is_active=True).count(),
                'available_devices': Device.objects.filter(status='AVAILABLE').count(),
                'overdue_assignments': 0  # Safe fallback
            }
        
        # Get warranty alerts with proper error handling
        try:
            warranty_alerts = get_warranty_alerts()[:5]  # Get only first 5
        except Exception as e:
            print(f"Error getting warranty alerts: {e}")
            warranty_alerts = []
        
        # Get recent assignments
        try:
            recent_assignments = Assignment.objects.select_related(
                'device', 'assigned_to_staff', 'assigned_to_department'
            ).order_by('-created_at')[:5]
        except Exception as e:
            print(f"Error getting recent assignments: {e}")
            recent_assignments = []
        
        context = {
            'summary': summary,
            'warranty_alerts': warranty_alerts,
            'recent_assignments': recent_assignments,
            'current_date': timezone.now().date(),
        }
        
        return render(request, 'home.html', context)
        
    except ImportError as e:
        print(f"Import error in home view: {e}")
        # Fallback context if models aren't available yet
        context = {
            'summary': {
                'total_devices': 0, 
                'active_assignments': 0, 
                'available_devices': 0, 
                'overdue_assignments': 0
            },
            'warranty_alerts': [],
            'recent_assignments': [],
            'current_date': timezone.now().date(),
        }
        return render(request, 'home.html', context)
    
    except Exception as e:
        print(f"Unexpected error in home view: {e}")
        # Return a basic error page or redirect to login
        return render(request, 'home.html', {
            'summary': {'total_devices': 0, 'active_assignments': 0, 'available_devices': 0, 'overdue_assignments': 0},
            'warranty_alerts': [],
            'recent_assignments': [],
            'current_date': timezone.now().date(),
            'error_message': 'Unable to load dashboard data. Please try refreshing the page.'
        })

def public_qr_verify(request, device_id):
    """Public QR code verification view (no login required)"""
    try:
        from inventory.models import Device
        from qr_management.models import QRCodeScan
        
        device = Device.objects.select_related(
            'device_type__subcategory__category',
            'vendor', 'current_location'
        ).get(device_id=device_id)
        
        # Log the scan
        try:
            QRCodeScan.objects.create(
                device=device,
                scanner_ip=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                scan_type='PUBLIC_VERIFY'
            )
        except:
            pass  # Don't fail if scan logging fails
        
        # Get current assignment
        current_assignment = device.assignments.filter(is_active=True).first()
        
        context = {
            'device': device,
            'current_assignment': current_assignment,
            'scan_time': timezone.now(),
        }
        
        return render(request, 'qr_management/public_verify.html', context)
        
    except Exception as e:
        context = {
            'error': f"Device {device_id} not found or error occurred: {str(e)}",
            'device_id': device_id
        }
        return render(request, 'qr_management/public_verify.html', context)

# URL patterns
urlpatterns = [
    # Home page
    path('', home_view, name='home'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('auth/', include('authentication.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # Built-in auth views
    
    # Main applications
    path('inventory/', include('inventory.urls')),
    path('reports/', include('reports.urls')),
    path('qr/', include('qr_management.urls')),
    
    # Public QR verification (no login required)
    path('verify/<str:device_id>/', public_qr_verify, name='public_qr_verify'),
    
    # API endpoints (for future mobile app)
    # path('api/v1/', include('api.urls')),  # We'll create this later
]

# Add Django Debug Toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Welcome to BPS IT Inventory Management System"

# Error handlers
def handler404(request, exception):
    return render(request, 'errors/404.html', status=404)

def handler500(request):
    return render(request, 'errors/500.html', status=500)

def handler403(request, exception):
    return render(request, 'errors/403.html', status=403)