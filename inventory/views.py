# inventory/views.py - COMPLETE VERSION WITH ALL FUNCTIONS

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg, Max, Min, F, Case, When
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
    DeviceCategory, DeviceType, DeviceSubcategory, Vendor,
    MaintenanceSchedule, AuditLog, Room, Building
)
from .forms import (
    DeviceForm, AssignmentForm, StaffForm, DepartmentForm, 
    LocationForm, DeviceSearchForm, AssignmentSearchForm,
    BulkAssignmentForm, MaintenanceForm, TransferForm,
    ReturnForm, VendorForm, DeviceTypeForm
)

# FIXED: Import with comprehensive error handling
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
            'maintenance_schedules',
            'qr_scans'
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
        
        # Get recent QR scans
        recent_scans = device.qr_scans.select_related(
            'scanned_by', 'scan_location'
        ).order_by('-timestamp')[:5]
        
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
        form = MaintenanceForm(request.POST)
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
        form = MaintenanceForm()
        
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
        return redirect('inventory:assignment_list'))
def assignment_transfer(request, assignment_id):
    """Transfer assignment to another staff/department"""
    try:
        assignment = get_object_or_404(Assignment, assignment_id=assignment_id, is_active=True)
        
        if request.method == 'POST':
            form = TransferForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Create new assignment
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
            form = TransferForm()
        
        context = {
            'form': form,
            'assignment': assignment,
            'title': f'Transfer Assignment {assignment.assignment_id}',
        }
        return render(request, 'inventory/assignment_transfer.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading assignment: {str(e)}")
        return redirect('inventory:assignment_list')