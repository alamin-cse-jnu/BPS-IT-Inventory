# bps_inventory/urls.py - FIXED VERSION
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, date

@login_required
def home_view(request):
    """Enhanced home view with quick stats - FIXED VERSION"""
    try:
        from inventory.models import Device, Assignment
        from inventory.utils import get_device_assignment_summary, get_warranty_alerts
    except ImportError:
        # Fallback if imports fail
        context = {
            'summary': {'total_devices': 0, 'active_assignments': 0, 'available_devices': 0, 'overdue_assignments': 0},
            'warranty_alerts': [],
            'recent_assignments': [],
            'current_date': timezone.now().date(),
        }
        return render(request, 'home.html', context)
    
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
    
    # FIXED: Get warranty alerts with proper error handling
    try:
        warranty_alerts = get_warranty_alerts()[:5]
        # Ensure each device has proper date objects
        processed_alerts = []
        for device in warranty_alerts:
            # Verify warranty_end_date is a proper date object
            if hasattr(device, 'warranty_end_date'):
                if isinstance(device.warranty_end_date, str):
                    try:
                        # Convert string to date object
                        device.warranty_end_date = datetime.strptime(device.warranty_end_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        # Skip devices with invalid dates
                        continue
                elif device.warranty_end_date is None:
                    # Skip devices without warranty dates
                    continue
            processed_alerts.append(device)
        warranty_alerts = processed_alerts
    except Exception as e:
        print(f"Error in warranty_alerts: {e}")
        warranty_alerts = []
    
    # FIXED: Get recent assignments with proper date handling
    try:
        recent_assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
        ).order_by('-created_at')[:5]
        
        # Process assignments to ensure proper date objects
        processed_assignments = []
        for assignment in recent_assignments:
            # Handle start_date
            if hasattr(assignment, 'start_date') and assignment.start_date:
                if isinstance(assignment.start_date, str):
                    try:
                        assignment.start_date = datetime.strptime(assignment.start_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        assignment.start_date = None
            
            # Handle expected_return_date
            if hasattr(assignment, 'expected_return_date') and assignment.expected_return_date:
                if isinstance(assignment.expected_return_date, str):
                    try:
                        assignment.expected_return_date = datetime.strptime(assignment.expected_return_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        assignment.expected_return_date = None
            
            processed_assignments.append(assignment)
        
        recent_assignments = processed_assignments
        
    except Exception as e:
        print(f"Error in recent_assignments: {e}")
        recent_assignments = []
    
    # Safe context creation
    context = {
        'summary': summary,
        'warranty_alerts': warranty_alerts,
        'recent_assignments': recent_assignments,
        'current_date': timezone.now().date(),  # Always provide current date
        'settings': {
            'BPS_VERSION': getattr(settings, 'BPS_VERSION', '1.0.0'),
            'BPS_ORGANIZATION': getattr(settings, 'BPS_ORGANIZATION', 'Bangladesh Parliament Secretariat'),
        }
    }
    
    return render(request, 'home.html', context)

def public_qr_verify(request, device_id):
    """Public QR verification endpoint"""
    try:
        from qr_management.views import qr_verify
        return qr_verify(request, device_id)
    except ImportError:
        from django.http import HttpResponse
        return HttpResponse("QR verification not available", status=404)

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