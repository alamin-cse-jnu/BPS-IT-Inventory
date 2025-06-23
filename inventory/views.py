from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, Value, CharField, Prefetch
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
from datetime import date, timedelta
import json
import csv

from .models import (
    Device, DeviceCategory, DeviceSubCategory, DeviceType, 
    Vendor, Assignment, Staff, Department, Location, Room,
    MaintenanceSchedule, AuditLog, AssignmentHistory
)
from .forms import DeviceForm, DeviceSearchForm, AssignmentForm, BulkAssignmentForm
from .utils import get_device_assignment_summary, get_warranty_alerts, get_overdue_assignments

@login_required
def device_list(request):
    """Main device listing page with search and filters"""
    devices = Device.objects.select_related(
        'device_type__subcategory__category', 'vendor'
    ).prefetch_related('assignments')
    
    # Search functionality
    search_form = DeviceSearchForm(request.GET)
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        category = search_form.cleaned_data.get('category')
        status = search_form.cleaned_data.get('status')
        assigned_department = search_form.cleaned_data.get('assigned_department')
        
        if query:
            devices = devices.filter(
                Q(device_id__icontains=query) |
                Q(device_name__icontains=query) |
                Q(asset_tag__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query) |
                Q(serial_number__icontains=query)
            )
        
        if category:
            devices = devices.filter(device_type__subcategory__category=category)
        
        if status:
            devices = devices.filter(status=status)
        
        if assigned_department:
            devices = devices.filter(
                assignments__assigned_to_department=assigned_department,
                assignments__is_active=True
            )
    
    # Annotations for display
    devices = devices.annotate(
        assignment_status=Case(
            When(assignments__is_active=True, then=Value('assigned')),
            default=Value('available'),
            output_field=CharField()
        )
    )
    
    # Pagination
    paginator = Paginator(devices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    summary = get_device_assignment_summary()
    warranty_alerts = get_warranty_alerts()
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'summary': summary,
        'warranty_alerts': warranty_alerts[:5],
        'total_devices': devices.count(),
    }
    
    return render(request, 'inventory/device_list.html', context)

@login_required
def device_detail(request, device_id):
    """Detailed view of a single device"""
    device = get_object_or_404(
        Device.objects.select_related(
            'device_type__subcategory__category', 'vendor', 'created_by', 'updated_by'
        ).prefetch_related(
            'assignments__assigned_to_staff',
            'assignments__assigned_to_department', 
            'assignments__assigned_to_location',
            'maintenance_schedules',
            'qr_scans'
        ), 
        device_id=device_id
    )
    
    current_assignment = device.assignments.filter(is_active=True).first()
    assignment_history = device.assignments.select_related(
        'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
    ).order_by('-created_at')[:10]
    maintenance_history = device.maintenance_schedules.select_related(
        'vendor', 'created_by'
    ).order_by('-scheduled_date')[:5]
    recent_scans = device.qr_scans.select_related(
        'scanned_by', 'scan_location'
    ).order_by('-timestamp')[:5]
    
    context = {
        'device': device,
        'current_assignment': current_assignment,
        'assignment_history': assignment_history,
        'maintenance_history': maintenance_history,
        'recent_scans': recent_scans,
        'is_warranty_expiring': device.warranty_expires_soon,
    }
    
    return render(request, 'inventory/device_detail.html', context)

@login_required
def device_add(request):
    """Add new device"""
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.created_by = request.user
            device.updated_by = request.user
            device.save()
            
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                model_name='Device',
                object_id=device.device_id,
                object_repr=str(device),
                changes={'created': 'New device added'}
            )
            
            messages.success(request, f'Device {device.device_id} added successfully.')
            return redirect('inventory:device_detail', device_id=device.device_id)
    else:
        form = DeviceForm()
    
    context = {
        'form': form,
        'title': 'Add New Device',
        'submit_text': 'Add Device'
    }
    
    return render(request, 'inventory/device_form.html', context)

