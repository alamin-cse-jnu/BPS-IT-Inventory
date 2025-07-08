# bps_inventory/context_processors.py
"""
Context processors for BPS IT Inventory Management System.
Provides global template variables and settings.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q


def bps_settings(request):
    """
    Add BPS system settings to template context.
    Makes configuration values available in all templates.
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


def user_context(request):
    """
    Add user-related context variables.
    Provides user profile and permission information.
    """
    context = {
        'user_full_name': '',
        'user_role': '',
        'user_department': '',
        'user_permissions': {},
        'is_authenticated': request.user.is_authenticated,
    }
    
    if request.user.is_authenticated:
        try:
            # Get user's full name
            if hasattr(request.user, 'first_name') and hasattr(request.user, 'last_name'):
                context['user_full_name'] = f"{request.user.first_name} {request.user.last_name}".strip()
            
            if not context['user_full_name']:
                context['user_full_name'] = request.user.username
            
            # Get user's staff profile if exists
            if hasattr(request.user, 'staff_profile'):
                staff_profile = request.user.staff_profile
                context['user_role'] = staff_profile.role if hasattr(staff_profile, 'role') else 'Staff'
                context['user_department'] = staff_profile.department.name if hasattr(staff_profile, 'department') and staff_profile.department else 'N/A'
                
                # Get user permissions from role
                if hasattr(staff_profile, 'role_permissions'):
                    context['user_permissions'] = staff_profile.role_permissions
            
            # Check if user is superuser
            if request.user.is_superuser:
                context['user_role'] = 'System Administrator'
                context['user_permissions'] = {
                    'can_view_all_devices': True,
                    'can_manage_assignments': True,
                    'can_approve_requests': True,
                    'can_generate_reports': True,
                    'can_manage_users': True,
                    'can_system_admin': True,
                    'can_manage_maintenance': True,
                    'can_manage_vendors': True,
                    'can_bulk_operations': True,
                    'can_export_data': True,
                    'can_view_financial_data': True,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': True,
                }
                
        except Exception as e:
            # Fallback in case of errors
            context['user_full_name'] = request.user.username
            context['user_role'] = 'User'
            context['user_department'] = 'N/A'
    
    return context


def navigation_context(request):
    """
    Add navigation-related context variables.
    Provides menu items and navigation state.
    """
    context = {
        'nav_items': [],
        'current_app': '',
        'current_view': '',
        'breadcrumbs': [],
    }
    
    if request.user.is_authenticated:
        # Get current app and view
        if hasattr(request, 'resolver_match') and request.resolver_match:
            context['current_app'] = request.resolver_match.app_name or ''
            context['current_view'] = request.resolver_match.url_name or ''
        
        # Build navigation items based on user permissions
        nav_items = []
        
        # Dashboard (always available for authenticated users)
        nav_items.append({
            'name': 'Dashboard',
            'url': '/inventory/',
            'icon': 'fas fa-tachometer-alt',
            'active': context['current_app'] == 'inventory' and context['current_view'] == 'dashboard',
        })
        
        # Devices management
        nav_items.append({
            'name': 'Devices',
            'url': '/inventory/devices/',
            'icon': 'fas fa-desktop',
            'active': context['current_app'] == 'inventory' and 'device' in context['current_view'],
            'submenu': [
                {'name': 'All Devices', 'url': '/inventory/devices/'},
                {'name': 'Add Device', 'url': '/inventory/devices/add/'},
                {'name': 'Categories', 'url': '/inventory/categories/'},
            ]
        })
        
        # Assignments management
        nav_items.append({
            'name': 'Assignments',
            'url': '/inventory/assignments/',
            'icon': 'fas fa-hand-paper',
            'active': context['current_app'] == 'inventory' and 'assignment' in context['current_view'],
            'submenu': [
                {'name': 'All Assignments', 'url': '/inventory/assignments/'},
                {'name': 'Create Assignment', 'url': '/inventory/assignments/add/'},
                {'name': 'Overdue Items', 'url': '/inventory/assignments/overdue/'},
            ]
        })
        
        # Reports (if user has permission)
        user_permissions = context.get('user_permissions', {})
        if user_permissions.get('can_generate_reports', False) or request.user.is_superuser:
            nav_items.append({
                'name': 'Reports',
                'url': '/reports/',
                'icon': 'fas fa-chart-bar',
                'active': context['current_app'] == 'reports',
                'submenu': [
                    {'name': 'Device Reports', 'url': '/reports/devices/'},
                    {'name': 'Assignment Reports', 'url': '/reports/assignments/'},
                    {'name': 'Maintenance Reports', 'url': '/reports/maintenance/'},
                ]
            })
        
        # QR Management
        nav_items.append({
            'name': 'QR Codes',
            'url': '/qr/',
            'icon': 'fas fa-qrcode',
            'active': context['current_app'] == 'qr_management',
        })
        
        # Administration (if user has permission)
        if user_permissions.get('can_manage_users', False) or request.user.is_superuser:
            nav_items.append({
                'name': 'Administration',
                'url': '/auth/users/',
                'icon': 'fas fa-cogs',
                'active': context['current_app'] == 'authentication' and 'user' in context['current_view'],
                'submenu': [
                    {'name': 'Users', 'url': '/auth/users/'},
                    {'name': 'Roles', 'url': '/auth/roles/'},
                    {'name': 'Departments', 'url': '/auth/departments/'},
                ]
            })
        
        context['nav_items'] = nav_items
    
    return context


