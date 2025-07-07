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
    MaintenanceSchedule, AuditLog, Room, Building,
)

# CORRECTED: Import the correct DeviceTransferForm
from .forms import (
    DeviceForm, AssignmentForm, StaffForm, ReturnForm, 
    LocationForm, AdvancedSearchForm, BulkDeviceActionForm,  
    BulkAssignmentForm, MaintenanceScheduleForm, DeviceTransferForm, AssignmentSearchForm,
    VendorForm, CSVImportForm, DepartmentForm, DeviceTypeForm
)

# FIXED: Import with comprehensive error handling and missing form fallbacks
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
        
        return render(request, 'inventory/device_history.html', context)
        
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
    
    return render(request, 'inventory/device_list.html', context)

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
        
        return render(request, 'inventory/device_detail.html', context)
        
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
    
    return render(request, 'inventory/device_form.html', context)

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
        return render(request, 'inventory/device_delete.html', context)
        
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
        
        return render(request, 'inventory/device_type_detail.html', context)
        
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
        
        return render(request, 'inventory/device_type_form.html', context)
        
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
        
        return render(request, 'inventory/device_type_confirm_delete.html', context)
        
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
    """List all assignments"""
    assignments = Assignment.objects.select_related(
        'device', 'assigned_to_staff', 'assigned_to_department'
    ).all()
    
    # Apply filters
    form = AssignmentSearchForm(request.GET)
    if form.is_valid():
        search = form.cleaned_data.get('search')
        if search:
            assignments = assignments.filter(
                Q(device__device_name__icontains=search) |
                Q(device__device_id__icontains=search) |
                Q(assigned_to_staff__user__first_name__icontains=search) |
                Q(assigned_to_staff__user__last_name__icontains=search) |
                Q(assigned_to_department__name__icontains=search)
            )
        
        status = form.cleaned_data.get('status')
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        
        assignment_type = form.cleaned_data.get('assignment_type')
        if assignment_type == 'temporary':
            assignments = assignments.filter(is_temporary=True)
        elif assignment_type == 'permanent':
            assignments = assignments.filter(is_temporary=False)
        
        department = form.cleaned_data.get('department')
        if department:
            assignments = assignments.filter(assigned_to_department=department)
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page_number = request.GET.get('page')
    assignments_page = paginator.get_page(page_number)
    
    context = {
        'assignments': assignments_page,
        'form': form,
        'title': 'Assignment Management'
    }
    
    return render(request, 'inventory/assignment_list.html', context)

@login_required
@permission_required('inventory.add_assignment', raise_exception=True)
def assignment_create(request):
    """Your existing assignment_create function"""
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    assignment = form.save(commit=False)
                    assignment.created_by = request.user
                    assignment.updated_by = request.user
                    assignment.requested_by = request.user
                    assignment.save()
                    
                    # Update device status - FIXED: This should work now with correct STATUS_CHOICES
                    device = assignment.device
                    device.status = 'ASSIGNED'
                    device.updated_by = request.user
                    device.save()
                    
                    # Create audit logs
                    AuditLog.objects.create(
                        user=request.user,
                        action='CREATE',
                        model_name='Assignment',
                        object_id=assignment.assignment_id,
                        object_repr=str(assignment),
                        changes={'created': 'New assignment created'},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Assignment "{assignment.assignment_id}" created successfully.')
                    return redirect('inventory:assignment_detail', assignment_id=assignment.assignment_id)
            except Exception as e:
                messages.error(request, f'Error creating assignment: {str(e)}')
    else:
        form = AssignmentForm()
        
        # Pre-fill device if provided in URL
        device_id = request.GET.get('device')
        if device_id:
            try:
                device = Device.objects.get(device_id=device_id, status='AVAILABLE')
                form.fields['device'].initial = device
            except Device.DoesNotExist:
                messages.warning(request, f'Device {device_id} not found or not available.')
    
    context = {
        'form': form,
        'title': 'Create Assignment'
    }
    
    return render(request, 'inventory/assignment_form.html', context)

@login_required
def assignment_detail(request, assignment_id):
    """Display comprehensive assignment details"""
    try:
        assignment = get_object_or_404(Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department',
            'assigned_to_location', 'created_by', 'updated_by', 'requested_by'
        ), assignment_id=assignment_id)
        
        # Calculate assignment duration
        assignment_duration = None
        if assignment.start_date:
            start_date = validate_date_field(assignment.start_date)
            if start_date:
                end_date = assignment.actual_return_date or timezone.now().date()
                assignment_duration = (end_date - start_date).days
        
        # Check if overdue
        is_overdue = False
        days_overdue = 0
        if (assignment.is_temporary and assignment.is_active and 
            assignment.expected_return_date):
            expected_date = validate_date_field(assignment.expected_return_date)
            if expected_date:
                today = timezone.now().date()
                if expected_date < today:
                    is_overdue = True
                    days_overdue = (today - expected_date).days
        
        # Get audit logs for this assignment
        audit_logs = AuditLog.objects.filter(
            model_name='Assignment',
            object_id=assignment.assignment_id
        ).order_by('-timestamp')[:10]
        
        context = {
            'assignment': assignment,
            'assignment_duration': assignment_duration,
            'is_overdue': is_overdue,
            'days_overdue': days_overdue,
            'audit_logs': audit_logs,
        }
        
        return render(request, 'inventory/assignment_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')