@login_required
def device_edit(request, device_id):
    """Edit existing device"""
    device = get_object_or_404(Device, device_id=device_id)
    
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device)
        if form.is_valid():
            changes = {}
            for field in form.changed_data:
                old_value = getattr(device, field)
                new_value = form.cleaned_data[field]
                changes[field] = {'old': str(old_value), 'new': str(new_value)}
            
            device = form.save(commit=False)
            device.updated_by = request.user
            device.save()
            
            if changes:
                AuditLog.objects.create(
                    user=request.user,
                    action='UPDATE',
                    model_name='Device',
                    object_id=device.device_id,
                    object_repr=str(device),
                    changes=changes
                )
            
            messages.success(request, f'Device {device.device_id} updated successfully.')
            return redirect('inventory:device_detail', device_id=device.device_id)
    else:
        form = DeviceForm(instance=device)
    
    context = {
        'form': form,
        'device': device,
        'title': f'Edit Device {device.device_id}',
        'submit_text': 'Update Device'
    }
    
    return render(request, 'inventory/device_form.html', context)

@login_required
@require_http_methods(["DELETE"])
def device_delete(request, device_id):
    """Delete device (soft delete by changing status)"""
    device = get_object_or_404(Device, device_id=device_id)
    
    if device.assignments.filter(is_active=True).exists():
        return JsonResponse({
            'success': False,
            'message': 'Cannot delete device with active assignments.'
        }, status=400)
    
    device.status = 'RETIRED'
    device.retirement_date = timezone.now().date()
    device.updated_by = request.user
    device.save()
    
    AuditLog.objects.create(
        user=request.user,
        action='DELETE',
        model_name='Device',
        object_id=device.device_id,
        object_repr=str(device),
        changes={'status': 'RETIRED', 'retirement_date': str(device.retirement_date)}
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Device {device.device_id} retired successfully.'
    })

@login_required
def device_bulk_actions(request):
    """Handle bulk actions on multiple devices"""
    if request.method == 'POST':
        action = request.POST.get('action')
        device_ids = request.POST.getlist('device_ids')
        
        if not device_ids:
            messages.error(request, 'No devices selected.')
            return redirect('inventory:device_list')
        
        devices = Device.objects.filter(device_id__in=device_ids)
        
        if action == 'bulk_assign':
            return redirect('inventory:bulk_assignment', device_ids=','.join(device_ids))
        
        elif action == 'export_selected':
            return device_export_csv(request, devices)
        
        elif action == 'bulk_status_change':
            new_status = request.POST.get('new_status')
            if new_status:
                updated_count = devices.update(
                    status=new_status,
                    updated_by=request.user
                )
                messages.success(request, f'Updated status for {updated_count} devices.')
        
    return redirect('inventory:device_list')

@login_required
def device_dashboard(request):
    """Main dashboard with overview statistics"""
    summary = get_device_assignment_summary()
    category_stats = DeviceCategory.objects.annotate(
        device_count=Count('subcategories__device_types__devices'),
        assigned_count=Count(
            'subcategories__device_types__devices',
            filter=Q(subcategories__device_types__devices__status='ASSIGNED')
        )
    ).filter(device_count__gt=0)
    
    recent_assignments = Assignment.objects.select_related(
        'device', 'assigned_to_staff', 'assigned_to_department'
    ).order_by('-created_at')[:10]
    
    recent_maintenance = MaintenanceSchedule.objects.select_related(
        'device'
    ).order_by('-created_at')[:5]
    
    warranty_alerts = get_warranty_alerts()
    
    status_distribution = Device.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    context = {
        'summary': summary,
        'category_stats': category_stats,
        'recent_assignments': recent_assignments,
        'recent_maintenance': recent_maintenance,
        'warranty_alerts': warranty_alerts[:10],
        'status_distribution': status_distribution,
    }
    
    return render(request, 'inventory/dashboard.html', context)

@login_required
def device_export_csv(request, devices=None):
    """Export devices to CSV"""
    if devices is None:
        devices = Device.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="devices_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Brand', 'Model',
        'Serial Number', 'Status', 'Assigned To', 'Location', 'Purchase Date',
        'Warranty End Date'
    ])
    
    for device in devices.select_related(
        'device_type__subcategory__category'
    ).prefetch_related('assignments'):
        current_assignment = device.assignments.filter(is_active=True).first()
        assigned_to = ''
        location = ''
        
        if current_assignment:
            if current_assignment.assigned_to_staff:
                assigned_to = current_assignment.assigned_to_staff.full_name
            elif current_assignment.assigned_to_department:
                assigned_to = current_assignment.assigned_to_department.name
            
            if current_assignment.assigned_to_location:
                location = str(current_assignment.assigned_to_location)
        
        writer.writerow([
            device.device_id,
            device.asset_tag,
            device.device_name,
            device.device_type.subcategory.category.name,
            device.brand,
            device.model,
            device.serial_number,
            device.get_status_display(),
            assigned_to,
            location,
            device.purchase_date,
            device.warranty_end_date
        ])
    
    return response

