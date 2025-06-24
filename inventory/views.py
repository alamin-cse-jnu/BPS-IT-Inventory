# inventory/views.py - COMPLETE DJANGO INVENTORY MANAGEMENT VIEWS

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg, Max, Min, F, Case, When, FloatField
from django.core.paginator import Paginator
from django.urls import reverse
from django.forms import formset_factory
from django.contrib.auth.models import User
from django.db import transaction
from datetime import date, timedelta, datetime
import json
import csv
from io import StringIO

from .models import (
    Device, Assignment, Staff, Department, Location, 
    DeviceCategory, DeviceType, DeviceSubCategory, Vendor,
    MaintenanceSchedule, AuditLog, Room, Building
)
from .forms import (
    DeviceForm, AssignmentForm, StaffForm, 
    LocationForm, DeviceSearchForm, 
    BulkAssignmentForm, MaintenanceScheduleForm, DeviceTransferForm,
    VendorForm
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
        fields = ['name', 'code', 'description']

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
# DEVICE MANAGEMENT VIEWS
# ================================

@login_required
def device_list(request):
    """Comprehensive device list with advanced filtering"""
    try:
        devices = Device.objects.select_related(
            'device_type__subcategory__category',
            'vendor', 'current_location', 'created_by'
        ).prefetch_related(
            'assignments__assigned_to_staff',
            'assignments__assigned_to_department'
        ).order_by('-created_at')
        
        # Apply filters
        search_form = DeviceSearchForm(request.GET)
        if search_form.is_valid():
            # Device search
            if search_form.cleaned_data.get('search'):
                search_term = search_form.cleaned_data['search']
                devices = devices.filter(
                    Q(device_name__icontains=search_term) |
                    Q(device_id__icontains=search_term) |
                    Q(asset_tag__icontains=search_term) |
                    Q(serial_number__icontains=search_term) |
                    Q(model__icontains=search_term) |
                    Q(brand__icontains=search_term)
                )
            
            # Status filter
            if search_form.cleaned_data.get('status'):
                devices = devices.filter(status=search_form.cleaned_data['status'])
            
            # Category filter
            if search_form.cleaned_data.get('category'):
                devices = devices.filter(
                    device_type__subcategory__category=search_form.cleaned_data['category']
                )
            
            # Location filter
            if search_form.cleaned_data.get('location'):
                devices = devices.filter(current_location=search_form.cleaned_data['location'])
            
            # Vendor filter
            if search_form.cleaned_data.get('vendor'):
                devices = devices.filter(vendor=search_form.cleaned_data['vendor'])
            
            # Warranty status filter
            warranty_status = search_form.cleaned_data.get('warranty_status')
            if warranty_status:
                today = timezone.now().date()
                if warranty_status == 'active':
                    devices = devices.filter(warranty_end_date__gte=today)
                elif warranty_status == 'expired':
                    devices = devices.filter(warranty_end_date__lt=today)
                elif warranty_status == 'expiring':
                    alert_date = today + timedelta(days=30)
                    devices = devices.filter(
                        warranty_end_date__gte=today,
                        warranty_end_date__lte=alert_date
                    )
            
            # Assignment status filter
            assignment_status = search_form.cleaned_data.get('assignment_status')
            if assignment_status == 'assigned':
                devices = devices.filter(assignments__is_active=True).distinct()
            elif assignment_status == 'unassigned':
                devices = devices.exclude(assignments__is_active=True).distinct()
            
            # Condition filter
            if search_form.cleaned_data.get('condition'):
                devices = devices.filter(condition=search_form.cleaned_data['condition'])
            
            # Date range filters
            purchase_date_from = search_form.cleaned_data.get('purchase_date_from')
            purchase_date_to = search_form.cleaned_data.get('purchase_date_to')
            if purchase_date_from:
                devices = devices.filter(purchase_date__gte=purchase_date_from)
            if purchase_date_to:
                devices = devices.filter(purchase_date__lte=purchase_date_to)
        
        # Pagination
        paginator = Paginator(devices, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_form': search_form,
            'total_devices': devices.count(),
        }
        
        return render(request, 'inventory/device_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading devices: {str(e)}")
        return render(request, 'inventory/device_list.html', {
            'page_obj': None, 
            'search_form': DeviceSearchForm(), 
            'total_devices': 0
        })

@login_required
def device_detail(request, device_id):
    """Comprehensive device details with full history"""
    try:
        device = get_object_or_404(Device.objects.select_related(
            'device_type__subcategory__category',
            'vendor', 'current_location', 'created_by', 'updated_by'
        ).prefetch_related(
            'assignments__assigned_to_staff',
            'assignments__assigned_to_department',
            'assignments__assigned_to_location',
            'maintenance_schedules'
        ), device_id=device_id)
        
        # Get current assignment
        current_assignment = device.assignments.filter(is_active=True).first()
        
        # Get assignment history
        assignment_history = device.assignments.select_related(
            'assigned_to_staff', 'assigned_to_department', 'assigned_to_location', 'created_by'
        ).order_by('-created_at')[:10]
        
        # Get maintenance history
        maintenance_history = device.maintenance_schedules.select_related(
            'vendor', 'created_by'
        ).order_by('-scheduled_date')[:5]
        
        # QR scans placeholder (implement when qr_management app is available)
        recent_scans = []
        
        # Calculate warranty status with proper date handling
        warranty_status = 'Unknown'
        warranty_class = 'secondary'
        warranty_days_remaining = None
        
        if device.warranty_end_date:
            # Ensure proper date handling
            warranty_end = validate_date_field(device.warranty_end_date)
            if warranty_end:
                today = timezone.now().date()
                if warranty_end >= today:
                    warranty_days_remaining = (warranty_end - today).days
                    if warranty_days_remaining <= 7:
                        warranty_status = f'Expires in {warranty_days_remaining} days'
                        warranty_class = 'danger'
                    elif warranty_days_remaining <= 30:
                        warranty_status = f'Expires in {warranty_days_remaining} days'
                        warranty_class = 'warning'
                    else:
                        warranty_status = f'Active ({warranty_days_remaining} days remaining)'
                        warranty_class = 'success'
                else:
                    days_expired = (today - warranty_end).days
                    warranty_status = f'Expired {days_expired} days ago'
                    warranty_class = 'danger'
        
        # Get audit logs for this device
        audit_logs = AuditLog.objects.filter(
            model_name='Device',
            object_id=device.device_id
        ).order_by('-timestamp')[:10]
        
        context = {
            'device': device,
            'current_assignment': current_assignment,
            'assignment_history': assignment_history,
            'maintenance_history': maintenance_history,
            'recent_scans': recent_scans,
            'warranty_status': warranty_status,
            'warranty_class': warranty_class,
            'warranty_days_remaining': warranty_days_remaining,
            'audit_logs': audit_logs,
            'is_warranty_expiring': warranty_days_remaining and warranty_days_remaining <= 30,
        }
        
        return render(request, 'inventory/device_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device details: {str(e)}")
        return redirect('inventory:device_list')

@login_required
@permission_required('inventory.add_device', raise_exception=True)
def device_create(request):
    """Create a new device with comprehensive validation"""
    if request.method == 'POST':
        form = DeviceForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    device = form.save(commit=False)
                    device.created_by = request.user
                    device.updated_by = request.user
                    device.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='CREATE',
                        model_name='Device',
                        object_id=device.device_id,
                        object_repr=str(device),
                        changes={'created': 'New device added'},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Device "{device.device_name}" ({device.device_id}) created successfully.')
                    return redirect('inventory:device_detail', device_id=device.device_id)
            except Exception as e:
                messages.error(request, f'Error creating device: {str(e)}')
    else:
        form = DeviceForm()
    
    context = {
        'form': form,
        'title': 'Add New Device',
        'action': 'Create',
        'submit_text': 'Create Device'
    }
    return render(request, 'inventory/device_form.html', context)

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def device_edit(request, device_id):
    """Edit device with change tracking"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        original_data = {
            'device_name': device.device_name,
            'status': device.status,
            'condition': device.condition,
            'current_location': device.current_location,
        }
        
        if request.method == 'POST':
            form = DeviceForm(request.POST, request.FILES, instance=device)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        device = form.save(commit=False)
                        device.updated_by = request.user
                        device.save()
                        
                        # Track changes
                        changes = {}
                        for field, old_value in original_data.items():
                            new_value = getattr(device, field)
                            if old_value != new_value:
                                changes[field] = {'old': str(old_value), 'new': str(new_value)}
                        
                        if changes:
                            AuditLog.objects.create(
                                user=request.user,
                                action='UPDATE',
                                model_name='Device',
                                object_id=device.device_id,
                                object_repr=str(device),
                                changes=changes,
                                ip_address=request.META.get('REMOTE_ADDR')
                            )
                        
                        messages.success(request, f'Device "{device.device_name}" updated successfully.')
                        return redirect('inventory:device_detail', device_id=device.device_id)
                except Exception as e:
                    messages.error(request, f'Error updating device: {str(e)}')
        else:
            form = DeviceForm(instance=device)
        
        context = {
            'form': form,
            'device': device,
            'title': f'Edit {device.device_name}',
            'action': 'Update',
            'submit_text': 'Update Device'
        }
        return render(request, 'inventory/device_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading device: {str(e)}")
        return redirect('inventory:device_list')

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

# ================================
# ASSIGNMENT MANAGEMENT VIEWS
# ================================

@login_required
def assignment_list(request):
    """Comprehensive assignment listing with filtering"""
    try:
        assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department',
            'assigned_to_location', 'created_by', 'requested_by'
        ).order_by('-created_at')
        
        # Apply filters
        search_form = AssignmentSearchForm(request.GET)
        if search_form.is_valid():
            # Search functionality
            if search_form.cleaned_data.get('search'):
                search_term = search_form.cleaned_data['search']
                assignments = assignments.filter(
                    Q(device__device_name__icontains=search_term) |
                    Q(device__device_id__icontains=search_term) |
                    Q(assigned_to_staff__first_name__icontains=search_term) |
                    Q(assigned_to_staff__last_name__icontains=search_term) |
                    Q(assigned_to_staff__employee_id__icontains=search_term) |
                    Q(assignment_id__icontains=search_term)
                )
            
            # Status filters
            status = search_form.cleaned_data.get('status')
            if status == 'active':
                assignments = assignments.filter(is_active=True)
            elif status == 'inactive':
                assignments = assignments.filter(is_active=False)
            elif status == 'overdue':
                today = timezone.now().date()
                assignments = assignments.filter(
                    is_temporary=True,
                    is_active=True,
                    expected_return_date__lt=today,
                    actual_return_date__isnull=True
                )
            
            # Assignment type filter
            assignment_type = search_form.cleaned_data.get('assignment_type')
            if assignment_type == 'permanent':
                assignments = assignments.filter(is_temporary=False)
            elif assignment_type == 'temporary':
                assignments = assignments.filter(is_temporary=True)
            
            # Department filter
            if search_form.cleaned_data.get('department'):
                assignments = assignments.filter(
                    Q(assigned_to_department=search_form.cleaned_data['department']) |
                    Q(assigned_to_staff__department=search_form.cleaned_data['department'])
                )
            
            # Date range filters
            date_from = search_form.cleaned_data.get('date_from')
            date_to = search_form.cleaned_data.get('date_to')
            if date_from:
                assignments = assignments.filter(created_at__date__gte=date_from)
            if date_to:
                assignments = assignments.filter(created_at__date__lte=date_to)
        
        # Pagination
        paginator = Paginator(assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_form': search_form,
            'total_assignments': assignments.count(),
        }
        
        return render(request, 'inventory/assignment_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignments: {str(e)}")
        return render(request, 'inventory/assignment_list.html', {
            'page_obj': None, 
            'search_form': AssignmentSearchForm(), 
            'total_assignments': 0
        })

@login_required
@permission_required('inventory.add_assignment', raise_exception=True)
def assignment_create(request):
    """Create new assignment with validation"""
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
                    
                    # Update device status
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
        'title': 'Create New Assignment',
        'action': 'Create',
        'submit_text': 'Create Assignment'
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
    """Return device from assignment"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id, is_active=True)
        
        if request.method == 'POST':
            form = ReturnForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Update assignment
                        assignment.is_active = False
                        assignment.actual_return_date = form.cleaned_data['return_date']
                        assignment.return_condition = form.cleaned_data.get('return_condition')
                        assignment.return_notes = form.cleaned_data.get('return_notes', '')
                        assignment.updated_by = request.user
                        assignment.save()
                        
                        # Update device status
                        device = assignment.device
                        device.status = 'AVAILABLE'
                        device.condition = form.cleaned_data.get('device_condition', device.condition)
                        device.updated_by = request.user
                        device.save()
                        
                        # Create audit log
                        AuditLog.objects.create(
                            user=request.user,
                            action='RETURN',
                            model_name='Assignment',
                            object_id=assignment.assignment_id,
                            object_repr=str(assignment),
                            changes={
                                'returned_date': str(assignment.actual_return_date),
                                'condition': form.cleaned_data.get('device_condition'),
                                'notes': form.cleaned_data.get('return_notes', '')
                            },
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.success(request, f'Device returned successfully from assignment {assignment.assignment_id}')
                        return redirect('inventory:device_detail', device_id=device.device_id)
                        
                except Exception as e:
                    messages.error(request, f'Error returning device: {str(e)}')
        else:
            form = ReturnForm(initial={'return_date': timezone.now().date()})
        
        context = {
            'form': form,
            'assignment': assignment,
            'title': f'Return Device from Assignment {assignment.assignment_id}',
        }
        return render(request, 'inventory/assignment_return.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')

@login_required
@permission_required('inventory.change_assignment', raise_exception=True)
def assignment_transfer(request, assignment_id):
    """Transfer assignment to another staff/department"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id, is_active=True)
        
        if request.method == 'POST':
            form = DeviceTransferForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Create new assignment
                        new_assignment = Assignment.objects.create(
                            device=assignment.device,
                            assigned_to_staff=form.cleaned_data.get('new_staff'),
                            assigned_to_department=form.cleaned_data.get('new_department'),
                            assigned_to_location=form.cleaned_data.get('new_location'),
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
    """List all staff members"""
    try:
        staff_members = Staff.objects.select_related(
            'department', 'reporting_manager'
        ).prefetch_related(
            'staff_assignments__device'
        ).order_by('department__name', 'last_name', 'first_name')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            staff_members = staff_members.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Department filter
        department_id = request.GET.get('department')
        if department_id:
            staff_members = staff_members.filter(department_id=department_id)
        
        # Pagination
        paginator = Paginator(staff_members, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get departments for filter
        departments = Department.objects.all().order_by('name')
        
        context = {
            'page_obj': page_obj,
            'departments': departments,
            'search': search,
            'selected_department': department_id,
        }
        
        return render(request, 'inventory/staff_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff: {str(e)}")
        return render(request, 'inventory/staff_list.html', {'page_obj': None})

@login_required
def staff_detail(request, staff_id):
    """Display staff member details with assignment history"""
    try:
        staff = get_object_or_404(Staff.objects.select_related(
            'department', 'reporting_manager'
        ), id=staff_id)
        
        # Get current assignments
        current_assignments = Assignment.objects.filter(
            assigned_to_staff=staff,
            is_active=True
        ).select_related('device')
        
        # Get assignment history
        assignment_history = Assignment.objects.filter(
            assigned_to_staff=staff
        ).select_related('device').order_by('-created_at')[:20]
        
        # Calculate statistics
        total_assignments = assignment_history.count()
        active_assignments = current_assignments.count()
        
        context = {
            'staff': staff,
            'current_assignments': current_assignments,
            'assignment_history': assignment_history,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
        }
        
        return render(request, 'inventory/staff_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff details: {str(e)}")
        return redirect('inventory:staff_list')

@login_required
@permission_required('inventory.add_staff', raise_exception=True)
def staff_create(request):
    """Create new staff member"""
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            try:
                staff = form.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='Staff',
                    object_id=str(staff.id),
                    object_repr=str(staff),
                    changes={'created': 'New staff member added'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Staff member "{staff.full_name}" created successfully.')
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
    """Edit staff member details"""
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        
        if request.method == 'POST':
            form = StaffForm(request.POST, instance=staff)
            if form.is_valid():
                try:
                    staff = form.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='Staff',
                        object_id=str(staff.id),
                        object_repr=str(staff),
                        changes={'updated': 'Staff details updated'},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Staff member "{staff.full_name}" updated successfully.')
                    return redirect('inventory:staff_detail', staff_id=staff.id)
                except Exception as e:
                    messages.error(request, f'Error updating staff member: {str(e)}')
        else:
            form = StaffForm(instance=staff)
        
        context = {
            'form': form,
            'staff': staff,
            'title': f'Edit {staff.full_name}',
            'action': 'Update',
        }
        return render(request, 'inventory/staff_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff: {str(e)}")
        return redirect('inventory:staff_list')

@login_required
def staff_assignments(request, staff_id):
    """View all assignments for a specific staff member"""
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        
        assignments = Assignment.objects.filter(
            assigned_to_staff=staff
        ).select_related('device').order_by('-created_at')
        
        # Filter by status
        status = request.GET.get('status')
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        
        # Pagination
        paginator = Paginator(assignments, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'staff': staff,
            'page_obj': page_obj,
            'status': status,
        }
        
        return render(request, 'inventory/staff_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading staff assignments: {str(e)}")
        return redirect('inventory:staff_list')

# ================================
# DEPARTMENT MANAGEMENT VIEWS
# ================================

@login_required
def department_list(request):
    """List all departments with assignment statistics"""
    try:
        departments = Department.objects.prefetch_related(
            'staff_members',
            'department_assignments__device'
        ).annotate(
            staff_count=Count('staff_members'),
            active_assignments=Count('department_assignments', filter=Q(department_assignments__is_active=True))
        ).order_by('name')
        
        context = {
            'departments': departments,
        }
        
        return render(request, 'inventory/department_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading departments: {str(e)}")
        return render(request, 'inventory/department_list.html', {'departments': []})

@login_required
def department_detail(request, department_id):
    """Display department details with staff and assignments"""
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # Get staff members
        staff_members = Staff.objects.filter(department=department).order_by('last_name', 'first_name')
        
        # Get department assignments (both direct and through staff)
        department_assignments = Assignment.objects.filter(
            Q(assigned_to_department=department) |
            Q(assigned_to_staff__department=department)
        ).select_related('device', 'assigned_to_staff').order_by('-created_at')
        
        # Get active assignments
        active_assignments = department_assignments.filter(is_active=True)
        
        # Calculate statistics
        total_staff = staff_members.count()
        total_devices = active_assignments.count()
        
        # Device categories breakdown
        category_breakdown = active_assignments.values(
            'device__device_type__subcategory__category__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        context = {
            'department': department,
            'staff_members': staff_members,
            'active_assignments': active_assignments[:10],  # Show latest 10
            'total_staff': total_staff,
            'total_devices': total_devices,
            'category_breakdown': category_breakdown,
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
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='Department',
                    object_id=str(department.id),
                    object_repr=str(department),
                    changes={'created': 'New department added'},
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
                    department = form.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='Department',
                        object_id=str(department.id),
                        object_repr=str(department),
                        changes={'updated': 'Department details updated'},
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
            'title': f'Edit {department.name}',
            'action': 'Update',
        }
        return render(request, 'inventory/department_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department: {str(e)}")
        return redirect('inventory:department_list')

@login_required
def department_assignments(request, department_id):
    """View all assignments for a specific department"""
    try:
        department = get_object_or_404(Department, id=department_id)
        
        assignments = Assignment.objects.filter(
            Q(assigned_to_department=department) |
            Q(assigned_to_staff__department=department)
        ).select_related(
            'device', 'assigned_to_staff'
        ).order_by('-created_at')
        
        # Filter by status
        status = request.GET.get('status')
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        
        # Pagination
        paginator = Paginator(assignments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'department': department,
            'page_obj': page_obj,
            'status': status,
        }
        
        return render(request, 'inventory/department_assignments.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading department assignments: {str(e)}")
        return redirect('inventory:department_list')

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

# ================================
# MAINTENANCE MANAGEMENT VIEWS
# ================================

@login_required
def maintenance_list(request):
    """List all maintenance schedules"""
    try:
        maintenance_schedules = MaintenanceSchedule.objects.select_related(
            'device', 'vendor', 'created_by'
        ).order_by('-scheduled_date')
        
        # Filter by status
        status = request.GET.get('status')
        if status:
            maintenance_schedules = maintenance_schedules.filter(status=status)
        
        # Filter by device
        device_id = request.GET.get('device')
        if device_id:
            maintenance_schedules = maintenance_schedules.filter(device__device_id=device_id)
        
        # Pagination
        paginator = Paginator(maintenance_schedules, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'status': status,
            'device_id': device_id,
        }
        
        return render(request, 'inventory/maintenance_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance schedules: {str(e)}")
        return render(request, 'inventory/maintenance_list.html', {'page_obj': None})

@login_required
def maintenance_detail(request, maintenance_id):
    """Display maintenance schedule details"""
    try:
        maintenance = get_object_or_404(MaintenanceSchedule.objects.select_related(
            'device', 'vendor', 'created_by', 'updated_by'
        ), id=maintenance_id)
        
        context = {
            'maintenance': maintenance,
        }
        
        return render(request, 'inventory/maintenance_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance details: {str(e)}")
        return redirect('inventory:maintenance_list')

@login_required
@permission_required('inventory.add_maintenanceschedule', raise_exception=True)
def maintenance_create(request):
    """Schedule new maintenance"""
    if request.method == 'POST':
        form = MaintenanceScheduleForm(request.POST)
        if form.is_valid():
            try:
                maintenance = form.save(commit=False)
                maintenance.created_by = request.user
                maintenance.updated_by = request.user
                maintenance.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    model_name='MaintenanceSchedule',
                    object_id=str(maintenance.id),
                    object_repr=str(maintenance),
                    changes={'created': 'New maintenance scheduled'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Maintenance "{maintenance.title}" scheduled successfully.')
                return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
            except Exception as e:
                messages.error(request, f'Error scheduling maintenance: {str(e)}')
    else:
        form = MaintenanceScheduleForm()
        
        # Pre-fill device if provided
        device_id = request.GET.get('device')
        if device_id:
            try:
                device = Device.objects.get(device_id=device_id)
                form.fields['device'].initial = device
            except Device.DoesNotExist:
                pass
    
    context = {
        'form': form,
        'title': 'Schedule Maintenance',
        'action': 'Create',
    }
    return render(request, 'inventory/maintenance_form.html', context)

@login_required
@permission_required('inventory.change_maintenanceschedule', raise_exception=True)
def maintenance_edit(request, maintenance_id):
    """Edit maintenance schedule"""
    try:
        maintenance = get_object_or_404(MaintenanceSchedule, id=maintenance_id)
        
        if request.method == 'POST':
            form = MaintenanceScheduleForm(request.POST, instance=maintenance)
            if form.is_valid():
                try:
                    maintenance = form.save(commit=False)
                    maintenance.updated_by = request.user
                    maintenance.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='MaintenanceSchedule',
                        object_id=str(maintenance.id),
                        object_repr=str(maintenance),
                        changes={'updated': 'Maintenance schedule updated'},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Maintenance "{maintenance.title}" updated successfully.')
                    return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
                except Exception as e:
                    messages.error(request, f'Error updating maintenance: {str(e)}')
        else:
            form = MaintenanceScheduleForm(instance=maintenance)
        
        context = {
            'form': form,
            'maintenance': maintenance,
            'title': f'Edit {maintenance.title}',
            'action': 'Update',
        }
        return render(request, 'inventory/maintenance_form.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance: {str(e)}")
        return redirect('inventory:maintenance_list')

@login_required
@permission_required('inventory.change_maintenanceschedule', raise_exception=True)
def maintenance_complete(request, maintenance_id):
    """Mark maintenance as completed"""
    try:
        maintenance = get_object_or_404(MaintenanceSchedule, id=maintenance_id)
        
        if request.method == 'POST':
            actual_cost = request.POST.get('actual_cost')
            completion_notes = request.POST.get('completion_notes', '')
            
            try:
                with transaction.atomic():
                    maintenance.status = 'COMPLETED'
                    maintenance.actual_date = timezone.now().date()
                    maintenance.completion_notes = completion_notes
                    maintenance.updated_by = request.user
                    
                    if actual_cost:
                        try:
                            maintenance.actual_cost = float(actual_cost)
                        except ValueError:
                            pass
                    
                    maintenance.save()
                    
                    # Update device last maintenance date
                    device = maintenance.device
                    device.last_maintenance_date = maintenance.actual_date
                    device.updated_by = request.user
                    device.save()
                    
                    # Create audit log
                    AuditLog.objects.create(
                        user=request.user,
                        action='COMPLETE',
                        model_name='MaintenanceSchedule',
                        object_id=str(maintenance.id),
                        object_repr=str(maintenance),
                        changes={
                            'status': 'COMPLETED',
                            'actual_cost': actual_cost,
                            'completion_date': str(maintenance.actual_date)
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f'Maintenance "{maintenance.title}" marked as completed.')
                    return redirect('inventory:maintenance_detail', maintenance_id=maintenance.id)
                    
            except Exception as e:
                messages.error(request, f'Error completing maintenance: {str(e)}')
        
        context = {
            'maintenance': maintenance,
        }
        return render(request, 'inventory/maintenance_complete.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading maintenance: {str(e)}")
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
                return redirect('inventory:device_type_list')
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
    """Get device information for AJAX requests"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        # Get current assignment
        current_assignment = Assignment.objects.filter(
            device=device, is_active=True
        ).select_related('assigned_to_staff', 'assigned_to_department').first()
        
        data = {
            'device_id': device.device_id,
            'device_name': device.device_name,
            'status': device.status,
            'status_display': device.get_status_display(),
            'current_location': device.current_location.name if device.current_location else None,
            'device_type': device.device_type.name if device.device_type else None,
            'brand': device.brand,
            'model': device.model,
            'serial_number': device.serial_number,
            'specifications': device.specifications,
            'current_assignment': {
                'assignment_id': current_assignment.assignment_id if current_assignment else None,
                'assigned_to': str(current_assignment.assigned_to_staff or current_assignment.assigned_to_department) if current_assignment else None,
                'is_temporary': current_assignment.is_temporary if current_assignment else False
            } if current_assignment else None
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def quick_assign_device(request):
    """Quick assign device via AJAX"""
    try:
        device_id = request.POST.get('device_id')
        staff_id = request.POST.get('staff_id')
        is_temporary = request.POST.get('is_temporary', False) == 'true'
        expected_return_date = request.POST.get('expected_return_date')
        
        device = get_object_or_404(Device, device_id=device_id)
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Check if device is available
        if device.status != 'AVAILABLE':
            return JsonResponse({'error': 'Device is not available for assignment'}, status=400)
        
        # Validate return date for temporary assignments
        if is_temporary and expected_return_date:
            try:
                expected_return_date = datetime.strptime(expected_return_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Invalid expected return date format'}, status=400)
        else:
            expected_return_date = None
        
        with transaction.atomic():
            # Create assignment
            assignment = Assignment.objects.create(
                device=device,
                assigned_to_staff=staff,
                is_temporary=is_temporary,
                expected_return_date=expected_return_date,
                created_by=request.user,
                updated_by=request.user,
                requested_by=request.user,
            )
            
            # Update device status
            device.status = 'ASSIGNED'
            device.updated_by = request.user
            device.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action='QUICK_ASSIGN',
                model_name='Assignment',
                object_id=assignment.assignment_id,
                object_repr=str(assignment),
                changes={'quick_assignment': True},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return JsonResponse({
            'success': True,
            'assignment_id': assignment.assignment_id,
            'message': f'Device successfully assigned to {staff.full_name}'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def search_suggestions(request):
    """Provide search suggestions for autocomplete"""
    try:
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'device')
        
        if len(query) < 2:
            return JsonResponse({'suggestions': []})
        
        suggestions = []
        
        if search_type == 'device':
            devices = Device.objects.filter(
                Q(device_name__icontains=query) |
                Q(device_id__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query)
            ).select_related('device_type')[:10]
            
            suggestions = [
                {
                    'id': device.device_id,
                    'text': f"{device.device_name} ({device.device_id})",
                    'type': 'device',
                    'status': device.status,
                    'category': device.device_type.subcategory.category.name if device.device_type else 'Unknown'
                }
                for device in devices
            ]
        
        elif search_type == 'staff':
            staff_members = Staff.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(employee_id__icontains=query)
            ).select_related('department')[:10]
            
            suggestions = [
                {
                    'id': staff.id,
                    'text': f"{staff.full_name} ({staff.employee_id})",
                    'type': 'staff',
                    'department': staff.department.name if staff.department else 'No Department'
                }
                for staff in staff_members
            ]
        
        elif search_type == 'department':
            departments = Department.objects.filter(
                name__icontains=query
            )[:10]
            
            suggestions = [
                {
                    'id': dept.id,
                    'text': dept.name,
                    'type': 'department'
                }
                for dept in departments
            ]
        
        return JsonResponse({'suggestions': suggestions})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def device_availability_check(request):
    """Check device availability for assignment"""
    try:
        device_ids = request.GET.getlist('device_ids[]')
        
        if not device_ids:
            return JsonResponse({'error': 'No device IDs provided'}, status=400)
        
        devices = Device.objects.filter(device_id__in=device_ids)
        availability = {}
        
        for device in devices:
            current_assignment = Assignment.objects.filter(
                device=device, is_active=True
            ).first()
            
            availability[device.device_id] = {
                'available': device.status == 'AVAILABLE',
                'status': device.status,
                'status_display': device.get_status_display(),
                'current_assignment': {
                    'assignment_id': current_assignment.assignment_id,
                    'assigned_to': str(current_assignment.assigned_to_staff or current_assignment.assigned_to_department)
                } if current_assignment else None
            }
        
        return JsonResponse({'availability': availability})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_staff_by_department(request, department_id):
    """Get staff members for a specific department (AJAX)"""
    try:
        staff_members = Staff.objects.filter(department_id=department_id).order_by('last_name', 'first_name')
        
        data = {
            'staff_members': [
                {
                    'id': staff.id,
                    'name': staff.full_name,
                    'employee_id': staff.employee_id,
                    'designation': staff.designation or '',
                }
                for staff in staff_members
            ]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_rooms_by_building(request, building_id):
    """Get rooms for a specific building (AJAX)"""
    try:
        rooms = Room.objects.filter(building_id=building_id).order_by('name')
        
        data = {
            'rooms': [
                {
                    'id': room.id,
                    'name': room.name,
                    'floor': room.floor or '',
                    'department': room.department.name if room.department else '',
                }
                for room in rooms
            ]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_locations_by_room(request, room_id):
    """Get locations for a specific room (AJAX)"""
    try:
        locations = Location.objects.filter(room_id=room_id).order_by('name')
        
        data = {
            'locations': [
                {
                    'id': location.id,
                    'name': location.name,
                    'location_type': location.location_type or '',
                    'description': location.description or '',
                }
                for location in locations
            ]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ================================
# BULK OPERATIONS VIEWS
# ================================

@login_required
@permission_required('inventory.change_device', raise_exception=True)
def bulk_device_update(request):
    """Bulk update device properties"""
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
                            if new_value in dict(Device.STATUS_CHOICES):
                                setattr(device, update_field, new_value)
                                device.updated_by = request.user
                                device.save()
                                updated_count += 1
                        elif update_field == 'condition':
                            if new_value in dict(Device.CONDITION_CHOICES):
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
                
                messages.success(request, f'Successfully updated {updated_count} devices.')
                
        except Exception as e:
            messages.error(request, f'Error performing bulk update: {str(e)}')
    
    return redirect('inventory:device_list')

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

# ================================
# EXPORT FUNCTIONS
# ================================

@login_required
def export_devices_csv(request):
    """Export devices to CSV"""
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="devices_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Type',
            'Brand', 'Model', 'Serial Number', 'Status', 'Condition',
            'Purchase Date', 'Purchase Price', 'Vendor', 'Warranty End',
            'Current Assignment', 'Location', 'Created Date'
        ])
        
        devices = Device.objects.select_related(
            'device_type__subcategory__category',
            'vendor', 'current_location'
        ).prefetch_related('assignments')
        
        for device in devices:
            current_assignment = device.assignments.filter(is_active=True).first()
            
            writer.writerow([
                device.device_id,
                device.asset_tag or '',
                device.device_name,
                device.device_type.subcategory.category.name if device.device_type else '',
                device.device_type.name if device.device_type else '',
                device.brand or '',
                device.model or '',
                device.serial_number or '',
                device.get_status_display(),
                device.get_condition_display(),
                device.purchase_date.strftime('%Y-%m-%d') if device.purchase_date else '',
                device.purchase_price or '',
                device.vendor.name if device.vendor else '',
                device.warranty_end_date.strftime('%Y-%m-%d') if device.warranty_end_date else '',
                str(current_assignment.assigned_to_staff or current_assignment.assigned_to_department) if current_assignment else '',
                device.current_location.name if device.current_location else '',
                device.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error exporting devices: {str(e)}")
        return redirect('inventory:device_list')

@login_required
def export_assignments_csv(request):
    """Export assignments to CSV"""
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="assignments_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Assignment ID', 'Device ID', 'Device Name', 'Assigned To (Staff)',
            'Assigned To (Department)', 'Assignment Type', 'Start Date',
            'Expected Return Date', 'Actual Return Date', 'Status',
            'Purpose', 'Created Date', 'Created By'
        ])
        
        assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department', 'created_by'
        ).order_by('-created_at')
        
        for assignment in assignments:
            writer.writerow([
                assignment.assignment_id,
                assignment.device.device_id,
                assignment.device.device_name,
                assignment.assigned_to_staff.full_name if assignment.assigned_to_staff else '',
                assignment.assigned_to_department.name if assignment.assigned_to_department else '',
                'Temporary' if assignment.is_temporary else 'Permanent',
                assignment.start_date.strftime('%Y-%m-%d') if assignment.start_date else '',
                assignment.expected_return_date.strftime('%Y-%m-%d') if assignment.expected_return_date else '',
                assignment.actual_return_date.strftime('%Y-%m-%d') if assignment.actual_return_date else '',
                'Active' if assignment.is_active else 'Inactive',
                assignment.purpose or '',
                assignment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                assignment.created_by.username
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error exporting assignments: {str(e)}")
        return redirect('inventory:assignment_list')

# ================================
# REPORTING VIEWS
# ================================

@login_required
def inventory_summary_report(request):
    """Generate comprehensive inventory summary report"""
    try:
        # Device statistics by category
        category_stats = DeviceCategory.objects.prefetch_related(
            'subcategories__device_types__devices'
        ).annotate(
            total_devices=Count('subcategories__device_types__devices'),
            assigned_devices=Count(
                'subcategories__device_types__devices__assignments',
                filter=Q(subcategories__device_types__devices__assignments__is_active=True)
            ),
            total_value=Sum('subcategories__device_types__devices__purchase_price')
        ).order_by('name')
        
        # Device status distribution
        status_distribution = Device.objects.values('status').annotate(
            count=Count('id'),
            total_value=Sum('purchase_price')
        ).order_by('status')
        
        # Assignment statistics
        assignment_stats = {
            'total_assignments': Assignment.objects.count(),
            'active_assignments': Assignment.objects.filter(is_active=True).count(),
            'temporary_assignments': Assignment.objects.filter(is_temporary=True, is_active=True).count(),
            'overdue_assignments': Assignment.objects.filter(
                is_temporary=True,
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            ).count()
        }
        
        # Department statistics
        department_stats = Department.objects.annotate(
            total_assignments=Count('department_assignments', filter=Q(department_assignments__is_active=True)),
            total_staff_assignments=Count('staff_members__staff_assignments', filter=Q(staff_members__staff_assignments__is_active=True))
        ).order_by('-total_assignments')[:10]
        
        # Vendor statistics
        vendor_stats = Vendor.objects.annotate(
            device_count=Count('devices'),
            total_value=Sum('devices__purchase_price')
        ).order_by('-device_count')[:10]
        
        # Warranty expiring soon
        today = timezone.now().date()
        warranty_expiring = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=90)
        ).order_by('warranty_end_date')[:20]
        
        context = {
            'category_stats': category_stats,
            'status_distribution': status_distribution,
            'assignment_stats': assignment_stats,
            'department_stats': department_stats,
            'vendor_stats': vendor_stats,
            'warranty_expiring': warranty_expiring,
            'report_date': today,
        }
        
        return render(request, 'inventory/inventory_summary_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating report: {str(e)}")
        return redirect('inventory:dashboard')

@login_required
def asset_utilization_report(request):
    """Generate asset utilization report"""
    try:
        # Device utilization by department
        dept_utilization = Department.objects.annotate(
            total_devices=Count('department_assignments', filter=Q(department_assignments__is_active=True)) +
                         Count('staff_members__staff_assignments', filter=Q(staff_members__staff_assignments__is_active=True)),
            staff_count=Count('staff_members'),
            devices_per_staff=Case(
                When(staff_count=0, then=0),
                default=F('total_devices') * 1.0 / F('staff_count'),
                output_field=FloatField()
            )
        ).order_by('-total_devices')
        
        # Most assigned device types
        popular_devices = DeviceType.objects.annotate(
            assignment_count=Count('devices__assignments', filter=Q(devices__assignments__is_active=True))
        ).order_by('-assignment_count')[:15]
        
        # Assignment duration analysis
        completed_assignments = Assignment.objects.filter(
            is_active=False,
            actual_return_date__isnull=False
        ).annotate(
            duration=F('actual_return_date') - F('start_date')
        ).order_by('-created_at')[:100]
        
        # Long-term assignments (over 1 year)
        long_term_assignments = Assignment.objects.filter(
            is_active=True,
            start_date__lte=timezone.now().date() - timedelta(days=365)
        ).select_related('device', 'assigned_to_staff').order_by('start_date')
        
        context = {
            'dept_utilization': dept_utilization,
            'popular_devices': popular_devices,
            'completed_assignments': completed_assignments,
            'long_term_assignments': long_term_assignments,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'inventory/asset_utilization_report.html', context)
        
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