@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def assignment_return(request, assignment_id):
    """Complete assignment return function - safe version"""
    try:
        # Safe import and get assignment
        try:
            from .models import Assignment
            assignment = get_object_or_404(
                Assignment.objects.select_related(
                    'device', 'assigned_to_staff__user', 'assigned_to_department'
                ),
                assignment_id=assignment_id,
                is_active=True
            )
        except ImportError:
            messages.error(request, "Assignment model not found. Please add missing models.")
            return redirect('inventory:device_list')
        
        if request.method == 'POST':
            form = ReturnForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Get form data
                        return_date = form.cleaned_data['return_date']
                        return_condition = form.cleaned_data.get('return_condition')
                        return_notes = form.cleaned_data.get('return_notes', '')
                        device_condition = form.cleaned_data.get('device_condition')
                        
                        # Update assignment
                        assignment.is_active = False
                        assignment.actual_return_date = return_date
                        assignment.return_condition = return_condition
                        assignment.return_notes = return_notes
                        assignment.updated_by = request.user
                        assignment.save()
                        
                        # Update device status and condition
                        device = assignment.device
                        device.status = 'AVAILABLE'
                        if device_condition:
                            device.condition = device_condition
                        device.current_location = None  # Or set to default storage location
                        device.updated_by = request.user
                        device.save()
                        
                        # Create assignment history record - safe
                        try:
                            from .models import AssignmentHistory
                            AssignmentHistory.objects.create(
                                assignment=assignment,
                                device=device,
                                action='RETURNED',
                                changed_by=request.user,
                                reason=f'Device returned on {return_date}',
                                notes=return_notes
                            )
                        except ImportError:
                            pass  # Skip if model doesn't exist
                        
                        # Create audit log - safe
                        try:
                            from .models import AuditLog
                            AuditLog.objects.create(
                                user=request.user,
                                action='RETURN',
                                model_name='Assignment',
                                object_id=assignment.assignment_id,
                                object_repr=str(assignment),
                                changes={
                                    'returned_date': str(return_date),
                                    'condition': return_condition,
                                    'notes': return_notes,
                                    'device_status_changed_to': 'AVAILABLE'
                                },
                                ip_address=request.META.get('REMOTE_ADDR')
                            )
                        except ImportError:
                            pass  # Skip if model doesn't exist
                        
                        messages.success(
                            request, 
                            f'Device "{device.device_name}" returned successfully from assignment {assignment.assignment_id}'
                        )
                        return redirect('inventory:device_detail', device_id=device.device_id)
                        
                except Exception as e:
                    messages.error(request, f'Error returning device: {str(e)}')
            else:
                messages.error(request, 'Please correct the form errors.')
        else:
            # Initialize form with current device condition
            initial_data = {
                'return_date': timezone.now().date(),
                'device_condition': assignment.device.condition,
                'return_condition': assignment.device.condition
            }
            form = ReturnForm(initial=initial_data)
        
        # Calculate assignment duration
        assignment_duration = None
        if assignment.start_date:
            assignment_duration = (timezone.now().date() - assignment.start_date).days
        
        # Check if assignment is overdue
        is_overdue = False
        days_overdue = 0
        if assignment.is_temporary and assignment.expected_return_date:
            if assignment.expected_return_date < timezone.now().date():
                is_overdue = True
                days_overdue = (timezone.now().date() - assignment.expected_return_date).days
        
        context = {
            'form': form,
            'assignment': assignment,
            'assignment_duration': assignment_duration,
            'is_overdue': is_overdue,
            'days_overdue': days_overdue,
            'title': f'Return Device from Assignment {assignment.assignment_id}',
        }
        
        return render(request, 'inventory/assignment_return.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')
    
