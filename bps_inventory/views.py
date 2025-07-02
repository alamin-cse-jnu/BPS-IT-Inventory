from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

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
        current_assignment = device.assignments.filter(is_active=True).first()
        
        # Create scan record if user is authenticated
        if request.user.is_authenticated:
            try:
                from qr_management.models import QRCodeScan
                QRCodeScan.objects.create(
                    device=device,
                    scanned_by=request.user,
                    scan_type='PUBLIC_VERIFICATION',
                    verification_success=True,
                    device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                    assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                    additional_data={
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': request.META.get('REMOTE_ADDR', ''),
                        'verification_method': 'public_qr_verify'
                    }
                )
            except ImportError:
                # QRCodeScan model might not exist yet
                pass
        
        context = {
            'device': device,
            'assignment': current_assignment,
            'verification_successful': True,
            'timestamp': timezone.now(),
            'is_public_view': True,
        }
        
        return render(request, 'qr_management/public_verify.html', context)
        
    except Exception as e:
        # Create failed scan record if user is authenticated
        if request.user.is_authenticated:
            try:
                from qr_management.models import QRCodeScan
                QRCodeScan.objects.create(
                    device_id=device_id,
                    scanned_by=request.user,
                    scan_type='PUBLIC_VERIFICATION',
                    verification_success=False,
                    error_message=str(e),
                    additional_data={
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': request.META.get('REMOTE_ADDR', ''),
                        'verification_method': 'public_qr_verify'
                    }
                )
            except ImportError:
                pass
        
        context = {
            'error': f"Device {device_id} not found or error occurred: {str(e)}",
            'device_id': device_id,
            'verification_successful': False,
            'timestamp': timezone.now(),
            'is_public_view': True,
        }
        return render(request, 'qr_management/public_verify.html', context)

@login_required
def system_health_check(request):
    """System health check view for administrators"""
    if not request.user.is_staff:
        return HttpResponse("Access Denied", status=403)
    
    try:
        from django.db import connection
        from django.core.management import call_command
        from io import StringIO
        
        health_data = {
            'database': 'OK',
            'timestamp': timezone.now(),
            'system_name': 'BPS IT Inventory Management System',
        }
        
        # Test database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_data['database'] = 'OK'
        except Exception as e:
            health_data['database'] = f'ERROR: {str(e)}'
        
        # Check models
        try:
            health_data['device_count'] = Device.objects.count()
            
            from inventory.models import Assignment, Staff, Department
            health_data['assignment_count'] = Assignment.objects.count()
            health_data['staff_count'] = Staff.objects.count()
            health_data['department_count'] = Department.objects.count()
            
        except Exception as e:
            health_data['model_error'] = str(e)
        
        # Check for pending migrations
        try:
            out = StringIO()
            call_command('showmigrations', '--plan', stdout=out)
            migration_output = out.getvalue()
            health_data['migrations'] = 'OK' if '[ ]' not in migration_output else 'PENDING'
        except Exception as e:
            health_data['migrations'] = f'ERROR: {str(e)}'
        
        context = {
            'health_data': health_data,
            'is_superuser': request.user.is_superuser,
        }
        
        return render(request, 'system/health_check.html', context)
        
    except Exception as e:
        return HttpResponse(f"Health Check Error: {str(e)}", status=500)

def api_documentation(request):
    """API documentation view"""
    api_endpoints = [
        {
            'name': 'Device Information',
            'url': '/inventory/api/device/<device_id>/info/',
            'method': 'GET',
            'description': 'Get detailed device information',
            'authentication': 'Required',
        },
        {
            'name': 'Quick Assign Device',
            'url': '/inventory/api/device/assign/',
            'method': 'POST',
            'description': 'Quickly assign a device to staff/department',
            'authentication': 'Required',
        },
        {
            'name': 'Search Suggestions',
            'url': '/inventory/api/search/suggestions/',
            'method': 'GET',
            'description': 'Get search suggestions for devices, staff, departments',
            'authentication': 'Required',
        },
        {
            'name': 'Device Availability',
            'url': '/inventory/api/device/availability/',
            'method': 'GET',
            'description': 'Check if a device is available for assignment',
            'authentication': 'Required',
        },
        {
            'name': 'Staff by Department',
            'url': '/inventory/api/staff/department/<department_id>/',
            'method': 'GET',
            'description': 'Get staff members in a specific department',
            'authentication': 'Required',
        },
        {
            'name': 'QR Code Verification',
            'url': '/verify/<device_id>/',
            'method': 'GET',
            'description': 'Public QR code verification (no auth required)',
            'authentication': 'None',
        },
        {
            'name': 'Mobile QR Scan',
            'url': '/qr/scan/mobile/',
            'method': 'POST',
            'description': 'Mobile-optimized QR scanning interface',
            'authentication': 'Required',
        },
        {
            'name': 'Report Progress',
            'url': '/reports/ajax/progress/<report_id>/',
            'method': 'GET',
            'description': 'Get report generation progress via AJAX',
            'authentication': 'Required',
        },
    ]
    
    context = {
        'api_endpoints': api_endpoints,
        'system_name': 'BPS IT Inventory Management System',
        'version': '1.0.0',
    }
    
    return render(request, 'api/documentation.html', context)

def system_status(request):
    """Public system status page"""
    try:
        # Basic system information (public)
        status_info = {
            'system_name': 'BPS IT Inventory Management System',
            'status': 'Operational',
            'timestamp': timezone.now(),
            'version': '1.0.0',
        }
        
        # Add basic stats if user is authenticated
        if request.user.is_authenticated:
            status_info.update({
                'total_devices': Device.objects.count(),
                'active_devices': Device.objects.filter(status='ACTIVE').count(),
                'database_status': 'Connected',
            })
        
        context = {
            'status_info': status_info,
            'is_authenticated': request.user.is_authenticated,
        }
        
        return render(request, 'system/status.html', context)
        
    except Exception as e:
        context = {
            'status_info': {
                'system_name': 'BPS IT Inventory Management System',
                'status': 'Error',
                'error': str(e),
                'timestamp': timezone.now(),
            },
            'is_authenticated': request.user.is_authenticated,
        }
        
        return render(request, 'system/status.html', context)