@login_required
def assignment_list(request):
    """List all assignments with filtering"""
    assignments = Assignment.objects.select_related(
        'device', 'assigned_to_staff', 'assigned_to_department', 
        'assigned_to_location', 'created_by'
    ).order_by('-created_at')
    
    # Filters
    assignment_type = request.GET.get('assignment_type')
    status_filter = request.GET.get('status')
    department_filter = request.GET.get('department')
    staff_filter = request.GET.get('staff')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')  # Corrected variable name
    
    if assignment_type:
        assignments = assignments.filter(assignment_type=assignment_type)
    
    if status_filter == 'active':
        assignments = assignments.filter(is_active=True)
    elif status_filter == 'inactive':
        assignments = assignments.filter(is_active=False)
    elif status_filter == 'overdue':
        assignments = assignments.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=date.today(),
            actual_return_date__isnull=True
        )
    
    if department_filter:
        assignments = assignments.filter(assigned_to_department_id=department_filter)
    
    if staff_filter:
        assignments = assignments.filter(assigned_to_staff_id=staff_filter)
    
    if date_from:
        assignments = assignments.filter(start_date__gte=date_from)
    
    if date_to:  # Corrected from Sdate_to to date_to
        assignments = assignments.filter(start_date__lte=date_to)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        assignments = assignments.filter(
            Q(assignment_id__icontains=search_query) |
            Q(device__device_id__icontains=search_query) |
            Q(device__device_name__icontains=search_query) |
            Q(assigned_to_staff__full_name__icontains=search_query) |
            Q(assigned_to_department__name__icontains=search_query) |
            Q(purpose__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_assignments = Assignment.objects.filter(is_active=True).count()
    overdue_assignments = get_overdue_assignments().count()
    temp_assignments = Assignment.objects.filter(
        is_temporary=True, is_active=True
    ).count()
    
    context = {
        'page_obj': page_obj,
        'departments': Department.objects.all(),
        'staff_members': Staff.objects.filter(is_active=True),
        'assignment_types': Assignment.ASSIGNMENT_TYPES,
        'total_assignments': total_assignments,
        'overdue_assignments': overdue_assignments,
        'temp_assignments': temp_assignments,
        'filters': {
            'assignment_type': assignment_type,
            'status': status_filter,
            'department': department_filter,
            'staff': staff_filter,
            'date_from': date_from,
            'date_to': date_to,
            'search': search_query,
        }
    }
    
    return render(request, 'inventory/assignment_list.html', context)

@login_required
def assignment_detail(request, assignment_id):
    """Detailed view of a single assignment"""
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department',
            'assigned_to_location', 'created_by', 'updated_by',
            'requested_by', 'approved_by'
        ),
        assignment_id=assignment_id
    )
    
    history = AssignmentHistory.objects.filter(assignment=assignment).select_related(
        'changed_by', 'new_staff', 'new_department', 'new_location'
    ).order_by('-changed_at')
    
    context = {
        'assignment': assignment,
        'history': history,
        'is_overdue': assignment.is_overdue,
    }
    
    return render(request, 'inventory/assignment_detail.html', context)

@login_required
def assignment_create(request, device_id=None):
    """Create new assignment"""
    device = None
    if device_id:
        device = get_object_or_404(Device, device_id=device_id)
        
        if device.assignments.filter(is_active=True).exists():
            messages.error(request, f'Device {device.device_id} is already assigned.')
            return redirect('inventory:device_detail', device_id=device.device_id)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, device=device)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user
            assignment.updated_by = request.user
            assignment.requested_by = request.user
            assignment.save()
            
            assignment.device.status = 'ASSIGNED'
            assignment.device.save()
            
            AssignmentHistory.objects.create(
                device=assignment.device,
                assignment=assignment,
                action='ASSIGNED',
                new_staff=assignment.assigned_to_staff,
                new_department=assignment.assigned_to_department,
                new_location=assignment.assigned_to_location,
                reason=f"New assignment: {assignment.assignment_type}",
                changed_by=request.user
            )
            
            AuditLog.objects.create(
                user=request.user,
                action='ASSIGN',
                model_name='Assignment',
                object_id=assignment.assignment_id,
                object_repr=str(assignment),
                changes={'device': assignment.device.device_id, 'type': assignment.assignment_type}
            )
            
            messages.success(request, f'Assignment {assignment.assignment_id} created successfully.')
            return redirect('inventory:assignment_detail', assignment_id=assignment.assignment_id)
    else:
        form = AssignmentForm(device=device)
    
    context = {
        'form': form,
        'device': device,
        'title': f'Assign Device {device.device_id}' if device else 'Create Assignment',
        'submit_text': 'Create Assignment'
    }
    
    return render(request, 'inventory/assignment_form.html', context)

