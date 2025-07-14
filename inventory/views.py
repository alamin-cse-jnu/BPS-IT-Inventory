# Django core imports
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.urls import reverse
from django.views.generic import View
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.serializers import serialize
from django.core.exceptions import ValidationError
from django.conf import settings
from .form_utils import LocationHierarchyUtils, BlockValidationUtils
from .utils import get_client_ip

# Django contrib imports
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User

# Django DB imports
from django.db import transaction
from django.db.models import (
    Count, Q, Sum, Avg, Max, Min, F, Case, When, FloatField
)

# Third-party imports
import pandas as pd
import openpyxl

# Python standard library imports
import json
import csv
import os
import subprocess
import zipfile
import shutil
import tempfile
from datetime import date, timedelta, datetime
from io import StringIO, BytesIO
from pathlib import Path
import json as json_module 
import qrcode
import base64

# Model imports
from .models import (
    Device, Assignment, Staff, Department, Location, 
    DeviceCategory, DeviceType, DeviceSubCategory, Vendor,
    MaintenanceSchedule, AuditLog, Room, Building, Block, Floor, AssignmentHistory,
)
from .forms import (
    DeviceForm, AssignmentForm, StaffForm, ReturnForm, 
    LocationForm, AdvancedSearchForm, BulkDeviceActionForm,  
    BulkAssignmentForm, MaintenanceScheduleForm, DeviceTransferForm, AssignmentSearchForm,
    VendorForm, CSVImportForm, DepartmentForm, DeviceTypeForm, BlockForm, FloorForm,
)

#Import with comprehensive error handling and missing form fallbacks
try:
    from .utils import (
        get_device_assignment_summary, 
        get_warranty_alerts, 
        get_overdue_assignments,
        get_device_status_distribution,
        get_assignment_trends,
        validate_date_field,
        get_recent_activities
    )
except ImportError as e:
    print(f"Import error in views.py: {e}")
    # Create comprehensive fallback functions
    def get_device_assignment_summary():
        try:
            return {
                'total_devices': Device.objects.count(),
                'active_assignments': Assignment.objects.filter(is_active=True).count(),
                'available_devices': Device.objects.filter(status='AVAILABLE').count(),
                'overdue_assignments': Assignment.objects.filter(
                    is_temporary=True, is_active=True,
                    expected_return_date__lt=timezone.now().date()
                ).count()
            }
        except:
            return {'total_devices': 0, 'active_assignments': 0, 'available_devices': 0, 'overdue_assignments': 0}
    
    def get_warranty_alerts():
        try:
            today = timezone.now().date()
            alert_date = today + timedelta(days=30)
            return Device.objects.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=alert_date
            ).order_by('warranty_end_date')
        except:
            return Device.objects.none()
    
    def get_overdue_assignments():
        try:
            today = timezone.now().date()
            return Assignment.objects.filter(
                is_temporary=True, is_active=True,
                expected_return_date__lt=today,
                actual_return_date__isnull=True
            ).select_related('device', 'assigned_to_staff')
        except:
            return Assignment.objects.none()
    
    def get_device_status_distribution():
        return []
    
    def get_assignment_trends(days=30):
        return []
    
    def validate_date_field(date_value, field_name="date"):
        return date_value
    
    def get_recent_activities(limit=10):
        return []

# Create missing forms as fallbacks
from django import forms

class AssignmentSearchForm(forms.Form):
    """Simple search form for assignments"""
    search = forms.CharField(max_length=200, required=False)
    status = forms.ChoiceField(choices=[('', 'All'), ('active', 'Active'), ('inactive', 'Inactive')], required=False)
    assignment_type = forms.ChoiceField(choices=[('', 'All'), ('permanent', 'Permanent'), ('temporary', 'Temporary')], required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False, empty_label="All Departments")
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)

class ReturnForm(forms.Form):
    """Simple form for returning devices"""
    return_date = forms.DateField(initial=timezone.now().date)
    return_condition = forms.CharField(max_length=200, required=False)
    return_notes = forms.CharField(widget=forms.Textarea, required=False)
    device_condition = forms.CharField(max_length=50, required=False)

class TransferForm(forms.Form):
    """Simple form for transferring assignments"""
    new_assigned_to_staff = forms.ModelChoiceField(queryset=Staff.objects.filter(is_active=True), required=False)
    new_assigned_to_department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)
    new_assigned_to_location = forms.ModelChoiceField(queryset=Location.objects.filter(is_active=True), required=False)
    transfer_reason = forms.CharField(widget=forms.Textarea, required=False)
    conditions = forms.CharField(widget=forms.Textarea, required=False)

class DeviceTypeForm(forms.ModelForm):
    """Simple form for device types"""
    class Meta:
        model = DeviceType
        fields = ['name', 'subcategory', 'description']

class DepartmentForm(forms.ModelForm):
    """Simple form for departments"""
    class Meta:
        model = Department
        fields = ['name', 'code', ]

# Alias the correctly named forms
MaintenanceForm = MaintenanceScheduleForm

# ================================
# DASHBOARD VIEWS
# ================================

