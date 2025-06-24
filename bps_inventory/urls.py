# bps_inventory/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def home_view(request):
    """Enhanced home view with quick stats"""
    from inventory.models import Device, Assignment
    from inventory.utils import get_device_assignment_summary, get_warranty_alerts
    
    # Get quick statistics
    summary = get_device_assignment_summary()
    warranty_alerts = get_warranty_alerts()[:5]
    recent_assignments = Assignment.objects.select_related(
        'device', 'assigned_to_staff'
    ).order_by('-created_at')[:5]
    
    context = {
        'summary': summary,
        'warranty_alerts': warranty_alerts,
        'recent_assignments': recent_assignments,
    }
    
    return render(request, 'home.html', context)

def public_qr_verify(request, device_id):
    """Public QR verification endpoint"""
    from qr_management.views import qr_verify
    return qr_verify(request, device_id)

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