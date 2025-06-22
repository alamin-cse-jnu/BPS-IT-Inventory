"""
URL configuration for BPS IT Inventory Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def home_view(request):
    return HttpResponse("""
    <h1>🏛️ BPS IT Inventory Management System</h1>
    <h2>Welcome to Bangladesh Parliament Secretary (IT) Inventory System</h2>
    <p>System Version: 1.0.0</p>
    <ul>
        <li><a href="/admin/">Admin Panel</a></li>
        <li><a href="/inventory/">Inventory Management</a></li>
        <li><a href="/reports/">Reports</a></li>
        <li><a href="/qr/">QR Code Management</a></li>
    </ul>
    """)

urlpatterns = [
    # Home page
    path('', home_view, name='home'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Main applications (we'll create these URLs next)
    path('inventory/', include('inventory.urls')),
    path('auth/', include('authentication.urls')),
    path('reports/', include('reports.urls')),
    path('qr/', include('qr_management.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "BPS IT Inventory Management"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Welcome to BPS IT Inventory Management System"