def notification_context(request):
    """
    Add notification context for authenticated users.
    Provides notification counts and recent notifications.
    """
    context = {
        'notifications': [],
        'unread_notifications': 0,
        'total_notifications': 0,
        'has_notifications': False,
    }
    
    if request.user.is_authenticated:
        try:
            # Cache key for user notifications
            cache_key = f'user_notifications_{request.user.id}'
            cached_notifications = cache.get(cache_key)
            
            if cached_notifications is None:
                # Get recent notifications (you can implement a proper notification system)
                notifications = []
                
                # Example: Check for overdue assignments
                try:
                    from inventory.models import Assignment
                    today = timezone.now().date()
                    
                    # User's overdue assignments
                    if hasattr(request.user, 'staff_profile'):
                        overdue_assignments = Assignment.objects.filter(
                            assigned_to_staff=request.user.staff_profile,
                            is_active=True,
                            is_temporary=True,
                            expected_return_date__lt=today,
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
                    user_permissions = context.get('user_permissions', {})
                    if user_permissions.get('can_manage_maintenance', False) or request.user.is_superuser:
                        try:
                            from inventory.models import Device
                            devices_needing_maintenance = Device.objects.filter(
                                status='NEEDS_MAINTENANCE'
                            ).count()
                            
                            if devices_needing_maintenance > 0:
                                notifications.append({
                                    'type': 'info',
                                    'title': 'Maintenance Required',
                                    'message': f'{devices_needing_maintenance} device(s) need maintenance',
                                    'url': '/inventory/devices/?status=NEEDS_MAINTENANCE',
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


def system_stats_context(request):
    """
    Add system statistics context.
    Provides quick stats for dashboard and sidebar.
    """
    context = {
        'stats': {
            'total_devices': 0,
            'active_assignments': 0,
            'available_devices': 0,
            'maintenance_devices': 0,
            'total_users': 0,
            'recent_assignments': 0,
        }
    }
    
    if request.user.is_authenticated:
        try:
            # Cache key for system stats
            cache_key = 'system_stats'
            cached_stats = cache.get(cache_key)
            
            if cached_stats is None:
                from inventory.models import Device, Assignment
                
                # Get device statistics
                device_stats = Device.objects.aggregate(
                    total=Count('id'),
                    available=Count('id', filter=Q(status='AVAILABLE')),
                    maintenance=Count('id', filter=Q(status='NEEDS_MAINTENANCE')),
                )
                
                # Get assignment statistics
                assignment_stats = Assignment.objects.aggregate(
                    active=Count('id', filter=Q(is_active=True)),
                    recent=Count('id', filter=Q(
                        assigned_date__gte=timezone.now() - timezone.timedelta(days=7)
                    )),
                )
                
                # Get user count
                user_count = User.objects.filter(is_active=True).count()
                
                stats = {
                    'total_devices': device_stats['total'] or 0,
                    'active_assignments': assignment_stats['active'] or 0,
                    'available_devices': device_stats['available'] or 0,
                    'maintenance_devices': device_stats['maintenance'] or 0,
                    'total_users': user_count,
                    'recent_assignments': assignment_stats['recent'] or 0,
                }
                
                # Cache stats for 10 minutes
                cache.set(cache_key, stats, 600)
                cached_stats = stats
            
            context['stats'] = cached_stats
            
        except Exception as e:
            # Fallback to zero stats on error
            pass
    
    return context