@login_required
def assignment_transfer(request, assignment_id):
    """Transfer assignment to different staff/location"""
    assignment = get_object_or_404(Assignment, assignment_id=assignment_id)
    
    if not assignment.is_active:
        messages.error(request, 'Cannot transfer inactive assignment.')
        return redirect('inventory:assignment_detail', assignment_id=assignment_id)
    
    if request.method == 'POST':
        old_staff = assignment.assigned_to_staff
        old_department = assignment.assigned_to_department
        old_location = assignment.assigned_to_location
        
        new_staff_id = request.POST.get('new_staff')
        new_department_id = request.POST.get('new_department')
        new_location_id = request.POST.get('new_location')
        transfer_reason = request.POST.get('transfer_reason', '')
        
        if not any([new_staff_id, new_department_id, new_location_id]):
            messages.error(request, 'Please select at least one assignment target.')
            return redirect('inventory:assignment_transfer', assignment_id=assignment_id)
        
        if new_staff_id:
            assignment.assigned_to_staff = Staff.objects.get(id=new_staff_id)
        else:
            assignment.assigned_to_staff = None
            
        if new_department_id:
            assignment.assigned_to_department = Department.objects.get(id=new_department_id)
        else:
            assignment.assigned_to_department = None
            
        if new_location_id:
            assignment.assigned_to_location = Location.objects.get(id=new_location_id)
        else:
            assignment.assigned_to_location = None
        
        assignment.updated_by = request.user
        assignment.save()
        
        AssignmentHistory.objects.create(
            device=assignment.device,
            assignment=assignment,
            action='TRANSFERRED',
            previous_staff=old_staff,
            previous_department=old_department,
            previous_location=old_location,
            new_staff=assignment.assigned_to_staff,
            new_department=assignment.assigned_to_department,
            new_location=assignment.assigned_to_location,
            reason=transfer_reason,
            changed_by=request.user
        )
        
        AuditLog.objects.create(
            user=request.user,
            action='TRANSFER',
            model_name='Assignment',
            object_id=assignment.assignment_id,
            object_repr=str(assignment),
            changes={
                'from': str(old_staff or old_department or old_location),
                'to': str(assignment.assigned_to_staff or assignment.assigned_to_department or assignment.assigned_to_location),
                'reason': transfer_reason
            }
        )
        
        messages.success(request, f'Assignment {assignment.assignment_id} transferred successfully.')
        return redirect('inventory:assignment_detail', assignment_id=assignment_id)
    
    context = {
        'assignment': assignment,
        'staff_members': Staff.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'locations': Location.objects.filter(is_active=True),
    }
    
    return render(request, 'inventory/assignment_transfer.html', context)

@login_required
def assignment_return(request, assignment_id):
    """Return device from assignment"""
    assignment = get_object_or_404(Assignment, assignment_id=assignment_id)
    
    if not assignment.is_active:
        messages.error(request, 'Assignment is already inactive.')
        return redirect('inventory:assignment_detail', assignment_id=assignment_id)
    
    if request.method == 'POST':
        return_notes = request.POST.get('return_notes', '')
        device_condition = request.POST.get('device_condition', assignment.device.condition)
        
        assignment.is_active = False
        assignment.actual_return_date = timezone.now().date()
        assignment.updated_by = request.user
        assignment.save()
        
        assignment.device.status = 'AVAILABLE'
        assignment.device.condition = device_condition
        assignment.device.updated_by = request.user
        assignment.device.save()
        
        AssignmentHistory.objects.create(
            device=assignment.device,
            assignment=assignment,
            action='RETURNED',
            previous_staff=assignment.assigned_to_staff,
            previous_department=assignment.assigned_to_department,
            previous_location=assignment.assigned_to_location,
            reason=return_notes,
            changed_by=request.user
        )
        
        AuditLog.objects.create(
            user=request.user,
            action='RETURN',
            model_name='Assignment',
            object_id=assignment.assignment_id,
            object_repr=str(assignment),
            changes={
                'returned_from': str(assignment.assigned_to_staff or assignment.assigned_to_department or assignment.assigned_to_location),
                'condition': device_condition,
                'notes': return_notes
            }
        )
        
        messages.success(request, f'Device {assignment.device.device_id} returned successfully.')
        return redirect('inventory:assignment_detail', assignment_id=assignment_id)
    
    context = {
        'assignment': assignment,
        'device_conditions': Device.CONDITION_STATUS,
    }
    
    return render(request, 'inventory/assignment_return.html', context)

