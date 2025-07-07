from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from inventory.models import Device

def home_view(request):
    """Home page view for BPS Inventory Management System"""
    try:
        # Quick statistics for homepage
        stats = {}
        if request.user.is_authenticated:
            from inventory.models import Assignment, MaintenanceSchedule
            
            stats = {
                'total_devices': Device.objects.count(),
                'active_assignments': Assignment.objects.filter(is_active=True).count(),
                'pending_maintenance': MaintenanceSchedule.objects.filter(status='SCHEDULED').count() if 'MaintenanceSchedule' in globals() else 0,
                'user_assignments': Assignment.objects.filter(
                    assigned_to_staff__user=request.user,
                    is_active=True
                ).count() if hasattr(request.user, 'staff_profile') else 0,
            }
        
        context = {
            'user': request.user,
            'system_name': 'BPS IT Inventory Management System',
            'organization': 'Bangladesh Parliament Secretariat',
            'current_date': timezone.now().date(),
            'stats': stats,
        }
        
        return render(request, 'home.html', context)
        
    except Exception as e:
        # Fallback context in case of errors
        context = {
            'user': request.user,
            'system_name': 'BPS IT Inventory Management System',
            'organization': 'Bangladesh Parliament Secretariat',
            'current_date': timezone.now().date(),
            'stats': {},
            'error': str(e) if request.user.is_superuser else None,
        }
        
        return render(request, 'home.html', context)

