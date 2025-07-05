

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

# URL patterns
urlpatterns = [
    # ================================
    # MAIN SYSTEM URLS - CONFIRMED EXISTS
    # ================================
    
    # Home page
    path('', views.home_view, name='home'),
    
    # System utilities - ALL CONFIRMED TO EXIST
    path('health/', views.system_health_check, name='system_health'),
    path('status/', views.system_status, name='system_status'),
    path('api/docs/', views.api_documentation, name='api_docs'),
    
    # ================================
    # ADMIN
    # ================================
    path('admin/', admin.site.urls),
    
    # ================================
    # AUTHENTICATION
    # ================================
    path('auth/', include('authentication.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # Built-in auth views
    
    # ================================
    # MAIN APPLICATIONS
    # ================================
    path('inventory/', include('inventory.urls')),
    path('reports/', include('reports.urls')),
    path('qr/', include('qr_management.urls')),
    
    # ================================
    # PUBLIC ENDPOINTS - CONFIRMED EXISTS
    # ================================
    
    # Public QR verification (no login required)
    path('verify/<str:device_id>/', views.public_qr_verify, name='public_qr_verify'),
    
    # ================================
    # FUTURE API ENDPOINTS
    # ================================
    # path('api/v1/', include('api.urls')),  # For future mobile app API
]

# ================================
# DEVELOPMENT CONFIGURATIONS
# ================================

# Add Django Debug Toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        # Debug toolbar not installed
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Welcome to BPS IT Inventory Management System"

# ================================
# ERROR HANDLERS
# ================================

def handler404(request, exception):
    """Custom 404 error handler"""
    from django.shortcuts import render
    return render(request, 'errors/404.html', {
        'error_code': '404',
        'error_title': 'Page Not Found',
        'error_message': 'The page you are looking for could not be found.',
        'system_name': 'BPS IT Inventory Management System',
    }, status=404)

def handler500(request):
    """Custom 500 error handler"""
    from django.shortcuts import render
    return render(request, 'errors/500.html', {
        'error_code': '500',
        'error_title': 'Internal Server Error',
        'error_message': 'An internal server error occurred. Please try again later.',
        'system_name': 'BPS IT Inventory Management System',
    }, status=500)

def handler403(request, exception):
    """Custom 403 error handler"""
    from django.shortcuts import render
    return render(request, 'errors/403.html', {
        'error_code': '403',
        'error_title': 'Access Forbidden',
        'error_message': 'You do not have permission to access this resource.',
        'system_name': 'BPS IT Inventory Management System',
    }, status=403)

def handler400(request, exception):
    """Custom 400 error handler"""
    from django.shortcuts import render
    return render(request, 'errors/400.html', {
        'error_code': '400',
        'error_title': 'Bad Request',
        'error_message': 'Your request could not be processed due to invalid data.',
        'system_name': 'BPS IT Inventory Management System',
    }, status=400)