@login_required
def bulk_assignment(request):
    """Create bulk assignments for multiple devices"""
    device_ids = request.GET.get('device_ids', '').split(',')
    devices = Device.objects.filter(
        device_id__in=device_ids,
        status__in=['AVAILABLE', 'IN_USE']
    ).exclude(assignments__is_active=True)
    
    if not devices.exists():
        messages.error(request, 'No available devices selected for assignment.')
        return redirect('inventory:device_list')
    
    if request.method == 'POST':
        assignment_type = request.POST.get('assignment_type')
        assigned_to_staff_id = request.POST.get('assigned_to_staff')
        assigned_to_department_id = request.POST.get('assigned_to_department')
        assigned_to_location_id = request.POST.get('assigned_to_location')
        purpose = request.POST.get('purpose', '')
        is_temporary = request.POST.get('is_temporary') == 'on'
        expected_return_date = request.POST.get('expected_return_date')
        
        if not any([assigned_to_staff_id, assigned_to_department_id, assigned_to_location_id]):
            messages.error(request, 'Please select at least one assignment target.')
            return render(request, 'inventory/bulk_assignment.html', {
                'devices': devices,
                'staff_members': Staff.objects.filter(is_active=True),
                'departments': Department.objects.all(),
                'locations': Location.objects.filter(is_active=True),
                'assignment_types': Assignment.ASSIGNMENT_TYPES,
            })
        
        created_count = 0
        for device in devices:
            assignment = Assignment.objects.create(
                device=device,
                assignment_type=assignment_type,
                assigned_to_staff_id=assigned_to_staff_id if assigned_to_staff_id else None,
                assigned_to_department_id=assigned_to_department_id if assigned_to_department_id else None,
                assigned_to_location_id=assigned_to_location_id if assigned_to_location_id else None,
                purpose=purpose,
                is_temporary=is_temporary,
                expected_return_date=expected_return_date if expected_return_date else None,
                created_by=request.user,
                updated_by=request.user,
                requested_by=request.user
            )
            
            device.status = 'ASSIGNED'
            device.save()
            
            AssignmentHistory.objects.create(
                device=device,
                assignment=assignment,
                action='ASSIGNED',
                new_staff=assignment.assigned_to_staff,
                new_department=assignment.assigned_to_department,
                new_location=assignment.assigned_to_location,
                reason=f"Bulk assignment: {assignment_type}",
                changed_by=request.user
            )
            
            created_count += 1
        
        AuditLog.objects.create(
            user=request.user,
            action='ASSIGN',
            model_name='Assignment',
            object_id='BULK',
            object_repr=f'Bulk assignment of {created_count} devices',
            changes={
                'device_count': created_count,
                'assignment_type': assignment_type,
                'target': assigned_to_staff_id or assigned_to_department_id or assigned_to_location_id
            }
        )
        
        messages.success(request, f'Successfully created {created_count} assignments.')
        return redirect('inventory:assignment_list')
    
    context = {
        'devices': devices,
        'staff_members': Staff.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'locations': Location.objects.filter(is_active=True),
        'assignment_types': Assignment.ASSIGNMENT_TYPES,
    }
    
    return render(request, 'inventory/bulk_assignment.html', context)

@login_required
def overdue_assignments(request):
    """List overdue assignments"""
    overdue = get_overdue_assignments()
    
    context = {
        'assignments': overdue,
        'title': 'Overdue Assignments',
    }
    
    return render(request, 'inventory/overdue_assignments.html', context)