def public_qr_verify(request, device_id):
    """Public QR verification view (no login required)"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        # Get current assignment info
        current_assignment = None
        try:
            from inventory.models import Assignment
            current_assignment = Assignment.objects.filter(
                device=device, is_active=True
            ).select_related('assigned_to_staff__user', 'assigned_to_department').first()
        except:
            pass
        
        # Create verification context
        context = {
            'device': device,
            'current_assignment': current_assignment,
            'verification_time': timezone.now(),
            'system_name': 'BPS IT Inventory Management System',
        }
        
        # Log QR scan if model exists
        try:
            from qr_management.models import QRCodeScan
            QRCodeScan.objects.create(
                device=device,
                scanned_at=timezone.now(),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200]
            )
        except:
            pass
        
        return render(request, 'public/qr_verify.html', context)
        
    except Exception as e:
        context = {
            'error': 'Device not found or invalid QR code',
            'device_id': device_id,
            'system_name': 'BPS IT Inventory Management System',
        }
        return render(request, 'public/qr_verify.html', context, status=404)


def system_health_check(request):
    """System health check endpoint"""
    try:
        # Database connectivity check
        device_count = Device.objects.count()
        db_status = "OK"
    except Exception as e:
        device_count = 0
        db_status = f"ERROR: {str(e)}"
    
    # Check cache if configured
    cache_status = "OK"
    try:
        from django.core.cache import cache
        cache.set('health_check', 'test', 30)
        if cache.get('health_check') != 'test':
            cache_status = "ERROR: Cache not working"
    except Exception as e:
        cache_status = f"ERROR: {str(e)}"
    
    # Media directory check
    import os
    media_status = "OK" if os.path.exists(settings.MEDIA_ROOT) else "ERROR: Media directory not found"
    
    # Static files check
    static_status = "OK" if os.path.exists(settings.STATIC_ROOT) else "WARNING: Static directory not found"
    
    health_data = {
        'status': 'healthy' if db_status == "OK" and cache_status == "OK" else 'unhealthy',
        'timestamp': timezone.now().isoformat(),
        'checks': {
            'database': {
                'status': db_status,
                'device_count': device_count
            },
            'cache': {
                'status': cache_status
            },
            'media': {
                'status': media_status,
                'path': str(settings.MEDIA_ROOT)
            },
            'static': {
                'status': static_status,
                'path': str(settings.STATIC_ROOT)
            }
        },
        'system_info': {
            'debug_mode': settings.DEBUG,
            'allowed_hosts': settings.ALLOWED_HOSTS,
            'database_engine': settings.DATABASES['default']['ENGINE']
        }
    }
    
    if request.GET.get('format') == 'json':
        return JsonResponse(health_data)
    
    return render(request, 'system/health.html', {'health_data': health_data})


@login_required
def system_status(request):
    """Detailed system status for authenticated users"""
    try:
        from inventory.models import Assignment, Staff, Department, Location
        
        # System statistics
        stats = {
            'devices': {
                'total': Device.objects.count(),
                'active': Device.objects.filter(status='AVAILABLE').count(),
                'assigned': Device.objects.filter(status='ASSIGNED').count(),
                'maintenance': Device.objects.filter(status='MAINTENANCE').count(),
            },
            'assignments': {
                'total': Assignment.objects.count(),
                'active': Assignment.objects.filter(is_active=True).count(),
                'overdue': Assignment.objects.filter(
                    is_active=True,
                    is_temporary=True,
                    expected_return_date__lt=timezone.now().date()
                ).count(),
            },
            'staff': {
                'total': Staff.objects.count(),
                'active': Staff.objects.filter(is_active=True).count(),
            },
            'locations': {
                'total': Location.objects.count(),
                'active': Location.objects.filter(is_active=True).count(),
            },
            'departments': {
                'total': Department.objects.count(),
                'active': Department.objects.filter(is_active=True).count(),
            }
        }
        
        # Recent activity
        recent_activities = []
        try:
            from inventory.models import AuditLog
            recent_activities = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
        except:
            pass
        
        # System uptime (approximate)
        import datetime
        uptime_data = {
            'server_time': timezone.now(),
            'django_version': getattr(settings, 'DJANGO_VERSION', 'Unknown'),
            'debug_mode': settings.DEBUG,
        }
        
        context = {
            'stats': stats,
            'recent_activities': recent_activities,
            'uptime_data': uptime_data,
            'title': 'System Status Dashboard'
        }
        
        return render(request, 'system/status.html', context)
        
    except Exception as e:
        context = {
            'error': str(e),
            'title': 'System Status - Error'
        }
        return render(request, 'system/status.html', context)

@login_required
def api_documentation(request):
    """API documentation view"""
    
    # API endpoints documentation
    api_endpoints = [
        {
            'name': 'Device List',
            'method': 'GET',
            'endpoint': '/api/v1/devices/',
            'description': 'Get list of all devices',
            'parameters': ['page', 'limit', 'status', 'category'],
            'example_response': {
                'count': 150,
                'results': [
                    {
                        'device_id': 'LAP-001',
                        'device_name': 'Dell Laptop',
                        'status': 'AVAILABLE',
                        'category': 'Laptop'
                    }
                ]
            }
        },
        {
            'name': 'Device Detail',
            'method': 'GET',
            'endpoint': '/api/v1/devices/{device_id}/',
            'description': 'Get detailed information about a specific device',
            'parameters': ['device_id'],
            'example_response': {
                'device_id': 'LAP-001',
                'device_name': 'Dell Laptop',
                'status': 'AVAILABLE',
                'specifications': {},
                'current_assignment': None
            }
        },
        {
            'name': 'Assignment List',
            'method': 'GET',
            'endpoint': '/api/v1/assignments/',
            'description': 'Get list of all assignments',
            'parameters': ['page', 'limit', 'is_active', 'staff_id'],
            'example_response': {
                'count': 75,
                'results': [
                    {
                        'assignment_id': 'ASN-001',
                        'device': 'LAP-001',
                        'assigned_to_staff': 'John Doe',
                        'is_active': True
                    }
                ]
            }
        }
    ]
    
    # Authentication information
    auth_info = {
        'method': 'Token Authentication',
        'header': 'Authorization: Token your_api_token_here',
        'obtain_token_endpoint': '/api/v1/auth/token/',
        'example': 'curl -H "Authorization: Token abc123" /api/v1/devices/'
    }
    
    context = {
        'api_endpoints': api_endpoints,
        'auth_info': auth_info,
        'base_url': request.build_absolute_uri('/api/v1/'),
        'title': 'API Documentation'
    }
    
    return render(request, 'system/api_docs.html', context)