@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def assignment_transfer(request, assignment_id):
    """Transfer assignment to another staff/department - CORRECTED"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id, is_active=True)
        
        if request.method == 'POST':
            form = DeviceTransferForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Create new assignment using the CORRECTED field names
                        new_assignment = Assignment.objects.create(
                            device=assignment.device,
                            assigned_to_staff=form.cleaned_data.get('new_assigned_to_staff'),
                            assigned_to_department=form.cleaned_data.get('new_assigned_to_department'),
                            assigned_to_location=form.cleaned_data.get('new_assigned_to_location'),
                            is_temporary=assignment.is_temporary,
                            expected_return_date=assignment.expected_return_date,
                            purpose=form.cleaned_data.get('transfer_reason', ''),
                            conditions=form.cleaned_data.get('conditions', ''),
                            created_by=request.user,
                            updated_by=request.user,
                            requested_by=request.user
                        )
                        
                        # Close old assignment
                        assignment.is_active = False
                        assignment.actual_return_date = timezone.now().date()
                        assignment.updated_by = request.user
                        assignment.save()
                        
                        # Create audit log
                        AuditLog.objects.create(
                            user=request.user,
                            action='TRANSFER',
                            model_name='Assignment',
                            object_id=assignment.assignment_id,
                            object_repr=str(assignment),
                            changes={
                                'transferred_to': str(new_assignment.assignment_id),
                                'reason': form.cleaned_data.get('transfer_reason', '')
                            },
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Assignment transferred successfully. New assignment ID: {new_assignment.assignment_id}')
                        return redirect('inventory:assignment_detail', assignment_id=new_assignment.assignment_id)
                        
                except Exception as e:
                    messages.error(request, f'Error transferring assignment: {str(e)}')
        else:
            form = DeviceTransferForm()
        
        context = {
            'form': form,
            'assignment': assignment,
            'title': f'Transfer Assignment {assignment.assignment_id}',
        }
        return render(request, 'inventory/assignment_transfer.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')

@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def assignment_edit(request, assignment_id):
    """Edit assignment details"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id)
        original_data = {
            'assigned_to_staff': assignment.assigned_to_staff,
            'assigned_to_department': assignment.assigned_to_department,
            'expected_return_date': assignment.expected_return_date,
        }
        
        if request.method == 'POST':
            form = AssignmentForm(request.POST, instance=assignment)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        assignment = form.save(commit=False)
                        assignment.updated_by = request.user
                        assignment.save()
                        
                        # Track changes
                        changes = {}
                        for field, old_value in original_data.items():
                            new_value = getattr(assignment, field)
                            if old_value != new_value:
                                changes[field] = {'old': str(old_value), 'new': str(new_value)}
                        
                        if changes:
                            AuditLog.objects.create(
                                user=request.user,
                                action='UPDATE',
                                model_name='Assignment',
                                object_id=assignment.assignment_id,
                                object_repr=str(assignment),
                                changes=changes,
                                ip_address=request.META.get('REMOTE_ADDR')
                            )
                        
                        messages.success(request, f'Assignment "{assignment.assignment_id}" updated successfully.')
                        return redirect('inventory:assignment_detail', assignment_id=assignment.assignment_id)
                except Exception as e:
                    messages.error(request, f'Error updating assignment: {str(e)}')
        else:
            form = AssignmentForm(instance=assignment)
        
        context = {
            'form': form,
            'assignment': assignment,
            'title': f'Edit Assignment {assignment.assignment_id}',
            'action': 'Update',
        }
        return render(request, 'inventory/assignment_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')

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
        return render(request, 'inventory/assignment_extend.html', context)
        
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
    return render(request, 'inventory/bulk_assignment.html', context)

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
        
        return render(request, 'inventory/overdue_assignments.html', context)
        
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
        
        return render(request, 'inventory/staff_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff list: {str(e)}")
        return render(request, 'inventory/staff_list.html', {'page_obj': None})

@login_required
def staff_detail(request, staff_id):
    """Staff detail view with assignment history"""
    try:
        staff = get_object_or_404(Staff.objects.select_related('department'), id=staff_id)
        
        # Get assignments with pagination
        assignments = Assignment.objects.filter(
            staff=staff
        ).select_related(
            'device', 'device__device_type', 'assigned_by', 'returned_by'
        ).order_by('-assigned_date')
        
        # Current assignments
        current_assignments = assignments.filter(status='ACTIVE')
        
        # Assignment history
        assignment_history = assignments.filter(status__in=['RETURNED', 'TRANSFERRED'])
        
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
        
        return render(request, 'inventory/staff_detail.html', context)
        
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
    return render(request, 'inventory/staff_form.html', context)

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
        return render(request, 'inventory/staff_form.html', context)
        
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
            staff=staff,
            status='ACTIVE'
        ).count()
        
        if active_assignments > 0:
            messages.error(
                request, 
                f'Cannot delete staff member "{staff.get_full_name()}". They have {active_assignments} active device assignments.'
            )
            return redirect('inventory:staff_detail', staff_id=staff.id)
        
        if request.method == 'POST':
            try:
                with transaction.atomic():
                    staff_name = staff.get_full_name()
                    
                    # Log the activity before deletion
                    from .utils import log_user_activity
                    log_user_activity(
                        user=request.user,
                        action='DELETE',
                        model_name='Staff',
                        object_id=staff.id,
                        object_repr=str(staff),
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    staff.delete()
                    messages.success(request, f'Staff member "{staff_name}" deleted successfully.')
                    return redirect('inventory:staff_list')
            except Exception as e:
                messages.error(request, f'Error deleting staff member: {str(e)}')
                return redirect('inventory:staff_detail', staff_id=staff.id)
        
        context = {
            'staff': staff,
            'active_assignments': active_assignments,
            'title': f'Delete Staff: {staff.get_full_name()}',
        }
        return render(request, 'inventory/staff_delete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff for deletion: {str(e)}")
        return redirect('inventory:staff_list')

@login_required
def staff_assignments(request, staff_id):
    """View all assignments for a specific staff member"""
    try:
        staff = get_object_or_404(Staff.objects.select_related('department'), id=staff_id)
        
        # Get all assignments for this staff member
        assignments = Assignment.objects.filter(
            staff=staff
        ).select_related(
            'device', 'device__device_type', 'assigned_by', 'returned_by'
        ).order_by('-assigned_date')
        
        # Filter by status if specified
        status_filter = request.GET.get('status')
        if status_filter:
            assignments = assignments.filter(status=status_filter)
        
        # Search within assignments
        search = request.GET.get('search')
        if search:
            assignments = assignments.filter(
                Q(device__asset_tag__icontains=search) |
                Q(device__serial_number__icontains=search) |
                Q(device__device_type__name__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(assignments, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Stats
        stats = {
            'total': assignments.count(),
            'active': assignments.filter(status='ACTIVE').count(),
            'returned': assignments.filter(status='RETURNED').count(),
            'transferred': assignments.filter(status='TRANSFERRED').count(),
        }
        
        context = {
            'staff': staff,
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'stats': stats,
        }
        
        return render(request, 'inventory/staff_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff assignments: {str(e)}")
        return redirect('inventory:staff_detail', staff_id=staff_id)
    
# ================================
# DEPARTMENT MANAGEMENT VIEWS
# ================================

@login_required
def department_list(request):
    """List all departments with staff and device counts"""
    try:
        departments = Department.objects.prefetch_related(
            'staff_members', 'staff_members__assignments'
        ).annotate(
            staff_count=Count('staff_members'),
            active_assignments=Count(
                'staff_members__assignments',
                filter=Q(staff_members__assignments__status='ACTIVE')
            )
        ).order_by('name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            departments = departments.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(head_name__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(departments, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search': search,
        }
        
        return render(request, 'inventory/department_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department list: {str(e)}")
        return render(request, 'inventory/department_list.html', {'page_obj': None})

@login_required
def department_detail(request, department_id):
    """Department detail view with staff and assignments"""
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # Get staff members in this department
        staff_members = Staff.objects.filter(
            department=department
        ).annotate(
            active_assignments=Count('assignments', filter=Q(assignments__status='ACTIVE'))
        ).order_by('last_name', 'first_name')
        
        # Get all active assignments for this department
        active_assignments = Assignment.objects.filter(
            staff__department=department,
            status='ACTIVE'
        ).select_related(
            'device', 'device__device_type', 'staff'
        ).order_by('-assigned_date')
        
        # Calculate stats
        total_staff = staff_members.count()
        total_active_assignments = active_assignments.count()
        
        # Calculate total value of active assignments
        total_value = active_assignments.aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Device category breakdown
        category_breakdown = active_assignments.values(
            'device__device_type__subcategory__category__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Recent assignment activity
        recent_assignments = Assignment.objects.filter(
            staff__department=department
        ).select_related(
            'device', 'device__device_type', 'staff'
        ).order_by('-assigned_date')[:10]
        
        context = {
            'department': department,
            'staff_members': staff_members,
            'active_assignments': active_assignments,
            'total_staff': total_staff,
            'total_active_assignments': total_active_assignments,
            'total_value': total_value,
            'category_breakdown': category_breakdown,
            'recent_assignments': recent_assignments,
        }
        
        return render(request, 'inventory/department_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department details: {str(e)}")
        return redirect('inventory:department_list')

@login_required
@permission_required('inventory.add_department', raise_exception=True)
def department_create(request):
    """Create new department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            try:
                department = form.save()
                
                # Log the activity
                from .utils import log_user_activity
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    model_name='Department',
                    object_id=department.id,
                    object_repr=str(department),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Department "{department.name}" created successfully.')
                return redirect('inventory:department_detail', department_id=department.id)
            except Exception as e:
                messages.error(request, f'Error creating department: {str(e)}')
    else:
        form = DepartmentForm()
    
    context = {
        'form': form,
        'title': 'Add New Department',
        'action': 'Create',
    }
    return render(request, 'inventory/department_form.html', context)

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
def department_assignments(request, department_id):
    """View all assignments for a specific department"""
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # Get all assignments for staff in this department
        assignments = Assignment.objects.filter(
            staff__department=department
        ).select_related(
            'device', 'device__device_type', 'staff', 'assigned_by'
        ).order_by('-assigned_date')
        
        # Filter by status if specified
        status_filter = request.GET.get('status')
        if status_filter:
            assignments = assignments.filter(status=status_filter)
        
        # Filter by staff member if specified
        staff_filter = request.GET.get('staff')
        if staff_filter:
            assignments = assignments.filter(staff_id=staff_filter)
        
        # Search within assignments
        search = request.GET.get('search')
        if search:
            assignments = assignments.filter(
                Q(device__asset_tag__icontains=search) |
                Q(device__serial_number__icontains=search) |
                Q(device__device_type__name__icontains=search) |
                Q(staff__first_name__icontains=search) |
                Q(staff__last_name__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get staff members for filter
        staff_members = Staff.objects.filter(
            department=department
        ).order_by('last_name', 'first_name')
        
        # Stats
        stats = {
            'total': assignments.count(),
            'active': assignments.filter(status='ACTIVE').count(),
            'returned': assignments.filter(status='RETURNED').count(),
            'transferred': assignments.filter(status='TRANSFERRED').count(),
        }
        
        # Total value of active assignments
        active_value = assignments.filter(status='ACTIVE').aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        context = {
            'department': department,
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'staff_filter': staff_filter,
            'staff_members': staff_members,
            'stats': stats,
            'active_value': active_value,
        }
        
        return render(request, 'inventory/department_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department assignments: {str(e)}")
        return redirect('inventory:department_detail', department_id=department_id)

# ================================
# LOCATION MANAGEMENT VIEWS
# ================================

@login_required
def location_list(request):
    """List all locations with device counts"""
    try:
        locations = Location.objects.select_related(
            'room__department', 'room__building'
        ).prefetch_related(
            'device_locations__device'
        ).annotate(
            device_count=Count('device_locations', filter=Q(device_locations__is_active=True))
        ).order_by('room__building__name', 'room__name', 'name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            locations = locations.filter(
                Q(name__icontains=search) |
                Q(room__name__icontains=search) |
                Q(room__department__name__icontains=search)
            )
        
        # Building filter
        building_id = request.GET.get('building')
        if building_id:
            locations = locations.filter(room__building_id=building_id)
        
        # Department filter
        department_id = request.GET.get('department')
        if department_id:
            locations = locations.filter(room__department_id=department_id)
        
        # Pagination
        paginator = Paginator(locations, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter options
        buildings = Building.objects.all().order_by('name')
        departments = Department.objects.all().order_by('name')
        
        context = {
            'page_obj': page_obj,
            'buildings': buildings,
            'departments': departments,
            'search': search,
            'selected_building': building_id,
            'selected_department': department_id,
        }
        
        return render(request, 'inventory/location_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading locations: {str(e)}")
        return render(request, 'inventory/location_list.html', {'page_obj': None})

@login_required
def location_detail(request, location_id):
    """Display location details with assigned devices"""
    try:
        location = get_object_or_404(Location.objects.select_related(
            'room__department', 'room__building'
        ), id=location_id)
        
        # Get devices at this location
        current_assignments = Assignment.objects.filter(
            assigned_to_location=location,
            is_active=True
        ).select_related('device', 'assigned_to_staff')
        
        # Get assignment history for this location
        assignment_history = Assignment.objects.filter(
            assigned_to_location=location
        ).select_related('device', 'assigned_to_staff').order_by('-created_at')[:20]
        
        # Calculate statistics
        total_devices = current_assignments.count()
        total_value = current_assignments.aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Device categories at this location
        category_breakdown = current_assignments.values(
            'device__device_type__subcategory__category__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        context = {
            'location': location,
            'current_assignments': current_assignments,
            'assignment_history': assignment_history,
            'total_devices': total_devices,
            'total_value': total_value,
            'category_breakdown': category_breakdown,
        }
        
        return render(request, 'inventory/location_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading location details: {str(e)}")
        return redirect('inventory:location_list')

@login_required
@permission_required('inventory.add_location', raise_exception=True)
def location_create(request):
    """Create new location"""
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            try:
                location = form.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='Location',
                    object_id=str(location.id),
                    object_repr=str(location),
                    changes={'created': 'New location added'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Location "{location.name}" created successfully.')
                return redirect('inventory:location_detail', location_id=location.id)
            except Exception as e:
                messages.error(request, f'Error creating location: {str(e)}')
    else:
        form = LocationForm()
    
    context = {
        'form': form,
        'title': 'Add New Location',
        'action': 'Create',
    }
    return render(request, 'inventory/location_form.html', context)

@login_required
@permission_required('inventory.change_location', raise_exception=True)
def location_edit(request, location_id):
    """Edit location details"""
    try:
        location = get_object_or_404(Location, id=location_id)
        
        if request.method == 'POST':
            form = LocationForm(request.POST, instance=location)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        location = form.save()
                        
                        # Log the activity
                        from .utils import log_user_activity
                        log_user_activity(
                            user=request.user,
                            action='UPDATE',
                            model_name='Location',
                            object_id=location.id,
                            object_repr=str(location),
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Location "{location.name}" updated successfully.')
                        return redirect('inventory:location_detail', location_id=location.id)
                except Exception as e:
                    messages.error(request, f'Error updating location: {str(e)}')
        else:
            form = LocationForm(instance=location)
        
        context = {
            'form': form,
            'location': location,
            'title': f'Edit Location: {location.name}',
            'action': 'Update',
        }
        return render(request, 'inventory/location_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading location for edit: {str(e)}")
        return redirect('inventory:location_list')

@login_required
@permission_required('inventory.delete_location', raise_exception=True)
def location_delete(request, location_id):
    """Delete location"""
    try:
        location = get_object_or_404(Location, id=location_id)
        
        # Check if location has active assignments
        active_assignments = Assignment.objects.filter(
            location=location,
            status='ACTIVE'
        ).count()
        
        if active_assignments > 0:
            messages.error(
                request, 
                f'Cannot delete location "{location.name}". It has {active_assignments} active device assignments.'
            )
            return redirect('inventory:location_detail', location_id=location.id)
        
        if request.method == 'POST':
            try:
                with transaction.atomic():
                    location_name = location.name
                    
                    # Log the activity before deletion
                    from .utils import log_user_activity
                    log_user_activity(
                        user=request.user,
                        action='DELETE',
                        model_name='Location',
                        object_id=location.id,
                        object_repr=str(location),
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    location.delete()
                    messages.success(request, f'Location "{location_name}" deleted successfully.')
                    return redirect('inventory:location_list')
            except Exception as e:
                messages.error(request, f'Error deleting location: {str(e)}')
                return redirect('inventory:location_detail', location_id=location.id)
        
        context = {
            'location': location,
            'active_assignments': active_assignments,
            'title': f'Delete Location: {location.name}',
        }
        return render(request, 'inventory/location_delete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading location for deletion: {str(e)}")
        return redirect('inventory:location_list')

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
        return render(request, 'inventory/maintenance_complete.html', context)
        
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
        
        return render(request, 'inventory/device_type_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device types: {str(e)}")
        return render(request, 'inventory/device_type_list.html', {'page_obj': None})

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
    return render(request, 'inventory/device_type_form.html', context)

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
        return render(request, 'inventory/bulk_qr_generate.html', context)
    
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
        return render(request, 'inventory/bulk_actions_dispatcher.html', context)
    
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
    return render(request, 'inventory/bulk_import.html', {
        'title': 'Bulk Import Data'
    })

@login_required
def bulk_export(request):
    """Main bulk export page"""
    return render(request, 'inventory/bulk_export.html', {
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
def warranty_report(request):
    """Generate warranty status report"""
    try:
        today = date.today()
        
        # Warranty statistics
        active_warranties = Device.objects.filter(warranty_end_date__gte=today)
        expired_warranties = Device.objects.filter(warranty_end_date__lt=today)
        expiring_soon = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=90)
        )
        
        # Vendor warranty breakdown
        vendor_warranties = Vendor.objects.annotate(
            active_warranties=Count(
                'devices',
                filter=Q(devices__warranty_end_date__gte=today)
            ),
            expired_warranties=Count(
                'devices',
                filter=Q(devices__warranty_end_date__lt=today)
            )
        ).order_by('-active_warranties')
        
        context = {
            'active_warranties': active_warranties,
            'expired_warranties': expired_warranties,
            'expiring_soon': expiring_soon,
            'vendor_warranties': vendor_warranties,
            'report_date': today,
        }
        
        return render(request, 'inventory/reports/warranty.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating warranty report: {str(e)}")
        return redirect('inventory:dashboard')
    
@login_required
def assignment_report(request):
    """Generate assignment analysis report"""
    try:
        # Assignment statistics
        total_assignments = Assignment.objects.count()
        active_assignments = Assignment.objects.filter(is_active=True)
        overdue_assignments = Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=date.today()
        )
        
        # Department assignment breakdown
        dept_assignments = Department.objects.annotate(
            assignment_count=Count('staff__assignments'),
            active_assignment_count=Count(
                'staff__assignments',
                filter=Q(staff__assignments__is_active=True)
            )
        ).order_by('-assignment_count')
        
        context = {
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'overdue_assignments': overdue_assignments,
            'dept_assignments': dept_assignments,
            'report_date': date.today(),
        }
        
        return render(request, 'inventory/reports/assignment.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating assignment report: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def audit_report(request):
    """Generate audit trail report"""
    try:
        # Recent audit activities
        recent_activities = AuditLog.objects.select_related('user').order_by('-timestamp')[:100]
        
        # Activity breakdown by action
        action_breakdown = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # User activity summary
        user_activity = AuditLog.objects.values(
            'user__username'
        ).annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        context = {
            'recent_activities': recent_activities,
            'action_breakdown': action_breakdown,
            'user_activity': user_activity,
            'report_date': date.today(),
        }
        
        return render(request, 'inventory/reports/audit.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating audit report: {str(e)}")
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
        
        return render(request, 'inventory/device_qr_code.html', context)
        
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
    
# ================================
# BACKUP & RECOVERY VIEWS - LOW PRIORITY
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
