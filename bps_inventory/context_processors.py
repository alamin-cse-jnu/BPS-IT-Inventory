# bps_inventory/context_processors.py
"""
Main context processors for BPS IT Inventory Management System.
Provides global template variables and settings for all templates.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q
from django.urls import resolve, reverse


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
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000'),
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
        'user_initials': '',
        'user_avatar_url': '',
    }
    
    if request.user.is_authenticated:
        try:
            # Get user's full name
            if hasattr(request.user, 'first_name') and hasattr(request.user, 'last_name'):
                context['user_full_name'] = f"{request.user.first_name} {request.user.last_name}".strip()
            
            if not context['user_full_name']:
                context['user_full_name'] = request.user.username
            
            # Generate user initials
            if request.user.first_name and request.user.last_name:
                context['user_initials'] = f"{request.user.first_name[0]}{request.user.last_name[0]}".upper()
            else:
                context['user_initials'] = request.user.username[:2].upper()
            
            # Get user's staff profile if exists
            if hasattr(request.user, 'staff_profile'):
                staff_profile = request.user.staff_profile
                context['user_role'] = staff_profile.designation if hasattr(staff_profile, 'designation') else 'Staff'
                context['user_department'] = staff_profile.department.name if hasattr(staff_profile, 'department') and staff_profile.department else 'N/A'
                
                # Get user permissions from role assignments
                try:
                    from authentication.models import UserRoleAssignment
                    role_assignment = UserRoleAssignment.objects.filter(
                        user=request.user, 
                        is_active=True
                    ).first()
                    
                    if role_assignment and role_assignment.role:
                        permissions = role_assignment.role.permissions.all()
                        user_permissions = {}
                        for perm in permissions:
                            user_permissions[perm.permission_name] = True
                        context['user_permissions'] = user_permissions
                        
                except ImportError:
                    # If authentication models don't exist, set basic permissions
                    context['user_permissions'] = {
                        'can_view_devices': True,
                        'can_view_assignments': True,
                        'can_scan_qr_codes': True,
                    }
                    
            # Set superuser permissions
            if request.user.is_superuser:
                context['user_permissions'] = {
                    'can_view_devices': True,
                    'can_add_devices': True,
                    'can_edit_devices': True,
                    'can_delete_devices': True,
                    'can_view_assignments': True,
                    'can_create_assignments': True,
                    'can_edit_assignments': True,
                    'can_view_staff': True,
                    'can_manage_staff': True,
                    'can_view_locations': True,
                    'can_manage_locations': True,
                    'can_manage_maintenance': True,
                    'can_generate_reports': True,
                    'can_scan_qr_codes': True,
                    'can_manage_users': True,
                    'can_view_audit_logs': True,
                    'can_export_data': True,
                }
                
        except Exception as e:
            # Fallback for any errors
            pass
    
    return context


def navigation_context(request):
    """
    Add navigation context variables.
    Provides navigation menu items and current page context.
    """
    context = {
        'nav_items': [],
        'current_app': '',
        'current_view': '',
        'current_url_name': '',
        'breadcrumbs': [],
    }
    
    if request.user.is_authenticated:
        try:
            # Get current URL information
            current_url = resolve(request.path_info)
            context['current_app'] = current_url.app_name or ''
            context['current_view'] = current_url.url_name or ''
            context['current_url_name'] = current_url.url_name or ''
            
            # Get user permissions
            user_permissions = context.get('user_permissions', {})
            
            # Build navigation items based on permissions
            nav_items = []
            
            # Dashboard (always visible for authenticated users)
            nav_items.append({
                'name': 'Dashboard',
                'url': reverse('inventory:dashboard') if 'inventory' in settings.INSTALLED_APPS else '/',
                'icon': 'fas fa-tachometer-alt',
                'active': context['current_app'] == 'inventory' and context['current_view'] == 'dashboard',
                'permission_required': None,
            })
            
            # Devices Management
            if user_permissions.get('can_view_devices', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Devices',
                    'url': reverse('inventory:device_list') if 'inventory' in settings.INSTALLED_APPS else '/devices/',
                    'icon': 'fas fa-laptop',
                    'active': context['current_app'] == 'inventory' and 'device' in context['current_view'],
                    'permission_required': 'can_view_devices',
                    'submenu': [
                        {'name': 'All Devices', 'url': reverse('inventory:device_list') if 'inventory' in settings.INSTALLED_APPS else '/devices/'},
                        {'name': 'Add Device', 'url': reverse('inventory:device_add') if 'inventory' in settings.INSTALLED_APPS else '/devices/add/'},
                        {'name': 'Device Categories', 'url': reverse('inventory:device_categories') if 'inventory' in settings.INSTALLED_APPS else '/devices/categories/'},
                    ]
                })
            
            # Assignments Management
            if user_permissions.get('can_view_assignments', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Assignments',
                    'url': reverse('inventory:assignment_list') if 'inventory' in settings.INSTALLED_APPS else '/assignments/',
                    'icon': 'fas fa-user-tag',
                    'active': context['current_app'] == 'inventory' and 'assignment' in context['current_view'],
                    'permission_required': 'can_view_assignments',
                    'submenu': [
                        {'name': 'All Assignments', 'url': reverse('inventory:assignment_list') if 'inventory' in settings.INSTALLED_APPS else '/assignments/'},
                        {'name': 'Create Assignment', 'url': reverse('inventory:assignment_create') if 'inventory' in settings.INSTALLED_APPS else '/assignments/create/'},
                        {'name': 'Overdue Items', 'url': reverse('inventory:assignment_overdue') if 'inventory' in settings.INSTALLED_APPS else '/assignments/overdue/'},
                    ]
                })
            
            # Staff Management
            if user_permissions.get('can_view_staff', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Staff',
                    'url': reverse('inventory:staff_list') if 'inventory' in settings.INSTALLED_APPS else '/staff/',
                    'icon': 'fas fa-users',
                    'active': context['current_app'] == 'inventory' and 'staff' in context['current_view'],
                    'permission_required': 'can_view_staff',
                })
            
            # Locations Management
            if user_permissions.get('can_view_locations', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Locations',
                    'url': reverse('inventory:location_list') if 'inventory' in settings.INSTALLED_APPS else '/locations/',
                    'icon': 'fas fa-map-marker-alt',
                    'active': context['current_app'] == 'inventory' and 'location' in context['current_view'],
                    'permission_required': 'can_view_locations',
                })
            
            # Maintenance Management
            if user_permissions.get('can_manage_maintenance', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Maintenance',
                    'url': reverse('inventory:maintenance_list') if 'inventory' in settings.INSTALLED_APPS else '/maintenance/',
                    'icon': 'fas fa-tools',
                    'active': context['current_app'] == 'inventory' and 'maintenance' in context['current_view'],
                    'permission_required': 'can_manage_maintenance',
                })
            
            # Reports
            if user_permissions.get('can_generate_reports', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Reports',
                    'url': reverse('reports:dashboard') if 'reports' in settings.INSTALLED_APPS else '/reports/',
                    'icon': 'fas fa-chart-bar',
                    'active': context['current_app'] == 'reports',
                    'permission_required': 'can_generate_reports',
                    'submenu': [
                        {'name': 'Device Reports', 'url': '/reports/devices/'},
                        {'name': 'Assignment Reports', 'url': '/reports/assignments/'},
                        {'name': 'Maintenance Reports', 'url': '/reports/maintenance/'},
                    ]
                })
            
            # QR Management
            if user_permissions.get('can_scan_qr_codes', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'QR Codes',
                    'url': reverse('qr_management:index') if 'qr_management' in settings.INSTALLED_APPS else '/qr/',
                    'icon': 'fas fa-qrcode',
                    'active': context['current_app'] == 'qr_management',
                    'permission_required': 'can_scan_qr_codes',
                })
            
            # Administration (if user has permission)
            if user_permissions.get('can_manage_users', False) or request.user.is_superuser:
                nav_items.append({
                    'name': 'Administration',
                    'url': reverse('authentication:user_list') if 'authentication' in settings.INSTALLED_APPS else '/auth/users/',
                    'icon': 'fas fa-cogs',
                    'active': context['current_app'] == 'authentication',
                    'permission_required': 'can_manage_users',
                    'submenu': [
                        {'name': 'Users', 'url': '/auth/users/'},
                        {'name': 'Roles', 'url': '/auth/roles/'},
                        {'name': 'Departments', 'url': '/auth/departments/'},
                        {'name': 'System Settings', 'url': '/auth/settings/'},
                    ]
                })
            
            context['nav_items'] = nav_items
            
        except Exception as e:
            # Fallback navigation
            context['nav_items'] = [
                {
                    'name': 'Dashboard',
                    'url': '/',
                    'icon': 'fas fa-tachometer-alt',
                    'active': True,
                    'permission_required': None,
                }
            ]
    
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
        'notification_types': {
            'success': 0,
            'warning': 0,
            'error': 0,
            'info': 0,
        }
    }
    
    if request.user.is_authenticated:
        try:
            # Cache key for user notifications
            cache_key = f'user_notifications_{request.user.id}'
            cached_notifications = cache.get(cache_key)
            
            if cached_notifications is None:
                notifications = []
                
                # Check for overdue assignments
                try:
                    if hasattr(request.user, 'staff_profile'):
                        from inventory.models import Assignment
                        today = timezone.now().date()
                        
                        # User's overdue assignments
                        overdue_assignments = Assignment.objects.filter(
                            assigned_to_staff=request.user.staff_profile,
                            is_active=True,
                            assignment_type='TEMPORARY',
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
                                'icon': 'fas fa-exclamation-triangle',
                            })
                
                    # Check for devices needing maintenance (if user has permission)
                    user_permissions = context.get('user_permissions', {})
                    if user_permissions.get('can_manage_maintenance', False) or request.user.is_superuser:
                        try:
                            from inventory.models import Device
                            devices_needing_maintenance = Device.objects.filter(
                                status__in=['MAINTENANCE', 'NEEDS_MAINTENANCE']
                            ).count()
                            
                            if devices_needing_maintenance > 0:
                                notifications.append({
                                    'type': 'info',
                                    'title': 'Maintenance Required',
                                    'message': f'{devices_needing_maintenance} device(s) need maintenance',
                                    'url': '/inventory/devices/?status=MAINTENANCE',
                                    'timestamp': timezone.now(),
                                    'icon': 'fas fa-tools',
                                })
                        except:
                            pass
                            
                    # Check for recent assignments (for staff)
                    try:
                        if hasattr(request.user, 'staff_profile'):
                            from inventory.models import Assignment
                            recent_assignments = Assignment.objects.filter(
                                assigned_to_staff=request.user.staff_profile,
                                assignment_date__gte=timezone.now().date() - timezone.timedelta(days=7),
                                is_active=True
                            ).count()
                            
                            if recent_assignments > 0:
                                notifications.append({
                                    'type': 'success',
                                    'title': 'Recent Assignments',
                                    'message': f'You have {recent_assignments} new assignment(s) this week',
                                    'url': '/inventory/assignments/my/',
                                    'timestamp': timezone.now(),
                                    'icon': 'fas fa-check-circle',
                                })
                    except:
                        pass
                
                except Exception:
                    pass
                
                # Cache notifications for 5 minutes
                cache.set(cache_key, notifications, 300)
                cached_notifications = notifications
            
            # Process notifications
            context['notifications'] = cached_notifications[:10]  # Show only recent 10
            context['unread_notifications'] = len(cached_notifications)
            context['total_notifications'] = len(cached_notifications)
            context['has_notifications'] = len(cached_notifications) > 0
            
            # Count notifications by type
            for notification in cached_notifications:
                notif_type = notification.get('type', 'info')
                if notif_type in context['notification_types']:
                    context['notification_types'][notif_type] += 1
            
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
            'system_health': 'good',
        },
        'performance_metrics': {
            'response_time': 0,
            'cache_hit_rate': 0,
            'error_rate': 0,
        }
    }
    
    if request.user.is_authenticated:
        try:
            # Cache key for system stats
            cache_key = 'system_stats'
            cached_stats = cache.get(cache_key)
            
            if cached_stats is None:
                try:
                    from inventory.models import Device, Assignment
                    
                    # Get device statistics
                    device_stats = Device.objects.aggregate(
                        total=Count('device_id'),
                        available=Count('device_id', filter=Q(status='AVAILABLE')),
                        maintenance=Count('device_id', filter=Q(status__in=['MAINTENANCE', 'NEEDS_MAINTENANCE'])),
                    )
                    
                    # Get assignment statistics
                    assignment_stats = Assignment.objects.aggregate(
                        active=Count('id', filter=Q(is_active=True)),
                        recent=Count('id', filter=Q(
                            assignment_date__gte=timezone.now() - timezone.timedelta(days=7)
                        )),
                    )
                    
                    # Get user count
                    user_count = User.objects.filter(is_active=True).count()
                    
                    # Determine system health
                    total_devices = device_stats['total'] or 0
                    maintenance_devices = device_stats['maintenance'] or 0
                    system_health = 'good'
                    
                    if total_devices > 0:
                        maintenance_ratio = maintenance_devices / total_devices
                        if maintenance_ratio > 0.2:
                            system_health = 'warning'
                        elif maintenance_ratio > 0.3:
                            system_health = 'critical'
                    
                    stats = {
                        'total_devices': total_devices,
                        'active_assignments': assignment_stats['active'] or 0,
                        'available_devices': device_stats['available'] or 0,
                        'maintenance_devices': maintenance_devices,
                        'total_users': user_count,
                        'recent_assignments': assignment_stats['recent'] or 0,
                        'system_health': system_health,
                    }
                    
                    # Cache stats for 10 minutes
                    cache.set(cache_key, stats, 600)
                    cached_stats = stats
                    
                except Exception:
                    # Fallback to zero stats on error
                    cached_stats = {
                        'total_devices': 0,
                        'active_assignments': 0,
                        'available_devices': 0,
                        'maintenance_devices': 0,
                        'total_users': 0,
                        'recent_assignments': 0,
                        'system_health': 'unknown',
                    }
            
            context['stats'] = cached_stats
            
        except Exception as e:
            # Fallback to empty stats on error
            pass
    
    return context