@login_required
def staff_assignments(request, staff_id):
    """View all assignments for a specific staff member"""
    staff = get_object_or_404(Staff, employee_id=staff_id)
    
    assignments = Assignment.objects.filter(
        assigned_to_staff=staff
    ).select_related('device').order_by('-created_at')
    
    active_assignments = assignments.filter(is_active=True)
    assignment_history = assignments.filter(is_active=False)
    
    context = {
        'staff': staff,
        'active_assignments': active_assignments,
        'assignment_history': assignment_history,
    }
    
    return render(request, 'inventory/staff_assignments.html', context)

@login_required
def department_assignments(request, department_id):
    """View all assignments for a specific department"""
    department = get_object_or_404(Department, id=department_id)
    
    assignments = Assignment.objects.filter(
        Q(assigned_to_department=department) |
        Q(assigned_to_staff__department=department)
    ).select_related('device', 'assigned_to_staff').order_by('-created_at')
    
    active_assignments = assignments.filter(is_active=True)
    assignment_history = assignments.filter(is_active=False)
    
    context = {
        'department': department,
        'active_assignments': active_assignments,
        'assignment_history': assignment_history,
    }
    
    return render(request, 'inventory/department_assignments.html', context)

@login_required
def ajax_get_subcategories(request):
    """Get subcategories for a given category"""
    category_id = request.GET.get('category_id')
    if category_id:
        subcategories = DeviceSubCategory.objects.filter(
            category_id=category_id, is_active=True
        ).values('id', 'name')
        return JsonResponse({'subcategories': list(subcategories)})
    return JsonResponse({'subcategories': []})

@login_required
def ajax_get_device_types(request):
    """Get device types for a given subcategory"""
    subcategory_id = request.GET.get('subcategory_id')
    if subcategory_id:
        device_types = DeviceType.objects.filter(
            subcategory_id=subcategory_id, is_active=True
        ).values('id', 'name')
        return JsonResponse({'device_types': list(device_types)})
    return JsonResponse({'device_types': []})

@login_required
def ajax_get_locations_by_room(request):
    """Get locations for a specific room"""
    room_id = request.GET.get('room_id')
    if room_id:
        locations = Location.objects.filter(
            room_id=room_id, is_active=True
        ).values('id', 'name', 'location_code')
        return JsonResponse({'locations': list(locations)})
    return JsonResponse({'locations': []})

@login_required
def ajax_device_quick_info(request, device_id):
    """Get quick device information for tooltips/modals"""
    try:
        device = Device.objects.select_related(
            'device_type', 'vendor'
        ).get(device_id=device_id)
        
        current_assignment = device.assignments.filter(is_active=True).first()
        
        data = {
            'device_id': device.device_id,
            'device_name': device.device_name,
            'status': device.get_status_display(),
            'brand': device.brand,
            'model': device.model,
            'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else 'Unassigned',
            'warranty_status': 'Active' if device.is_warranty_active else 'Expired'
        }
        
        return JsonResponse(data)
    except Device.DoesNotExist:
        return JsonResponse({'error': 'Device not found'}, status=404)

@login_required
@require_http_methods(["POST"])
def ajax_assignment_quick_actions(request, assignment_id):
    """Quick actions for assignments (AJAX)"""
    assignment = get_object_or_404(Assignment, assignment_id=assignment_id)
    action = request.POST.get('action')
    
    if action == 'extend_return_date':
        new_date = request.POST.get('new_return_date')
        if new_date:
            assignment.expected_return_date = new_date
            assignment.updated_by = request.user
            assignment.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                model_name='Assignment',
                object_id=assignment.assignment_id,
                object_repr=str(assignment),
                changes={'expected_return_date': new_date}
            )
            return JsonResponse({'success': True, 'message': 'Return date extended'})
    
    elif action == 'mark_critical':
        assignment.device.is_critical = True
        assignment.device.updated_by = request.user
        assignment.device.save()
        AuditLog.objects.create(
            user=request.user,
            action='UPDATE',
            model_name='Device',
            object_id=assignment.device.device_id,
            object_repr=str(assignment.device),
            changes={'is_critical': True}
        )
        return JsonResponse({'success': True, 'message': 'Device marked as critical'})
    
    return JsonResponse({'success': False, 'message': 'Invalid action'})