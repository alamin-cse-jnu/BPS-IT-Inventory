# inventory/context_processors.py
"""
Context processors for BPS IT Inventory Management System.
Legacy compatibility module - provides backward compatibility.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q


def bps_settings(request):
    """
    Legacy BPS system settings context processor.
    Provides basic system configuration variables.
    """
    return {
        'BPS_SYSTEM_NAME': getattr(settings, 'BPS_SYSTEM_NAME', 'BPS IT Inventory Management System'),
        'BPS_VERSION': getattr(settings, 'BPS_VERSION', '1.0.0'),
        'BPS_ORGANIZATION': getattr(settings, 'BPS_ORGANIZATION', 'Bangladesh Parliament Secretariat'),
        'BPS_CONTACT_EMAIL': getattr(settings, 'BPS_CONTACT_EMAIL', 'it@parliament.gov.bd'),
        'BPS_ADMIN_NAME': getattr(settings, 'BPS_ADMIN_NAME', 'System Administrator'),
        'QR_CODE_BASE_URL': getattr(settings, 'QR_CODE_BASE_URL', 'http://127.0.0.1:8000'),
        'CURRENT_YEAR': timezone.now().year,
        'CURRENT_DATE': timezone.now().date(),
        'DEBUG': settings.DEBUG,
    }


def notification_context(request):
    """
    Legacy notification context processor.
    Provides system notifications and alerts for authenticated users.
    """
    context = {
        'notifications': [],
        'unread_notifications': 0,
        'total_notifications': 0,
        'has_notifications': False,
        'system_alerts': [],
    }
    
    if request.user.is_authenticated:
        try:
            # Use caching to avoid repeated database queries
            cache_key = f"notifications_{request.user.id}"
            cached_notifications = cache.get(cache_key)
            
            if cached_notifications is None:
                notifications = []
                
                # Check for overdue assignments for current user
                try:
                    if hasattr(request.user, 'staff_profile'):
                        from inventory.models import Assignment
                        
                        overdue_assignments = Assignment.objects.filter(
                            assigned_to_staff=request.user.staff_profile,
                            is_active=True,
                            assignment_type='TEMPORARY',
                            expected_return_date__lt=timezone.now().date(),
                            actual_return_date__isnull=True
                        ).count()
                        
                        if overdue_assignments > 0:
                            notifications.append({
                                'type': 'warning',
                                'title': 'Overdue Assignments',
                                'message': f'You have {overdue_assignments} overdue device(s)',
                                'url': '/inventory/assignments/overdue/',
                                'timestamp': timezone.now(),
                            })
                
                    # Check for devices needing maintenance (if user has permission)
                    if request.user.is_superuser or hasattr(request.user, 'staff_profile'):
                        try:
                            from inventory.models import Device
                            devices_needing_maintenance = Device.objects.filter(
                                status='MAINTENANCE'
                            ).count()
                            
                            if devices_needing_maintenance > 0:
                                notifications.append({
                                    'type': 'info',
                                    'title': 'Maintenance Required',
                                    'message': f'{devices_needing_maintenance} device(s) need maintenance',
                                    'url': '/inventory/devices/?status=MAINTENANCE',
                                    'timestamp': timezone.now(),
                                })
                        except:
                            pass
                
                except Exception:
                    pass
                
                # Cache notifications for 5 minutes
                cache.set(cache_key, notifications, 300)
                cached_notifications = notifications
            
            context['notifications'] = cached_notifications[:10]  # Show only recent 10
            context['unread_notifications'] = len(cached_notifications)
            context['total_notifications'] = len(cached_notifications)
            context['has_notifications'] = len(cached_notifications) > 0
            
        except Exception as e:
            # Fallback to empty notifications on error
            pass
    
    return context


def quick_stats(request):
    """
    Legacy quick statistics context processor.
    Provides system-wide statistics for dashboard widgets.
    """
    context = {
        'quick_stats': {
            'total_devices': 0,
            'active_assignments': 0,
            'maintenance_pending': 0,
            'available_devices': 0,
            'total_staff': 0,
            'total_locations': 0,
        }
    }
    
    if request.user.is_authenticated:
        try:
            # Use caching to avoid repeated database queries
            cache_key = "quick_stats"
            cached_stats = cache.get(cache_key)
            
            if cached_stats is None:
                try:
                    from inventory.models import Device, Assignment, Staff, Location
                    
                    stats = {
                        'total_devices': Device.objects.count(),
                        'active_assignments': Assignment.objects.filter(is_active=True).count(),
                        'maintenance_pending': Device.objects.filter(
                            status__in=['MAINTENANCE', 'NEEDS_MAINTENANCE']
                        ).count(),
                        'available_devices': Device.objects.filter(status='AVAILABLE').count(),
                        'total_staff': Staff.objects.filter(is_active=True).count(),
                        'total_locations': Location.objects.filter(is_active=True).count(),
                    }
                    
                    # Cache stats for 10 minutes
                    cache.set(cache_key, stats, 600)
                    cached_stats = stats
                    
                except Exception:
                    # Fallback to empty stats on error
                    cached_stats = {
                        'total_devices': 0,
                        'active_assignments': 0,
                        'maintenance_pending': 0,
                        'available_devices': 0,
                        'total_staff': 0,
                        'total_locations': 0,
                    }
            
            context['quick_stats'] = cached_stats
            
        except Exception as e:
            # Fallback to empty stats on error
            pass
    
    return context


def notifications(request):
    """
    Alias for notification_context to maintain backward compatibility.
    This function exists to prevent ImportError when settings.py references it.
    """
    return notification_context(request)


def system_stats_context(request):
    """
    Legacy system statistics context processor.
    Provides detailed system statistics for dashboard and reports.
    """
    context = {
        'system_stats': {
            'total_devices': 0,
            'active_assignments': 0,
            'pending_maintenance': 0,
            'total_locations': 0,
            'total_staff': 0,
            'total_vendors': 0,
            'devices_by_status': {},
            'recent_activities': 0,
        },
        'last_updated': timezone.now(),
    }
    
    if request.user.is_authenticated:
        try:
            # Use caching to avoid repeated database queries
            cache_key = "system_stats"
            cached_stats = cache.get(cache_key)
            
            if cached_stats is None:
                try:
                    from inventory.models import Device, Assignment, Location, Staff, Vendor
                    
                    # Device statistics by status
                    device_status_counts = Device.objects.values('status').annotate(
                        count=Count('device_id')
                    )
                    devices_by_status = {item['status']: item['count'] for item in device_status_counts}
                    
                    stats = {
                        'total_devices': Device.objects.count(),
                        'active_assignments': Assignment.objects.filter(is_active=True).count(),
                        'pending_maintenance': Device.objects.filter(status='MAINTENANCE').count(),
                        'total_locations': Location.objects.filter(is_active=True).count(),
                        'total_staff': Staff.objects.filter(is_active=True).count(),
                        'total_vendors': Vendor.objects.filter(is_active=True).count(),
                        'devices_by_status': devices_by_status,
                        'recent_activities': Assignment.objects.filter(
                            assignment_date__gte=timezone.now().date() - timezone.timedelta(days=7)
                        ).count(),
                    }
                    
                    # Cache stats for 15 minutes
                    cache.set(cache_key, stats, 900)
                    cached_stats = stats
                    
                except Exception:
                    # Fallback to empty stats on error
                    cached_stats = {
                        'total_devices': 0,
                        'active_assignments': 0,
                        'pending_maintenance': 0,
                        'total_locations': 0,
                        'total_staff': 0,
                        'total_vendors': 0,
                        'devices_by_status': {},
                        'recent_activities': 0,
                    }
            
            context['system_stats'] = cached_stats
            
        except Exception as e:
            # Fallback to empty stats on error
            pass
    
    return context