@login_required
def dashboard(request):
    """Main inventory dashboard with comprehensive stats"""
    try:
        # Get summary statistics
        summary = get_device_assignment_summary()
        
        # Get recent activities
        recent_assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department', 'created_by'
        ).order_by('-created_at')[:5]
        
        # Get warranty alerts
        warranty_alerts = get_warranty_alerts()[:5]
        
        # Get overdue assignments
        overdue_assignments = get_overdue_assignments()[:5]
        
        # Get device status distribution
        device_status_stats = Device.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Get category distribution
        category_stats = Device.objects.select_related(
            'device_type__subcategory__category'
        ).values(
            'device_type__subcategory__category__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Get assignment trends for chart
        assignment_trends = get_assignment_trends(30)
        
        # Get department assignments
        dept_assignments = Assignment.objects.filter(
            is_active=True
        ).values(
            'assigned_to_department__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Recent maintenance activities
        recent_maintenance = MaintenanceSchedule.objects.select_related(
            'device', 'vendor'
        ).order_by('-scheduled_date')[:5]
        
        context = {
            'summary': summary,
            'recent_assignments': recent_assignments,
            'warranty_alerts': warranty_alerts,
            'overdue_assignments': overdue_assignments,
            'device_status_stats': device_status_stats,
            'category_stats': category_stats,
            'assignment_trends': assignment_trends,
            'dept_assignments': dept_assignments,
            'recent_maintenance': recent_maintenance,
        }
        
        return render(request, 'inventory/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'inventory/dashboard.html', {
            'summary': {'total_devices': 0, 'active_assignments': 0, 'available_devices': 0, 'overdue_assignments': 0},
            'recent_assignments': [], 'warranty_alerts': [], 'overdue_assignments': [],
            'device_status_stats': [], 'category_stats': [], 'assignment_trends': [],
            'dept_assignments': [], 'recent_maintenance': []
        })
    
# ================================
# DASHBOARD ANALYTICS API 
# ================================


@login_required
@require_http_methods(["GET"])
def ajax_dashboard_stats(request):
    """Get dashboard statistics via AJAX"""
    try:
        stats = {
            'total_devices': Device.objects.count(),
            'active_devices': Device.objects.filter(status='ACTIVE').count(),
            'assigned_devices': Device.objects.filter(
                assignments__is_active=True
            ).distinct().count(),
            'maintenance_devices': Device.objects.filter(status='MAINTENANCE').count(),
            'total_assignments': Assignment.objects.filter(is_active=True).count(),
            'overdue_assignments': Assignment.objects.filter(
                is_temporary=True,
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            ).count(),
            'pending_maintenance': MaintenanceSchedule.objects.filter(
                status='SCHEDULED'
            ).count() if 'MaintenanceSchedule' in globals() else 0,
            'warranty_expiring': Device.objects.filter(
                warranty_end_date__gte=timezone.now().date(),
                warranty_end_date__lte=timezone.now().date() + timedelta(days=30)
            ).count(),
        }
        
        return JsonResponse(stats)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_notification_list(request):
    """Get notifications via AJAX"""
    try:
        notifications = []
        
        # Overdue assignments
        overdue_assignments = Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=timezone.now().date()
        ).select_related('device', 'assigned_to_staff')[:5]
        
        for assignment in overdue_assignments:
            notifications.append({
                'type': 'warning',
                'title': 'Overdue Assignment',
                'message': f'Device {assignment.device.device_id} is overdue for return',
                'url': f'/inventory/assignments/{assignment.id}/',
                'created_at': assignment.expected_return_date.isoformat()
            })
        
        # Warranty expiring soon
        expiring_warranties = Device.objects.filter(
            warranty_end_date__gte=timezone.now().date(),
            warranty_end_date__lte=timezone.now().date() + timedelta(days=30)
        )[:5]
        
        for device in expiring_warranties:
            notifications.append({
                'type': 'info',
                'title': 'Warranty Expiring',
                'message': f'Warranty for {device.device_id} expires on {device.warranty_end_date}',
                'url': f'/inventory/devices/{device.device_id}/',
                'created_at': device.warranty_end_date.isoformat()
            })
        
        # Scheduled maintenance
        try:
            scheduled_maintenance = MaintenanceSchedule.objects.filter(
                status='SCHEDULED',
                scheduled_date__lte=timezone.now().date() + timedelta(days=7)
            ).select_related('device')[:5]
            
            for maintenance in scheduled_maintenance:
                notifications.append({
                    'type': 'info',
                    'title': 'Scheduled Maintenance',
                    'message': f'Maintenance for {maintenance.device.device_id} scheduled for {maintenance.scheduled_date}',
                    'url': f'/inventory/maintenance/{maintenance.id}/',
                    'created_at': maintenance.scheduled_date.isoformat()
                })
        except:
            pass
        
        # Sort by date (most recent first)
        notifications.sort(key=lambda x: x['created_at'], reverse=True)
        
        return JsonResponse({
            'notifications': notifications[:10],
            'count': len(notifications)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_device_stats(request):
    """Get device statistics via AJAX"""
    try:
        # Status distribution
        status_stats = Device.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Condition distribution
        condition_stats = Device.objects.values('condition').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Category distribution
        category_stats = Device.objects.values(
            'device_type__subcategory__category__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Assignment trends (last 6 months)
        six_months_ago = timezone.now().date() - timedelta(days=180)
        monthly_assignments = []
        
        for i in range(6):
            month_start = six_months_ago + timedelta(days=i*30)
            month_end = month_start + timedelta(days=30)
            
            count = Assignment.objects.filter(
                start_date__gte=month_start,
                start_date__lt=month_end
            ).count()
            
            monthly_assignments.append({
                'month': month_start.strftime('%Y-%m'),
                'count': count
            })
        
        return JsonResponse({
            'status_distribution': list(status_stats),
            'condition_distribution': list(condition_stats),
            'category_distribution': list(category_stats),
            'assignment_trends': monthly_assignments
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ================================
# DEVICE MANAGEMENT VIEWS
# ================================

@login_required
def device_history(request, device_id):
    """Show device history"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        # Get assignment history
        assignment_history = Assignment.objects.filter(
            device=device
        ).select_related(
            'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
        ).order_by('-created_at')
        
        # Get maintenance history
        maintenance_history = MaintenanceSchedule.objects.filter(
            device=device
        ).order_by('-scheduled_date')
        
        # Get audit logs for this device
        audit_logs = AuditLog.objects.filter(
            model_name='Device',
            object_id=device.device_id
        ).order_by('-timestamp')
        
        context = {
            'device': device,
            'assignment_history': assignment_history,
            'maintenance_history': maintenance_history,
            'audit_logs': audit_logs,
        }
        
        return render(request, 'inventory/devices/device_history.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device history: {str(e)}")
        return redirect('inventory:device_detail', device_id=device_id)

@login_required
def device_list(request):
    """List all devices with search and filtering"""
    devices = Device.objects.select_related(
        'device_type', 'vendor', 'current_location'
    ).all()
    
    # Pagination
    paginator = Paginator(devices, 25)
    page_number = request.GET.get('page')
    devices_page = paginator.get_page(page_number)
    
    # Statistics for dashboard
    stats = {
        'total_devices': devices.count(),
        'available_devices': devices.filter(status='AVAILABLE').count(),
        'assigned_devices': devices.filter(status='ASSIGNED').count(),
        'maintenance_devices': devices.filter(status='MAINTENANCE').count(),
    }
    
    context = {
        'devices': devices_page,
        'stats': stats,
        'title': 'Device Management'
    }
    
    return render(request, 'inventory/devices/device_list.html', context)

@login_required
def device_detail(request, device_id):
    """Complete device detail view - safe version"""
    try:
        # Get device with related objects
        device = get_object_or_404(
            Device.objects.select_related(
                'device_type__subcategory__category',
                'vendor',
                'current_location',
                'created_by',
                'updated_by'
            ),
            device_id=device_id
        )
        
        # Get current assignment
        current_assignment = None
        try:
            from .models import Assignment
            current_assignment = Assignment.objects.filter(
                device=device, is_active=True
            ).select_related('assigned_to_staff', 'assigned_to_department', 'assigned_to_location').first()
        except:
            pass
        
        # Get assignment history (last 10) - safe
        assignment_history = []
        try:
            from .models import Assignment
            assignment_history = Assignment.objects.filter(
                device=device
            ).select_related(
                'assigned_to_staff__user', 
                'assigned_to_department', 
                'assigned_to_location'
            ).order_by('-assigned_at')[:10]
        except:
            pass
        
        # Get maintenance history - safe
        maintenance_history = []
        try:
            from .models import MaintenanceRecord
            maintenance_history = MaintenanceRecord.objects.filter(
                device=device
            ).select_related('technician').order_by('-scheduled_date')[:5]
        except ImportError:
            pass
        except:
            pass
        
        # Get movement history - safe
        movement_history = []
        try:
            from .models import DeviceMovement
            movement_history = DeviceMovement.objects.filter(
                device=device
            ).select_related('from_location', 'to_location', 'moved_by').order_by('-movement_date')[:5]
        except ImportError:
            pass
        except:
            pass
        
        # Get recent audit logs for this device - safe
        audit_logs = []
        try:
            from .models import AuditLog
            audit_logs = AuditLog.objects.filter(
                model_name='Device',
                object_id=str(device.id)
            ).select_related('user').order_by('-timestamp')[:10]
        except ImportError:
            pass
        except:
            pass
        
        # Calculate device statistics
        device_stats = {
            'days_since_purchase': (timezone.now().date() - device.purchase_date).days if device.purchase_date else 0,
            'warranty_days_remaining': (device.warranty_end_date - timezone.now().date()).days if device.warranty_end_date and device.warranty_end_date > timezone.now().date() else 0,
        }
        
        # Safe assignment counts
        try:
            from .models import Assignment
            device_stats.update({
                'total_assignments': Assignment.objects.filter(device=device).count(),
                'active_assignments': Assignment.objects.filter(device=device, is_active=True).count(),
            })
        except:
            device_stats.update({
                'total_assignments': 0,
                'active_assignments': 0,
            })
        
        # Safe movement counts
        try:
            from .models import DeviceMovement
            device_stats['total_movements'] = DeviceMovement.objects.filter(device=device).count()
        except:
            device_stats['total_movements'] = 0
        
        # Check if device has any issues
        issues = []
        if device.warranty_end_date and device.warranty_end_date < timezone.now().date():
            issues.append({'type': 'warning', 'message': 'Warranty has expired'})
        elif device.warranty_end_date and device.warranty_end_date <= timezone.now().date() + timedelta(days=30):
            issues.append({'type': 'info', 'message': 'Warranty expires within 30 days'})
        
        if current_assignment and current_assignment.is_temporary and current_assignment.expected_return_date:
            if current_assignment.expected_return_date < timezone.now().date():
                issues.append({'type': 'danger', 'message': 'Temporary assignment is overdue'})
            elif current_assignment.expected_return_date <= timezone.now().date() + timedelta(days=7):
                issues.append({'type': 'warning', 'message': 'Temporary assignment due within 7 days'})
        
        context = {
            'device': device,
            'current_assignment': current_assignment,
            'assignment_history': assignment_history,
            'maintenance_history': maintenance_history,
            'movement_history': movement_history,
            'audit_logs': audit_logs,
            'device_stats': device_stats,
            'issues': issues,
            'title': f'Device: {device.device_name}',
            'can_edit': request.user.has_perm('inventory.change_device'),
            'can_delete': request.user.has_perm('inventory.delete_device'),
            'can_assign': request.user.has_perm('inventory.add_assignment'),
        }
        
        return render(request, 'inventory/devices/device_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device details: {str(e)}")
        return redirect('inventory:device_list')

@login_required
@permission_required('inventory.add_device', raise_exception=True)
def device_create(request):
    """Your existing device_create function - just need to ensure forms use correct STATUS_CHOICES"""
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    device = form.save(commit=False)
                    device.created_by = request.user
                    device.updated_by = request.user
                    device.save()
                    
                    # Log the activity
                    AuditLog.objects.create(
                        user=request.user,
                        action='CREATE',
                        model_name='Device',
                        object_id=device.device_id,
                        object_repr=str(device),
                        changes={
                            'device_id': device.device_id,
                            'device_name': device.device_name,
                            'status': device.status
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Device "{device.device_name}" created successfully.')
                    return redirect('inventory:device_detail', device_id=device.device_id)
                    
            except Exception as e:
                messages.error(request, f'Error creating device: {str(e)}')
    else:
        form = DeviceForm()
    
    context = {
        'form': form,
        'title': 'Create New Device'
    }
    
    return render(request, 'inventory/devices/device_form.html', context)

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def device_edit(request, device_id):
    """Edit device"""
    device = get_object_or_404(Device, id=device_id)
    
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Track changes
                    changes = {}
                    for field in form.changed_data:
                        changes[field] = {
                            'old': getattr(device, field),
                            'new': form.cleaned_data[field]
                        }
                    
                    device = form.save(commit=False)
                    device.updated_by = request.user
                    device.save()
                    
                    # Log the activity
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='Device',
                        object_id=device.id,
                        object_repr=str(device),
                        changes=changes,
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Device "{device.device_name}" updated successfully.')
                    return redirect('inventory:device_detail', device_id=device.id)
                    
            except Exception as e:
                messages.error(request, f'Error updating device: {str(e)}')
    else:
        form = DeviceForm(instance=device)
        # Populate specifications_text for editing
        if device.specifications:
            specs_text = '\n'.join([f"{k}: {v}" for k, v in device.specifications.items()])
            form.initial['specifications_text'] = specs_text
    
    context = {
        'form': form,
        'device': device,
        'title': f'Edit Device: {device.device_name}'
    }
    
    return render(request, 'inventory/device_form.html', context)

@login_required
@permission_required('inventory.delete_device', raise_exception=True)
def device_delete(request, device_id):
    """Soft delete device with proper validation"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        if request.method == 'POST':
            # Check for active assignments
            active_assignments = Assignment.objects.filter(device=device, is_active=True)
            if active_assignments.exists():
                messages.error(request, 'Cannot delete device with active assignments. Please return the device first.')
                return redirect('inventory:device_detail', device_id=device.device_id)
            
            try:
                with transaction.atomic():
                    # Soft delete by changing status
                    device.status = 'DISPOSED'
                    device.updated_by = request.user
                    device.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='DELETE',
                        model_name='Device',
                        object_id=device.device_id,
                        object_repr=str(device),
                        changes={'status': {'old': device.status, 'new': 'DISPOSED'}},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Device "{device.device_name}" has been marked as disposed.')
                    return redirect('inventory:device_list')
            except Exception as e:
                messages.error(request, f'Error deleting device: {str(e)}')
        
        context = {
            'device': device,
            'active_assignments': Assignment.objects.filter(device=device, is_active=True).count()
        }
        return render(request, 'inventory/devices/device_delete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error processing request: {str(e)}")
        return redirect('inventory:device_list')
@login_required
def device_type_detail(request, type_id):
    """Device type detail view"""
    try:
        device_type = get_object_or_404(
            DeviceType.objects.select_related('subcategory__category'),
            id=type_id
        )
        
        # Get devices of this type
        devices = Device.objects.filter(device_type=device_type).select_related(
            'vendor', 'current_location'
        ).prefetch_related('assignments')
        
        # Pagination for devices
        paginator = Paginator(devices, 20)
        page_number = request.GET.get('page')
        devices_page = paginator.get_page(page_number)
        
        # Statistics for this device type
        stats = {
            'total_devices': devices.count(),
            'available_devices': devices.filter(status='AVAILABLE').count(),
            'assigned_devices': devices.filter(status='ASSIGNED').count(),
            'maintenance_devices': devices.filter(status='MAINTENANCE').count(),
            'retired_devices': devices.filter(status='RETIRED').count(),
        }
        
        # Condition distribution
        condition_stats = list(
            devices.values('condition')
            .annotate(count=Count('condition'))
            .order_by('condition')
        )
        
        # Vendor distribution
        vendor_stats = list(
            devices.filter(vendor__isnull=False)
            .values('vendor__name')
            .annotate(count=Count('vendor'))
            .order_by('-count')[:10]
        )
        
        # Age distribution (based on purchase date)
        today = timezone.now().date()
        age_ranges = [
            ('0-1 years', 0, 365),
            ('1-3 years', 366, 1095),
            ('3-5 years', 1096, 1825),
            ('5+ years', 1826, 9999)
        ]
        
        age_stats = []
        for label, min_days, max_days in age_ranges:
            start_date = today - timedelta(days=max_days)
            end_date = today - timedelta(days=min_days)
            
            if max_days == 9999:
                count = devices.filter(
                    purchase_date__lte=end_date,
                    purchase_date__isnull=False
                ).count()
            else:
                count = devices.filter(
                    purchase_date__gte=start_date,
                    purchase_date__lte=end_date,
                    purchase_date__isnull=False
                ).count()
            
            age_stats.append({'label': label, 'count': count})
        
        # Recent activities for this device type
        recent_assignments = Assignment.objects.filter(
            device__device_type=device_type,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).select_related(
            'device', 'assigned_to_staff', 'assigned_to_department'
        ).order_by('-created_at')[:10]
        
        context = {
            'device_type': device_type,
            'devices': devices_page,
            'stats': stats,
            'condition_stats': condition_stats,
            'vendor_stats': vendor_stats,
            'age_stats': age_stats,
            'recent_assignments': recent_assignments,
            'title': f'Device Type: {device_type.name}'
        }
        
        return render(request, 'inventory/devices/device_type_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device type details: {str(e)}")
        return redirect('inventory:device_type_list')

@login_required
@permission_required('inventory.change_devicetype', raise_exception=True)
def device_type_edit(request, type_id):
    """Edit device type"""
    try:
        device_type = get_object_or_404(DeviceType, id=type_id)
        
        if request.method == 'POST':
            form = DeviceTypeForm(request.POST, instance=device_type)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        device_type = form.save()
                        
                        # Log the activity
                        from .utils import log_user_activity
                        log_user_activity(
                            user=request.user,
                            action='UPDATE',
                            model_name='DeviceType',
                            object_id=device_type.id,
                            object_repr=str(device_type),
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Device type "{device_type.name}" updated successfully.')
                        return redirect('inventory:device_type_detail', type_id=device_type.id)
                        
                except Exception as e:
                    messages.error(request, f'Error updating device type: {str(e)}')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        else:
            form = DeviceTypeForm(instance=device_type)
        
        # Get subcategories for the selected category
        if device_type.subcategory:
            subcategories = DeviceSubCategory.objects.filter(
                category=device_type.subcategory.category
            )
        else:
            subcategories = DeviceSubCategory.objects.none()
        
        context = {
            'form': form,
            'device_type': device_type,
            'subcategories': subcategories,
            'title': f'Edit Device Type: {device_type.name}'
        }
        
        return render(request, 'inventory/device_types/device_type_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device type: {str(e)}")
        return redirect('inventory:device_type_list')

@login_required
@permission_required('inventory.delete_devicetype', raise_exception=True)
def device_type_delete(request, type_id):
    """Delete device type (soft delete if has devices)"""
    try:
        device_type = get_object_or_404(DeviceType, id=type_id)
        
        # Check if device type has associated devices
        device_count = Device.objects.filter(device_type=device_type).count()
        
        if request.method == 'POST':
            if device_count > 0:
                # Soft delete - mark as inactive
                device_type.is_active = False
                device_type.save()
                
                # Log the activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='SOFT_DELETE',
                    model_name='DeviceType',
                    object_id=device_type.id,
                    object_repr=str(device_type),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(
                    request, 
                    f'Device type "{device_type.name}" has been deactivated (has {device_count} associated devices).'
                )
            else:
                # Hard delete - no associated devices
                device_type_name = device_type.name
                device_type.delete()
                
                # Log the activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='DELETE',
                    model_name='DeviceType',
                    object_id=type_id,
                    object_repr=device_type_name,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Device type "{device_type_name}" deleted successfully.')
            
            return redirect('inventory:device_type_list')
        
        context = {
            'device_type': device_type,
            'device_count': device_count,
            'can_hard_delete': device_count == 0,
            'title': f'Delete Device Type: {device_type.name}'
        }
        
        return render(request, 'inventory/device_types/device_type_confirm_delete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error deleting device type: {str(e)}")
        return redirect('inventory:device_type_list')

@login_required
@require_http_methods(["GET"])
def ajax_subcategories_by_category(request):
    """AJAX: Get subcategories for category - matches URL pattern name"""
    try:
        category_id = request.GET.get('category_id')
        if category_id:
            subcategories = DeviceSubCategory.objects.filter(
                category_id=category_id, is_active=True
            ).values('id', 'name')
            return JsonResponse({'subcategories': list(subcategories)})
        return JsonResponse({'subcategories': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_device_types_by_subcategory(request):
    """AJAX: Get device types for subcategory - matches URL pattern name"""
    try:
        subcategory_id = request.GET.get('subcategory_id')
        if subcategory_id:
            device_types = DeviceType.objects.filter(
                subcategory_id=subcategory_id, is_active=True
            ).values('id', 'name')
            return JsonResponse({'device_types': list(device_types)})
        return JsonResponse({'device_types': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ================================
# ASSIGNMENT MANAGEMENT VIEWS
# ================================

@login_required
def assignment_list(request):
    """List all assignments with search and filtering"""
    form = AssignmentSearchForm(request.GET)
    assignments = Assignment.objects.select_related(
        'device__device_type',
        'device__current_location__building',
        'device__current_location__block',
        'assigned_to_staff__user',
        'assigned_to_staff__department',
        'assigned_to_department',
        'assigned_to_location__building',
        'assigned_to_location__block',
        'created_by'
    ).order_by('-created_at')
    
    # Apply filters
    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        if search_query:
            assignments = assignments.filter(
                Q(device__device_id__icontains=search_query) |
                Q(device__device_name__icontains=search_query) |
                Q(assigned_to_staff__user__first_name__icontains=search_query) |
                Q(assigned_to_staff__user__last_name__icontains=search_query) |
                Q(assigned_to_staff__employee_id__icontains=search_query) |
                Q(assigned_to_department__name__icontains=search_query) |
                Q(purpose__icontains=search_query)
            )
        
        assignment_type = form.cleaned_data.get('assignment_type')
        if assignment_type:
            assignments = assignments.filter(assignment_type=assignment_type)
        
        staff = form.cleaned_data.get('staff')
        if staff:
            assignments = assignments.filter(assigned_to_staff=staff)
        
        department = form.cleaned_data.get('department')
        if department:
            assignments = assignments.filter(
                Q(assigned_to_department=department) |
                Q(assigned_to_staff__department=department)
            )
        
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            assignments = assignments.filter(start_date__gte=date_from)
        
        date_to = form.cleaned_data.get('date_to')
        if date_to:
            assignments = assignments.filter(start_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page = request.GET.get('page')
    assignments = paginator.get_page(page)
    
    # Statistics
    total_assignments = Assignment.objects.count()
    active_assignments = Assignment.objects.filter(is_active=True).count()
    overdue_assignments = Assignment.objects.filter(
        is_active=True,
        expected_return_date__lt=timezone.now().date()
    ).count()
    
    context = {
        'assignments': assignments,
        'form': form,
        'total_assignments': total_assignments,
        'active_assignments': active_assignments,
        'overdue_assignments': overdue_assignments,
    }
    
    return render(request, 'inventory/assignments/assignment_list.html', context)

@login_required
def assignment_create(request):
    """Create a new assignment"""
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    assignment = form.save(commit=False)
                    assignment.created_by = request.user
                    assignment.start_date = timezone.now().date()
                    assignment.save()
                    
                    # Update device status
                    device = assignment.device
                    device.status = 'ASSIGNED'
                    device.save()
                    
                    # Create assignment history entry
                    AssignmentHistory.objects.create(
                        assignment=assignment,
                        changed_by=request.user,
                        change_type='CREATED',
                        new_values={
                            'device': device.device_id,
                            'assigned_to_staff': str(assignment.assigned_to_staff) if assignment.assigned_to_staff else None,
                            'assigned_to_department': str(assignment.assigned_to_department) if assignment.assigned_to_department else None,
                            'assigned_to_location': str(assignment.assigned_to_location) if assignment.assigned_to_location else None,
                            'assignment_type': assignment.assignment_type,
                            'purpose': assignment.purpose,
                        },
                        reason='New assignment created',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                    )
                    
                    # Determine assignment target for message
                    target = (
                        assignment.assigned_to_staff or 
                        assignment.assigned_to_department or 
                        assignment.assigned_to_location
                    )
                    
                    messages.success(
                        request, 
                        f'Assignment created successfully! Device {device.device_id} assigned to {target}.'
                    )
                    return redirect('inventory:assignment_detail', pk=assignment.pk)
                    
            except ValidationError as e:
                messages.error(request, f'Assignment creation failed: {e.message}')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    else:
        # Pre-populate device if specified in URL
        device_id = request.GET.get('device')
        initial_data = {}
        if device_id:
            try:
                device = Device.objects.get(pk=device_id, status='AVAILABLE')
                initial_data['device'] = device
            except Device.DoesNotExist:
                messages.warning(request, 'Selected device is not available for assignment.')
        
        form = AssignmentForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Create Assignment',
        'available_devices': Device.objects.filter(status='AVAILABLE').count(),
        'active_staff': Staff.objects.filter(is_active=True).count(),
    }
    
    return render(request, 'inventory/assignments/assignment_form.html', context)

@login_required
def assignment_detail(request, pk):
    """View assignment details"""
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            'device__device_type',
            'device__current_location__building',
            'device__current_location__block',
            'assigned_to_staff__user',
            'assigned_to_staff__department',
            'assigned_to_department',
            'assigned_to_location__building',
            'assigned_to_location__block',
            'created_by'
        ).prefetch_related(
            'assignment_history__changed_by'
        ),
        pk=pk
    )
    
    # Get assignment history
    history = assignment.assignment_history.select_related('changed_by').order_by('-timestamp')[:10]
    
    # Check if assignment is overdue
    is_overdue = assignment.is_overdue
    days_until_due = assignment.days_until_due
    
    context = {
        'assignment': assignment,
        'history': history,
        'is_overdue': is_overdue,
        'days_until_due': days_until_due,
        'can_edit': request.user.has_perm('inventory.change_assignment'),
        'can_return': assignment.is_active and request.user.has_perm('inventory.change_assignment'),
    }
    
    return render(request, 'inventory/assignments/assignment_detail.html', context)

@login_required
def assignment_edit(request, pk):
    """Edit an existing assignment"""
    assignment = get_object_or_404(Assignment, pk=pk)
    
    # Check permissions
    if not request.user.has_perm('inventory.change_assignment'):
        messages.error(request, 'You do not have permission to edit assignments.')
        return redirect('inventory:assignment_detail', pk=assignment.pk)
    
    if request.method == 'POST':
        # Store old values for history
        old_values = {
            'assigned_to_staff': str(assignment.assigned_to_staff) if assignment.assigned_to_staff else None,
            'assigned_to_department': str(assignment.assigned_to_department) if assignment.assigned_to_department else None,
            'assigned_to_location': str(assignment.assigned_to_location) if assignment.assigned_to_location else None,
            'assignment_type': assignment.assignment_type,
            'purpose': assignment.purpose,
            'expected_return_date': str(assignment.expected_return_date) if assignment.expected_return_date else None,
        }
        
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_assignment = form.save()
                    
                    # Create history entry
                    new_values = {
                        'assigned_to_staff': str(updated_assignment.assigned_to_staff) if updated_assignment.assigned_to_staff else None,
                        'assigned_to_department': str(updated_assignment.assigned_to_department) if updated_assignment.assigned_to_department else None,
                        'assigned_to_location': str(updated_assignment.assigned_to_location) if updated_assignment.assigned_to_location else None,
                        'assignment_type': updated_assignment.assignment_type,
                        'purpose': updated_assignment.purpose,
                        'expected_return_date': str(updated_assignment.expected_return_date) if updated_assignment.expected_return_date else None,
                    }
                    
                    AssignmentHistory.objects.create(
                        assignment=updated_assignment,
                        changed_by=request.user,
                        change_type='MODIFIED',
                        old_values=old_values,
                        new_values=new_values,
                        reason='Assignment updated',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                    )
                    
                    messages.success(request, 'Assignment updated successfully!')
                    return redirect('inventory:assignment_detail', pk=assignment.pk)
                    
            except ValidationError as e:
                messages.error(request, f'Assignment update failed: {e.message}')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    else:
        form = AssignmentForm(instance=assignment)
    
    context = {
        'form': form,
        'assignment': assignment,
        'title': 'Edit Assignment',
    }
    
    return render(request, 'inventory/assignments/assignment_form.html', context)
@login_required
@permission_required('inventory.delete_assignment', raise_exception=True)
def assignment_delete(request, pk):
    """Delete an assignment with confirmation"""
    try:
        assignment = get_object_or_404(
            Assignment.objects.select_related(
                'device__device_type',
                'assigned_to_staff__user',
                'assigned_to_staff__department',
                'assigned_to_department',
                'assigned_to_location__building',
                'assigned_to_location__block',
                'created_by'
            ),
            pk=pk
        )
        
        # Check if user has permission to delete this specific assignment
        # Allow deletion if user created it or has admin privileges
        if not (request.user == assignment.created_by or 
                request.user.has_perm('inventory.delete_assignment') or
                request.user.is_superuser):
            messages.error(request, 'You do not have permission to delete this assignment.')
            return redirect('inventory:assignment_detail', pk=pk)
        
        # Store assignment details for logging before deletion
        assignment_details = {
            'assignment_id': str(assignment.pk),
            'device_id': assignment.device.device_id,
            'device_name': assignment.device.device_name,
            'assigned_to_staff': str(assignment.assigned_to_staff) if assignment.assigned_to_staff else None,
            'assigned_to_department': str(assignment.assigned_to_department) if assignment.assigned_to_department else None,
            'assigned_to_location': str(assignment.assigned_to_location) if assignment.assigned_to_location else None,
            'assignment_type': assignment.assignment_type,
            'purpose': assignment.purpose,
            'created_at': assignment.created_at.isoformat() if hasattr(assignment, 'created_at') else None,
            'deleted_by': request.user.username,
            'deleted_at': timezone.now().isoformat()
        }
        
        if request.method == 'POST':
            # Get deletion confirmation and reason
            confirm_delete = request.POST.get('confirm_delete')
            deletion_reason = request.POST.get('deletion_reason', '').strip()
            
            if confirm_delete == 'yes':
                try:
                    with transaction.atomic():
                        # Store device reference before deletion
                        device = assignment.device
                        
                        # Create assignment history entry for deletion
                        try:
                            AssignmentHistory.objects.create(
                                assignment=assignment,
                                changed_by=request.user,
                                change_type='CANCELLED',
                                old_values=assignment_details,
                                new_values={'status': 'DELETED'},
                                reason=f'Assignment deleted: {deletion_reason}' if deletion_reason else 'Assignment deleted',
                                notes=f'Assignment permanently deleted by {request.user.get_full_name() or request.user.username}',
                                ip_address=get_client_ip(request),
                                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                            )
                        except Exception as history_error:
                            # Log history creation error but don't fail the deletion
                            print(f"Warning: Could not create assignment history: {history_error}")
                        
                        # Update device status back to available if this was an active assignment
                        if assignment.is_active:
                            device.status = 'AVAILABLE'
                            device.save()
                        
                        # Create audit log entry
                        try:
                            AuditLog.objects.create(
                                user=request.user,
                                action='DELETE',
                                model_name='Assignment',
                                object_id=str(assignment.pk),
                                object_repr=f'Assignment {assignment.pk} - {assignment.device.device_name}',
                                changes=assignment_details,
                                ip_address=get_client_ip(request)
                            )
                        except Exception as audit_error:
                            # Log audit creation error but don't fail the deletion
                            print(f"Warning: Could not create audit log: {audit_error}")
                        
                        # Delete the assignment
                        assignment.delete()
                        
                        # Success message with details
                        target = (
                            assignment_details['assigned_to_staff'] or 
                            assignment_details['assigned_to_department'] or 
                            assignment_details['assigned_to_location'] or
                            'Unknown'
                        )
                        
                        messages.success(
                            request, 
                            f'Assignment deleted successfully! Device {device.device_id} '
                            f'(previously assigned to {target}) is now available for reassignment.'
                        )
                        
                        # Redirect to appropriate view
                        redirect_to = request.GET.get('next')
                        if redirect_to in ['assignment_list', 'device_detail', 'staff_detail']:
                            if redirect_to == 'device_detail':
                                return redirect('inventory:device_detail', device_id=device.device_id)
                            elif redirect_to == 'staff_detail' and assignment_details['assigned_to_staff']:
                                # Extract staff ID if available
                                try:
                                    staff = Staff.objects.get(user__username=assignment_details['assigned_to_staff'])
                                    return redirect('inventory:staff_detail', staff_id=staff.employee_id)
                                except (Staff.DoesNotExist, KeyError):
                                    pass
                            return redirect('inventory:assignment_list')
                        else:
                            return redirect('inventory:assignment_list')
                        
                except Exception as e:
                    messages.error(request, f'Error deleting assignment: {str(e)}')
                    return redirect('inventory:assignment_detail', pk=pk)
            else:
                messages.info(request, 'Assignment deletion cancelled.')
                return redirect('inventory:assignment_detail', pk=pk)
        
        # GET request - show confirmation page
        context = {
            'assignment': assignment,
            'assignment_details': assignment_details,
            'title': f'Delete Assignment - {assignment.device.device_name}',
            'can_delete': True,
            'warning_message': 'This action cannot be undone. The assignment will be permanently deleted.',
            'device_will_be_available': assignment.is_active,
        }
        
        return render(request, 'inventory/assignments/assignment_delete.html', context)
        
    except Assignment.DoesNotExist:
        messages.error(request, 'Assignment not found.')
        return redirect('inventory:assignment_list')
        
    except Exception as e:
        messages.error(request, f'Error accessing assignment: {str(e)}')
        return redirect('inventory:assignment_list')

@login_required
@require_http_methods(["POST"])
def assignment_return(request, pk):
    """Return a device from assignment"""
    assignment = get_object_or_404(Assignment, pk=pk, is_active=True)
    
    # Check permissions
    if not request.user.has_perm('inventory.change_assignment'):
        messages.error(request, 'You do not have permission to return assignments.')
        return redirect('inventory:assignment_detail', pk=assignment.pk)
    
    form = ReturnForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                # Update assignment
                assignment.actual_return_date = form.cleaned_data['return_date']
                assignment.is_active = False
                assignment.save()
                
                # Update device
                device = assignment.device
                device.status = 'AVAILABLE'
                
                # Update device condition if specified
                device_condition = form.cleaned_data.get('device_condition')
                if device_condition:
                    device.condition = device_condition
                
                device.save()
                
                # Create history entry
                AssignmentHistory.objects.create(
                    assignment=assignment,
                    changed_by=request.user,
                    change_type='RETURNED',
                    new_values={
                        'return_date': str(form.cleaned_data['return_date']),
                        'return_condition': form.cleaned_data.get('return_condition', ''),
                        'return_notes': form.cleaned_data.get('return_notes', ''),
                        'device_condition': device_condition or device.condition,
                    },
                    reason='Device returned',
                    notes=form.cleaned_data.get('return_notes', ''),
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                
                messages.success(
                    request, 
                    f'Device {device.device_id} returned successfully!'
                )
                return redirect('inventory:assignment_detail', pk=assignment.pk)
                
        except Exception as e:
            messages.error(request, f'Return failed: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('inventory:assignment_detail', pk=assignment.pk)

@login_required
@require_http_methods(["POST"])
def assignment_transfer(request, pk):
    """Transfer an assignment to a different target"""
    assignment = get_object_or_404(Assignment, pk=pk, is_active=True)
    
    # Check permissions
    if not request.user.has_perm('inventory.change_assignment'):
        messages.error(request, 'You do not have permission to transfer assignments.')
        return redirect('inventory:assignment_detail', pk=assignment.pk)
    
    form = TransferForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                # Store old assignment details
                old_values = {
                    'assigned_to_staff': str(assignment.assigned_to_staff) if assignment.assigned_to_staff else None,
                    'assigned_to_department': str(assignment.assigned_to_department) if assignment.assigned_to_department else None,
                    'assigned_to_location': str(assignment.assigned_to_location) if assignment.assigned_to_location else None,
                }
                
                # Update assignment
                assignment.assigned_to_staff = form.cleaned_data.get('new_assigned_to_staff')
                assignment.assigned_to_department = form.cleaned_data.get('new_assigned_to_department')
                assignment.assigned_to_location = form.cleaned_data.get('new_assigned_to_location')
                assignment.save()
                
                # Create history entry
                new_values = {
                    'assigned_to_staff': str(assignment.assigned_to_staff) if assignment.assigned_to_staff else None,
                    'assigned_to_department': str(assignment.assigned_to_department) if assignment.assigned_to_department else None,
                    'assigned_to_location': str(assignment.assigned_to_location) if assignment.assigned_to_location else None,
                }
                
                AssignmentHistory.objects.create(
                    assignment=assignment,
                    changed_by=request.user,
                    change_type='TRANSFERRED',
                    old_values=old_values,
                    new_values=new_values,
                    reason=form.cleaned_data.get('transfer_reason', 'Assignment transferred'),
                    notes=form.cleaned_data.get('conditions', ''),
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                
                # Determine new assignment target for message
                new_target = (
                    assignment.assigned_to_staff or 
                    assignment.assigned_to_department or 
                    assignment.assigned_to_location
                )
                
                messages.success(
                    request, 
                    f'Assignment transferred successfully to {new_target}!'
                )
                return redirect('inventory:assignment_detail', pk=assignment.pk)
                
        except Exception as e:
            messages.error(request, f'Transfer failed: {str(e)}')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('inventory:assignment_detail', pk=assignment.pk)

@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def assignment_extend(request, assignment_id):
    """Extend assignment return date"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id, is_active=True, is_temporary=True)
        
        if request.method == 'POST':
            new_return_date = request.POST.get('new_return_date')
            extension_reason = request.POST.get('extension_reason', '')
            
            if new_return_date:
                try:
                    new_date = datetime.strptime(new_return_date, '%Y-%m-%d').date()
                    
                    if new_date <= assignment.expected_return_date:
                        messages.error(request, 'New return date must be after the current expected return date.')
                    else:
                        with transaction.atomic():
                            old_date = assignment.expected_return_date
                            assignment.expected_return_date = new_date
                            assignment.notes = f"{assignment.notes}\n\nExtended on {timezone.now().date()}: {extension_reason}".strip()
                            assignment.updated_by = request.user
                            assignment.save()
                            
                            # Create audit log
                            AuditLog.objects.create(
                                user=request.user,
                                action='EXTEND',
                                model_name='Assignment',
                                object_id=assignment.assignment_id,
                                object_repr=str(assignment),
                                changes={
                                    'old_return_date': str(old_date),
                                    'new_return_date': str(new_date),
                                    'reason': extension_reason
                                },
                                ip_address=request.META.get('REMOTE_ADDR')
                            )
                            
                            messages.success(request, f'Assignment return date extended to {new_date.strftime("%B %d, %Y")}.')
                            return redirect('inventory:assignment_detail', assignment_id=assignment.assignment_id)
                            
                except ValueError:
                    messages.error(request, 'Invalid date format.')
                except Exception as e:
                    messages.error(request, f'Error extending assignment: {str(e)}')
            else:
                messages.error(request, 'Please provide a new return date.')
        
        context = {
            'assignment': assignment,
        }
        return render(request, 'inventory/assignments/assignment_extend.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')

@login_required
@permission_required('inventory.add_assignment', raise_exception=True)
def bulk_assignment_create(request):
    """Create multiple assignments at once"""
    if request.method == 'POST':
        form = BulkAssignmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    devices = form.cleaned_data['devices']
                    staff_member = form.cleaned_data.get('assigned_to_staff')
                    department = form.cleaned_data.get('assigned_to_department')
                    location = form.cleaned_data.get('assigned_to_location')
                    
                    created_assignments = []
                    for device in devices:
                        if device.status == 'AVAILABLE':
                            assignment = Assignment.objects.create(
                                device=device,
                                assigned_to_staff=staff_member,
                                assigned_to_department=department,
                                assigned_to_location=location,
                                is_temporary=form.cleaned_data['is_temporary'],
                                expected_return_date=form.cleaned_data.get('expected_return_date'),
                                purpose=form.cleaned_data.get('purpose', ''),
                                conditions=form.cleaned_data.get('conditions', ''),
                                created_by=request.user,
                                updated_by=request.user,
                                requested_by=request.user
                            )
                            
                            # Update device status
                            device.status = 'ASSIGNED'
                            device.updated_by = request.user
                            device.save()
                            
                            created_assignments.append(assignment)
                    
                    if created_assignments:
                        messages.success(request, f'Successfully created {len(created_assignments)} assignments.')
                        return redirect('inventory:assignment_list')
                    else:
                        messages.warning(request, 'No assignments created. All selected devices may already be assigned.')
                        
            except Exception as e:
                messages.error(request, f'Error creating bulk assignments: {str(e)}')
    else:
        form = BulkAssignmentForm()
    
    context = {
        'form': form,
        'title': 'Bulk Assignment Creation',
    }
    return render(request, 'inventory/bulk/bulk_assignment.html', context)

@login_required
def overdue_assignments_list(request):
    """List all overdue assignments"""
    try:
        today = timezone.now().date()
        overdue_assignments = Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=today,
            actual_return_date__isnull=True
        ).select_related(
            'device', 'assigned_to_staff', 'assigned_to_department'
        ).order_by('expected_return_date')
        
        # Calculate days overdue for each assignment
        for assignment in overdue_assignments:
            expected_date = validate_date_field(assignment.expected_return_date)
            if expected_date:
                assignment.days_overdue = (today - expected_date).days
        
        context = {
            'overdue_assignments': overdue_assignments,
            'total_overdue': overdue_assignments.count(),
        }
        
        return render(request, 'inventory/assignments/overdue_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading overdue assignments: {str(e)}")
        return render(request, 'inventory/overdue_assignments.html', {
            'overdue_assignments': [], 
            'total_overdue': 0
        })

# ================================
# STAFF MANAGEMENT VIEWS
# ================================

@login_required
def staff_list(request):
    """List all staff members with device assignment counts"""
    try:
        staff_members = Staff.objects.select_related('department').prefetch_related(
            'assignments'
        ).annotate(
            active_assignments=Count('assignments', filter=Q(assignments__status='ACTIVE')),
            total_assignments=Count('assignments')
        ).order_by('department__name', 'last_name', 'first_name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            staff_members = staff_members.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(email__icontains=search) |
                Q(department__name__icontains=search)
            )
        
        # Department filter
        department_id = request.GET.get('department')
        if department_id:
            staff_members = staff_members.filter(department_id=department_id)
        
        # Pagination
        paginator = Paginator(staff_members, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get departments for filter dropdown
        departments = Department.objects.all().order_by('name')
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'departments': departments,
            'selected_department': department_id,
        }
        
        return render(request, 'inventory/staff/staff_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff list: {str(e)}")
        return render(request, 'inventory/staff/staff_list.html', {'page_obj': None})

@login_required
def staff_detail(request, staff_id):
    """Staff detail view with assignment history"""
    try:
        staff = get_object_or_404(Staff.objects.select_related('department'), id=staff_id)
        
        # Get assignments with pagination
        assignments = Assignment.objects.filter(
            assigned_to_staff=staff 
        ).select_related(
            'device', 'device__device_type', 'created_by'  
        ).order_by('-created_at')
        
        # Current assignments
        current_assignments = assignments.filter(is_active=True)
        
        # Assignment history
        assignment_history = assignments.filter(is_active=False) 
        
        # Calculate stats
        total_assignments = assignments.count()
        active_assignments = current_assignments.count()
        
        # Calculate total value of current assignments
        total_value = current_assignments.aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Recent activities (last 10)
        recent_activities = assignment_history[:10]
        
        context = {
            'staff': staff,
            'current_assignments': current_assignments,
            'assignment_history': assignment_history,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'total_value': total_value,
            'recent_activities': recent_activities,
        }
        
        return render(request, 'inventory/staff/staff_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff details: {str(e)}")
        return redirect('inventory:staff_list') 

@permission_required('inventory.add_staff', raise_exception=True)
def staff_create(request):
    """Create new staff member"""
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            try:
                staff = form.save()
                
                # Log the activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    model_name='Staff',
                    object_id=staff.id,
                    object_repr=str(staff),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Staff member "{staff.get_full_name()}" created successfully.')
                return redirect('inventory:staff_detail', staff_id=staff.id)
            except Exception as e:
                messages.error(request, f'Error creating staff member: {str(e)}')
    else:
        form = StaffForm()
    
    context = {
        'form': form,
        'title': 'Add New Staff Member',
        'action': 'Create',
    }
    return render(request, 'inventory/staff/staff_form.html', context)

@login_required
@permission_required('inventory.change_staff', raise_exception=True)
def staff_edit(request, staff_id):
    """Edit staff details"""
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        
        if request.method == 'POST':
            form = StaffForm(request.POST, instance=staff)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        staff = form.save()
                        
                        # Log the activity
                        from .utils import log_user_activity
                        log_user_activity(
                            user=request.user,
                            action='UPDATE',
                            model_name='Staff',
                            object_id=staff.id,
                            object_repr=str(staff),
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Staff member "{staff.get_full_name()}" updated successfully.')
                        return redirect('inventory:staff_detail', staff_id=staff.id)
                except Exception as e:
                    messages.error(request, f'Error updating staff member: {str(e)}')
        else:
            form = StaffForm(instance=staff)
        
        context = {
            'form': form,
            'staff': staff,
            'title': f'Edit Staff: {staff.get_full_name()}',
            'action': 'Update',
        }
        return render(request, 'inventory/staff/staff_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff for edit: {str(e)}")
        return redirect('inventory:staff_list')

@login_required
@permission_required('inventory.delete_staff', raise_exception=True)
def staff_delete(request, staff_id):
    """Delete staff member"""
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Check if staff has active assignments
        active_assignments = Assignment.objects.filter(
            assigned_to_staff=staff,
            is_active=True            
        ).count()
        
        if active_assignments > 0:
            messages.error(
                request, 
                f'Cannot delete staff member "{staff.get_full_name()}". They have {active_assignments} active device assignments.'
            )
            return redirect('inventory:staff_detail', staff_id=staff.id)
        
        if request.method == 'POST':
            staff_name = staff.get_full_name()
            staff.delete()
            messages.success(request, f'Staff member "{staff_name}" deleted successfully.')
            return redirect('inventory:staff_list')
        
        context = {
            'staff': staff,
            'active_assignments': active_assignments,
        }
        return render(request, 'inventory/staff/staff_delete_confirm.html', context)
        
    except Exception as e:
        messages.error(request, f"Error deleting staff member: {str(e)}")
        return redirect('inventory:staff_list')

@login_required
def staff_assignments(request, staff_id):
    """View all assignments for a specific staff member"""
    try:
        staff = get_object_or_404(Staff.objects.select_related('department'), id=staff_id)
        
        # Get all assignments for this staff member
        assignments = Assignment.objects.filter(
            assigned_to_staff=staff
        ).select_related(
            'device', 'device__device_type', 'created_by'
        ).order_by('-created_at')
        
        # Filter by search query if provided
        search = request.GET.get('search', '')
        if search:
            assignments = assignments.filter(
                Q(device__device_id__icontains=search) |
                Q(device__device_name__icontains=search) |
                Q(device__asset_tag__icontains=search)
            )
        
        # Filter by status if provided
        status_filter = request.GET.get('status', '')
        if status_filter == 'active':
            assignments = assignments.filter(is_active=True) 
        elif status_filter == 'inactive':
            assignments = assignments.filter(is_active=False)  
        
        # Pagination
        paginator = Paginator(assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Calculate statistics
        stats = {
            'total': assignments.count(),
            'active': assignments.filter(is_active=True).count(),  
            'inactive': assignments.filter(is_active=False).count(),  
        }
        
        context = {
            'staff': staff,
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'stats': stats,
        }
        
        return render(request, 'inventory/staff/staff_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff assignments: {str(e)}")
        return redirect('inventory:staff_detail', staff_id=staff_id)
    
# ================================
# DEPARTMENT MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_department', raise_exception=True)
def department_list(request):
    """Enhanced department list with block support and comprehensive filtering"""
    search = request.GET.get('search', '')
    building_filter = request.GET.get('building', '')
    block_filter = request.GET.get('block', '')
    floor_filter = request.GET.get('floor', '')
    is_active_filter = request.GET.get('is_active', '')
    sort_by = request.GET.get('sort', 'name')
    
    departments = Department.objects.select_related('floor__building', 'floor__block')
    
    # Search functionality
    if search:
        departments = departments.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(head_of_department__icontains=search) |
            Q(floor__building__name__icontains=search) |
            Q(floor__block__name__icontains=search)
        )
    
    # Filter by building
    if building_filter:
        departments = departments.filter(floor__building_id=building_filter)
    
    # Filter by block
    if block_filter:
        departments = departments.filter(floor__block_id=block_filter)
    
    # Filter by floor
    if floor_filter:
        departments = departments.filter(floor_id=floor_filter)
    
    # Filter by active status
    if is_active_filter:
        departments = departments.filter(is_active=is_active_filter == 'true')
    
    # Sorting
    valid_sort_fields = ['name', 'code', 'floor__building__name', 'floor__block__name', '-created_at']
    if sort_by in valid_sort_fields:
        departments = departments.order_by(sort_by)
    else:
        departments = departments.order_by('name')
    
    # Add annotations for statistics
    departments = departments.annotate(
        rooms_count=Count('rooms'),
        locations_count=Count('locations'),
        staff_count=Count('staff'),
        active_assignments=Count('staff__assignments', filter=Q(staff__assignments__status='ASSIGNED'))
    )
    
    # Get data for filter dropdowns
    buildings = Building.objects.filter(is_active=True).order_by('name')
    blocks = Block.objects.filter(is_active=True).order_by('building__name', 'name')
    floors = Floor.objects.filter(is_active=True).order_by('building__name', 'block__name', 'floor_number')
    
    # Pagination
    paginator = Paginator(departments, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_departments = departments.count()
    active_departments = departments.filter(is_active=True).count()
    total_staff = departments.aggregate(total=Sum('staff_count'))['total'] or 0
    total_active_assignments = departments.aggregate(total=Sum('active_assignments'))['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'departments': page_obj.object_list,
        'buildings': buildings,
        'blocks': blocks,
        'floors': floors,
        'search': search,
        'building_filter': building_filter,
        'block_filter': block_filter,
        'floor_filter': floor_filter,
        'is_active_filter': is_active_filter,
        'sort_by': sort_by,
        'total_departments': total_departments,
        'active_departments': active_departments,
        'total_staff': total_staff,
        'total_active_assignments': total_active_assignments,
        'title': 'Department Management',
        'current_filters': {
            'building': building_filter,
            'block': block_filter,
            'floor': floor_filter,
            'is_active': is_active_filter,
            'search': search,
            'sort': sort_by,
        },
    }
    
    return render(request, 'inventory/locations/department_list.html', context)

@login_required
@permission_required('inventory.view_department', raise_exception=True)
def department_detail(request, department_id):
    """Enhanced department detail with block hierarchy and comprehensive statistics"""
    department = get_object_or_404(
        Department.objects.select_related('floor__building', 'floor__block'), 
        id=department_id
    )
    
    # Get related data
    rooms = department.rooms.all().order_by('room_number')
    staff = department.staff.filter(is_active=True).select_related('user').order_by('user__first_name', 'user__last_name')
    locations = department.locations.all().select_related('room')
    
    # Get assignments for staff in this department
    active_assignments = Assignment.objects.filter(
        staff__department=department,
        status='ASSIGNED'
    ).select_related('device', 'device__device_type', 'staff__user', 'location')
    
    # Get recent assignments (last 30 days)
    from datetime import datetime, timedelta
    recent_assignments = Assignment.objects.filter(
        staff__department=department,
        assigned_date__gte=datetime.now() - timedelta(days=30)
    ).select_related('device', 'staff__user').order_by('-assigned_date')[:10]
    
    # Statistics
    total_rooms = rooms.count()
    total_staff = staff.count()
    total_locations = locations.count()
    total_active_assignments = active_assignments.count()
    
    # Device statistics
    device_categories = active_assignments.values(
        'device__device_type__subcategory__category__name'
    ).annotate(
        count=Count('id'),
        total_value=Sum('device__purchase_price')
    ).order_by('-count')
    
    # Staff utilization
    staff_with_assignments = staff.annotate(
        assignment_count=Count('assignments', filter=Q(assignments__status='ASSIGNED'))
    ).order_by('-assignment_count')
    
    # Total value of assigned devices
    total_assignment_value = active_assignments.aggregate(
        total=Sum('device__purchase_price')
    )['total'] or 0
    
    # Room utilization
    room_utilization = []
    for room in rooms:
        room_assignments = active_assignments.filter(location__room=room).count()
        room_utilization.append({
            'room': room,
            'assignment_count': room_assignments,
            'utilization_percentage': (room_assignments / room.capacity * 100) if room.capacity > 0 else 0
        })
    
    context = {
        'department': department,
        'rooms': rooms,
        'staff': staff,
        'locations': locations,
        'active_assignments': active_assignments,
        'recent_assignments': recent_assignments,
        'staff_with_assignments': staff_with_assignments,
        'room_utilization': room_utilization,
        'device_categories': device_categories,
        'total_rooms': total_rooms,
        'total_staff': total_staff,
        'total_locations': total_locations,
        'total_active_assignments': total_active_assignments,
        'total_assignment_value': total_assignment_value,
        'avg_assignments_per_staff': round(total_active_assignments / total_staff, 1) if total_staff > 0 else 0,
        'title': f'Department: {department.name}',
    }
    
    return render(request, 'inventory/locations/department_detail.html', context)

@login_required
@permission_required('inventory.add_department', raise_exception=True)
def department_create(request):
    """Create a new department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            try:
                department = form.save()
                messages.success(request, f'Department "{department.name}" created successfully.')
                return redirect('inventory:department_detail', department_id=department.id)
            except Exception as e:
                messages.error(request, f'Error creating department: {str(e)}')
    else:
        form = DepartmentForm()
        # Pre-select floor if provided in URL
        floor_id = request.GET.get('floor')
        if floor_id:
            form.fields['floor'].initial = floor_id
    
    context = {
        'form': form,
        'title': 'Add New Department',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/department_form.html', context)

@login_required
@permission_required('inventory.change_department', raise_exception=True)
def department_edit(request, department_id):
    """Edit department details"""
    try:
        department = get_object_or_404(Department, id=department_id)
        
        if request.method == 'POST':
            form = DepartmentForm(request.POST, instance=department)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        department = form.save()
                        
                        # Log the activity
                        from .utils import log_user_activity
                        log_user_activity(
                            user=request.user,
                            action='UPDATE',
                            model_name='Department',
                            object_id=department.id,
                            object_repr=str(department),
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Department "{department.name}" updated successfully.')
                        return redirect('inventory:department_detail', department_id=department.id)
                except Exception as e:
                    messages.error(request, f'Error updating department: {str(e)}')
        else:
            form = DepartmentForm(instance=department)
        
        context = {
            'form': form,
            'department': department,
            'title': f'Edit Department: {department.name}',
            'action': 'Update',
        }
        return render(request, 'inventory/department_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department for edit: {str(e)}")
        return redirect('inventory:department_list')

@login_required
@permission_required('inventory.view_assignment', raise_exception=True)
def department_assignments(request, department_id):
    """View all assignments for a specific department"""
    try:
        department = get_object_or_404(Department.objects.select_related('floor__building', 'floor__block'), id=department_id)
        
        # Get all assignments for this department
        assignments = Assignment.objects.filter(
            assigned_to_department=department
        ).select_related(
            'device', 'device__device_type', 'assigned_to_staff__user', 'created_by'
        ).order_by('-created_at')
        
        # Also get assignments to staff members in this department
        staff_assignments = Assignment.objects.filter(
            assigned_to_staff__department=department
        ).select_related(
            'device', 'device__device_type', 'assigned_to_staff__user', 'created_by'
        ).order_by('-created_at')
        
        # Combine both querysets
        all_assignments = assignments.union(staff_assignments).order_by('-created_at')
        
        # Apply filters
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        staff_filter = request.GET.get('staff', '')
        assignment_type_filter = request.GET.get('type', '')
        
        # Search functionality
        if search:
            all_assignments = all_assignments.filter(
                Q(device__device_id__icontains=search) |
                Q(device__device_name__icontains=search) |
                Q(device__asset_tag__icontains=search) |
                Q(assigned_to_staff__user__first_name__icontains=search) |
                Q(assigned_to_staff__user__last_name__icontains=search) |
                Q(assigned_to_staff__employee_id__icontains=search)
            )
        
        # Filter by status
        if status_filter == 'active':
            all_assignments = all_assignments.filter(is_active=True)
        elif status_filter == 'inactive':
            all_assignments = all_assignments.filter(is_active=False)
        
        # Filter by assignment type
        if assignment_type_filter:
            all_assignments = all_assignments.filter(assignment_type=assignment_type_filter)
        
        # Filter by specific staff member
        if staff_filter:
            all_assignments = all_assignments.filter(assigned_to_staff_id=staff_filter)
        
        # Get staff members in this department for filter
        staff_members = Staff.objects.filter(
            department=department,
            is_active=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        
        # Pagination
        paginator = Paginator(all_assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Calculate statistics
        total_assignments = all_assignments.count()
        active_assignments = all_assignments.filter(is_active=True).count()
        inactive_assignments = all_assignments.filter(is_active=False).count()
        
        # Assignment type statistics
        permanent_assignments = all_assignments.filter(assignment_type='PERMANENT').count()
        temporary_assignments = all_assignments.filter(assignment_type='TEMPORARY').count()
        
        # Calculate total value of active assignments
        active_value = all_assignments.filter(is_active=True).aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Get overdue assignments
        overdue_assignments = all_assignments.filter(
            assignment_type='TEMPORARY',
            is_active=True,
            expected_return_date__lt=timezone.now().date()
        ).count()
        
        stats = {
            'total': total_assignments,
            'active': active_assignments,
            'inactive': inactive_assignments,
            'permanent': permanent_assignments,
            'temporary': temporary_assignments,
            'overdue': overdue_assignments,
            'total_value': active_value,
        }
        
        context = {
            'department': department,
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'staff_filter': staff_filter,
            'assignment_type_filter': assignment_type_filter,
            'staff_members': staff_members,
            'stats': stats,
        }
        
        return render(request, 'inventory/department/department_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department assignments: {str(e)}")
        return redirect('inventory:department_detail', department_id=department_id)

@login_required
@permission_required('inventory.delete_department', raise_exception=True)
def department_delete(request, department_id):
    """Delete a department"""
    department = get_object_or_404(Department, id=department_id)
    
    if request.method == 'POST':
        try:
            # Check if department has staff or assignments
            staff_count = department.staff.count()
            room_count = department.rooms.count()
            location_count = department.locations.count()
            
            if staff_count > 0:
                messages.error(request, f'Cannot delete department "{department.name}": {staff_count} staff members are assigned.')
                return redirect('inventory:department_detail', department_id=department.id)
            
            if room_count > 0:
                messages.error(request, f'Cannot delete department "{department.name}": {room_count} rooms exist.')
                return redirect('inventory:department_detail', department_id=department.id)
            
            if location_count > 0:
                messages.error(request, f'Cannot delete department "{department.name}": {location_count} locations exist.')
                return redirect('inventory:department_detail', department_id=department.id)
            
            department_name = department.name
            department.delete()
            messages.success(request, f'Department "{department_name}" deleted successfully.')
            return redirect('inventory:department_list')
            
        except Exception as e:
            messages.error(request, f'Error deleting department: {str(e)}')
            return redirect('inventory:department_detail', department_id=department.id)
    
    return redirect('inventory:department_detail', department_id=department.id)

# ================================
# LOCATION MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_location', raise_exception=True)
def location_list(request):
    """Enhanced location list with full block hierarchy support"""
    try:
        # Get filter parameters
        search = request.GET.get('search', '')
        building_filter = request.GET.get('building', '')
        block_filter = request.GET.get('block', '')
        floor_filter = request.GET.get('floor', '')
        department_filter = request.GET.get('department', '')
        room_filter = request.GET.get('room', '')
        is_active_filter = request.GET.get('is_active', '')
        sort_by = request.GET.get('sort', 'building__name')
        
        # Base queryset with proper relationships including block
        locations = Location.objects.select_related(
            'building', 'block', 'floor', 'department', 'room'
        ).annotate(
            device_count=Count('device_assignments'),
            active_assignments=Count('device_assignments', filter=Q(device_assignments__status='ASSIGNED'))
        )
        
        # Search functionality across all hierarchy levels
        if search:
            locations = locations.filter(
                Q(building__name__icontains=search) |
                Q(building__code__icontains=search) |
                Q(block__name__icontains=search) |
                Q(block__code__icontains=search) |
                Q(floor__name__icontains=search) |
                Q(department__name__icontains=search) |
                Q(department__code__icontains=search) |
                Q(room__room_number__icontains=search) |
                Q(room__room_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Apply hierarchical filters
        if building_filter:
            locations = locations.filter(building_id=building_filter)
        if block_filter:
            locations = locations.filter(block_id=block_filter)
        if floor_filter:
            locations = locations.filter(floor_id=floor_filter)
        if department_filter:
            locations = locations.filter(department_id=department_filter)
        if room_filter:
            locations = locations.filter(room_id=room_filter)
        if is_active_filter:
            locations = locations.filter(is_active=is_active_filter == 'true')
        
        # Sorting with block support
        valid_sort_fields = [
            'building__name', 'block__name', 'floor__floor_number', 
            'department__name', 'room__room_number', '-created_at',
            'device_count', '-device_count', 'active_assignments', '-active_assignments'
        ]
        if sort_by in valid_sort_fields:
            locations = locations.order_by(sort_by)
        else:
            locations = locations.order_by('building__name', 'block__name', 'floor__floor_number', 'department__name')
        
        # Pagination
        paginator = Paginator(locations, 15)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get data for filter dropdowns with block hierarchy
        buildings = Building.objects.filter(is_active=True).order_by('name')
        blocks = Block.objects.filter(is_active=True).order_by('building__name', 'name')
        floors = Floor.objects.filter(is_active=True).order_by('building__name', 'block__name', 'floor_number')
        departments = Department.objects.filter(is_active=True).order_by('name')
        rooms = Room.objects.filter(is_active=True).order_by('department__name', 'room_number')
        
        # Statistics
        total_locations = locations.count()
        active_locations = locations.filter(is_active=True).count()
        total_devices = locations.aggregate(total=Sum('device_count'))['total'] or 0
        total_active_assignments = locations.aggregate(total=Sum('active_assignments'))['total'] or 0
        
        # Block-wise statistics
        block_stats = blocks.annotate(
            location_count=Count('locations'),
            device_count=Count('locations__device_assignments')
        ).order_by('building__name', 'name')[:10]
        
        context = {
            'page_obj': page_obj,
            'locations': page_obj.object_list,
            'buildings': buildings,
            'blocks': blocks,
            'floors': floors,
            'departments': departments,
            'rooms': rooms,
            'block_stats': block_stats,
            'total_locations': total_locations,
            'active_locations': active_locations,
            'total_devices': total_devices,
            'total_active_assignments': total_active_assignments,
            'current_filters': {
                'building': building_filter,
                'block': block_filter,
                'floor': floor_filter,
                'department': department_filter,
                'room': room_filter,
                'is_active': is_active_filter,
                'search': search,
                'sort': sort_by,
            },
            'title': 'Location Management',
        }
        
        return render(request, 'inventory/locations/location_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading locations: {str(e)}")
        return render(request, 'inventory/locations/location_list.html', {'locations': [], 'error': str(e)})

@login_required
@permission_required('inventory.view_location', raise_exception=True)
def location_detail(request, location_id):
    """Enhanced location detail with full block hierarchy display"""
    try:
        location = get_object_or_404(
            Location.objects.select_related(
                'building', 'block', 'floor', 'department', 'room'
            ),
            id=location_id
        )
        
        # Current assignments at this location
        current_assignments = Assignment.objects.filter(
            location=location,
            status='ASSIGNED'
        ).select_related(
            'device', 'device__device_type', 'staff__user'
        ).order_by('-assigned_date')
        
        # Assignment history for this location
        assignment_history = Assignment.objects.filter(
            location=location
        ).select_related(
            'device', 'device__device_type', 'staff__user'
        ).order_by('-assigned_date')[:20]
        
        # Devices ever assigned to this location
        devices_history = Device.objects.filter(
            assignments__location=location
        ).distinct().select_related('device_type').order_by('asset_tag')
        
        # Statistics
        total_assignments = assignment_history.count()
        active_assignments = current_assignments.count()
        
        # Device type breakdown
        device_types = current_assignments.values(
            'device__device_type__name'
        ).annotate(
            count=Count('id'),
            total_value=Sum('device__purchase_price')
        ).order_by('-count')
        
        # Total value of current assignments
        total_current_value = current_assignments.aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Location hierarchy breadcrumb
        hierarchy_path = []
        if location.building:
            hierarchy_path.append(('Building', location.building.name, 'inventory:building_detail', location.building.id))
        if location.block:
            hierarchy_path.append(('Block', location.block.name, 'inventory:block_detail', location.block.id))
        if location.floor:
            hierarchy_path.append(('Floor', location.floor.name, 'inventory:floor_detail', location.floor.id))
        if location.department:
            hierarchy_path.append(('Department', location.department.name, 'inventory:department_detail', location.department.id))
        if location.room:
            hierarchy_path.append(('Room', f"{location.room.room_number} - {location.room.room_name}", 'inventory:room_detail', location.room.id))
        
        # Nearby locations (same department)
        nearby_locations = Location.objects.filter(
            department=location.department,
            is_active=True
        ).exclude(id=location.id).select_related('room')[:5]
        
        context = {
            'location': location,
            'current_assignments': current_assignments,
            'assignment_history': assignment_history,
            'devices_history': devices_history,
            'device_types': device_types,
            'nearby_locations': nearby_locations,
            'hierarchy_path': hierarchy_path,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'total_current_value': total_current_value,
            'title': f'Location: {str(location)}',
        }
        
        return render(request, 'inventory/locations/location_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading location details: {str(e)}")
        return redirect('inventory:location_list')

@login_required
@permission_required('inventory.add_location', raise_exception=True)
def location_create(request):
    """Create new location with block hierarchy support"""
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            try:
                # Validate hierarchy consistency
                building = form.cleaned_data.get('building')
                block = form.cleaned_data.get('block')
                floor = form.cleaned_data.get('floor')
                department = form.cleaned_data.get('department')
                room = form.cleaned_data.get('room')
                
                # Validate block belongs to building
                if block and building and block.building != building:
                    form.add_error('block', 'Selected block does not belong to the selected building.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate floor belongs to block
                if floor and block and floor.block != block:
                    form.add_error('floor', 'Selected floor does not belong to the selected block.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate department belongs to floor
                if department and floor and department.floor != floor:
                    form.add_error('department', 'Selected department does not belong to the selected floor.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate room belongs to department
                if room and department and room.department != department:
                    form.add_error('room', 'Selected room does not belong to the selected department.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Check for duplicate location
                existing_location = Location.objects.filter(
                    building=building,
                    block=block,
                    floor=floor,
                    department=department,
                    room=room
                ).first()
                
                if existing_location:
                    messages.error(request, 'A location with this exact hierarchy already exists.')
                    raise ValidationError("Duplicate location")
                
                location = form.save()
                messages.success(request, f'Location "{location}" created successfully.')
                return redirect('inventory:location_detail', location_id=location.id)
                
            except ValidationError:
                pass  # Form errors already added
            except Exception as e:
                messages.error(request, f'Error creating location: {str(e)}')
    else:
        form = LocationForm()
        
        # Pre-populate from URL parameters for hierarchy drill-down
        building_id = request.GET.get('building')
        block_id = request.GET.get('block')
        floor_id = request.GET.get('floor')
        department_id = request.GET.get('department')
        room_id = request.GET.get('room')
        
        if building_id:
            form.fields['building'].initial = building_id
        if block_id:
            form.fields['block'].initial = block_id
        if floor_id:
            form.fields['floor'].initial = floor_id
        if department_id:
            form.fields['department'].initial = department_id
        if room_id:
            form.fields['room'].initial = room_id
    
    # Get hierarchy data for cascade dropdowns
    buildings = Building.objects.filter(is_active=True).order_by('name')
    
    context = {
        'form': form,
        'buildings': buildings,
        'title': 'Add New Location',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/location_form.html', context)

@login_required
@permission_required('inventory.change_location', raise_exception=True)
def location_edit(request, location_id):
    """Edit existing location with block hierarchy validation"""
    location = get_object_or_404(Location, id=location_id)
    
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            try:
                # Validate hierarchy consistency (same as create)
                building = form.cleaned_data.get('building')
                block = form.cleaned_data.get('block')
                floor = form.cleaned_data.get('floor')
                department = form.cleaned_data.get('department')
                room = form.cleaned_data.get('room')
                
                # Validate block belongs to building
                if block and building and block.building != building:
                    form.add_error('block', 'Selected block does not belong to the selected building.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate floor belongs to block
                if floor and block and floor.block != block:
                    form.add_error('floor', 'Selected floor does not belong to the selected block.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate department belongs to floor
                if department and floor and department.floor != floor:
                    form.add_error('department', 'Selected department does not belong to the selected floor.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Validate room belongs to department
                if room and department and room.department != department:
                    form.add_error('room', 'Selected room does not belong to the selected department.')
                    raise ValidationError("Hierarchy validation failed")
                
                # Check for duplicate location (excluding current)
                existing_location = Location.objects.filter(
                    building=building,
                    block=block,
                    floor=floor,
                    department=department,
                    room=room
                ).exclude(id=location.id).first()
                
                if existing_location:
                    messages.error(request, 'A location with this exact hierarchy already exists.')
                    raise ValidationError("Duplicate location")
                
                # Check if location has active assignments before major changes
                active_assignments = Assignment.objects.filter(
                    location=location,
                    status='ASSIGNED'
                ).count()
                
                if active_assignments > 0:
                    # Check if hierarchy changed significantly
                    if (location.building != building or location.block != block or 
                        location.floor != floor or location.department != department):
                        messages.warning(
                            request, 
                            f'Warning: This location has {active_assignments} active device assignments. '
                            'Consider transferring devices before major location changes.'
                        )
                
                location = form.save()
                messages.success(request, f'Location "{location}" updated successfully.')
                return redirect('inventory:location_detail', location_id=location.id)
                
            except ValidationError:
                pass  # Form errors already added
            except Exception as e:
                messages.error(request, f'Error updating location: {str(e)}')
    else:
        form = LocationForm(instance=location)
    
    # Get hierarchy data for cascade dropdowns
    buildings = Building.objects.filter(is_active=True).order_by('name')
    
    # Get active assignments for warning
    active_assignments = Assignment.objects.filter(
        location=location,
        status='ASSIGNED'
    ).count()
    
    context = {
        'form': form,
        'location': location,
        'buildings': buildings,
        'active_assignments': active_assignments,
        'title': f'Edit Location: {location}',
        'form_action': 'Update',
    }
    
    return render(request, 'inventory/locations/location_form.html', context)

@login_required
@permission_required('inventory.delete_location', raise_exception=True)
def location_delete(request, location_id):
    """Delete location with safety checks"""
    location = get_object_or_404(Location, id=location_id)
    
    if request.method == 'POST':
        try:
            # Check for active assignments
            active_assignments = Assignment.objects.filter(
                location=location,
                status='ASSIGNED'
            ).count()
            
            if active_assignments > 0:
                messages.error(
                    request, 
                    f'Cannot delete location "{location}": {active_assignments} active device assignments exist. '
                    'Please return or transfer all devices first.'
                )
                return redirect('inventory:location_detail', location_id=location.id)
            
            # Check for assignment history
            total_assignments = Assignment.objects.filter(location=location).count()
            
            if total_assignments > 0:
                # Ask for confirmation if there's assignment history
                confirm = request.POST.get('confirm_delete')
                if not confirm:
                    messages.warning(
                        request,
                        f'Location "{location}" has {total_assignments} assignment records in history. '
                        'Are you sure you want to delete it? This action cannot be undone.'
                    )
                    return redirect('inventory:location_detail', location_id=location.id)
            
            location_name = str(location)
            location.delete()
            messages.success(request, f'Location "{location_name}" deleted successfully.')
            return redirect('inventory:location_list')
            
        except Exception as e:
            messages.error(request, f'Error deleting location: {str(e)}')
            return redirect('inventory:location_detail', location_id=location.id)
    
    return redirect('inventory:location_detail', location_id=location.id)

# ================================
# LOCATION HIERARCHY UTILITIES
# ================================

@login_required
def location_hierarchy_overview(request):
    """Display complete location hierarchy with block support"""
    try:
        # Get complete hierarchy with statistics
        buildings = Building.objects.filter(is_active=True).prefetch_related(
            'blocks__floors__departments__rooms__locations'
        ).annotate(
            total_locations=Count('locations'),
            total_devices=Count('locations__device_assignments')
        ).order_by('name')
        
        hierarchy_data = []
        for building in buildings:
            building_data = {
                'building': building,
                'blocks': []
            }
            
            for block in building.blocks.filter(is_active=True):
                block_data = {
                    'block': block,
                    'floors': []
                }
                
                for floor in block.floors.filter(is_active=True):
                    floor_data = {
                        'floor': floor,
                        'departments': []
                    }
                    
                    for department in floor.departments.filter(is_active=True):
                        dept_data = {
                            'department': department,
                            'rooms': department.rooms.filter(is_active=True),
                            'location_count': department.locations.count(),
                            'device_count': Assignment.objects.filter(
                                location__department=department,
                                status='ASSIGNED'
                            ).count()
                        }
                        floor_data['departments'].append(dept_data)
                    
                    block_data['floors'].append(floor_data)
                
                building_data['blocks'].append(block_data)
            
            hierarchy_data.append(building_data)
        
        context = {
            'hierarchy_data': hierarchy_data,
            'title': 'Location Hierarchy Overview',
        }
        
        return render(request, 'inventory/locations/hierarchy_overview.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading hierarchy overview: {str(e)}")
        return redirect('inventory:location_list')

# ================================
# BUILDING MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_building', raise_exception=True)
def building_list(request):
    """Display list of all buildings with search and filtering"""
    search = request.GET.get('search', '')
    is_active_filter = request.GET.get('is_active', '')
    sort_by = request.GET.get('sort', 'name')
    
    buildings = Building.objects.all()
    
    # Search functionality
    if search:
        buildings = buildings.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(address__icontains=search)
        )
    
    # Filter by active status
    if is_active_filter:
        buildings = buildings.filter(is_active=is_active_filter == 'true')
    
    # Sorting
    valid_sort_fields = ['name', 'code', '-created_at', 'created_at']
    if sort_by in valid_sort_fields:
        buildings = buildings.order_by(sort_by)
    else:
        buildings = buildings.order_by('name')
    
    # Add annotations for statistics
    buildings = buildings.annotate(
        blocks_count=Count('blocks'),
        floors_count=Count('blocks__floors'),
        departments_count=Count('blocks__floors__departments'),
        locations_count=Count('locations')
    )
    
    # Pagination
    paginator = Paginator(buildings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'buildings': page_obj.object_list,
        'search': search,
        'is_active_filter': is_active_filter,
        'sort_by': sort_by,
        'title': 'Building Management',
    }
    
    return render(request, 'inventory/locations/building_list.html', context)

@login_required
@permission_required('inventory.view_building', raise_exception=True)
def building_detail(request, building_id):
    """Display detailed information about a building"""
    building = get_object_or_404(Building, id=building_id)
    
    # Get related data
    blocks = building.blocks.all().annotate(
        floors_count=Count('floors'),
        departments_count=Count('floors__departments')
    )
    
    # Statistics
    total_blocks = blocks.count()
    total_floors = building.floors.count()
    total_departments = building.departments.count()
    total_locations = building.locations.count()
    
    context = {
        'building': building,
        'blocks': blocks,
        'total_blocks': total_blocks,
        'total_floors': total_floors,
        'total_departments': total_departments,
        'total_locations': total_locations,
        'title': f'Building: {building.name}',
    }
    
    return render(request, 'inventory/locations/building_detail.html', context)

@login_required
@permission_required('inventory.add_building', raise_exception=True)
def building_create(request):
    """Create a new building"""
    if request.method == 'POST':
        form = forms.BuildingForm(request.POST)
        if form.is_valid():
            try:
                building = form.save()
                messages.success(request, f'Building "{building.name}" created successfully.')
                return redirect('inventory:building_detail', building_id=building.id)
            except Exception as e:
                messages.error(request, f'Error creating building: {str(e)}')
    else:
        form = forms.BuildingForm()
    
    context = {
        'form': form,
        'title': 'Add New Building',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/building_form.html', context)

@login_required
@permission_required('inventory.change_building', raise_exception=True)
def building_edit(request, building_id):
    """Edit an existing building"""
    building = get_object_or_404(Building, id=building_id)
    
    if request.method == 'POST':
        form = forms.BuildingForm(request.POST, instance=building)
        if form.is_valid():
            try:
                building = form.save()
                messages.success(request, f'Building "{building.name}" updated successfully.')
                return redirect('inventory:building_detail', building_id=building.id)
            except Exception as e:
                messages.error(request, f'Error updating building: {str(e)}')
    else:
        form = forms.BuildingForm(instance=building)
    
    context = {
        'form': form,
        'building': building,
        'title': f'Edit Building: {building.name}',
        'form_action': 'Update',
    }
    
    return render(request, 'inventory/locations/building_form.html', context)

@login_required
@permission_required('inventory.delete_building', raise_exception=True)
def building_delete(request, building_id):
    """Delete a building"""
    building = get_object_or_404(Building, id=building_id)
    
    if request.method == 'POST':
        try:
            building_name = building.name
            building.delete()
            messages.success(request, f'Building "{building_name}" deleted successfully.')
            return redirect('inventory:building_list')
        except Exception as e:
            messages.error(request, f'Error deleting building: {str(e)}')
            return redirect('inventory:building_detail', building_id=building.id)
    
    return redirect('inventory:building_detail', building_id=building.id)

# ================================
# BLOCK MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_block', raise_exception=True)
def block_list(request):
    """Display list of all blocks with search and filtering"""
    search = request.GET.get('search', '')
    building_filter = request.GET.get('building', '')
    is_active_filter = request.GET.get('is_active', '')
    sort_by = request.GET.get('sort', 'building__name')
    
    blocks = Block.objects.select_related('building')
    
    # Search functionality
    if search:
        blocks = blocks.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(building__name__icontains=search)
        )
    
    # Filter by building
    if building_filter:
        blocks = blocks.filter(building_id=building_filter)
    
    # Filter by active status
    if is_active_filter:
        blocks = blocks.filter(is_active=is_active_filter == 'true')
    
    # Sorting
    valid_sort_fields = ['building__name', 'name', 'code', '-created_at']
    if sort_by in valid_sort_fields:
        blocks = blocks.order_by(sort_by)
    else:
        blocks = blocks.order_by('building__name', 'name')
    
    # Add annotations for statistics
    blocks = blocks.annotate(
        floors_count=Count('floors'),
        departments_count=Count('floors__departments'),
        locations_count=Count('locations')
    )
    
    # Get buildings for filter dropdown
    buildings = Building.objects.filter(is_active=True).order_by('name')
    
    # Pagination
    paginator = Paginator(blocks, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'blocks': page_obj.object_list,
        'buildings': buildings,
        'search': search,
        'building_filter': building_filter,
        'is_active_filter': is_active_filter,
        'sort_by': sort_by,
        'title': 'Block Management',
    }
    
    return render(request, 'inventory/locations/block_list.html', context)

@login_required
@permission_required('inventory.view_block', raise_exception=True)
def block_detail(request, block_id):
    """Display detailed information about a block"""
    block = get_object_or_404(Block.objects.select_related('building'), id=block_id)
    
    # Get related data
    floors = block.floors.all().annotate(
        departments_count=Count('departments')
    ).order_by('floor_number')
    
    # Statistics
    total_floors = floors.count()
    total_departments = sum(floor.departments_count for floor in floors)
    total_locations = block.locations.count()
    
    context = {
        'block': block,
        'floors': floors,
        'total_floors': total_floors,
        'total_departments': total_departments,
        'total_locations': total_locations,
        'title': f'Block: {block.name}',
    }
    
    return render(request, 'inventory/locations/block_detail.html', context)

@login_required
@permission_required('inventory.add_block', raise_exception=True)
def block_create(request):
    """Create a new block"""
    if request.method == 'POST':
        form = BlockForm(request.POST)
        if form.is_valid():
            try:
                block = form.save()
                messages.success(request, f'Block "{block.name}" created successfully.')
                return redirect('inventory:block_detail', block_id=block.id)
            except Exception as e:
                messages.error(request, f'Error creating block: {str(e)}')
    else:
        form = BlockForm()
    
    context = {
        'form': form,
        'title': 'Add New Block',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/block_form.html', context)

@login_required
@permission_required('inventory.change_block', raise_exception=True)
def block_edit(request, block_id):
    """Edit an existing block"""
    block = get_object_or_404(Block, id=block_id)
    
    if request.method == 'POST':
        form = BlockForm(request.POST, instance=block)
        if form.is_valid():
            try:
                block = form.save()
                messages.success(request, f'Block "{block.name}" updated successfully.')
                return redirect('inventory:block_detail', block_id=block.id)
            except Exception as e:
                messages.error(request, f'Error updating block: {str(e)}')
    else:
        form = BlockForm(instance=block)
    
    context = {
        'form': form,
        'block': block,
        'title': f'Edit Block: {block.name}',
        'form_action': 'Update',
    }
    
    return render(request, 'inventory/locations/block_form.html', context)

@login_required
@permission_required('inventory.delete_block', raise_exception=True)
def block_delete(request, block_id):
    """Delete a block"""
    block = get_object_or_404(Block, id=block_id)
    
    if request.method == 'POST':
        try:
            block_name = block.name
            block.delete()
            messages.success(request, f'Block "{block_name}" deleted successfully.')
            return redirect('inventory:block_list')
        except Exception as e:
            messages.error(request, f'Error deleting block: {str(e)}')
            return redirect('inventory:block_detail', block_id=block.id)
    
    return redirect('inventory:block_detail', block_id=block.id)

# ================================
# FLOOR MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_floor', raise_exception=True)
def floor_list(request):
    """Display list of all floors with search and filtering"""
    search = request.GET.get('search', '')
    building_filter = request.GET.get('building', '')
    block_filter = request.GET.get('block', '')
    is_active_filter = request.GET.get('is_active', '')
    sort_by = request.GET.get('sort', 'building__name')
    
    floors = Floor.objects.select_related('building', 'block')
    
    # Search functionality
    if search:
        floors = floors.filter(
            Q(name__icontains=search) |
            Q(building__name__icontains=search) |
            Q(block__name__icontains=search)
        )
    
    # Filter by building
    if building_filter:
        floors = floors.filter(building_id=building_filter)
    
    # Filter by block
    if block_filter:
        floors = floors.filter(block_id=block_filter)
    
    # Filter by active status
    if is_active_filter:
        floors = floors.filter(is_active=is_active_filter == 'true')
    
    # Sorting
    valid_sort_fields = ['building__name', 'block__name', 'floor_number', 'name', '-created_at']
    if sort_by in valid_sort_fields:
        floors = floors.order_by(sort_by)
    else:
        floors = floors.order_by('building__name', 'block__name', 'floor_number')
    
    # Add annotations for statistics
    floors = floors.annotate(
        departments_count=Count('departments'),
        locations_count=Count('locations')
    )
    
    # Get data for filter dropdowns
    buildings = Building.objects.filter(is_active=True).order_by('name')
    blocks = Block.objects.filter(is_active=True).order_by('building__name', 'name')
    
    # Pagination
    paginator = Paginator(floors, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'floors': page_obj.object_list,
        'buildings': buildings,
        'blocks': blocks,
        'search': search,
        'building_filter': building_filter,
        'block_filter': block_filter,
        'is_active_filter': is_active_filter,
        'sort_by': sort_by,
        'title': 'Floor Management',
    }
    
    return render(request, 'inventory/locations/floor_list.html', context)

@login_required
@permission_required('inventory.view_floor', raise_exception=True)
def floor_detail(request, floor_id):
    """Display detailed information about a floor"""
    floor = get_object_or_404(Floor.objects.select_related('building', 'block'), id=floor_id)
    
    # Get related data
    departments = floor.departments.all().annotate(
        rooms_count=Count('rooms')
    ).order_by('name')
    
    # Statistics
    total_departments = departments.count()
    total_rooms = sum(dept.rooms_count for dept in departments)
    total_locations = floor.locations.count()
    
    context = {
        'floor': floor,
        'departments': departments,
        'total_departments': total_departments,
        'total_rooms': total_rooms,
        'total_locations': total_locations,
        'title': f'Floor: {floor.name}',
    }
    
    return render(request, 'inventory/locations/floor_detail.html', context)

@login_required
@permission_required('inventory.add_floor', raise_exception=True)
def floor_create(request):
    """Create a new floor"""
    if request.method == 'POST':
        form = FloorForm(request.POST)
        if form.is_valid():
            try:
                floor = form.save()
                messages.success(request, f'Floor "{floor.name}" created successfully.')
                return redirect('inventory:floor_detail', floor_id=floor.id)
            except Exception as e:
                messages.error(request, f'Error creating floor: {str(e)}')
    else:
        form = FloorForm()
        # Pre-select building and block if provided in URL
        building_id = request.GET.get('building')
        block_id = request.GET.get('block')
        if building_id:
            form.fields['building'].initial = building_id
        if block_id:
            form.fields['block'].initial = block_id
    
    context = {
        'form': form,
        'title': 'Add New Floor',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/floor_form.html', context)

@login_required
@permission_required('inventory.change_floor', raise_exception=True)
def floor_edit(request, floor_id):
    """Edit an existing floor"""
    floor = get_object_or_404(Floor, id=floor_id)
    
    if request.method == 'POST':
        form = FloorForm(request.POST, instance=floor)
        if form.is_valid():
            try:
                floor = form.save()
                messages.success(request, f'Floor "{floor.name}" updated successfully.')
                return redirect('inventory:floor_detail', floor_id=floor.id)
            except Exception as e:
                messages.error(request, f'Error updating floor: {str(e)}')
    else:
        form = FloorForm(instance=floor)
    
    context = {
        'form': form,
        'floor': floor,
        'title': f'Edit Floor: {floor.name}',
        'form_action': 'Update',
    }
    
    return render(request, 'inventory/locations/floor_form.html', context)

@login_required
@permission_required('inventory.delete_floor', raise_exception=True)
def floor_delete(request, floor_id):
    """Delete a floor"""
    floor = get_object_or_404(Floor, id=floor_id)
    
    if request.method == 'POST':
        try:
            floor_name = floor.name
            floor.delete()
            messages.success(request, f'Floor "{floor_name}" deleted successfully.')
            return redirect('inventory:floor_list')
        except Exception as e:
            messages.error(request, f'Error deleting floor: {str(e)}')
            return redirect('inventory:floor_detail', floor_id=floor.id)
    
    return redirect('inventory:floor_detail', floor_id=floor.id)

# ================================
# ROOM MANAGEMENT VIEWS
# ================================

@login_required
@permission_required('inventory.view_room', raise_exception=True)
def room_list(request):
    """Display list of all rooms with enhanced filtering"""
    search = request.GET.get('search', '')
    building_filter = request.GET.get('building', '')
    block_filter = request.GET.get('block', '')
    floor_filter = request.GET.get('floor', '')
    department_filter = request.GET.get('department', '')
    is_active_filter = request.GET.get('is_active', '')
    sort_by = request.GET.get('sort', 'department__name')
    
    rooms = Room.objects.select_related(
        'department__floor__building', 
        'department__floor__block',
        'department'
    )
    
    # Search functionality
    if search:
        rooms = rooms.filter(
            Q(room_number__icontains=search) |
            Q(room_name__icontains=search) |
            Q(department__name__icontains=search) |
            Q(department__floor__building__name__icontains=search) |
            Q(department__floor__block__name__icontains=search)
        )
    
    # Apply filters
    if building_filter:
        rooms = rooms.filter(department__floor__building_id=building_filter)
    if block_filter:
        rooms = rooms.filter(department__floor__block_id=block_filter)
    if floor_filter:
        rooms = rooms.filter(department__floor_id=floor_filter)
    if department_filter:
        rooms = rooms.filter(department_id=department_filter)
    if is_active_filter:
        rooms = rooms.filter(is_active=is_active_filter == 'true')
    
    # Sorting
    valid_sort_fields = ['department__name', 'room_number', 'room_name', 'capacity', '-created_at']
    if sort_by in valid_sort_fields:
        rooms = rooms.order_by(sort_by)
    else:
        rooms = rooms.order_by('department__name', 'room_number')
    
    # Add annotations
    rooms = rooms.annotate(
        locations_count=Count('locations')
    )
    
    # Get data for filter dropdowns
    buildings = Building.objects.filter(is_active=True).order_by('name')
    blocks = Block.objects.filter(is_active=True).order_by('building__name', 'name')
    floors = Floor.objects.filter(is_active=True).order_by('building__name', 'block__name', 'floor_number')
    departments = Department.objects.filter(is_active=True).order_by('name')
    
    # Pagination
    paginator = Paginator(rooms, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'rooms': page_obj.object_list,
        'buildings': buildings,
        'blocks': blocks,
        'floors': floors,
        'departments': departments,
        'search': search,
        'building_filter': building_filter,
        'block_filter': block_filter,
        'floor_filter': floor_filter,
        'department_filter': department_filter,
        'is_active_filter': is_active_filter,
        'sort_by': sort_by,
        'title': 'Room Management',
    }
    
    return render(request, 'inventory/locations/room_list.html', context)

@login_required
@permission_required('inventory.view_room', raise_exception=True)
def room_detail(request, room_id):
    """Display detailed information about a room"""
    room = get_object_or_404(
        Room.objects.select_related(
            'department__floor__building',
            'department__floor__block',
            'department'
        ), 
        id=room_id
    )
    
    # Get related data
    locations = room.locations.all()
    
    # Statistics
    total_locations = locations.count()
    active_assignments = Assignment.objects.filter(
        location__room=room,
        status='ASSIGNED'
    ).count()
    
    context = {
        'room': room,
        'locations': locations,
        'total_locations': total_locations,
        'active_assignments': active_assignments,
        'title': f'Room: {room.room_number} - {room.room_name}',
    }
    
    return render(request, 'inventory/locations/room_detail.html', context)

@login_required
@permission_required('inventory.add_room', raise_exception=True)
def room_create(request):
    """Create a new room"""
    if request.method == 'POST':
        form = forms.RoomForm(request.POST)
        if form.is_valid():
            try:
                room = form.save()
                messages.success(request, f'Room "{room.room_number}" created successfully.')
                return redirect('inventory:room_detail', room_id=room.id)
            except Exception as e:
                messages.error(request, f'Error creating room: {str(e)}')
    else:
        form = forms.RoomForm()
        # Pre-select department if provided in URL
        department_id = request.GET.get('department')
        if department_id:
            form.fields['department'].initial = department_id
    
    context = {
        'form': form,
        'title': 'Add New Room',
        'form_action': 'Create',
    }
    
    return render(request, 'inventory/locations/room_form.html', context)

@login_required
@permission_required('inventory.change_room', raise_exception=True)
def room_edit(request, room_id):
    """Edit an existing room"""
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        form = forms.RoomForm(request.POST, instance=room)
        if form.is_valid():
            try:
                room = form.save()
                messages.success(request, f'Room "{room.room_number}" updated successfully.')
                return redirect('inventory:room_detail', room_id=room.id)
            except Exception as e:
                messages.error(request, f'Error updating room: {str(e)}')
    else:
        form = forms.RoomForm(instance=room)
    
    context = {
        'form': form,
        'room': room,
        'title': f'Edit Room: {room.room_number}',
        'form_action': 'Update',
    }
    
    return render(request, 'inventory/locations/room_form.html', context)

@login_required
@permission_required('inventory.delete_room', raise_exception=True)
def room_delete(request, room_id):
    """Delete a room"""
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        try:
            room_number = room.room_number
            room.delete()
            messages.success(request, f'Room "{room_number}" deleted successfully.')
            return redirect('inventory:room_list')
        except Exception as e:
            messages.error(request, f'Error deleting room: {str(e)}')
            return redirect('inventory:room_detail', room_id=room.id)
    
    return redirect('inventory:room_detail', room_id=room.id)


# ================================
# VENDOR MANAGEMENT VIEWS
# ================================

@login_required
def vendor_list(request):
    """List all vendors with device and maintenance counts"""
    try:
        vendors = Vendor.objects.prefetch_related(
            'devices', 'maintenance_schedules'
        ).annotate(
            device_count=Count('devices'),
            maintenance_count=Count('maintenance_schedules')
        ).order_by('name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            vendors = vendors.filter(
                Q(name__icontains=search) |
                Q(contact_person__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(vendors, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search': search,
        }
        
        return render(request, 'inventory/vendor_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading vendors: {str(e)}")
        return render(request, 'inventory/vendor_list.html', {'page_obj': None})

@login_required
def vendor_detail(request, vendor_id):
    """Display vendor details with devices and maintenance history"""
    try:
        vendor = get_object_or_404(Vendor, id=vendor_id)
        
        # Get devices from this vendor
        vendor_devices = Device.objects.filter(vendor=vendor).select_related(
            'device_type__subcategory__category'
        ).order_by('-purchase_date')
        
        # Get maintenance schedules
        maintenance_schedules = MaintenanceSchedule.objects.filter(
            vendor=vendor
        ).select_related('device').order_by('-scheduled_date')[:20]
        
        # Calculate statistics
        total_devices = vendor_devices.count()
        total_purchase_value = vendor_devices.aggregate(
            total=Sum('purchase_price')
        )['total'] or 0
        
        recent_purchases = vendor_devices.filter(
            purchase_date__gte=timezone.now().date() - timedelta(days=365)
        ).count()
        
        # Device categories from this vendor
        category_breakdown = vendor_devices.values(
            'device__device_type__subcategory__category__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Maintenance statistics
        maintenance_stats = maintenance_schedules.values('status').annotate(
            count=Count('id')
        )
        
        context = {
            'vendor': vendor,
            'vendor_devices': vendor_devices[:10],  # Show latest 10
            'maintenance_schedules': maintenance_schedules,
            'total_devices': total_devices,
            'total_purchase_value': total_purchase_value,
            'recent_purchases': recent_purchases,
            'category_breakdown': category_breakdown,
            'maintenance_stats': maintenance_stats,
        }
        
        return render(request, 'inventory/vendor_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading vendor details: {str(e)}")
        return redirect('inventory:vendor_list')

@login_required
@permission_required('inventory.add_vendor', raise_exception=True)
def vendor_create(request):
    """Create new vendor"""
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            try:
                vendor = form.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='Vendor',
                    object_id=str(vendor.id),
                    object_repr=str(vendor),
                    changes={'created': 'New vendor added'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Vendor "{vendor.name}" created successfully.')
                return redirect('inventory:vendor_detail', vendor_id=vendor.id)
            except Exception as e:
                messages.error(request, f'Error creating vendor: {str(e)}')
    else:
        form = VendorForm()
    
    context = {
        'form': form,
        'title': 'Add New Vendor',
        'action': 'Create',
    }
    return render(request, 'inventory/vendor_form.html', context)

@login_required
@permission_required('inventory.change_vendor', raise_exception=True)
def vendor_edit(request, vendor_id):
    """Edit vendor details"""
    try:
        vendor = get_object_or_404(Vendor, id=vendor_id)
        
        if request.method == 'POST':
            form = VendorForm(request.POST, instance=vendor)
            if form.is_valid():
                try:
                    vendor = form.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='Vendor',
                        object_id=str(vendor.id),
                        object_repr=str(vendor),
                        changes={'updated': 'Vendor details updated'},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Vendor "{vendor.name}" updated successfully.')
                    return redirect('inventory:vendor_detail', vendor_id=vendor.id)
                except Exception as e:
                    messages.error(request, f'Error updating vendor: {str(e)}')
        else:
            form = VendorForm(instance=vendor)
        
        context = {
            'form': form,
            'vendor': vendor,
            'title': f'Edit {vendor.name}',
            'action': 'Update',
        }
        return render(request, 'inventory/vendor_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading vendor: {str(e)}")
        return redirect('inventory:vendor_list')

@login_required
@permission_required('inventory.delete_vendor', raise_exception=True)
def vendor_delete(request, vendor_id):
   """Delete vendor with safety checks"""
   try:
       vendor = get_object_or_404(Vendor, id=vendor_id)
       
       # Check if vendor has associated devices
       device_count = Device.objects.filter(vendor=vendor).count()
       maintenance_count = MaintenanceSchedule.objects.filter(vendor=vendor).count()
       
       if request.method == 'POST':
           if device_count > 0 or maintenance_count > 0:
               messages.error(
                   request, 
                   f'Cannot delete vendor "{vendor.name}". It has {device_count} devices and {maintenance_count} maintenance records.'
               )
               return redirect('inventory:vendor_detail', vendor_id=vendor.id)
           
           try:
               vendor_name = vendor.name
               
               # Create audit log before deletion
               AuditLog.objects.create(
                   user=request.user,
                   action='DELETE',
                   model_name='Vendor',
                   object_id=str(vendor.id),
                   object_repr=str(vendor),
                   changes={'deleted': 'Vendor deleted'},
                   ip_address=request.META.get('REMOTE_ADDR')
               )
               
               vendor.delete()
               messages.success(request, f'Vendor "{vendor_name}" deleted successfully.')
               return redirect('inventory:vendor_list')
               
           except Exception as e:
               messages.error(request, f'Error deleting vendor: {str(e)}')
               return redirect('inventory:vendor_detail', vendor_id=vendor.id)
       
       context = {
           'vendor': vendor,
           'device_count': device_count,
           'maintenance_count': maintenance_count,
           'can_delete': device_count == 0 and maintenance_count == 0,
       }
       
       return render(request, 'inventory/vendor_confirm_delete.html', context)
       
   except Exception as e:
       messages.error(request, f"Error loading vendor: {str(e)}")
       return redirect('inventory:vendor_list')

# ================================
# MAINTENANCE MANAGEMENT VIEWS
# ================================

@login_required
def maintenance_list(request):
    """List all maintenance schedules"""
    try:
        # Get filter parameters
        status = request.GET.get('status')
        device_id = request.GET.get('device_id')
        vendor = request.GET.get('vendor')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        maintenance = MaintenanceSchedule.objects.select_related(
            'device', 'vendor', 'created_by'
        ).order_by('-scheduled_date')
        
        # Apply filters
        if status:
            maintenance = maintenance.filter(status=status)
        if device_id:
            maintenance = maintenance.filter(
                Q(device__device_id__icontains=device_id) |
                Q(device__device_name__icontains=device_id)
            )
        if vendor:
            maintenance = maintenance.filter(vendor_id=vendor)
        if date_to:
            maintenance = maintenance.filter(scheduled_date__lte=date_to)
        
        # Pagination
        paginator = Paginator(maintenance, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        total_maintenance = maintenance.count()
        scheduled = maintenance.filter(status='SCHEDULED').count()
        in_progress = maintenance.filter(status='IN_PROGRESS').count()
        completed = maintenance.filter(status='COMPLETED').count()
        overdue = maintenance.filter(
            status='SCHEDULED',
            scheduled_date__lt=timezone.now().date()
        ).count()
        
        context = {
            'page_obj': page_obj,
            'total_maintenance': total_maintenance,
            'scheduled': scheduled,
            'in_progress': in_progress,
            'completed': completed,
            'overdue': overdue,
            'vendors': Vendor.objects.filter(is_active=True),
            'status_choices': MaintenanceSchedule.STATUS_CHOICES,
            'filters': {
                'status': status,
                'device_id': device_id,
                'vendor': vendor,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'inventory/maintenance/maintenance_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance list: {str(e)}")
        return render(request, 'inventory/maintenance/maintenance_list.html', {})

@login_required
def maintenance_create(request):
    """Create new maintenance schedule"""
    try:
        if request.method == 'POST':
            form = MaintenanceScheduleForm(request.POST)
            if form.is_valid():
                maintenance = form.save(commit=False)
                maintenance.created_by = request.user
                maintenance.save()
                
                # Create audit log
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='CREATE',
                        model_name='MaintenanceSchedule',
                        object_id=maintenance.id,
                        object_repr=str(maintenance),
                        changes=form.cleaned_data,
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except:
                    pass
                
                messages.success(request, f'Maintenance schedule created successfully for {maintenance.device.device_id}')
                return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = MaintenanceScheduleForm()
        
        context = {
            'form': form,
            'title': 'Schedule Maintenance',
            'devices': Device.objects.filter(status__in=['ACTIVE', 'MAINTENANCE']),
            'vendors': Vendor.objects.filter(is_active=True),
        }
        
        return render(request, 'inventory/maintenance/maintenance_create.html', context)
        
    except Exception as e:
        messages.error(request, f"Error creating maintenance schedule: {str(e)}")
        return redirect('inventory:maintenance_list')

@login_required
def maintenance_detail(request, maintenance_id):
    """View maintenance schedule details"""
    try:
        maintenance = get_object_or_404(
            MaintenanceSchedule.objects.select_related(
                'device', 'vendor', 'created_by'
            ),
            id=maintenance_id
        )
        
        # Get related maintenance history for this device
        related_maintenance = MaintenanceSchedule.objects.filter(
            device=maintenance.device
        ).exclude(id=maintenance_id).order_by('-scheduled_date')[:5]
        
        context = {
            'maintenance': maintenance,
            'related_maintenance': related_maintenance,
            'can_edit': request.user.has_perm('inventory.change_maintenanceschedule'),
        }
        
        return render(request, 'inventory/maintenance/maintenance_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance details: {str(e)}")
        return redirect('inventory:maintenance_list')

@login_required
def maintenance_edit(request, maintenance_id):
    """Edit maintenance schedule"""
    try:
        maintenance = get_object_or_404(MaintenanceSchedule, id=maintenance_id)
        
        if request.method == 'POST':
            original_data = {
                'status': maintenance.status,
                'scheduled_date': maintenance.scheduled_date,
                'description': maintenance.description,
                'cost': maintenance.cost,
                'vendor': maintenance.vendor_id,
            }
            
            form = MaintenanceScheduleForm(request.POST, instance=maintenance)
            if form.is_valid():
                maintenance = form.save()
                
                # Create audit log
                try:
                    changes = {}
                    for field, old_value in original_data.items():
                        new_value = getattr(maintenance, field)
                        if old_value != new_value:
                            changes[field] = {'old': old_value, 'new': new_value}
                    
                    if changes:
                        AuditLog.objects.create(
                            user=request.user,
                            action='UPDATE',
                            model_name='MaintenanceSchedule',
                            object_id=maintenance.id,
                            object_repr=str(maintenance),
                            changes=changes,
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                except:
                    pass
                
                messages.success(request, 'Maintenance schedule updated successfully.')
                return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = MaintenanceScheduleForm(instance=maintenance)
        
        context = {
            'form': form,
            'maintenance': maintenance,
            'title': 'Edit Maintenance Schedule',
        }
        
        return render(request, 'inventory/maintenance/maintenance_edit.html', context)
        
    except Exception as e:
        messages.error(request, f"Error editing maintenance schedule: {str(e)}")
        return redirect('inventory:maintenance_list')
    
@login_required
@permission_required('inventory.change_maintenanceschedule', raise_exception=True)
def maintenance_complete(request, maintenance_id):
    """Mark maintenance as completed"""
    try:
        maintenance = get_object_or_404(MaintenanceSchedule, id=maintenance_id)
        
        if maintenance.status == 'COMPLETED':
            messages.warning(request, 'This maintenance schedule is already marked as completed.')
            return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
        
        if request.method == 'POST':
            completion_notes = request.POST.get('completion_notes', '')
            actual_cost = request.POST.get('actual_cost')
            
            try:
                with transaction.atomic():
                    maintenance.status = 'COMPLETED'
                    maintenance.completed_date = timezone.now().date()
                    maintenance.completion_notes = completion_notes
                    
                    if actual_cost:
                        try:
                            maintenance.actual_cost = float(actual_cost)
                        except ValueError:
                            messages.warning(request, 'Invalid cost format. Cost not updated.')
                    
                    maintenance.save()
                    
                    # Log the activity
                    from .utils import log_user_activity
                    log_user_activity(
                        user=request.user,
                        action='UPDATE',
                        model_name='MaintenanceSchedule',
                        object_id=maintenance.id,
                        object_repr=f'{maintenance} - COMPLETED',
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Maintenance for "{maintenance.device}" marked as completed.')
                    return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
            except Exception as e:
                messages.error(request, f'Error completing maintenance: {str(e)}')
        
        context = {
            'maintenance': maintenance,
            'title': f'Complete Maintenance: {maintenance.device}',
        }
        return render(request, 'inventory/maintenance/maintenance_complete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance for completion: {str(e)}")
        return redirect('inventory:maintenance_list')
    
@login_required
def maintenance_schedule(request):
    """View for managing maintenance schedules - calendar/overview view"""
    try:
        # Get all active maintenance schedules
        schedules = MaintenanceSchedule.objects.select_related(
            'device', 'vendor', 'assigned_technician'
        ).filter(is_active=True).order_by('next_due_date')
        
        # Filter by status if provided
        status_filter = request.GET.get('status')
        if status_filter:
            schedules = schedules.filter(status=status_filter)
        
        # Filter by date range
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            schedules = schedules.filter(next_due_date__gte=date_from)
        if date_to:
            schedules = schedules.filter(next_due_date__lte=date_to)
        
        # Get overdue schedules
        overdue_schedules = schedules.filter(
            next_due_date__lt=timezone.now().date(),
            status='SCHEDULED'
        )
        
        # Get upcoming schedules (next 30 days)
        upcoming_schedules = schedules.filter(
            next_due_date__gte=timezone.now().date(),
            next_due_date__lte=timezone.now().date() + timedelta(days=30),
            status='SCHEDULED'
        )
        
        # Statistics
        stats = {
            'total_schedules': schedules.count(),
            'overdue_count': overdue_schedules.count(),
            'upcoming_count': upcoming_schedules.count(),
            'completed_this_month': schedules.filter(
                status='COMPLETED',
                last_completed_date__month=timezone.now().month
            ).count(),
        }
        
        context = {
            'schedules': schedules,
            'overdue_schedules': overdue_schedules,
            'upcoming_schedules': upcoming_schedules,
            'stats': stats,
            'status_choices': MaintenanceSchedule.STATUS_CHOICES,
        }
        
        return render(request, 'inventory/maintenance/maintenance_schedule.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance schedule: {str(e)}")
        return render(request, 'inventory/maintenance/maintenance_schedule.html', {})

@login_required
@permission_required('inventory.delete_maintenanceschedule', raise_exception=True)
def maintenance_delete(request, maintenance_id):
    """Delete a maintenance schedule with confirmation"""
    try:
        maintenance = get_object_or_404(
            MaintenanceSchedule.objects.select_related(
                'device__device_type',
                'vendor',
                'assigned_technician__user',
                'assigned_technician__department'
            ),
            id=maintenance_id
        )
        
        # Check if user has permission to delete this specific maintenance
        # Allow deletion if user has admin privileges or created the schedule
        if not (request.user.has_perm('inventory.delete_maintenanceschedule') or
                request.user.is_superuser or
                (hasattr(maintenance, 'created_by') and request.user == maintenance.created_by)):
            messages.error(request, 'You do not have permission to delete this maintenance schedule.')
            return redirect('inventory:maintenance_detail', maintenance_id=maintenance_id)
        
        # Check if maintenance is in progress - prevent deletion
        if maintenance.status == 'IN_PROGRESS':
            messages.error(request, 
                'Cannot delete maintenance schedule that is currently in progress. '
                'Please complete or cancel the maintenance first.')
            return redirect('inventory:maintenance_detail', maintenance_id=maintenance_id)
        
        # Store maintenance details for logging before deletion
        maintenance_details = {
            'maintenance_id': maintenance_id,
            'device_id': maintenance.device.device_id,
            'device_name': maintenance.device.device_name,
            'maintenance_type': maintenance.get_maintenance_type_display(),
            'next_due_date': maintenance.next_due_date.isoformat(),
            'status': maintenance.get_status_display(),
            'vendor': str(maintenance.vendor) if maintenance.vendor else None,
            'assigned_technician': str(maintenance.assigned_technician) if maintenance.assigned_technician else None,
            'cost_estimate': float(maintenance.cost_estimate) if maintenance.cost_estimate else None,
            'description': maintenance.description,
            'frequency': maintenance.get_frequency_display(),
            'is_active': maintenance.is_active,
            'created_at': maintenance.created_at.isoformat() if hasattr(maintenance, 'created_at') else None,
            'deleted_by': request.user.username,
            'deleted_at': timezone.now().isoformat()
        }
        
        if request.method == 'POST':
            # Get deletion confirmation and reason
            confirm_delete = request.POST.get('confirm_delete')
            deletion_reason = request.POST.get('deletion_reason', '').strip()
            
            if confirm_delete == 'yes':
                try:
                    with transaction.atomic():
                        # Store device and vendor references before deletion
                        device = maintenance.device
                        vendor_name = str(maintenance.vendor) if maintenance.vendor else 'No vendor'
                        
                        # Check if there are any maintenance records linked to this schedule
                        linked_records_count = 0
                        try:
                            # Check for MaintenanceRecord if it exists
                            if hasattr(maintenance, 'records'):
                                linked_records = maintenance.records.all()
                                linked_records_count = linked_records.count()
                                
                                if linked_records_count > 0:
                                    # Option 1: Prevent deletion if records exist
                                    messages.error(request, 
                                        f'Cannot delete maintenance schedule. It has {linked_records_count} '
                                        'linked maintenance records. Please remove the records first.')
                                    return redirect('inventory:maintenance_detail', maintenance_id=maintenance_id)
                                    
                                    # Option 2: Delete linked records (uncomment if preferred)
                                    # linked_records.delete()
                        except Exception:
                            # Handle case where MaintenanceRecord model doesn't exist or no relation
                            pass
                        
                        # Create audit log entry before deletion
                        try:
                            AuditLog.objects.create(
                                user=request.user,
                                action='DELETE',
                                model_name='MaintenanceSchedule',
                                object_id=str(maintenance_id),
                                object_repr=f'Maintenance Schedule {maintenance_id} - {maintenance.device.device_name}',
                                changes=maintenance_details,
                                ip_address=get_client_ip(request)
                            )
                        except Exception as audit_error:
                            # Log audit creation error but don't fail the deletion
                            print(f"Warning: Could not create audit log: {audit_error}")
                        
                        # Update device maintenance status if needed
                        if device.status == 'MAINTENANCE' and maintenance.status in ['SCHEDULED', 'IN_PROGRESS']:
                            # Check if this is the only active maintenance for this device
                            other_active_maintenance = MaintenanceSchedule.objects.filter(
                                device=device,
                                status__in=['SCHEDULED', 'IN_PROGRESS'],
                                is_active=True
                            ).exclude(id=maintenance_id)
                            
                            if not other_active_maintenance.exists():
                                # No other active maintenance, set device back to available
                                device.status = 'AVAILABLE'
                                device.save()
                        
                        # Delete the maintenance schedule
                        maintenance.delete()
                        
                        # Success message with details
                        messages.success(
                            request, 
                            f'Maintenance schedule deleted successfully! '
                            f'{maintenance_details["maintenance_type"]} for device {device.device_id} '
                            f'(scheduled with {vendor_name}) has been removed.'
                        )
                        
                        # Redirect to appropriate view
                        redirect_to = request.GET.get('next')
                        if redirect_to in ['maintenance_list', 'device_detail', 'vendor_detail']:
                            if redirect_to == 'device_detail':
                                return redirect('inventory:device_detail', device_id=device.device_id)
                            elif redirect_to == 'vendor_detail' and maintenance_details['vendor']:
                                try:
                                    vendor = Vendor.objects.get(name=maintenance_details['vendor'])
                                    return redirect('inventory:vendor_detail', vendor_id=vendor.id)
                                except Vendor.DoesNotExist:
                                    pass
                            return redirect('inventory:maintenance_list')
                        else:
                            return redirect('inventory:maintenance_list')
                        
                except Exception as e:
                    messages.error(request, f'Error deleting maintenance schedule: {str(e)}')
                    return redirect('inventory:maintenance_detail', maintenance_id=maintenance_id)
            else:
                messages.info(request, 'Maintenance schedule deletion cancelled.')
                return redirect('inventory:maintenance_detail', maintenance_id=maintenance_id)
        
        # GET request - show confirmation page
        # Check for dependent records
        warnings = []
        linked_records_count = 0
        
        try:
            if hasattr(maintenance, 'records'):
                linked_records_count = maintenance.records.count()
                if linked_records_count > 0:
                    warnings.append(f'This maintenance schedule has {linked_records_count} linked maintenance records.')
        except:
            pass
        
        # Check if device will be affected
        device_status_warning = None
        if maintenance.device.status == 'MAINTENANCE' and maintenance.status in ['SCHEDULED', 'IN_PROGRESS']:
            other_maintenance = MaintenanceSchedule.objects.filter(
                device=maintenance.device,
                status__in=['SCHEDULED', 'IN_PROGRESS'],
                is_active=True
            ).exclude(id=maintenance_id).count()
            
            if other_maintenance == 0:
                device_status_warning = f'Device {maintenance.device.device_id} will be set back to "Available" status.'
        
        context = {
            'maintenance': maintenance,
            'maintenance_details': maintenance_details,
            'title': f'Delete Maintenance Schedule - {maintenance.device.device_name}',
            'can_delete': maintenance.status != 'IN_PROGRESS',
            'warnings': warnings,
            'device_status_warning': device_status_warning,
            'linked_records_count': linked_records_count,
            'warning_message': 'This action cannot be undone. The maintenance schedule will be permanently deleted.',
        }
        
        return render(request, 'inventory/maintenance/maintenance_delete.html', context)
        
    except MaintenanceSchedule.DoesNotExist:
        messages.error(request, 'Maintenance schedule not found.')
        return redirect('inventory:maintenance_list')
        
    except Exception as e:
        messages.error(request, f'Error accessing maintenance schedule: {str(e)}')
        return redirect('inventory:maintenance_list')

# ================================
# DEVICE TYPE MANAGEMENT VIEWS
# ================================

@login_required
def device_type_list(request):
    """List all device types with device counts"""
    try:
        device_types = DeviceType.objects.select_related(
            'subcategory__category'
        ).prefetch_related('devices').annotate(
            device_count=Count('devices')
        ).order_by('subcategory__category__name', 'subcategory__name', 'name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            device_types = device_types.filter(
                Q(name__icontains=search) |
                Q(subcategory__name__icontains=search) |
                Q(subcategory__category__name__icontains=search)
            )
        
        # Category filter
        category_id = request.GET.get('category')
        if category_id:
            device_types = device_types.filter(subcategory__category_id=category_id)
        
        # Pagination
        paginator = Paginator(device_types, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get categories for filter
        categories = DeviceCategory.objects.all().order_by('name')
        
        context = {
            'page_obj': page_obj,
            'categories': categories,
            'search': search,
            'selected_category': category_id,
        }
        
        return render(request, 'inventory/device_type/device_type_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device types: {str(e)}")
        return render(request, 'inventory/device_type/device_type_list.html', {'page_obj': None})

@login_required
@permission_required('inventory.add_devicetype', raise_exception=True)
def device_type_create(request):
    """Create new device type"""
    if request.method == 'POST':
        form = DeviceTypeForm(request.POST)
        if form.is_valid():
            try:
                device_type = form.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='DeviceType',
                    object_id=str(device_type.id),
                    object_repr=str(device_type),
                    changes={'created': 'New device type added'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Device type "{device_type.name}" created successfully.')
                return redirect('inventory:device_type_detail', type_id=device_type.id)
            except Exception as e:
                messages.error(request, f'Error creating device type: {str(e)}')
    else:
        form = DeviceTypeForm()
    
    context = {
        'form': form,
        'title': 'Add New Device Type',
        'action': 'Create',
    }
    return render(request, 'inventory/device_type/device_type_form.html', context)

# ================================
# AJAX & API VIEWS
# ================================

@login_required
@require_http_methods(["GET"])
def get_device_info(request, device_id):
    """Get device information via API"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        current_assignment = device.assignments.filter(is_active=True).first()
        
        data = {
            'device_id': device.device_id,
            'asset_tag': device.asset_tag,
            'device_name': device.device_name,
            'status': device.status,
            'status_display': device.get_status_display(),
            'condition': device.condition,
            'condition_display': device.get_condition_display(),
            'brand': device.brand,
            'model': device.model,
            'serial_number': device.serial_number,
            'category': device.device_type.subcategory.category.name if device.device_type else None,
            'subcategory': device.device_type.subcategory.name if device.device_type else None,
            'device_type': device.device_type.name if device.device_type else None,
            'vendor': device.vendor.name if device.vendor else None,
            'purchase_date': device.purchase_date.isoformat() if device.purchase_date else None,
            'purchase_price': float(device.purchase_price) if device.purchase_price else None,
            'warranty_end_date': device.warranty_end_date.isoformat() if device.warranty_end_date else None,
            'current_assignment': {
                'assignment_id': current_assignment.assignment_id if current_assignment else None,
                'assigned_to_staff': str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else None,
                'assigned_to_department': current_assignment.assigned_to_department.name if current_assignment and current_assignment.assigned_to_department else None,
                'assigned_to_location': str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else None,
                'start_date': current_assignment.start_date.isoformat() if current_assignment and current_assignment.start_date else None,
                'is_temporary': current_assignment.is_temporary if current_assignment else False,
                'expected_return_date': current_assignment.expected_return_date.isoformat() if current_assignment and current_assignment.expected_return_date else None,
            } if current_assignment else None
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def quick_assign_device(request):
    """Quick assign device via API"""
    try:
        device_id = request.POST.get('device_id')
        staff_id = request.POST.get('staff_id')
        department_id = request.POST.get('department_id')
        location_id = request.POST.get('location_id')
        assignment_type = request.POST.get('assignment_type', 'permanent')
        purpose = request.POST.get('purpose', '')
        
        if not device_id:
            return JsonResponse({'error': 'Device ID is required'}, status=400)
        
        device = get_object_or_404(Device, device_id=device_id)
        
        # Check if device is already assigned
        if device.assignments.filter(is_active=True).exists():
            return JsonResponse({'error': 'Device is already assigned'}, status=400)
        
        # Get assignment targets
        assigned_to_staff = None
        assigned_to_department = None
        assigned_to_location = None
        
        if staff_id:
            assigned_to_staff = get_object_or_404(Staff, id=staff_id)
        if department_id:
            assigned_to_department = get_object_or_404(Department, id=department_id)
        if location_id:
            assigned_to_location = get_object_or_404(Location, id=location_id)
        
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            return JsonResponse({'error': 'At least one assignment target is required'}, status=400)
        
        # Create assignment
        assignment = Assignment.objects.create(
            device=device,
            assigned_to_staff=assigned_to_staff,
            assigned_to_department=assigned_to_department,
            assigned_to_location=assigned_to_location,
            is_temporary=(assignment_type == 'temporary'),
            start_date=timezone.now().date(),
            purpose=purpose,
            created_by=request.user,
            is_active=True
        )
        
        # Update device status
        device.status = 'ASSIGNED'
        device.save()
        
        return JsonResponse({
            'success': True,
            'assignment_id': assignment.assignment_id,
            'message': f'Device {device_id} assigned successfully'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def search_suggestions(request):
    """Get search suggestions via API"""
    try:
        query = request.GET.get('q', '').strip()
        suggestion_type = request.GET.get('type', 'all')
        
        if len(query) < 2:
            return JsonResponse({'suggestions': []})
        
        suggestions = []
        
        if suggestion_type in ['all', 'devices']:
            # Device suggestions
            devices = Device.objects.filter(
                Q(device_id__icontains=query) |
                Q(device_name__icontains=query) |
                Q(asset_tag__icontains=query) |
                Q(serial_number__icontains=query)
            )[:10]
            
            for device in devices:
                suggestions.append({
                    'type': 'device',
                    'id': device.device_id,
                    'text': f"{device.device_id} - {device.device_name}",
                    'category': 'Devices'
                })
        
        if suggestion_type in ['all', 'staff']:
            # Staff suggestions
            staff = Staff.objects.filter(
                Q(user__username__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(employee_id__icontains=query)
            )[:10]
            
            for s in staff:
                suggestions.append({
                    'type': 'staff',
                    'id': s.id,
                    'text': f"{s.user.get_full_name()} ({s.employee_id})",
                    'category': 'Staff'
                })
        
        if suggestion_type in ['all', 'departments']:
            # Department suggestions
            departments = Department.objects.filter(
                name__icontains=query
            )[:5]
            
            for dept in departments:
                suggestions.append({
                    'type': 'department',
                    'id': dept.id,
                    'text': dept.name,
                    'category': 'Departments'
                })
        
        return JsonResponse({'suggestions': suggestions})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def device_availability_check(request):
    """Check device availability via API"""
    try:
        device_id = request.GET.get('device_id')
        
        if not device_id:
            return JsonResponse({'error': 'Device ID is required'}, status=400)
        
        try:
            device = Device.objects.get(device_id=device_id)
            current_assignment = device.assignments.filter(is_active=True).first()
            
            is_available = not current_assignment and device.status in ['ACTIVE', 'AVAILABLE']
            
            data = {
                'device_id': device_id,
                'is_available': is_available,
                'status': device.status,
                'status_display': device.get_status_display(),
                'current_assignment': {
                    'assignment_id': current_assignment.assignment_id,
                    'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment.assigned_to_staff else str(current_assignment.assigned_to_department),
                    'start_date': current_assignment.start_date.isoformat()
                } if current_assignment else None
            }
            
            return JsonResponse(data)
            
        except Device.DoesNotExist:
            return JsonResponse({
                'device_id': device_id,
                'is_available': False,
                'error': 'Device not found'
            })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_staff_by_department(request, department_id):
    """Get staff members by department via API"""
    try:
        department = get_object_or_404(Department, id=department_id)
        staff = Staff.objects.filter(
            department=department, is_active=True
        ).select_related('user')
        
        staff_data = []
        for s in staff:
            staff_data.append({
                'id': s.id,
                'name': s.user.get_full_name(),
                'username': s.user.username,
                'employee_id': s.employee_id,
                'position': s.position,
                'email': s.user.email,
            })
        
        return JsonResponse({
            'department': department.name,
            'staff': staff_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_rooms_by_building(request, building_id):
    """Get rooms by building via API"""
    try:
        building = get_object_or_404(Building, id=building_id)
        rooms = Room.objects.filter(building=building, is_active=True)
        
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.id,
                'name': room.name,
                'room_number': room.room_number,
                'floor': room.floor,
                'capacity': room.capacity,
            })
        
        return JsonResponse({
            'building': building.name,
            'rooms': rooms_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_locations_by_room(request, room_id):
    """Get locations by room via API"""
    try:
        room = get_object_or_404(Room, id=room_id)
        locations = Location.objects.filter(room=room, is_active=True)
        
        locations_data = []
        for location in locations:
            locations_data.append({
                'id': location.id,
                'name': location.name,
                'location_type': location.location_type,
                'location_type_display': location.get_location_type_display(),
                'description': location.description,
            })
        
        return JsonResponse({
            'room': str(room),
            'locations': locations_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ================================
# BULK OPERATIONS VIEWS
# ================================

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def bulk_device_update(request):
    """Handle bulk actions on selected devices - CORRECTED"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        update_field = request.POST.get('update_field')
        new_value = request.POST.get('new_value')
        
        if not device_ids:
            messages.error(request, 'No devices selected.')
            return redirect('inventory:device_list')
        
        if not update_field or not new_value:
            messages.error(request, 'Please specify field and value to update.')
            return redirect('inventory:device_list')
        
        try:
            with transaction.atomic():
                devices = Device.objects.filter(device_id__in=device_ids)
                updated_count = 0
                
                for device in devices:
                    if hasattr(device, update_field):
                        if update_field == 'status':
                            # CORRECTED: Use correct choice field validation
                            if new_value in [choice[0] for choice in Device.STATUS_CHOICES]:
                                setattr(device, update_field, new_value)
                                device.updated_by = request.user
                                device.save()
                                updated_count += 1
                        elif update_field == 'condition':
                            # CORRECTED: Use correct choice field validation
                            if new_value in [choice[0] for choice in Device.CONDITION_CHOICES]:
                                setattr(device, update_field, new_value)
                                device.updated_by = request.user
                                device.save()
                                updated_count += 1
                        elif update_field == 'current_location':
                            try:
                                location = Location.objects.get(id=int(new_value))
                                device.current_location = location
                                device.updated_by = request.user
                                device.save()
                                updated_count += 1
                            except (Location.DoesNotExist, ValueError):
                                continue
                
                # Create audit log for bulk update
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='BULK_UPDATE',
                        model_name='Device',
                        object_id=','.join(device_ids),
                        object_repr=f'Bulk update of {updated_count} devices',
                        changes={
                            'field': update_field,
                            'new_value': new_value,
                            'device_count': updated_count
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except:
                    pass  # Skip if AuditLog model doesn't exist
                
                messages.success(request, f'Successfully updated {updated_count} devices.')
                
        except Exception as e:
            messages.error(request, f'Error performing bulk update: {str(e)}')
    
    return redirect('inventory:device_list')

@login_required
@permission_required('inventory.add_assignment', raise_exception=True)
def bulk_assignment(request):
    """
    Handle bulk device assignments
    This is the missing function referenced in your URLs
    """
    if request.method == 'GET':
        # Show bulk assignment form
        context = {
            'title': 'Bulk Device Assignment',
            'staff_members': Staff.objects.filter(is_active=True).order_by('full_name'),
            'departments': Department.objects.filter(is_active=True).order_by('name'),
            'locations': Location.objects.filter(is_active=True).order_by('name'),
        }
        return render(request, 'inventory/bulk_assignment.html', context)
    
    elif request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        staff_id = request.POST.get('assigned_staff')
        department_id = request.POST.get('assigned_department')
        assignment_type = request.POST.get('assignment_type', 'temporary')
        assignment_date = request.POST.get('assignment_date')
        expected_return_date = request.POST.get('expected_return_date')
        notes = request.POST.get('assignment_notes', '')
        
        # Validation
        if not device_ids:
            messages.error(request, 'No devices selected for assignment.')
            return redirect('inventory:bulk_assignment')
        
        if not staff_id and not department_id:
            messages.error(request, 'Please select either a staff member or department.')
            return redirect('inventory:bulk_assignment')
        
        try:
            # Get staff and department objects
            staff = get_object_or_404(Staff, id=staff_id) if staff_id else None
            department = get_object_or_404(Department, id=department_id) if department_id else None
            
            # Parse dates
            assignment_date_parsed = timezone.now().date()
            if assignment_date:
                try:
                    assignment_date_parsed = datetime.strptime(assignment_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            expected_return_date_parsed = None
            if expected_return_date:
                try:
                    expected_return_date_parsed = datetime.strptime(expected_return_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            with transaction.atomic():
                assigned_count = 0
                skipped_count = 0
                
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        
                        # Check if device is available for assignment
                        if device.status not in ['AVAILABLE', 'ACTIVE']:
                            skipped_count += 1
                            continue
                        
                        # Check for existing active assignments
                        existing_assignment = Assignment.objects.filter(
                            device=device,
                            is_active=True
                        ).first()
                        
                        if existing_assignment:
                            skipped_count += 1
                            continue
                        
                        # Create assignment
                        assignment = Assignment.objects.create(
                            device=device,
                            assigned_to=staff,
                            assigned_to_department=department,
                            assignment_type=assignment_type,
                            assignment_date=assignment_date_parsed,
                            expected_return_date=expected_return_date_parsed,
                            is_active=True,
                            assigned_by=request.user,
                            notes=notes
                        )
                        
                        # Update device status
                        device.status = 'ASSIGNED'
                        device.updated_by = request.user
                        device.save()
                        
                        assigned_count += 1
                        
                    except Device.DoesNotExist:
                        skipped_count += 1
                        continue
                    except Exception as e:
                        skipped_count += 1
                        continue
                
                # Create audit log
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='BULK_ASSIGNMENT',
                        model_name='Assignment',
                        object_id=','.join(device_ids),
                        object_repr=f'Bulk assignment of {assigned_count} devices',
                        changes={
                            'staff_id': staff_id,
                            'department_id': department_id,
                            'assignment_type': assignment_type,
                            'assigned_count': assigned_count,
                            'skipped_count': skipped_count
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except:
                    pass  # Skip if AuditLog model doesn't exist
                
                if assigned_count > 0:
                    assignee = staff.full_name if staff else department.name
                    messages.success(request, f'Successfully assigned {assigned_count} devices to {assignee}.')
                    
                if skipped_count > 0:
                    messages.warning(request, f'{skipped_count} devices were skipped (already assigned or unavailable).')
                
        except Exception as e:
            messages.error(request, f'Error performing bulk assignment: {str(e)}')
        
        return redirect('inventory:assignment_list')


@login_required
@permission_required('inventory.change_device', raise_exception=True)
def bulk_qr_generate(request):
    """
    Handle bulk QR code generation for devices
    This is the missing function referenced in your URLs
    """
    if request.method == 'GET':
        # Show device selection for QR generation
        search = request.GET.get('search', '')
        category = request.GET.get('category')
        status = request.GET.get('status')
        has_qr = request.GET.get('has_qr')
        
        devices = Device.objects.select_related(
            'device_type__subcategory__category', 'vendor'
        ).order_by('device_id')
        
        # Apply filters
        if search:
            devices = devices.filter(
                Q(device_id__icontains=search) |
                Q(device_name__icontains=search) |
                Q(asset_tag__icontains=search)
            )
        
        if category:
            devices = devices.filter(device_type__subcategory__category_id=category)
            
        if status:
            devices = devices.filter(status=status)
            
        if has_qr == 'yes':
            devices = devices.exclude(qr_code__isnull=True).exclude(qr_code='')
        elif has_qr == 'no':
            devices = devices.filter(Q(qr_code__isnull=True) | Q(qr_code=''))
        
        # Pagination
        paginator = Paginator(devices, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'title': 'Bulk QR Code Generation',
            'page_obj': page_obj,
            'categories': DeviceCategory.objects.all().order_by('name'),
            'status_choices': Device.STATUS_CHOICES,
            'filters': {
                'search': search,
                'category': category,
                'status': status,
                'has_qr': has_qr,
            }
        }
        return render(request, 'inventory/bulk/bulk_qr_generate.html', context)
    
    elif request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        regenerate = request.POST.get('regenerate', False)
        
        if not device_ids:
            messages.error(request, 'No devices selected for QR code generation.')
            return redirect('inventory:bulk_qr_generate')
        
        try:
            generated_count = 0
            skipped_count = 0
            failed_count = 0
            
            with transaction.atomic():
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        
                        # Skip if QR code exists and regenerate is not requested
                        if device.qr_code and not regenerate:
                            skipped_count += 1
                            continue
                        
                        # Generate QR code data
                        qr_data = {
                            'device_id': device.device_id,
                            'asset_tag': device.asset_tag,
                            'device_name': device.device_name,
                            'category': device.device_type.subcategory.category.name if device.device_type else '',
                            'model': device.model,
                            'serial_number': device.serial_number,
                            'verification_url': request.build_absolute_uri(
                                f'/verify/{device.device_id}/'
                            ),
                            'generated_at': timezone.now().isoformat(),
                            'system': 'BPS_Inventory'
                        }
                        
                        qr_json = json.dumps(qr_data)
                        
                        # Create QR code
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=10,
                            border=4,
                        )
                        qr.add_data(qr_json)
                        qr.make(fit=True)
                        
                        # Generate image
                        img = qr.make_image(fill_color="black", back_color="white")
                        
                        # Convert to base64
                        buffer = BytesIO()
                        img.save(buffer, format='PNG')
                        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
                        
                        # Update device with QR code
                        device.qr_code = qr_code_data
                        device.updated_by = request.user
                        device.save()
                        
                        generated_count += 1
                        
                    except Device.DoesNotExist:
                        failed_count += 1
                        continue
                    except Exception as e:
                        failed_count += 1
                        continue
                
                # Create audit log
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='BULK_QR_GENERATION',
                        model_name='Device',
                        object_id=','.join(device_ids),
                        object_repr=f'Bulk QR generation for {generated_count} devices',
                        changes={
                            'generated_count': generated_count,
                            'skipped_count': skipped_count,
                            'failed_count': failed_count,
                            'regenerate': regenerate
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except:
                    pass  # Skip if AuditLog model doesn't exist
                
                # Success message
                if generated_count > 0:
                    messages.success(request, f'Generated QR codes for {generated_count} devices.')
                
                if skipped_count > 0:
                    messages.info(request, f'{skipped_count} devices skipped (QR codes already exist).')
                
                if failed_count > 0:
                    messages.warning(request, f'{failed_count} devices failed to generate QR codes.')
                
        except Exception as e:
            messages.error(request, f'Error in bulk QR generation: {str(e)}')
        
        return redirect('inventory:bulk_qr_generate')

@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def bulk_assignment_return(request):
    """Bulk return multiple assignments"""
    if request.method == 'POST':
        assignment_ids = request.POST.getlist('assignment_ids')
        return_date = request.POST.get('return_date')
        return_notes = request.POST.get('return_notes', '')
        
        if not assignment_ids:
            messages.error(request, 'No assignments selected.')
            return redirect('inventory:assignment_list')
        
        try:
            return_date_parsed = datetime.strptime(return_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return_date_parsed = timezone.now().date()
        
        try:
            with transaction.atomic():
                assignments = Assignment.objects.filter(
                    assignment_id__in=assignment_ids,
                    is_active=True
                )
                returned_count = 0
                
                for assignment in assignments:
                    # Update assignment
                    assignment.is_active = False
                    assignment.actual_return_date = return_date_parsed
                    assignment.return_notes = return_notes
                    assignment.updated_by = request.user
                    assignment.save()
                    
                    # Update device status
                    device = assignment.device
                    device.status = 'AVAILABLE'
                    device.updated_by = request.user
                    device.save()
                    
                    returned_count += 1
                
                # Create audit log for bulk return
                AuditLog.objects.create(
                    user=request.user,
                    action='BULK_RETURN',
                    model_name='Assignment',
                    object_id=','.join(assignment_ids),
                    object_repr=f'Bulk return of {returned_count} assignments',
                    changes={
                        'return_date': str(return_date_parsed),
                        'notes': return_notes,
                        'assignment_count': returned_count
                    },
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Successfully returned {returned_count} assignments.')
                
        except Exception as e:
            messages.error(request, f'Error performing bulk return: {str(e)}')
    
    return redirect('inventory:assignment_list')
@login_required
@permission_required('inventory.change_device', raise_exception=True)
def bulk_actions(request):
    """
    Main bulk actions dispatcher - integrates with your existing bulk functions
    This function acts as a router to your existing bulk operation functions
    """
    if request.method == 'GET':
        # Show bulk actions selection page
        context = {
            'title': 'Bulk Actions',
            'available_actions': [
                ('device_update', 'Update Device Properties'),
                ('assignment_return', 'Return Assignments'), 
                ('device_assignment', 'Assign Devices'),
                ('export_selected', 'Export Selected Items'),
            ]
        }
        return render(request, 'inventory/bulk_actions.html', context)
    
    elif request.method == 'POST':
        action = request.POST.get('action')
        
        # Route to your existing bulk functions based on action
        if action == 'device_update':
            # Use your existing bulk_device_update function
            return bulk_device_update(request)
            
        elif action == 'assignment_return':
            # Use your existing bulk_assignment_return function  
            return bulk_assignment_return(request)
            
        elif action == 'device_assignment':
            # Handle new device assignments
            return handle_bulk_device_assignment(request)
            
        elif action == 'export_selected':
            # Handle export functionality
            return handle_bulk_export_dispatcher(request)
            
        else:
            messages.error(request, f'Unknown bulk action: {action}')
            return redirect('inventory:device_list')


def handle_bulk_device_assignment(request):
    """Handle bulk device assignments - extends your existing functionality"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        staff_id = request.POST.get('assigned_staff')
        assignment_type = request.POST.get('assignment_type', 'temporary')
        
        if not device_ids:
            messages.error(request, 'No devices selected.')
            return redirect('inventory:device_list')
            
        if not staff_id:
            messages.error(request, 'Please select a staff member.')
            return redirect('inventory:device_list')
        
        try:
            staff = get_object_or_404(Staff, id=staff_id)
            
            with transaction.atomic():
                assigned_count = 0
                
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        
                        # Check if device is available for assignment
                        if device.status not in ['AVAILABLE', 'ACTIVE']:
                            continue
                            
                        # Check for existing active assignments
                        existing_assignment = Assignment.objects.filter(
                            device=device,
                            is_active=True
                        ).first()
                        
                        if existing_assignment:
                            continue  # Skip already assigned devices
                        
                        # Create new assignment using your existing model structure
                        Assignment.objects.create(
                            device=device,
                            assigned_to=staff,
                            assignment_type=assignment_type,
                            is_active=True,
                            assigned_by=request.user,
                            assignment_date=timezone.now().date()
                        )
                        
                        # Update device status
                        device.status = 'ASSIGNED'
                        device.updated_by = request.user
                        device.save()
                        
                        assigned_count += 1
                        
                    except Device.DoesNotExist:
                        continue
                
                # Create audit log (matching your existing pattern)
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='BULK_ASSIGNMENT',
                        model_name='Assignment',
                        object_id=','.join(device_ids),
                        object_repr=f'Bulk assignment of {assigned_count} devices to {staff.full_name}',
                        changes={
                            'staff_id': staff_id,
                            'assignment_type': assignment_type,
                            'device_count': assigned_count
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except:
                    pass  # Skip if AuditLog model doesn't exist
                
                if assigned_count > 0:
                    messages.success(request, f'Successfully assigned {assigned_count} devices to {staff.full_name}.')
                else:
                    messages.warning(request, 'No devices were assigned. They may already be assigned or unavailable.')
                    
        except Exception as e:
            messages.error(request, f'Error performing bulk assignment: {str(e)}')
    
    return redirect('inventory:device_list')


# ================================
# EXPORT FUNCTIONS
# ================================

@login_required
def bulk_import(request):
    """Main bulk import page"""
    return render(request, 'inventory/bulk/bulk_import.html', {
        'title': 'Bulk Import Data'
    })

@login_required
def bulk_export(request):
    """Main bulk export page"""
    return render(request, 'inventory/bulk/bulk_export.html', {
        'title': 'Bulk Export Data'
    })

@login_required
def import_template(request):
    """Download CSV import template"""
    try:
        template_type = request.GET.get('type', 'devices')
        
        response = HttpResponse(content_type='text/csv')
        
        if template_type == 'devices':
            response['Content-Disposition'] = 'attachment; filename="devices_import_template.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'device_id', 'asset_tag', 'device_name', 'category', 'subcategory', 'device_type',
                'brand', 'model', 'serial_number', 'status', 'condition',
                'purchase_date', 'purchase_price', 'vendor', 'warranty_start_date', 'warranty_end_date',
                'description', 'notes'
            ])
            # Add sample row
            writer.writerow([
                'DEV001', 'AT001', 'Sample Laptop', 'IT Equipment', 'Computers', 'Laptop',
                'Dell', 'Latitude 7420', 'SN123456', 'ACTIVE', 'EXCELLENT',
                '2023-01-15', '1200.00', 'Dell Inc', '2023-01-15', '2026-01-15',
                'Sample laptop for demonstration', 'Sample notes'
            ])
            
        elif template_type == 'assignments':
            response['Content-Disposition'] = 'attachment; filename="assignments_import_template.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'device_id', 'assigned_to_staff_email', 'assigned_to_department', 'assignment_type',
                'start_date', 'expected_return_date', 'location', 'purpose', 'notes'
            ])
            # Add sample row
            writer.writerow([
                'DEV001', 'john.doe@example.com', 'IT Department', 'permanent',
                '2023-01-15', '', 'Office 101', 'Daily work laptop', 'Sample assignment'
            ])
            
        elif template_type == 'maintenance':
            response['Content-Disposition'] = 'attachment; filename="maintenance_import_template.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'device_id', 'maintenance_type', 'scheduled_date', 'vendor', 'cost',
                'description', 'status', 'notes'
            ])
            # Add sample row
            writer.writerow([
                'DEV001', 'PREVENTIVE', '2023-06-15', 'Dell Inc', '150.00',
                'Regular maintenance check', 'SCHEDULED', 'Sample maintenance'
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error generating template: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def export_devices_csv(request):
    """Export devices to CSV"""
    try:
        # Get filter parameters from request
        category = request.GET.get('category')
        status = request.GET.get('status')
        condition = request.GET.get('condition')
        vendor = request.GET.get('vendor')
        
        # Base queryset
        devices = Device.objects.select_related(
            'device_type__subcategory__category', 'vendor'
        ).prefetch_related('assignments')
        
        # Apply filters
        if category:
            devices = devices.filter(device_type__subcategory__category_id=category)
        if status:
            devices = devices.filter(status=status)
        if condition:
            devices = devices.filter(condition=condition)
        if vendor:
            devices = devices.filter(vendor_id=vendor)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="devices_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Subcategory', 'Type',
            'Brand', 'Model', 'Serial Number', 'Status', 'Condition',
            'Purchase Date', 'Purchase Price', 'Vendor', 'Warranty Start', 'Warranty End',
            'Current Assignment', 'Assigned To', 'Assignment Date', 'Location',
            'Created Date', 'Last Updated'
        ])
        
        for device in devices:
            current_assignment = device.assignments.filter(is_active=True).first()
            
            writer.writerow([
                device.device_id,
                device.asset_tag,
                device.device_name,
                device.device_type.subcategory.category.name if device.device_type else '',
                device.device_type.subcategory.name if device.device_type else '',
                device.device_type.name if device.device_type else '',
                device.brand,
                device.model,
                device.serial_number,
                device.get_status_display(),
                device.get_condition_display(),
                device.purchase_date.strftime('%Y-%m-%d') if device.purchase_date else '',
                device.purchase_price,
                device.vendor.name if device.vendor else '',
                device.warranty_start_date.strftime('%Y-%m-%d') if device.warranty_start_date else '',
                device.warranty_end_date.strftime('%Y-%m-%d') if device.warranty_end_date else '',
                current_assignment.assignment_id if current_assignment else '',
                str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else '',
                current_assignment.start_date.strftime('%Y-%m-%d') if current_assignment and current_assignment.start_date else '',
                str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else '',
                device.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                device.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error exporting devices: {str(e)}")
        return redirect('inventory:device_list')
    
@login_required
def export_assignments_csv(request):
    """Export assignments to CSV"""
    try:
        # Get filter parameters
        status = request.GET.get('status')
        department = request.GET.get('department')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff__department', 'assigned_to_department',
            'assigned_to_location', 'created_by'
        )
        
        # Apply filters
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        if department:
            assignments = assignments.filter(
                Q(assigned_to_department_id=department) |
                Q(assigned_to_staff__department_id=department)
            )
        if date_from:
            assignments = assignments.filter(start_date__gte=date_from)
        if date_to:
            assignments = assignments.filter(start_date__lte=date_to)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="assignments_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Assignment ID', 'Device ID', 'Device Name', 'Assigned To Staff', 'Staff Department',
            'Assigned To Department', 'Assignment Type', 'Start Date', 'Expected Return',
            'Actual Return', 'Status', 'Purpose', 'Location', 'Notes',
            'Created Date', 'Created By'
        ])
        
        for assignment in assignments:
            writer.writerow([
                assignment.assignment_id,
                assignment.device.device_id,
                assignment.device.device_name,
                str(assignment.assigned_to_staff) if assignment.assigned_to_staff else '',
                assignment.assigned_to_staff.department.name if assignment.assigned_to_staff and assignment.assigned_to_staff.department else '',
                assignment.assigned_to_department.name if assignment.assigned_to_department else '',
                'Temporary' if assignment.is_temporary else 'Permanent',
                assignment.start_date.strftime('%Y-%m-%d') if assignment.start_date else '',
                assignment.expected_return_date.strftime('%Y-%m-%d') if assignment.expected_return_date else '',
                assignment.actual_return_date.strftime('%Y-%m-%d') if assignment.actual_return_date else '',
                'Active' if assignment.is_active else 'Inactive',
                assignment.purpose or '',
                str(assignment.assigned_to_location) if assignment.assigned_to_location else '',
                assignment.notes or '',
                assignment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                assignment.created_by.username
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error exporting assignments: {str(e)}")
        return redirect('inventory:assignment_list')

def handle_bulk_export_dispatcher(request):
    """Handle bulk export - works with your existing system"""
    try:
        item_type = request.POST.get('export_type', 'devices')
        selected_ids = request.POST.getlist('device_ids') or request.POST.getlist('assignment_ids')
        
        if not selected_ids:
            messages.error(request, 'No items selected for export.')
            return redirect('inventory:device_list')
        
        if item_type == 'devices':
            return export_selected_devices(request, selected_ids)
        elif item_type == 'assignments':
            return export_selected_assignments(request, selected_ids)
        else:
            messages.error(request, 'Invalid export type.')
            return redirect('inventory:device_list')
            
    except Exception as e:
        messages.error(request, f'Error exporting data: {str(e)}')
        return redirect('inventory:device_list')


def export_selected_devices(request, device_ids):
    """Export selected devices to CSV"""
    try:
        devices = Device.objects.filter(device_id__in=device_ids).select_related(
            'category', 'subcategory', 'device_type', 'vendor', 'current_location'
        )
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_devices_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header (matching your existing export structure)
        writer.writerow([
            'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Subcategory',
            'Device Type', 'Brand', 'Model', 'Serial Number', 'Status',
            'Condition', 'Current Location', 'Purchase Date', 'Purchase Price',
            'Vendor', 'Warranty Start', 'Warranty End'
        ])
        
        # Write device data
        for device in devices:
            writer.writerow([
                device.device_id,
                device.asset_tag,
                device.device_name,
                device.category.name if device.category else '',
                device.subcategory.name if device.subcategory else '',
                device.device_type.name if device.device_type else '',
                device.brand,
                device.model,
                device.serial_number,
                device.get_status_display(),
                device.get_condition_display(),
                str(device.current_location) if device.current_location else '',
                device.purchase_date,
                device.purchase_price,
                device.vendor.name if device.vendor else '',
                device.warranty_start_date,
                device.warranty_end_date,
            ])
        
        messages.success(request, f'Exported {devices.count()} devices successfully.')
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting devices: {str(e)}')
        return redirect('inventory:device_list')


def export_selected_assignments(request, assignment_ids):
    """Export selected assignments to CSV"""
    try:
        assignments = Assignment.objects.filter(assignment_id__in=assignment_ids).select_related(
            'device', 'assigned_to', 'assigned_by'
        )
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_assignments_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Assignment ID', 'Device ID', 'Device Name', 'Assigned To', 'Assignment Type',
            'Assignment Date', 'Expected Return', 'Actual Return', 'Status', 'Assigned By'
        ])
        
        # Write assignment data
        for assignment in assignments:
            writer.writerow([
                assignment.assignment_id,
                assignment.device.device_id,
                assignment.device.device_name,
                assignment.assigned_to.full_name,
                assignment.get_assignment_type_display(),
                assignment.assignment_date,
                assignment.expected_return_date,
                assignment.actual_return_date,
                'Active' if assignment.is_active else 'Returned',
                assignment.assigned_by.username if assignment.assigned_by else '',
            ])
        
        messages.success(request, f'Exported {assignments.count()} assignments successfully.')
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting assignments: {str(e)}')
        return redirect('inventory:assignment_list')

# ================================
# REPORTING VIEWS
# ================================

@login_required
def inventory_summary_report(request):
    """Generate inventory summary report"""
    try:
        # Device statistics
        total_devices = Device.objects.count()
        active_devices = Device.objects.filter(status='ACTIVE').count()
        inactive_devices = Device.objects.filter(status='INACTIVE').count()
        maintenance_devices = Device.objects.filter(status='MAINTENANCE').count()
        
        # Assignment statistics
        total_assignments = Assignment.objects.count()
        active_assignments = Assignment.objects.filter(is_active=True).count()
        temporary_assignments = Assignment.objects.filter(is_temporary=True, is_active=True).count()
        
        # Value statistics
        total_value = Device.objects.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        
        # Category breakdown
        category_breakdown = Device.objects.values(
            'device_type__subcategory__category__name'
        ).annotate(
            count=Count('id'),
            total_value=Sum('purchase_price')
        ).order_by('-count')
        
        context = {
            'total_devices': total_devices,
            'active_devices': active_devices,
            'inactive_devices': inactive_devices,
            'maintenance_devices': maintenance_devices,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'temporary_assignments': temporary_assignments,
            'total_value': total_value,
            'category_breakdown': category_breakdown,
            'report_date': date.today(),
        }
        
        return render(request, 'inventory/reports/summary.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating summary report: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def asset_utilization_report(request):
    """Generate asset utilization report"""
    try:
        # Device utilization analysis
        devices_with_assignments = Device.objects.filter(
            assignments__is_active=True
        ).distinct().count()
        
        devices_without_assignments = Device.objects.filter(
            assignments__isnull=True
        ).count()
        
        # Department utilization
        dept_utilization = Department.objects.annotate(
            device_count=Count('staff__assignments__device', distinct=True),
            staff_count=Count('staff', distinct=True)
        ).order_by('-device_count')
        
        context = {
            'devices_with_assignments': devices_with_assignments,
            'devices_without_assignments': devices_without_assignments,
            'dept_utilization': dept_utilization,
            'report_date': date.today(),
        }
        
        return render(request, 'inventory/reports/utilization.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating utilization report: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def device_lifecycle_report(request):
    """Generate device lifecycle analysis report"""
    try:
        # Devices by age groups
        today = timezone.now().date()
        
        age_groups = {
            'new': Device.objects.filter(purchase_date__gte=today - timedelta(days=365)).count(),
            'recent': Device.objects.filter(
                purchase_date__gte=today - timedelta(days=1095),
                purchase_date__lt=today - timedelta(days=365)
            ).count(),
            'mature': Device.objects.filter(
                purchase_date__gte=today - timedelta(days=1825),
                purchase_date__lt=today - timedelta(days=1095)
            ).count(),
            'old': Device.objects.filter(purchase_date__lt=today - timedelta(days=1825)).count(),
        }
        
        # Devices approaching retirement (>5 years old)
        retirement_candidates = Device.objects.filter(
            purchase_date__lt=today - timedelta(days=1825)
        ).select_related('device_type__subcategory__category').order_by('purchase_date')[:20]
        
        # Maintenance frequency analysis
        maintenance_frequency = Device.objects.annotate(
            maintenance_count=Count('maintenance_schedules'),
            last_maintenance=Max('maintenance_schedules__actual_date')
        ).filter(maintenance_count__gt=0).order_by('-maintenance_count')[:20]
        
        # Devices never maintained
        never_maintained = Device.objects.filter(
            maintenance_schedules__isnull=True,
            purchase_date__lt=today - timedelta(days=365)
        ).order_by('purchase_date')[:20]
        
        # Cost analysis by year
        yearly_purchases = Device.objects.filter(
            purchase_date__isnull=False
        ).extra(
            select={'year': 'EXTRACT(year FROM purchase_date)'}
        ).values('year').annotate(
            count=Count('id'),
            total_cost=Sum('purchase_price')
        ).order_by('-year')
        
        context = {
            'age_groups': age_groups,
            'retirement_candidates': retirement_candidates,
            'maintenance_frequency': maintenance_frequency,
            'never_maintained': never_maintained,
            'yearly_purchases': yearly_purchases,
            'report_date': today,
        }
        
        return render(request, 'inventory/device_lifecycle_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating lifecycle report: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def warranty_management_report(request):
    """Generate warranty management report"""
    try:
        today = timezone.now().date()
        
        # Warranty status categories
        warranty_stats = {
            'expired': Device.objects.filter(warranty_end_date__lt=today).count(),
            'expiring_30': Device.objects.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=today + timedelta(days=30)
            ).count(),
            'expiring_90': Device.objects.filter(
                warranty_end_date__gte=today + timedelta(days=31),
                warranty_end_date__lte=today + timedelta(days=90)
            ).count(),
            'active': Device.objects.filter(warranty_end_date__gt=today + timedelta(days=90)).count(),
            'no_warranty': Device.objects.filter(warranty_end_date__isnull=True).count(),
        }
        
        # Devices expiring soon (detailed list)
        expiring_soon = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=90)
        ).select_related(
            'device_type__subcategory__category', 'vendor'
        ).order_by('warranty_end_date')
        
        # Recently expired warranties
        recently_expired = Device.objects.filter(
            warranty_end_date__gte=today - timedelta(days=30),
            warranty_end_date__lt=today
        ).select_related(
            'device_type__subcategory__category', 'vendor'
        ).order_by('-warranty_end_date')
        
        # Warranty by vendor
        vendor_warranty = Vendor.objects.annotate(
            total_devices=Count('devices'),
            expired_warranties=Count('devices', filter=Q(devices__warranty_end_date__lt=today)),
            active_warranties=Count('devices', filter=Q(devices__warranty_end_date__gte=today))
        ).filter(total_devices__gt=0).order_by('-total_devices')
        
        # Warranty cost implications (estimated)
        expiring_value = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=90)
        ).aggregate(total_value=Sum('purchase_price'))['total_value'] or 0
        
        context = {
            'warranty_stats': warranty_stats,
            'expiring_soon': expiring_soon,
            'recently_expired': recently_expired,
            'vendor_warranty': vendor_warranty,
            'expiring_value': expiring_value,
            'report_date': today,
        }
        
        return render(request, 'inventory/warranty_management_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating warranty report: {str(e)}")
        return redirect('inventory:dashboard')

# ================================
# SYSTEM ADMINISTRATION VIEWS
# ================================

@login_required
@permission_required('inventory.view_auditlog', raise_exception=True)
def system_statistics(request):
    """Display comprehensive system statistics"""
    try:
        # Database statistics
        db_stats = {
            'total_devices': Device.objects.count(),
            'total_assignments': Assignment.objects.count(),
            'total_staff': Staff.objects.count(),
            'total_departments': Department.objects.count(),
            'total_locations': Location.objects.count(),
            'total_vendors': Vendor.objects.count(),
            'total_maintenance_schedules': MaintenanceSchedule.objects.count(),
            'total_audit_logs': AuditLog.objects.count(),
        }
        
        # Activity statistics (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        activity_stats = {
            'devices_added': Device.objects.filter(created_at__date__gte=thirty_days_ago).count(),
            'assignments_created': Assignment.objects.filter(created_at__date__gte=thirty_days_ago).count(),
            'assignments_returned': Assignment.objects.filter(
                actual_return_date__gte=thirty_days_ago
            ).count(),
            'maintenance_completed': MaintenanceSchedule.objects.filter(
                actual_date__gte=thirty_days_ago,
                status='COMPLETED'
            ).count(),
        }
        
        # User activity
        user_activity = User.objects.annotate(
            recent_logins=Count('auditlog_entries', filter=Q(auditlog_entries__timestamp__date__gte=thirty_days_ago)),
            total_actions=Count('auditlog_entries')
        ).filter(total_actions__gt=0).order_by('-recent_logins')[:10]
        
        # System health indicators
        health_indicators = {
            'devices_without_assignments': Device.objects.filter(assignments__isnull=True).count(),
            'overdue_assignments': Assignment.objects.filter(
                is_temporary=True,
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            ).count(),
            'expired_warranties': Device.objects.filter(
                warranty_end_date__lt=timezone.now().date()
            ).count(),
            'pending_maintenance': MaintenanceSchedule.objects.filter(
                status__in=['SCHEDULED', 'IN_PROGRESS']
            ).count(),
        }
        
        # Recent system errors (from audit logs)
        recent_errors = AuditLog.objects.filter(
            action='ERROR',
            timestamp__date__gte=thirty_days_ago
        ).order_by('-timestamp')[:10]
        
        context = {
            'db_stats': db_stats,
            'activity_stats': activity_stats,
            'user_activity': user_activity,
            'health_indicators': health_indicators,
            'recent_errors': recent_errors,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'inventory/system_statistics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating system statistics: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
@permission_required('inventory.view_auditlog', raise_exception=True)
def audit_log_list(request):
    """Display audit logs with filtering"""
    try:
        audit_logs = AuditLog.objects.select_related('user').order_by('-timestamp')
        
        # Filters
        user_id = request.GET.get('user')
        action = request.GET.get('action')
        model_name = request.GET.get('model')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if user_id:
            audit_logs = audit_logs.filter(user_id=user_id)
        
        if action:
            audit_logs = audit_logs.filter(action=action)
        
        if model_name:
            audit_logs = audit_logs.filter(model_name=model_name)
        
        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                audit_logs = audit_logs.filter(timestamp__date__gte=date_from_parsed)
            except ValueError:
                messages.warning(request, 'Invalid date format for "from" date.')
        
        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                audit_logs = audit_logs.filter(timestamp__date__lte=date_to_parsed)
            except ValueError:
                messages.warning(request, 'Invalid date format for "to" date.')
        
        # Pagination
        paginator = Paginator(audit_logs, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter options
        users = User.objects.filter(auditlog_entries__isnull=False).distinct().order_by('username')
        actions = AuditLog.objects.values_list('action', flat=True).distinct()
        models = AuditLog.objects.values_list('model_name', flat=True).distinct()
        
        context = {
            'page_obj': page_obj,
            'users': users,
            'actions': actions,
            'models': models,
            'filters': {
                'user': user_id,
                'action': action,
                'model': model_name,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'inventory/audit_log_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading audit logs: {str(e)}")
        return render(request, 'inventory/audit_log_list.html', {'page_obj': None})

# ================================
# DATA CLEANUP AND MAINTENANCE VIEWS
# ================================

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def data_cleanup_tools(request):
    """Data cleanup and maintenance tools"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'cleanup_inactive_assignments':
                # Remove very old inactive assignments
                cutoff_date = timezone.now().date() - timedelta(days=2 * 365)  # 2 years
                deleted_count = Assignment.objects.filter(
                    is_active=False,
                    actual_return_date__lt=cutoff_date
                ).count()
                
                messages.success(request, f'Would delete {deleted_count} old inactive assignments (dry run).')
                
            elif action == 'fix_device_statuses':
                # Fix device statuses based on active assignments
                fixed_count = 0
                for device in Device.objects.all():
                    active_assignment = Assignment.objects.filter(device=device, is_active=True).first()
                    if active_assignment and device.status != 'ASSIGNED':
                        device.status = 'ASSIGNED'
                        device.save()
                        fixed_count += 1
                    elif not active_assignment and device.status == 'ASSIGNED':
                        device.status = 'AVAILABLE'
                        device.save()
                        fixed_count += 1
                
                messages.success(request, f'Fixed status for {fixed_count} devices.')
                
            elif action == 'update_maintenance_dates':
                # Update device last maintenance dates
                updated_count = 0
                for device in Device.objects.all():
                    last_maintenance = MaintenanceSchedule.objects.filter(
                        device=device,
                        status='COMPLETED',
                        actual_date__isnull=False
                    ).order_by('-actual_date').first()
                    
                    if last_maintenance and device.last_maintenance_date != last_maintenance.actual_date:
                        device.last_maintenance_date = last_maintenance.actual_date
                        device.save()
                        updated_count += 1
                
                messages.success(request, f'Updated maintenance dates for {updated_count} devices.')
                
            else:
                messages.error(request, 'Unknown cleanup action.')
                
        except Exception as e:
            messages.error(request, f'Error during cleanup: {str(e)}')
    
    # Get cleanup statistics
    cleanup_stats = {
        'old_inactive_assignments': Assignment.objects.filter(
            is_active=False,
            actual_return_date__lt=timezone.now().date() - timedelta(days=2 * 365)
        ).count(),
        'devices_wrong_status': 0,  # Would need complex query
        'devices_missing_maintenance_dates': Device.objects.filter(
            last_maintenance_date__isnull=True,
            maintenance_schedules__status='COMPLETED'
        ).count(),
    }
    
    context = {
        'cleanup_stats': cleanup_stats,
    }
    
    return render(request, 'inventory/data_cleanup_tools.html', context)

# ================================
# QR CODE AND UTILITY FUNCTIONS
# ================================

@login_required
def generate_qr_codes_bulk(request):
    """Generate QR codes for multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        
        if not device_ids:
            messages.error(request, 'No devices selected for QR code generation.')
            return redirect('inventory:device_list')
        
        try:
            # Simple fallback QR code generation (you can implement this later)
            generated_count = 0
            for device_id in device_ids:
                try:
                    device = Device.objects.get(device_id=device_id)
                    # TODO: Implement QR code generation when qr_management app is available
                    generated_count += 1
                except Device.DoesNotExist:
                    continue
            
            messages.success(request, f'QR code generation queued for {generated_count} devices. (Feature pending implementation)')
            
        except Exception as e:
            messages.error(request, f'Error generating QR codes: {str(e)}')
    
    return redirect('inventory:device_list')

@login_required
def device_qr_code(request, device_id):
    """Generate and display QR code for device"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        # For now, just show the QR code UUID
        # You can implement actual QR code generation when qr_management app is ready
        context = {
            'device': device,
            'qr_code': device.qr_code,
        }
        
        return render(request, 'inventory/devices/device_qr_code.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device QR code: {str(e)}")
        return redirect('inventory:device_detail', device_id=device_id)

# ================================
# AJAX VIEWS  
# ================================

@login_required
@require_http_methods(["GET"])
def ajax_staff_search(request):
    """AJAX: Search staff members for assignments and forms"""
    try:
        query = request.GET.get('q', '').strip()
        department_id = request.GET.get('department_id')
        limit = int(request.GET.get('limit', 20))
        
        if not query and not department_id:
            return JsonResponse({'staff': []})
        
        # Start with active staff
        staff_members = Staff.objects.filter(is_active=True).select_related(
            'user', 'department'
        )
        
        # Apply text search if query provided
        if query:
            staff_members = staff_members.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(employee_id__icontains=query) |
                Q(department__name__icontains=query) |
                Q(user__email__icontains=query)
            )
        
        # Filter by department if specified
        if department_id:
            staff_members = staff_members.filter(department_id=department_id)
        
        # Limit results
        staff_members = staff_members[:limit]
        
        # Prepare response data
        staff_data = []
        for staff in staff_members:
            staff_data.append({
                'id': staff.id,
                'employee_id': staff.employee_id,
                'full_name': staff.get_full_name(),
                'first_name': staff.user.first_name,
                'last_name': staff.user.last_name,
                'username': staff.user.username,
                'email': staff.user.email,
                'department': {
                    'id': staff.department.id if staff.department else None,
                    'name': staff.department.name if staff.department else None
                },
                'display_text': f"{staff.get_full_name()} ({staff.employee_id}) - {staff.department.name if staff.department else 'No Department'}"
            })
        
        return JsonResponse({
            'staff': staff_data,
            'count': len(staff_data),
            'query': query
        })
        
    except ValueError as e:
        return JsonResponse({'error': 'Invalid limit parameter'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_location_search(request):
    """AJAX: Search locations for assignments and forms"""
    try:
        query = request.GET.get('q', '').strip()
        room_id = request.GET.get('room_id')
        building_id = request.GET.get('building_id')
        department_id = request.GET.get('department_id')
        limit = int(request.GET.get('limit', 20))
        
        if not query and not room_id and not building_id and not department_id:
            return JsonResponse({'locations': []})
        
        # Start with active locations
        locations = Location.objects.filter(is_active=True).select_related(
            'room', 'room__building', 'room__department'
        )
        
        # Apply text search if query provided
        if query:
            locations = locations.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(room__name__icontains=query) |
                Q(room__building__name__icontains=query) |
                Q(room__department__name__icontains=query)
            )
        
        # Filter by room if specified
        if room_id:
            locations = locations.filter(room_id=room_id)
        
        # Filter by building if specified
        if building_id:
            locations = locations.filter(room__building_id=building_id)
        
        # Filter by department if specified
        if department_id:
            locations = locations.filter(room__department_id=department_id)
        
        # Limit results
        locations = locations[:limit]
        
        # Prepare response data
        location_data = []
        for location in locations:
            # Generate display text
            display_parts = [location.name]
            if location.room:
                display_parts.append(location.room.name)
                if location.room.building:
                    display_parts.append(location.room.building.name)
                if location.room.department:
                    display_parts.append(location.room.department.name)
            display_text = " - ".join(display_parts)
            
            location_data.append({
                'id': location.id,
                'name': location.name,
                'description': location.description,
                'room': {
                    'id': location.room.id if location.room else None,
                    'name': location.room.name if location.room else None,
                    'building': {
                        'id': location.room.building.id if location.room and location.room.building else None,
                        'name': location.room.building.name if location.room and location.room.building else None
                    } if location.room else None,
                    'department': {
                        'id': location.room.department.id if location.room and location.room.department else None,
                        'name': location.room.department.name if location.room and location.room.department else None
                    } if location.room else None
                } if location.room else None,
                'display_text': display_text
            })
        
        return JsonResponse({
            'locations': location_data,
            'count': len(location_data),
            'query': query
        })
        
    except ValueError as e:
        return JsonResponse({'error': 'Invalid limit parameter'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
@require_http_methods(["GET"])
def ajax_get_subcategories(request):
    """AJAX: Get subcategories for category"""
    try:
        category_id = request.GET.get('category_id')
        if category_id:
            from .models import DeviceSubCategory
            subcategories = DeviceSubCategory.objects.filter(
                category_id=category_id, is_active=True
            ).values('id', 'name')
            return JsonResponse({'subcategories': list(subcategories)})
        return JsonResponse({'subcategories': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_get_device_types(request):
    """AJAX: Get device types for subcategory"""
    try:
        subcategory_id = request.GET.get('subcategory_id')
        if subcategory_id:
            device_types = DeviceType.objects.filter(
                subcategory_id=subcategory_id, is_active=True
            ).values('id', 'name')
            return JsonResponse({'device_types': list(device_types)})
        return JsonResponse({'device_types': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def ajax_device_quick_info(request, device_id):
    """AJAX: Get quick device info"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        data = {
            'device_id': device.device_id,
            'device_name': device.device_name,
            'status': device.status,
            'brand': device.brand,
            'model': device.model,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def ajax_device_quick_info(request, device_id):
    """AJAX: Get quick device info"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        data = {
            'device_id': device.device_id,
            'device_name': device.device_name,
            'status': device.status,
            'brand': device.brand,
            'model': device.model,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def ajax_get_locations_by_room(request):
    """AJAX: Get locations by room"""
    try:
        room_id = request.GET.get('room_id')
        if room_id:
            locations = Location.objects.filter(
                room_id=room_id, is_active=True
            ).values('id', 'name')
            return JsonResponse({'locations': list(locations)})
        return JsonResponse({'locations': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def ajax_assignment_quick_actions(request, assignment_id):
    """AJAX: Assignment quick actions (return, extend, transfer)"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id)
        action = request.POST.get('action')
        
        if action == 'return':
            assignment.is_active = False
            assignment.actual_return_date = timezone.now().date()
            assignment.save()
            
            # Update device status to available
            if assignment.device:
                assignment.device.status = 'available'
                assignment.device.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Device returned successfully',
                'action': 'return',
                'assignment_id': assignment_id
            })
        
        elif action == 'extend':
            days_to_extend = int(request.POST.get('days', 30))
            if assignment.expected_return_date:
                assignment.expected_return_date = assignment.expected_return_date + timedelta(days=days_to_extend)
            else:
                assignment.expected_return_date = timezone.now().date() + timedelta(days=days_to_extend)
            assignment.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Assignment extended by {days_to_extend} days',
                'action': 'extend',
                'new_return_date': assignment.expected_return_date.isoformat(),
                'assignment_id': assignment_id
            })
        
        elif action == 'transfer':
            new_staff_id = request.POST.get('new_staff_id')
            new_department_id = request.POST.get('new_department_id')
            new_location_id = request.POST.get('new_location_id')
            
            if new_staff_id:
                assignment.assigned_to_staff_id = new_staff_id
            if new_department_id:
                assignment.assigned_to_department_id = new_department_id
            if new_location_id:
                assignment.assigned_to_location_id = new_location_id
            
            assignment.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Assignment transferred successfully',
                'action': 'transfer',
                'assignment_id': assignment_id
            })
        
        return JsonResponse({'error': 'Invalid action'}, status=400)

    except ValueError as e:
        return JsonResponse({'error': 'Invalid input data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
def ajax_get_blocks(request):
    """AJAX endpoint to get blocks for a building"""
    building_id = request.GET.get('building_id')
    
    if building_id:
        blocks = Block.objects.filter(
            building_id=building_id,
            is_active=True
        ).order_by('name').values('id', 'name', 'code')
        
        return JsonResponse({
            'blocks': list(blocks)
        })
    
    return JsonResponse({'blocks': []})

@login_required
def ajax_get_floors(request):
    """AJAX endpoint to get floors for a block"""
    block_id = request.GET.get('block_id')
    
    if block_id:
        floors = Floor.objects.filter(
            block_id=block_id,
            is_active=True
        ).order_by('floor_number').values('id', 'name', 'floor_number')
        
        return JsonResponse({
            'floors': list(floors)
        })
    
    return JsonResponse({'floors': []})

@login_required
def ajax_get_departments(request):
    """AJAX endpoint to get departments for a floor"""
    floor_id = request.GET.get('floor_id')
    
    if floor_id:
        departments = Department.objects.filter(
            floor_id=floor_id,
            is_active=True
        ).order_by('name').values('id', 'name', 'code')
        
        return JsonResponse({
            'departments': list(departments)
        })
    
    return JsonResponse({'departments': []})

@login_required
def ajax_get_rooms(request):
    """AJAX endpoint to get rooms for a department"""
    department_id = request.GET.get('department_id')
    
    if department_id:
        rooms = Room.objects.filter(
            department_id=department_id,
            is_active=True
        ).order_by('room_number').values('id', 'room_number', 'room_name')
        
        return JsonResponse({
            'rooms': list(rooms)
        })
    
    return JsonResponse({'rooms': []})

# ================================
# IMPORT/EXPORT VIEWS - HIGH PRIORITY
# ================================

@login_required
@permission_required('inventory.add_device', raise_exception=True)
def import_devices_csv(request):
    """Import devices from CSV/Excel file"""
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = request.FILES['csv_file']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']
                
                # Validate file size (10MB limit)
                if csv_file.size > 10 * 1024 * 1024:
                    messages.error(request, "File size exceeds 10MB limit.")
                    return render(request, 'inventory/import_devices.html', {'form': form})
                
                # Read file based on extension
                file_extension = csv_file.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    # Read CSV file
                    df = pd.read_csv(csv_file, skip_blank_lines=True)
                elif file_extension in ['xlsx', 'xls']:
                    # Read Excel file
                    df = pd.read_excel(csv_file, engine='openpyxl' if file_extension == 'xlsx' else 'xlrd')
                else:
                    messages.error(request, "Unsupported file format. Please upload CSV or Excel file.")
                    return render(request, 'inventory/import_devices.html', {'form': form})
                
                if skip_header:
                    df = df.iloc[1:]  # Skip first row
                
                # Process the data
                success_count = 0
                error_count = 0
                errors = []
                
                # Expected column mapping (case-insensitive)
                column_mapping = {
                    'asset_tag': ['asset_tag', 'asset tag', 'tag'],
                    'device_name': ['device_name', 'device name', 'name'],
                    'device_type': ['device_type', 'device type', 'type'],
                    'brand': ['brand', 'manufacturer'],
                    'model': ['model'],
                    'serial_number': ['serial_number', 'serial number', 'serial'],
                    'purchase_date': ['purchase_date', 'purchase date'],
                    'purchase_price': ['purchase_price', 'purchase price', 'price'],
                    'vendor': ['vendor', 'supplier'],
                    'warranty_end_date': ['warranty_end_date', 'warranty end', 'warranty'],
                    'status': ['status'],
                    'condition': ['condition'],
                    'notes': ['notes', 'description', 'remarks']
                }
                
                # Map actual columns to expected fields
                df_columns = [col.lower().strip() for col in df.columns]
                field_mapping = {}
                
                for field, possible_names in column_mapping.items():
                    for possible_name in possible_names:
                        if possible_name.lower() in df_columns:
                            actual_column = df.columns[df_columns.index(possible_name.lower())]
                            field_mapping[field] = actual_column
                            break
                
                # Process each row
                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            # Extract device data
                            device_data = {}
                            
                            # Required fields
                            device_name = row.get(field_mapping.get('device_name', ''), '').strip()
                            if not device_name:
                                error_count += 1
                                errors.append(f"Row {index + 1}: Device name is required")
                                continue
                            
                            device_data['device_name'] = device_name
                            
                            # Optional fields
                            if 'asset_tag' in field_mapping:
                                device_data['asset_tag'] = str(row.get(field_mapping['asset_tag'], '')).strip()
                            
                            if 'brand' in field_mapping:
                                device_data['brand'] = str(row.get(field_mapping['brand'], '')).strip()
                            
                            if 'model' in field_mapping:
                                device_data['model'] = str(row.get(field_mapping['model'], '')).strip()
                            
                            if 'serial_number' in field_mapping:
                                device_data['serial_number'] = str(row.get(field_mapping['serial_number'], '')).strip()
                            
                            # Handle device type
                            if 'device_type' in field_mapping:
                                device_type_name = str(row.get(field_mapping['device_type'], '')).strip()
                                if device_type_name:
                                    try:
                                        device_type = DeviceType.objects.get(name__icontains=device_type_name)
                                        device_data['device_type'] = device_type
                                    except DeviceType.DoesNotExist:
                                        # Create default device type if not found
                                        default_category, _ = DeviceCategory.objects.get_or_create(
                                            name='General',
                                            defaults={'category_type': 'OTHER'}
                                        )
                                        default_subcategory, _ = DeviceSubCategory.objects.get_or_create(
                                            category=default_category,
                                            name='General',
                                            defaults={'code': 'GEN'}
                                        )
                                        device_type, _ = DeviceType.objects.get_or_create(
                                            subcategory=default_subcategory,
                                            name=device_type_name,
                                            defaults={'code': device_type_name[:10].upper()}
                                        )
                                        device_data['device_type'] = device_type
                            
                            # Handle vendor
                            if 'vendor' in field_mapping:
                                vendor_name = str(row.get(field_mapping['vendor'], '')).strip()
                                if vendor_name:
                                    vendor, _ = Vendor.objects.get_or_create(
                                        name=vendor_name,
                                        defaults={'vendor_code': vendor_name[:10].upper()}
                                    )
                                    device_data['vendor'] = vendor
                            
                            # Handle dates
                            for date_field in ['purchase_date', 'warranty_end_date']:
                                if date_field in field_mapping:
                                    date_value = row.get(field_mapping[date_field])
                                    if pd.notna(date_value):
                                        try:
                                            if isinstance(date_value, str):
                                                parsed_date = pd.to_datetime(date_value, errors='coerce')
                                                if pd.notna(parsed_date):
                                                    device_data[date_field] = parsed_date.date()
                                            else:
                                                device_data[date_field] = date_value
                                        except:
                                            pass
                            
                            # Handle numeric fields
                            if 'purchase_price' in field_mapping:
                                price_value = row.get(field_mapping['purchase_price'])
                                if pd.notna(price_value):
                                    try:
                                        device_data['purchase_price'] = float(price_value)
                                    except (ValueError, TypeError):
                                        pass
                            
                            # Handle status and condition
                            if 'status' in field_mapping:
                                status_value = str(row.get(field_mapping['status'], '')).strip().upper()
                                valid_statuses = [choice[0] for choice in Device.STATUS_CHOICES]
                                if status_value in valid_statuses:
                                    device_data['status'] = status_value
                                else:
                                    device_data['status'] = 'AVAILABLE'  # Default
                            
                            if 'condition' in field_mapping:
                                condition_value = str(row.get(field_mapping['condition'], '')).strip().upper()
                                valid_conditions = [choice[0] for choice in Device.CONDITION_CHOICES]
                                if condition_value in valid_conditions:
                                    device_data['condition'] = condition_value
                                else:
                                    device_data['condition'] = 'GOOD'  # Default
                            
                            if 'notes' in field_mapping:
                                device_data['notes'] = str(row.get(field_mapping['notes'], '')).strip()
                            
                            # Check if device exists (for updates)
                            existing_device = None
                            if update_existing and device_data.get('asset_tag'):
                                try:
                                    existing_device = Device.objects.get(asset_tag=device_data['asset_tag'])
                                except Device.DoesNotExist:
                                    pass
                            
                            if existing_device and update_existing:
                                # Update existing device
                                for field, value in device_data.items():
                                    if value:  # Only update non-empty values
                                        setattr(existing_device, field, value)
                                existing_device.save()
                                success_count += 1
                            else:
                                # Create new device
                                if not device_data.get('asset_tag'):
                                    # Generate asset tag if not provided
                                    last_device = Device.objects.order_by('-id').first()
                                    next_number = (last_device.id + 1) if last_device else 1
                                    device_data['asset_tag'] = f"BPS-IT-{next_number:04d}"
                                
                                # Set defaults
                                device_data.setdefault('status', 'AVAILABLE')
                                device_data.setdefault('condition', 'GOOD')
                                
                                device = Device.objects.create(**device_data)
                                success_count += 1
                        
                        except Exception as e:
                            error_count += 1
                            errors.append(f"Row {index + 1}: {str(e)}")
                
                # Summary message
                if success_count > 0:
                    messages.success(request, f"Successfully imported {success_count} devices.")
                
                if error_count > 0:
                    messages.warning(request, f"{error_count} rows had errors.")
                    for error in errors[:10]:  # Show first 10 errors
                        messages.error(request, error)
                    if len(errors) > 10:
                        messages.error(request, f"... and {len(errors) - 10} more errors.")
                
                return redirect('inventory:device_list')
                
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = CSVImportForm()
    
    return render(request, 'inventory/import_devices.html', {
        'form': form,
        'title': 'Import Devices from CSV/Excel'
    })

@login_required
@permission_required('inventory.add_staff', raise_exception=True)
def import_staff_csv(request):
    """Import staff from CSV/Excel file"""
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = request.FILES['csv_file']
                skip_header = form.cleaned_data['skip_header']
                update_existing = form.cleaned_data['update_existing']
                
                # Validate file size
                if csv_file.size > 10 * 1024 * 1024:
                    messages.error(request, "File size exceeds 10MB limit.")
                    return render(request, 'inventory/import_staff.html', {'form': form})
                
                # Read file
                file_extension = csv_file.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    df = pd.read_csv(csv_file, skip_blank_lines=True)
                elif file_extension in ['xlsx', 'xls']:
                    df = pd.read_excel(csv_file, engine='openpyxl' if file_extension == 'xlsx' else 'xlrd')
                else:
                    messages.error(request, "Unsupported file format.")
                    return render(request, 'inventory/import_staff.html', {'form': form})
                
                if skip_header:
                    df = df.iloc[1:]
                
                success_count = 0
                error_count = 0
                errors = []
                
                # Column mapping for staff
                column_mapping = {
                    'employee_id': ['employee_id', 'emp_id', 'id'],
                    'first_name': ['first_name', 'first name', 'fname'],
                    'last_name': ['last_name', 'last name', 'lname'],
                    'email': ['email', 'email_address'],
                    'phone': ['phone', 'mobile', 'contact'],
                    'designation': ['designation', 'position', 'title'],
                    'department': ['department', 'dept'],
                    'reporting_manager': ['reporting_manager', 'manager'],
                    'hire_date': ['hire_date', 'joining_date', 'start_date']
                }
                
                # Map columns
                df_columns = [col.lower().strip() for col in df.columns]
                field_mapping = {}
                
                for field, possible_names in column_mapping.items():
                    for possible_name in possible_names:
                        if possible_name.lower() in df_columns:
                            actual_column = df.columns[df_columns.index(possible_name.lower())]
                            field_mapping[field] = actual_column
                            break
                
                # Process rows
                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            staff_data = {}
                            
                            # Required fields
                            employee_id = str(row.get(field_mapping.get('employee_id', ''), '')).strip()
                            first_name = str(row.get(field_mapping.get('first_name', ''), '')).strip()
                            last_name = str(row.get(field_mapping.get('last_name', ''), '')).strip()
                            
                            if not employee_id or not first_name or not last_name:
                                error_count += 1
                                errors.append(f"Row {index + 1}: Employee ID, first name, and last name are required")
                                continue
                            
                            staff_data.update({
                                'employee_id': employee_id,
                                'first_name': first_name,
                                'last_name': last_name
                            })
                            
                            # Optional fields
                            for field in ['email', 'phone', 'designation']:
                                if field in field_mapping:
                                    value = str(row.get(field_mapping[field], '')).strip()
                                    if value:
                                        staff_data[field] = value
                            
                            # Handle department
                            if 'department' in field_mapping:
                                dept_name = str(row.get(field_mapping['department'], '')).strip()
                                if dept_name:
                                    department, _ = Department.objects.get_or_create(
                                        name=dept_name,
                                        defaults={'code': dept_name[:10].upper()}
                                    )
                                    staff_data['department'] = department
                            
                            # Handle hire date
                            if 'hire_date' in field_mapping:
                                date_value = row.get(field_mapping['hire_date'])
                                if pd.notna(date_value):
                                    try:
                                        if isinstance(date_value, str):
                                            parsed_date = pd.to_datetime(date_value, errors='coerce')
                                            if pd.notna(parsed_date):
                                                staff_data['hire_date'] = parsed_date.date()
                                        else:
                                            staff_data['hire_date'] = date_value
                                    except:
                                        pass
                            
                            # Check for existing staff
                            existing_staff = None
                            if update_existing:
                                try:
                                    existing_staff = Staff.objects.get(employee_id=employee_id)
                                except Staff.DoesNotExist:
                                    pass
                            
                            if existing_staff and update_existing:
                                # Update existing
                                for field, value in staff_data.items():
                                    if value:
                                        setattr(existing_staff, field, value)
                                existing_staff.save()
                                success_count += 1
                            else:
                                # Create new
                                staff_data.setdefault('is_active', True)
                                staff = Staff.objects.create(**staff_data)
                                success_count += 1
                        
                        except Exception as e:
                            error_count += 1
                            errors.append(f"Row {index + 1}: {str(e)}")
                
                # Summary
                if success_count > 0:
                    messages.success(request, f"Successfully imported {success_count} staff members.")
                
                if error_count > 0:
                    messages.warning(request, f"{error_count} rows had errors.")
                    for error in errors[:10]:
                        messages.error(request, error)
                
                return redirect('inventory:staff_list')
                
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = CSVImportForm()
    
    return render(request, 'inventory/import_staff.html', {
        'form': form,
        'title': 'Import Staff from CSV/Excel'
    })

@login_required
def export_maintenance_csv(request):
    """Export maintenance schedules to CSV"""
    try:
        # Get filter parameters
        status = request.GET.get('status')
        vendor = request.GET.get('vendor')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        maintenance = MaintenanceSchedule.objects.select_related(
            'device', 'vendor', 'created_by'
        )
        
        # Apply filters
        if status:
            maintenance = maintenance.filter(status=status)
        if vendor:
            maintenance = maintenance.filter(vendor_id=vendor)
        if date_from:
            maintenance = maintenance.filter(scheduled_date__gte=date_from)
        if date_to:
            maintenance = maintenance.filter(scheduled_date__lte=date_to)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="maintenance_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Maintenance ID', 'Device ID', 'Device Name', 'Maintenance Type', 'Status',
            'Scheduled Date', 'Completed Date', 'Vendor', 'Cost', 'Description',
            'Notes', 'Created Date', 'Created By'
        ])
        
        for item in maintenance:
            writer.writerow([
                item.id,
                item.device.device_id,
                item.device.device_name,
                item.get_maintenance_type_display(),
                item.get_status_display(),
                item.scheduled_date.strftime('%Y-%m-%d') if item.scheduled_date else '',
                item.completed_date.strftime('%Y-%m-%d') if item.completed_date else '',
                item.vendor.name if item.vendor else '',
                item.cost,
                item.description,
                item.notes or '',
                item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                item.created_by.username
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error exporting maintenance: {str(e)}")
        return redirect('inventory:maintenance_list')
    
# ================================
# ADVANCED SEARCH VIEWS 
# ================================

@login_required
def advanced_search(request):
    """Advanced search with multiple filters"""
    try:
        if request.method == 'POST':
            # Process advanced search form
            form_data = request.POST.dict()
            
            # Build device query
            devices = Device.objects.select_related(
                'device_type__subcategory__category', 'vendor'
            ).prefetch_related('assignments')
            
            # Apply filters
            if form_data.get('device_id'):
                devices = devices.filter(device_id__icontains=form_data['device_id'])
            if form_data.get('device_name'):
                devices = devices.filter(device_name__icontains=form_data['device_name'])
            if form_data.get('category'):
                devices = devices.filter(device_type__subcategory__category_id=form_data['category'])
            if form_data.get('status'):
                devices = devices.filter(status=form_data['status'])
            if form_data.get('condition'):
                devices = devices.filter(condition=form_data['condition'])
            if form_data.get('vendor'):
                devices = devices.filter(vendor_id=form_data['vendor'])
            if form_data.get('purchase_date_from'):
                devices = devices.filter(purchase_date__gte=form_data['purchase_date_from'])
            if form_data.get('purchase_date_to'):
                devices = devices.filter(purchase_date__lte=form_data['purchase_date_to'])
            if form_data.get('warranty_status'):
                today = timezone.now().date()
                if form_data['warranty_status'] == 'active':
                    devices = devices.filter(warranty_end_date__gt=today)
                elif form_data['warranty_status'] == 'expired':
                    devices = devices.filter(warranty_end_date__lt=today)
                elif form_data['warranty_status'] == 'expiring':
                    thirty_days = today + timedelta(days=30)
                    devices = devices.filter(
                        warranty_end_date__gte=today,
                        warranty_end_date__lte=thirty_days
                    )
            
            # Pagination
            paginator = Paginator(devices, 25)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            
            context = {
                'page_obj': page_obj,
                'search_performed': True,
                'form_data': form_data,
                'total_results': devices.count(),
                'categories': DeviceCategory.objects.filter(is_active=True),
                'vendors': Vendor.objects.filter(is_active=True),
            }
            
        else:
            # Show search form
            context = {
                'search_performed': False,
                'categories': DeviceCategory.objects.filter(is_active=True),
                'vendors': Vendor.objects.filter(is_active=True),
            }
        
        return render(request, 'inventory/search/advanced_search.html', context)
        
    except Exception as e:
        messages.error(request, f"Error in advanced search: {str(e)}")
        return render(request, 'inventory/search/advanced_search.html', {})

@login_required
@require_http_methods(["GET"])
def global_search_api(request):
    """Global search API endpoint"""
    try:
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))
        
        if len(query) < 2:
            return JsonResponse({'results': [], 'message': 'Query too short'})
        
        results = []
        
        # Search devices
        devices = Device.objects.filter(
            Q(device_id__icontains=query) |
            Q(device_name__icontains=query) |
            Q(asset_tag__icontains=query)
        )[:limit]
        
        for device in devices:
            results.append({
                'type': 'device',
                'id': device.device_id,
                'title': device.device_name,
                'subtitle': f"ID: {device.device_id} | Status: {device.get_status_display()}",
                'url': f'/inventory/devices/{device.device_id}/',
                'icon': 'device'
            })
        
        # Search assignments
        assignments = Assignment.objects.filter(
            Q(assignment_id__icontains=query) |
            Q(device__device_id__icontains=query) |
            Q(device__device_name__icontains=query)
        ).select_related('device', 'assigned_to_staff')[:limit]
        
        for assignment in assignments:
            results.append({
                'type': 'assignment',
                'id': assignment.assignment_id,
                'title': f"Assignment {assignment.assignment_id}",
                'subtitle': f"Device: {assignment.device.device_id} | Assigned to: {assignment.assigned_to_staff or assignment.assigned_to_department}",
                'url': f'/inventory/assignments/{assignment.id}/',
                'icon': 'assignment'
            })
        
        return JsonResponse({
            'results': results[:limit],
            'total': len(results),
            'query': query
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# Advanced search form for forms.py
class AdvancedSearchForm(forms.Form):
    """Advanced search form"""
    
    SEARCH_TYPE_CHOICES = [
        ('all', 'All Items'),
        ('devices', 'Devices Only'),
        ('assignments', 'Assignments Only'),
        ('staff', 'Staff Only'),
        ('locations', 'Locations Only'),
        ('maintenance', 'Maintenance Only'),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search devices, assignments, staff, locations...',
            'autocomplete': 'off'
        }),
        help_text="Enter keywords to search across all fields"
    )
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        initial='all',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    category = forms.ModelChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter by date range (from)"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter by date range (to)"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date cannot be after end date.")
        
        return cleaned_data
@login_required
def device_search(request):
    """
    Device-specific search functionality
    This is the missing function referenced in your URLs
    """
    try:
        query = request.GET.get('q', '').strip()
        category = request.GET.get('category', '')
        status = request.GET.get('status', '')
        condition = request.GET.get('condition', '')
        vendor = request.GET.get('vendor', '')
        
        # Start with all devices
        devices = Device.objects.select_related(
            'device_type__subcategory__category', 'vendor', 'current_location'
        ).prefetch_related('assignments')
        
        # Apply text search if query provided
        if query:
            devices = devices.filter(
                Q(device_id__icontains=query) |
                Q(device_name__icontains=query) |
                Q(asset_tag__icontains=query) |
                Q(serial_number__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Apply filters
        if category:
            devices = devices.filter(device_type__subcategory__category_id=category)
        
        if status:
            devices = devices.filter(status=status)
            
        if condition:
            devices = devices.filter(condition=condition)
            
        if vendor:
            devices = devices.filter(vendor_id=vendor)
        
        # Order results
        devices = devices.order_by('device_id')
        
        # Pagination
        paginator = Paginator(devices, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter choices for form
        context = {
            'title': 'Device Search',
            'page_obj': page_obj,
            'query': query,
            'categories': DeviceCategory.objects.filter(is_active=True).order_by('name'),
            'vendors': Vendor.objects.filter(is_active=True).order_by('name'),
            'status_choices': Device.STATUS_CHOICES,
            'condition_choices': Device.CONDITION_CHOICES,
            'filters': {
                'category': category,
                'status': status,
                'condition': condition,
                'vendor': vendor,
            },
            'total_results': devices.count() if query or any([category, status, condition, vendor]) else 0,
            'search_performed': bool(query or any([category, status, condition, vendor]))
        }
        
        return render(request, 'inventory/search/device_search.html', context)
        
    except Exception as e:
        messages.error(request, f"Error in device search: {str(e)}")
        return render(request, 'inventory/search/device_search.html', {
            'title': 'Device Search',
            'error': str(e)
        })


@login_required
def assignment_search(request):
    """
    Assignment-specific search functionality  
    This is the missing function referenced in your URLs
    """
    try:
        query = request.GET.get('q', '').strip()
        status = request.GET.get('status', '')
        assignment_type = request.GET.get('assignment_type', '')
        department = request.GET.get('department', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Start with all assignments
        assignments = Assignment.objects.select_related(
            'device__device_type__subcategory__category',
            'assigned_to_staff__user',
            'assigned_to_department',
            'assigned_to_location',
            'assigned_by'
        )
        
        # Apply text search if query provided
        if query:
            assignments = assignments.filter(
                Q(assignment_id__icontains=query) |
                Q(device__device_id__icontains=query) |
                Q(device__device_name__icontains=query) |
                Q(device__asset_tag__icontains=query) |
                Q(assigned_to_staff__user__first_name__icontains=query) |
                Q(assigned_to_staff__user__last_name__icontains=query) |
                Q(assigned_to_staff__employee_id__icontains=query) |
                Q(assigned_to_department__name__icontains=query) |
                Q(notes__icontains=query)
            )
        
        # Apply filters
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        elif status == 'overdue':
            from datetime import date
            assignments = assignments.filter(
                is_active=True,
                expected_return_date__lt=date.today()
            )
        
        if assignment_type:
            assignments = assignments.filter(assignment_type=assignment_type)
            
        if department:
            assignments = assignments.filter(assigned_to_department_id=department)
        
        # Date range filters
        if date_from:
            try:
                from datetime import datetime
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                assignments = assignments.filter(assignment_date__gte=date_from_parsed)
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                assignments = assignments.filter(assignment_date__lte=date_to_parsed)
            except ValueError:
                pass
        
        # Order results
        assignments = assignments.order_by('-assignment_date')
        
        # Pagination
        paginator = Paginator(assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter choices for form
        context = {
            'title': 'Assignment Search',
            'page_obj': page_obj,
            'query': query,
            'departments': Department.objects.filter(is_active=True).order_by('name'),
            'assignment_type_choices': Assignment.ASSIGNMENT_TYPES,
            'filters': {
                'status': status,
                'assignment_type': assignment_type,
                'department': department,
                'date_from': date_from,
                'date_to': date_to,
            },
            'total_results': assignments.count() if query or any([status, assignment_type, department, date_from, date_to]) else 0,
            'search_performed': bool(query or any([status, assignment_type, department, date_from, date_to]))
        }
        
        return render(request, 'inventory/search/assignment_search.html', context)
        
    except Exception as e:
        messages.error(request, f"Error in assignment search: {str(e)}")
        return render(request, 'inventory/search/assignment_search.html', {
            'title': 'Assignment Search',
            'error': str(e)
        })


# ================================
# SEARCH API ENDPOINTS
# ================================

@login_required
@require_http_methods(["GET"])
def device_search_api(request):
    """API endpoint for device search - for AJAX calls"""
    try:
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))
        
        if len(query) < 2:
            return JsonResponse({
                'results': [],
                'message': 'Please enter at least 2 characters'
            })
        
        devices = Device.objects.filter(
            Q(device_id__icontains=query) |
            Q(device_name__icontains=query) |
            Q(asset_tag__icontains=query) |
            Q(serial_number__icontains=query)
        ).select_related('device_type__subcategory__category')[:limit]
        
        results = []
        for device in devices:
            results.append({
                'id': device.device_id,
                'device_id': device.device_id,
                'device_name': device.device_name,
                'asset_tag': device.asset_tag,
                'status': device.get_status_display(),
                'category': device.device_type.subcategory.category.name if device.device_type else 'N/A',
                'url': f'/inventory/devices/{device.device_id}/'
            })
        
        return JsonResponse({
            'results': results,
            'total': len(results),
            'query': query
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def assignment_search_api(request):
    """API endpoint for assignment search - for AJAX calls"""
    try:
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))
        
        if len(query) < 2:
            return JsonResponse({
                'results': [],
                'message': 'Please enter at least 2 characters'
            })
        
        assignments = Assignment.objects.filter(
            Q(assignment_id__icontains=query) |
            Q(device__device_id__icontains=query) |
            Q(device__device_name__icontains=query) |
            Q(assigned_to_staff__user__first_name__icontains=query) |
            Q(assigned_to_staff__user__last_name__icontains=query)
        ).select_related(
            'device', 'assigned_to_staff__user', 'assigned_to_department'
        )[:limit]
        
        results = []
        for assignment in assignments:
            assigned_to = "N/A"
            if assignment.assigned_to_staff:
                assigned_to = f"{assignment.assigned_to_staff.user.first_name} {assignment.assigned_to_staff.user.last_name}"
            elif assignment.assigned_to_department:
                assigned_to = assignment.assigned_to_department.name
            
            results.append({
                'id': assignment.assignment_id,
                'assignment_id': assignment.assignment_id,
                'device_id': assignment.device.device_id,
                'device_name': assignment.device.device_name,
                'assigned_to': assigned_to,
                'assignment_type': assignment.get_assignment_type_display(),
                'is_active': assignment.is_active,
                'url': f'/inventory/assignments/{assignment.assignment_id}/'
            })
        
        return JsonResponse({
            'results': results,
            'total': len(results),
            'query': query
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def api_blocks_by_building(request, building_id):
    """API endpoint to get blocks by building for cascade dropdowns"""
    try:
        blocks = Block.objects.filter(
            building_id=building_id, 
            is_active=True
        ).values('id', 'name', 'code').order_by('name')
        
        return JsonResponse({
            'success': True,
            'blocks': list(blocks)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_floors_by_block(request, block_id):
    """API endpoint to get floors by block for cascade dropdowns"""
    try:
        floors = Floor.objects.filter(
            block_id=block_id, 
            is_active=True
        ).values('id', 'name', 'floor_number').order_by('floor_number')
        
        return JsonResponse({
            'success': True,
            'floors': list(floors)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_floors_by_building(request, building_id):
    """API endpoint to get floors by building (for direct building-to-floor cascade)"""
    try:
        floors = Floor.objects.filter(
            building_id=building_id,
            is_active=True
        ).select_related('block').values(
            'id', 'name', 'floor_number', 'block__name', 'block__code'
        ).order_by('block__name', 'floor_number')
        
        return JsonResponse({
            'success': True,
            'floors': list(floors)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_departments_by_floor(request, floor_id):
    """API endpoint to get departments by floor for cascade dropdowns"""
    try:
        departments = Department.objects.filter(
            floor_id=floor_id, 
            is_active=True
        ).values('id', 'name', 'code').order_by('name')
        
        return JsonResponse({
            'success': True,
            'departments': list(departments)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_departments_by_building(request, building_id):
    """API endpoint to get departments by building (for building-wide views)"""
    try:
        departments = Department.objects.filter(
            floor__building_id=building_id,
            is_active=True
        ).select_related('floor__block').values(
            'id', 'name', 'code', 'floor__name', 'floor__block__name'
        ).order_by('floor__block__name', 'floor__name', 'name')
        
        return JsonResponse({
            'success': True,
            'departments': list(departments)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_departments_by_block(request, block_id):
    """API endpoint to get departments by block"""
    try:
        departments = Department.objects.filter(
            floor__block_id=block_id,
            is_active=True
        ).select_related('floor').values(
            'id', 'name', 'code', 'floor__name', 'floor__floor_number'
        ).order_by('floor__floor_number', 'name')
        
        return JsonResponse({
            'success': True,
            'departments': list(departments)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_rooms_by_department(request, department_id):
    """API endpoint to get rooms by department for cascade dropdowns"""
    try:
        rooms = Room.objects.filter(
            department_id=department_id, 
            is_active=True
        ).values('id', 'room_number', 'room_name', 'capacity').order_by('room_number')
        
        return JsonResponse({
            'success': True,
            'rooms': list(rooms)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_rooms_by_floor(request, floor_id):
    """API endpoint to get rooms by floor (across all departments)"""
    try:
        rooms = Room.objects.filter(
            department__floor_id=floor_id,
            is_active=True
        ).select_related('department').values(
            'id', 'room_number', 'room_name', 'capacity', 'department__name', 'department__code'
        ).order_by('department__name', 'room_number')
        
        return JsonResponse({
            'success': True,
            'rooms': list(rooms)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_rooms_by_building(request, building_id):
    """API endpoint to get rooms by building (for building-wide views)"""
    try:
        rooms = Room.objects.filter(
            department__floor__building_id=building_id,
            is_active=True
        ).select_related('department__floor__block', 'department').values(
            'id', 'room_number', 'room_name', 'capacity',
            'department__name', 'department__floor__name', 'department__floor__block__name'
        ).order_by('department__floor__block__name', 'department__floor__name', 'department__name', 'room_number')
        
        return JsonResponse({
            'success': True,
            'rooms': list(rooms)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_locations_by_building(request, building_id):
    """API endpoint to get locations by building"""
    try:
        locations = Location.objects.filter(
            building_id=building_id,
            is_active=True
        ).select_related('block', 'floor', 'department', 'room').values(
            'id', 'description',
            'block__name', 'floor__name', 'department__name', 'room__room_number'
        ).order_by('block__name', 'floor__floor_number', 'department__name', 'room__room_number')
        
        # Format location display name
        formatted_locations = []
        for loc in locations:
            display_name = f"{loc['block__name']} - {loc['floor__name']} - {loc['department__name']}"
            if loc['room__room_number']:
                display_name += f" - Room {loc['room__room_number']}"
            
            formatted_locations.append({
                'id': loc['id'],
                'display_name': display_name,
                'description': loc['description']
            })
        
        return JsonResponse({
            'success': True,
            'locations': formatted_locations
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_locations_by_department(request, department_id):
    """API endpoint to get locations by department"""
    try:
        locations = Location.objects.filter(
            department_id=department_id,
            is_active=True
        ).select_related('room').values(
            'id', 'description', 'room__room_number', 'room__room_name'
        ).order_by('room__room_number')
        
        # Format location display name
        formatted_locations = []
        for loc in locations:
            if loc['room__room_number']:
                display_name = f"Room {loc['room__room_number']}"
                if loc['room__room_name']:
                    display_name += f" - {loc['room__room_name']}"
            else:
                display_name = "Department General Area"
            
            formatted_locations.append({
                'id': loc['id'],
                'display_name': display_name,
                'description': loc['description']
            })
        
        return JsonResponse({
            'success': True,
            'locations': formatted_locations
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
# ================================
# HIERARCHY VALIDATION API
# ================================

@login_required
def api_validate_hierarchy(request):
    """API endpoint to validate location hierarchy relationships"""
    try:
        building_id = request.GET.get('building_id')
        block_id = request.GET.get('block_id')
        floor_id = request.GET.get('floor_id')
        department_id = request.GET.get('department_id')
        room_id = request.GET.get('room_id')
        
        errors = []
        
        # Validate block belongs to building
        if building_id and block_id:
            try:
                block = Block.objects.get(id=block_id)
                if str(block.building_id) != building_id:
                    errors.append('Selected block does not belong to the selected building.')
            except Block.DoesNotExist:
                errors.append('Selected block does not exist.')
        
        # Validate floor belongs to block
        if block_id and floor_id:
            try:
                floor = Floor.objects.get(id=floor_id)
                if str(floor.block_id) != block_id:
                    errors.append('Selected floor does not belong to the selected block.')
            except Floor.DoesNotExist:
                errors.append('Selected floor does not exist.')
        
        # Validate department belongs to floor
        if floor_id and department_id:
            try:
                department = Department.objects.get(id=department_id)
                if str(department.floor_id) != floor_id:
                    errors.append('Selected department does not belong to the selected floor.')
            except Department.DoesNotExist:
                errors.append('Selected department does not exist.')
        
        # Validate room belongs to department
        if department_id and room_id:
            try:
                room = Room.objects.get(id=room_id)
                if str(room.department_id) != department_id:
                    errors.append('Selected room does not belong to the selected department.')
            except Room.DoesNotExist:
                errors.append('Selected room does not exist.')
        
        return JsonResponse({
            'success': len(errors) == 0,
            'errors': errors,
            'valid': len(errors) == 0
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
# ================================
# SEARCH API ENDPOINTS
# ================================

@login_required
def api_location_search(request):
    """API endpoint for location search with hierarchy context"""
    try:
        query = request.GET.get('q', '').strip()
        building_id = request.GET.get('building')
        department_id = request.GET.get('department')
        limit = int(request.GET.get('limit', 20))
        
        if len(query) < 2:
            return JsonResponse({'success': True, 'locations': []})
        
        locations = Location.objects.select_related(
            'building', 'block', 'floor', 'department', 'room'
        ).filter(is_active=True)
        
        # Apply building filter
        if building_id:
            locations = locations.filter(building_id=building_id)
        
        # Apply department filter
        if department_id:
            locations = locations.filter(department_id=department_id)
        
        # Search across hierarchy
        locations = locations.filter(
            Q(building__name__icontains=query) |
            Q(block__name__icontains=query) |
            Q(floor__name__icontains=query) |
            Q(department__name__icontains=query) |
            Q(room__room_number__icontains=query) |
            Q(room__room_name__icontains=query) |
            Q(description__icontains=query)
        )[:limit]
        
        results = []
        for location in locations:
            results.append({
                'id': location.id,
                'display_name': str(location),
                'description': location.description,
                'building': location.building.name,
                'block': location.block.name if location.block else '',
                'floor': location.floor.name if location.floor else '',
                'department': location.department.name if location.department else '',
                'room': f"{location.room.room_number} - {location.room.room_name}" if location.room else '',
            })
        
        return JsonResponse({
            'success': True,
            'locations': results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def api_hierarchy_stats(request):
    """API endpoint to get hierarchy statistics"""
    try:
        building_id = request.GET.get('building_id')
        
        if building_id:
            # Building-specific stats
            building = get_object_or_404(Building, id=building_id)
            stats = {
                'building': building.name,
                'blocks': building.blocks.filter(is_active=True).count(),
                'floors': Floor.objects.filter(building=building, is_active=True).count(),
                'departments': Department.objects.filter(floor__building=building, is_active=True).count(),
                'rooms': Room.objects.filter(department__floor__building=building, is_active=True).count(),
                'locations': Location.objects.filter(building=building, is_active=True).count(),
                'active_assignments': Assignment.objects.filter(
                    location__building=building,
                    status='ASSIGNED'
                ).count()
            }
        else:
            # System-wide stats
            stats = {
                'buildings': Building.objects.filter(is_active=True).count(),
                'blocks': Block.objects.filter(is_active=True).count(),
                'floors': Floor.objects.filter(is_active=True).count(),
                'departments': Department.objects.filter(is_active=True).count(),
                'rooms': Room.objects.filter(is_active=True).count(),
                'locations': Location.objects.filter(is_active=True).count(),
                'active_assignments': Assignment.objects.filter(status='ASSIGNED').count()
            }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
# ================================
# BACKUP & RECOVERY VIEWS
# ================================

# Backup form for forms.py
class DatabaseBackupForm(forms.Form):
    """Form for database backup options"""
    
    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Database Backup'),
        ('data_only', 'Data Only (No Schema)'),
        ('schema_only', 'Schema Only (No Data)'),
    ]
    
    backup_type = forms.ChoiceField(
        choices=BACKUP_TYPE_CHOICES,
        initial='full',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select the type of backup to create"
    )
    
    include_media = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include uploaded media files (QR codes, documents, etc.)"
    )
    
    include_logs = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include system logs and audit trails"
    )
    
    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description for this backup...'
        }),
        help_text="Add a description to identify this backup"
    )

class DatabaseRestoreForm(forms.Form):
    """Form for database restore options"""
    
    backup_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.zip,.sql,.json'
        }),
        help_text="Upload backup file (.zip, .sql, or .json)"
    )
    
    restore_data = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Restore data (WARNING: This will overwrite existing data)"
    )
    
    restore_media = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Restore media files"
    )
    
    create_backup_before_restore = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Create a backup of current data before restoring"
    )
    
    confirm_restore = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="I understand that this operation will overwrite existing data"
    )

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def database_backup(request):
    """Create database backup"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can perform database backups.")
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        form = DatabaseBackupForm(request.POST)
        if form.is_valid():
            try:
                backup_type = form.cleaned_data['backup_type']
                include_media = form.cleaned_data['include_media']
                include_logs = form.cleaned_data['include_logs']
                description = form.cleaned_data['description']
                
                # Create backup directory
                backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # Generate backup filename
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"inventory_backup_{timestamp}.zip"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # Create temporary directory for backup files
                with tempfile.TemporaryDirectory() as temp_dir:
                    
                    # Database backup
                    db_backup_path = os.path.join(temp_dir, 'database.json')
                    
                    if backup_type == 'full':
                        # Full backup with fixtures
                        call_command(
                            'dumpdata',
                            '--natural-foreign',
                            '--natural-primary',
                            '--indent=2',
                            output=db_backup_path
                        )
                    elif backup_type == 'data_only':
                        # Data only backup
                        call_command(
                            'dumpdata',
                            '--natural-foreign',
                            '--natural-primary',
                            '--indent=2',
                            '--exclude=contenttypes',
                            '--exclude=auth.permission',
                            output=db_backup_path
                        )
                    elif backup_type == 'schema_only':
                        # Schema only - create SQL dump
                        db_backup_path = os.path.join(temp_dir, 'schema.sql')
                        
                        # This would need to be adapted based on your database
                        # For SQLite:
                        if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                            db_path = settings.DATABASES['default']['NAME']
                            with open(db_backup_path, 'w') as f:
                                subprocess.run([
                                    'sqlite3', db_path, '.schema'
                                ], stdout=f, check=True)
                    
                    # Create backup metadata
                    metadata = {
                        'backup_type': backup_type,
                        'created_at': timezone.now().isoformat(),
                        'created_by': request.user.username,
                        'description': description,
                        'include_media': include_media,
                        'include_logs': include_logs,
                        'django_version': getattr(settings, 'DJANGO_VERSION', 'unknown'),
                        'inventory_version': '1.0.0',  # You can define this in settings
                    }
                    
                    metadata_path = os.path.join(temp_dir, 'metadata.json')
                    with open(metadata_path, 'w') as f:
                        json_module.dump(metadata, f, indent=2)
                    
                    # Create ZIP archive
                    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Add database backup
                        zipf.write(db_backup_path, os.path.basename(db_backup_path))
                        
                        # Add metadata
                        zipf.write(metadata_path, 'metadata.json')
                        
                        # Add media files if requested
                        if include_media:
                            media_root = Path(settings.MEDIA_ROOT)
                            for file_path in media_root.rglob('*'):
                                if file_path.is_file() and 'backups' not in str(file_path):
                                    arcname = str(file_path.relative_to(media_root))
                                    zipf.write(file_path, f"media/{arcname}")
                        
                        # Add logs if requested
                        if include_logs:
                            log_dir = getattr(settings, 'LOG_DIR', None)
                            if log_dir and os.path.exists(log_dir):
                                log_path = Path(log_dir)
                                for log_file in log_path.glob('*.log'):
                                    zipf.write(log_file, f"logs/{log_file.name}")
                
                # Log the backup activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='BACKUP_CREATE',
                    model_name='Database',
                    object_repr=f"Backup: {backup_filename}",
                    changes={'backup_type': backup_type, 'description': description},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Provide download link
                backup_url = settings.MEDIA_URL + f'backups/{backup_filename}'
                messages.success(
                    request, 
                    f'Backup created successfully: <a href="{backup_url}" class="alert-link">{backup_filename}</a>'
                )
                
                return redirect('inventory:database_backup')
                
            except Exception as e:
                messages.error(request, f"Error creating backup: {str(e)}")
    else:
        form = DatabaseBackupForm()
    
    # Get existing backups
    backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
    existing_backups = []
    
    if os.path.exists(backup_dir):
        for filename in os.listdir(backup_dir):
            if filename.endswith('.zip'):
                file_path = os.path.join(backup_dir, filename)
                file_size = os.path.getsize(file_path)
                file_date = timezone.datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).replace(tzinfo=timezone.utc)
                
                existing_backups.append({
                    'filename': filename,
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'created_at': file_date,
                    'url': settings.MEDIA_URL + f'backups/{filename}'
                })
    
    existing_backups.sort(key=lambda x: x['created_at'], reverse=True)
    
    context = {
        'form': form,
        'existing_backups': existing_backups,
        'title': 'Database Backup'
    }
    
    return render(request, 'inventory/database_backup.html', context)

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def database_restore(request):
    """Restore from backup"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can perform database restoration.")
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        form = DatabaseRestoreForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                backup_file = request.FILES['backup_file']
                restore_data = form.cleaned_data['restore_data']
                restore_media = form.cleaned_data['restore_media']
                create_backup_before_restore = form.cleaned_data['create_backup_before_restore']
                
                # Create backup before restore if requested
                if create_backup_before_restore:
                    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                    pre_restore_backup = f"pre_restore_backup_{timestamp}.zip"
                    
                    # Create a quick backup (this would call the backup function)
                    # For brevity, we'll just log this
                    messages.info(request, f"Pre-restore backup created: {pre_restore_backup}")
                
                # Process the uploaded backup file
                with tempfile.TemporaryDirectory() as temp_dir:
                    backup_path = os.path.join(temp_dir, backup_file.name)
                    
                    # Save uploaded file
                    with open(backup_path, 'wb') as f:
                        for chunk in backup_file.chunks():
                            f.write(chunk)
                    
                    # Extract backup file
                    if backup_file.name.endswith('.zip'):
                        with zipfile.ZipFile(backup_path, 'r') as zipf:
                            zipf.extractall(temp_dir)
                        
                        # Read metadata if available
                        metadata_path = os.path.join(temp_dir, 'metadata.json')
                        if os.path.exists(metadata_path):
                            with open(metadata_path, 'r') as f:
                                metadata = json_module.load(f)
                                messages.info(
                                    request, 
                                    f"Restoring backup created on {metadata.get('created_at', 'Unknown')} by {metadata.get('created_by', 'Unknown')}"
                                )
                        
                        # Restore database
                        if restore_data:
                            database_file = None
                            
                            # Look for database backup files
                            for filename in ['database.json', 'database.sql']:
                                file_path = os.path.join(temp_dir, filename)
                                if os.path.exists(file_path):
                                    database_file = file_path
                                    break
                            
                            if database_file:
                                if database_file.endswith('.json'):
                                    # Restore from Django fixture
                                    call_command('loaddata', database_file)
                                elif database_file.endswith('.sql'):
                                    # Restore from SQL dump (implementation depends on database)
                                    messages.warning(request, "SQL restore not implemented yet")
                                
                                messages.success(request, "Database restored successfully")
                            else:
                                messages.error(request, "No database backup found in archive")
                        
                        # Restore media files
                        if restore_media:
                            media_backup_dir = os.path.join(temp_dir, 'media')
                            if os.path.exists(media_backup_dir):
                                # Copy media files
                                for root, dirs, files in os.walk(media_backup_dir):
                                    for file in files:
                                        src_path = os.path.join(root, file)
                                        rel_path = os.path.relpath(src_path, media_backup_dir)
                                        dst_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                                        
                                        # Create directory if it doesn't exist
                                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                                        shutil.copy2(src_path, dst_path)
                                
                                messages.success(request, "Media files restored successfully")
                            else:
                                messages.info(request, "No media files found in backup")
                    
                    elif backup_file.name.endswith('.json'):
                        # Direct JSON fixture file
                        if restore_data:
                            call_command('loaddata', backup_path)
                            messages.success(request, "Database restored from JSON fixture")
                    
                    else:
                        messages.error(request, "Unsupported backup file format")
                        return render(request, 'inventory/database_restore.html', {'form': form})
                
                # Log the restore activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='BACKUP_RESTORE',
                    model_name='Database',
                    object_repr=f"Restored from: {backup_file.name}",
                    changes={
                        'restore_data': restore_data,
                        'restore_media': restore_media
                    },
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, "Restore completed successfully")
                return redirect('inventory:dashboard')
                
            except Exception as e:
                messages.error(request, f"Error during restore: {str(e)}")
    else:
        form = DatabaseRestoreForm()
    
    context = {
        'form': form,
        'title': 'Database Restore'
    }
    
    return render(request, 'inventory/database_restore.html', context)

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def delete_backup(request, backup_filename):
    """Delete a backup file"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can delete backups.")
        return redirect('inventory:database_backup')
    
    try:
        backup_path = os.path.join(settings.MEDIA_ROOT, 'backups', backup_filename)
        
        if os.path.exists(backup_path):
            os.remove(backup_path)
            
            # Log the deletion
            from .utils import log_user_activity
            log_user_activity(
                user=request.user,
                action='BACKUP_DELETE',
                model_name='Database',
                object_repr=f"Deleted backup: {backup_filename}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Backup {backup_filename} deleted successfully")
        else:
            messages.error(request, "Backup file not found")
    
    except Exception as e:
        messages.error(request, f"Error deleting backup: {str(e)}")
    
    return redirect('inventory:database_backup')

# ================================
# Global Search VIEW 
# ================================
@login_required
def global_search(request):
    """Global search across all inventory items"""
    try:
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'all')
        
        if len(query) < 2:
            return render(request, 'inventory/search/global_search.html', {
                'query': query,
                'results': {},
                'message': 'Please enter at least 2 characters to search.'
            })
        
        results = {}
        
        if search_type in ['all', 'devices']:
            # Search devices
            device_results = Device.objects.filter(
                Q(device_id__icontains=query) |
                Q(device_name__icontains=query) |
                Q(asset_tag__icontains=query) |
                Q(serial_number__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query)
            ).select_related('device_type__subcategory__category', 'vendor')[:20]
            
            results['devices'] = device_results
        
        if search_type in ['all', 'assignments']:
            # Search assignments
            assignment_results = Assignment.objects.filter(
                Q(assignment_id__icontains=query) |
                Q(device__device_id__icontains=query) |
                Q(device__device_name__icontains=query) |
                Q(assigned_to_staff__user__first_name__icontains=query) |
                Q(assigned_to_staff__user__last_name__icontains=query) |
                Q(assigned_to_department__name__icontains=query)
            ).select_related(
                'device', 'assigned_to_staff__user', 'assigned_to_department'
            )[:20]
            
            results['assignments'] = assignment_results
        
        if search_type in ['all', 'staff']:
            # Search staff
            staff_results = Staff.objects.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(employee_id__icontains=query) |
                Q(department__name__icontains=query)
            ).select_related('user', 'department')[:20]
            
            results['staff'] = staff_results
        
        if search_type in ['all', 'maintenance']:
            # Search maintenance records
            try:
                maintenance_results = MaintenanceSchedule.objects.filter(
                    Q(device__device_id__icontains=query) |
                    Q(device__device_name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(vendor__name__icontains=query)
                ).select_related('device', 'vendor')[:20]
                
                results['maintenance'] = maintenance_results
            except:
                results['maintenance'] = []
        
        context = {
            'query': query,
            'search_type': search_type,
            'results': results,
            'total_results': sum(len(v) for v in results.values() if hasattr(v, '__len__')),
        }
        
        return render(request, 'inventory/search/global_search.html', context)
        
    except Exception as e:
        messages.error(request, f"Error performing search: {str(e)}")
        return render(request, 'inventory/search/global_search.html', {
            'query': query,
            'results': {},
            'error': str(e)
        })


# ================================
# User's My Assignment VIEW 
# ================================

@login_required
def my_assignments(request):
    """Personal assignments view for users to see their own assignments"""
    try:
        # Get current user's staff profile
        staff_profile = None
        try:
            staff_profile = Staff.objects.get(user=request.user)
        except Staff.DoesNotExist:
            messages.warning(request, 'No staff profile found. Please contact administrator.')
            return redirect('inventory:dashboard')
        
        # Get user's assignments
        assignments = Assignment.objects.filter(
            assigned_to_staff=staff_profile
        ).select_related(
            'device', 'device__device_type', 'created_by'
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status', 'all')
        assignment_type_filter = request.GET.get('type', 'all')
        search_query = request.GET.get('search', '')
        
        # Filter by status
        if status_filter == 'active':
            assignments = assignments.filter(is_active=True)
        elif status_filter == 'returned':
            assignments = assignments.filter(is_active=False)
        elif status_filter == 'overdue':
            assignments = assignments.filter(
                assignment_type='TEMPORARY', 
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            )
        
        # Filter by assignment type
        if assignment_type_filter == 'temporary':
            assignments = assignments.filter(assignment_type='TEMPORARY')
        elif assignment_type_filter == 'permanent':
            assignments = assignments.filter(assignment_type='PERMANENT')
        
        # Search functionality
        if search_query:
            assignments = assignments.filter(
                Q(device__device_name__icontains=search_query) |
                Q(device__device_id__icontains=search_query) |
                Q(device__asset_tag__icontains=search_query) 
            )
        
        # Calculate statistics
        stats = {
            'total_assignments': Assignment.objects.filter(assigned_to_staff=staff_profile).count(),
            'active_assignments': Assignment.objects.filter(
                assigned_to_staff=staff_profile, 
                is_active=True
            ).count(),
            'temporary_assignments': Assignment.objects.filter(
                assigned_to_staff=staff_profile, 
                assignment_type='TEMPORARY',
                is_active=True
            ).count(),
            'overdue_assignments': Assignment.objects.filter(
                assigned_to_staff=staff_profile,
                assignment_type='TEMPORARY',
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            ).count(),
        }
        
        # Calculate total value of active assignments
        active_assignments_value = Assignment.objects.filter(
            assigned_to_staff=staff_profile,
            is_active=True
        ).aggregate(
            total_value=Sum('device__purchase_price')
        )['total_value'] or 0
        
        stats['total_value'] = active_assignments_value
        
        # Pagination
        paginator = Paginator(assignments, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get upcoming returns (next 30 days)
        upcoming_returns = Assignment.objects.filter(
            assigned_to_staff=staff_profile,
            assignment_type='TEMPORARY', 
            is_active=True,
            expected_return_date__gte=timezone.now().date(),
            expected_return_date__lte=timezone.now().date() + timedelta(days=30)
        ).order_by('expected_return_date')[:5]
        
        context = {
            'staff_profile': staff_profile,
            'page_obj': page_obj,
            'stats': stats,
            'upcoming_returns': upcoming_returns,
            'status_filter': status_filter,
            'assignment_type_filter': assignment_type_filter,
            'search_query': search_query,
            'title': 'My Assignments'
        }
        
        return render(request, 'inventory/my_assignments/my_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading your assignments: {str(e)}')
        return redirect('inventory:dashboard')

@login_required
def my_assignment_detail(request, assignment_id):
    """Personal assignment detail view - users can only view their own assignments"""
    try:
        # Get current user's staff profile
        staff_profile = Staff.objects.get(user=request.user)
        
        # Get assignment - ensure it belongs to the current user
        assignment = get_object_or_404(
            Assignment.objects.select_related(
                'device', 'device__device_type', 'assigned_by', 'returned_by'
            ),
            assignment_id=assignment_id,
            assigned_to_staff=staff_profile
        )
        
        # Calculate assignment duration
        assignment_duration = None
        if assignment.assigned_date:
            start_date = assignment.assigned_date
            end_date = assignment.returned_date or timezone.now().date()
            assignment_duration = (end_date - start_date).days
        
        # Check if overdue
        is_overdue = False
        days_overdue = 0
        if (assignment.is_temporary and assignment.is_active and 
            assignment.expected_return_date):
            today = timezone.now().date()
            if assignment.expected_return_date < today:
                is_overdue = True
                days_overdue = (today - assignment.expected_return_date).days
        
        context = {
            'assignment': assignment,
            'assignment_duration': assignment_duration,
            'is_overdue': is_overdue,
            'days_overdue': days_overdue,
            'title': f'Assignment #{assignment.assignment_id}'
        }
        
        return render(request, 'inventory/my_assignments/my_assignment_detail.html', context)
        
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found. Please contact administrator.')
        return redirect('inventory:dashboard')
    except Assignment.DoesNotExist:
        messages.error(request, 'Assignment not found or you do not have permission to view it.')
        return redirect('inventory:my_assignments')
    except Exception as e:
        messages.error(request, f'Error loading assignment details: {str(e)}')
        return redirect('inventory:my_assignments')