# bps_inventory/context_processors.py
# Location: bps_inventory/context_processors.py

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
                        context['user_permissions'] = {
                            'can_view_all_devices': role_assignment.role.can_view_all_devices,
                            'can_manage_assignments': role_assignment.role.can_manage_assignments,
                            'can_approve_requests': role_assignment.role.can_approve_requests,
                            'can_generate_reports': role_assignment.role.can_generate_reports,
                            'can_manage_users': role_assignment.role.can_manage_users,
                            'can_system_admin': role_assignment.role.can_system_admin,
                            'can_manage_maintenance': role_assignment.role.can_manage_maintenance,
                            'can_manage_vendors': role_assignment.role.can_manage_vendors,
                            'can_bulk_operations': role_assignment.role.can_bulk_operations,
                            'can_export_data': role_assignment.role.can_export_data,
                            'can_view_financial_data': role_assignment.role.can_view_financial_data,
                            'can_scan_qr_codes': role_assignment.role.can_scan_qr_codes,
                            'can_generate_qr_codes': role_assignment.role.can_generate_qr_codes,
                            'restricted_to_own_department': role_assignment.role.restricted_to_own_department,
                        }
                        context['user_role'] = role_assignment.role.display_name
                except:
                    pass
            
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
                    'restricted_to_own_department': False,
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
        'current_url_name': '',
        'breadcrumbs': [],
    }
    
    if request.user.is_authenticated:
        try:
            # Get current app and URL name
            if hasattr(request, 'resolver_match') and request.resolver_match:
                context['current_app'] = request.resolver_match.app_name or ''
                context['current_url_name'] = request.resolver_match.url_name or ''
            
            # Get user permissions for navigation filtering
            user_permissions = request.user.is_superuser or False
            
            # Build navigation items based on permissions
            nav_items = [
                {
                    'name': 'Dashboard',
                    'url': 'inventory:dashboard',
                    'icon': 'fas fa-tachometer-alt',
                    'permission_required': None,
                },
                {
                    'name': 'Devices',
                    'url': 'inventory:device_list',
                    'icon': 'fas fa-laptop',
                    'permission_required': 'can_view_all_devices',
                },
                {
                    'name': 'Assignments',
                    'url': 'inventory:assignment_list',
                    'icon': 'fas fa-user-tag',
                    'permission_required': 'can_manage_assignments',
                },
                {
                    'name': 'Locations',
                    'url': 'inventory:location_list',
                    'icon': 'fas fa-map-marker-alt',
                    'permission_required': None,
                },
                {
                    'name': 'Staff',
                    'url': 'inventory:staff_list',
                    'icon': 'fas fa-users',
                    'permission_required': 'can_manage_users',
                },
                {
                    'name': 'Vendors',
                    'url': 'inventory:vendor_list',
                    'icon': 'fas fa-building',
                    'permission_required': 'can_manage_vendors',
                },
                {
                    'name': 'Maintenance',
                    'url': 'inventory:maintenance_list',
                    'icon': 'fas fa-tools',
                    'permission_required': 'can_manage_maintenance',
                },
                {
                    'name': 'Reports',
                    'url': 'reports:dashboard',
                    'icon': 'fas fa-chart-bar',
                    'permission_required': 'can_generate_reports',
                },
                {
                    'name': 'QR Management',
                    'url': 'qr_management:index',
                    'icon': 'fas fa-qrcode',
                    'permission_required': 'can_scan_qr_codes',
                },
            ]
            
            # Filter navigation items based on permissions
            user_perms = context.get('user_permissions', {})
            for item in nav_items:
                if item['permission_required'] is None or user_permissions or user_perms.get(item['permission_required'], False):
                    context['nav_items'].append(item)
                    
        except Exception:
            pass
    
    return context


def notification_context(request):
    """
    Add notification context variables.
    Provides system notifications and alerts.
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
                        from django.utils import timezone
                        
                        overdue_assignments = Assignment.objects.filter(
                            assigned_to_staff=request.user.staff_profile,
                            is_active=True,
                            assignment_date__lt=timezone.now() - timezone.timedelta(days=30)
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


def system_stats_context(request):
    """
    Add system statistics context.
    Provides quick stats for dashboard and sidebar.
    """
    context = {
        'system_stats': {
            'total_devices': 0,
            'active_assignments': 0,
            'pending_maintenance': 0,
            'total_locations': 0,
            'total_staff': 0,
            'total_vendors': 0,
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
                    
                    stats = {
                        'total_devices': Device.objects.count(),
                        'active_assignments': Assignment.objects.filter(is_active=True).count(),
                        'pending_maintenance': Device.objects.filter(status='MAINTENANCE').count(),
                        'total_locations': Location.objects.filter(is_active=True).count(),
                        'total_staff': Staff.objects.filter(is_active=True).count(),
                        'total_vendors': Vendor.objects.filter(is_active=True).count(),
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
                    }
            
            context['system_stats'] = cached_stats
            
        except Exception as e:
            # Fallback to empty stats on error
            pass
    
    return context