# reports/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg, Max, Min, F
from django.core.paginator import Paginator
from datetime import date, timedelta, datetime
import json
import csv
from io import BytesIO

from inventory.models import (
    Device, Assignment, Staff, Department, Location, 
    DeviceCategory, Vendor, MaintenanceSchedule, AuditLog
)
from qr_management.models import QRCodeScan
from .models import ReportTemplate, ReportGeneration

@login_required
def reports_dashboard(request):
    """Main reports dashboard"""
    
    # Quick statistics
    total_devices = Device.objects.count()
    active_assignments = Assignment.objects.filter(is_active=True).count()
    overdue_assignments = Assignment.objects.filter(
        is_temporary=True,
        is_active=True,
        expected_return_date__lt=date.today(),
        actual_return_date__isnull=True
    ).count()
    
    # Recent report generations
    recent_reports = ReportGeneration.objects.select_related(
        'template', 'generated_by'
    ).order_by('-generation_started')[:10]
    
    # Available report templates
    report_templates = ReportTemplate.objects.filter(is_active=True)
    
    # Device status distribution
    device_status_stats = Device.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Assignment by department
    dept_assignment_stats = Assignment.objects.filter(
        is_active=True
    ).values(
        'assigned_to_department__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Recent QR scans
    recent_scans = QRCodeScan.objects.select_related(
        'device', 'scanned_by'
    ).order_by('-timestamp')[:5]
    
    context = {
        'total_devices': total_devices,
        'active_assignments': active_assignments,
        'overdue_assignments': overdue_assignments,
        'recent_reports': recent_reports,
        'report_templates': report_templates,
        'device_status_stats': device_status_stats,
        'dept_assignment_stats': dept_assignment_stats,
        'recent_scans': recent_scans,
    }
    
    return render(request, 'reports/dashboard.html', context)

@login_required
def inventory_report(request):
    """Comprehensive inventory report"""
    
    # Filters
    category_filter = request.GET.get('category')
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    export_format = request.GET.get('export')
    
    devices = Device.objects.select_related(
        'device_type__subcategory__category', 'vendor'
    ).prefetch_related('assignments')
    
    # Apply filters
    if category_filter:
        devices = devices.filter(device_type__subcategory__category_id=category_filter)
    
    if status_filter:
        devices = devices.filter(status=status_filter)
    
    if date_from:
        devices = devices.filter(purchase_date__gte=date_from)
    
    if date_to:
        devices = devices.filter(purchase_date__lte=date_to)
    
    if department_filter:
        devices = devices.filter(
            assignments__assigned_to_department_id=department_filter,
            assignments__is_active=True
        )
    
    # Export functionality
    if export_format == 'csv':
        return export_inventory_csv(devices)
    elif export_format == 'pdf':
        return export_inventory_pdf(devices)
    
    # Statistics
    total_devices = devices.count()
    total_value = devices.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
    avg_device_age = devices.aggregate(
        avg_age=Avg(timezone.now().date() - F('purchase_date'))
    )
    
    # Category breakdown
    category_breakdown = devices.values(
        'device_type__subcategory__category__name'
    ).annotate(
        count=Count('id'),
        total_value=Sum('purchase_price')
    ).order_by('-count')
    
    # Status distribution
    status_distribution = devices.values('status').annotate(
        count=Count('id')
    )
    
    # Warranty status
    warranty_stats = {
        'active': devices.filter(warranty_end_date__gte=date.today()).count(),
        'expired': devices.filter(warranty_end_date__lt=date.today()).count(),
        'expiring_soon': devices.filter(
            warranty_end_date__gte=date.today(),
            warranty_end_date__lte=date.today() + timedelta(days=30)
        ).count()
    }
    
    # Pagination
    paginator = Paginator(devices, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': DeviceCategory.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'device_statuses': Device.DEVICE_STATUS,
        'total_devices': total_devices,
        'total_value': total_value,
        'category_breakdown': category_breakdown,
        'status_distribution': status_distribution,
        'warranty_stats': warranty_stats,
        'filters': {
            'category': category_filter,
            'department': department_filter,
            'status': status_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'reports/inventory_report.html', context)

@login_required
def assignment_report(request):
    """Assignment analysis report"""
    
    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    department_filter = request.GET.get('department')
    assignment_type_filter = request.GET.get('assignment_type')
    status_filter = request.GET.get('status')
    export_format = request.GET.get('export')
    
    assignments = Assignment.objects.select_related(
        'device', 'assigned_to_staff', 'assigned_to_department',
        'assigned_to_location'
    )
    
    # Apply filters
    if date_from:
        assignments = assignments.filter(start_date__gte=date_from)
    
    if date_to:
        assignments = assignments.filter(start_date__lte=date_to)
    
    if department_filter:
        assignments = assignments.filter(assigned_to_department_id=department_filter)
    
    if assignment_type_filter:
        assignments = assignments.filter(assignment_type=assignment_type_filter)
    
    if status_filter == 'active':
        assignments = assignments.filter(is_active=True)
    elif status_filter == 'completed':
        assignments = assignments.filter(is_active=False)
    elif status_filter == 'overdue':
        assignments = assignments.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=date.today(),
            actual_return_date__isnull=True
        )
    
    # Export functionality
    if export_format == 'csv':
        return export_assignments_csv(assignments)
    
    # Statistics
    total_assignments = assignments.count()
    active_assignments = assignments.filter(is_active=True).count()
    completed_assignments = assignments.filter(is_active=False).count()
    overdue_assignments = assignments.filter(
        is_temporary=True,
        is_active=True,
        expected_return_date__lt=date.today(),
        actual_return_date__isnull=True
    ).count()
    
    # Assignment type breakdown
    type_breakdown = assignments.values('assignment_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Department breakdown
    dept_breakdown = assignments.filter(
        assigned_to_department__isnull=False
    ).values(
        'assigned_to_department__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Monthly assignment trend (last 12 months)
    monthly_data = []
    for i in range(12):
        month_start = date.today().replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = assignments.filter(
            start_date__gte=month_start,
            start_date__lt=month_end
        ).count()
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'count': count
        })
    monthly_data.reverse()
    
    # Top assigned devices
    top_devices = assignments.values(
        'device__device_id', 'device__device_name'
    ).annotate(
        assignment_count=Count('id')
    ).order_by('-assignment_count')[:10]
    
    # Pagination
    paginator = Paginator(assignments, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'departments': Department.objects.all(),
        'assignment_types': Assignment.ASSIGNMENT_TYPES,
        'total_assignments': total_assignments,
        'active_assignments': active_assignments,
        'completed_assignments': completed_assignments,
        'overdue_assignments': overdue_assignments,
        'type_breakdown': type_breakdown,
        'dept_breakdown': dept_breakdown,
        'monthly_data': monthly_data,
        'top_devices': top_devices,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'department': department_filter,
            'assignment_type': assignment_type_filter,
            'status': status_filter,
        }
    }
    
    return render(request, 'reports/assignment_report.html', context)

@login_required
def maintenance_report(request):
    """Maintenance analysis report"""
    
    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    maintenance_type_filter = request.GET.get('maintenance_type')
    status_filter = request.GET.get('status')
    vendor_filter = request.GET.get('vendor')
    
    maintenance_records = MaintenanceSchedule.objects.select_related(
        'device', 'vendor'
    )
    
    # Apply filters
    if date_from:
        maintenance_records = maintenance_records.filter(scheduled_date__gte=date_from)
    
    if date_to:
        maintenance_records = maintenance_records.filter(scheduled_date__lte=date_to)
    
    if maintenance_type_filter:
        maintenance_records = maintenance_records.filter(maintenance_type=maintenance_type_filter)
    
    if status_filter:
        maintenance_records = maintenance_records.filter(status=status_filter)
    
    if vendor_filter:
        maintenance_records = maintenance_records.filter(vendor_id=vendor_filter)
    
    # Statistics
    total_maintenance = maintenance_records.count()
    completed_maintenance = maintenance_records.filter(status='COMPLETED').count()
    pending_maintenance = maintenance_records.filter(status='SCHEDULED').count()
    total_cost = maintenance_records.filter(
        actual_cost__isnull=False
    ).aggregate(Sum('actual_cost'))['actual_cost__sum'] or 0
    
    # Maintenance type breakdown
    type_breakdown = maintenance_records.values('maintenance_type').annotate(
        count=Count('id'),
        total_cost=Sum('actual_cost')
    ).order_by('-count')
    
    # Vendor performance
    vendor_performance = maintenance_records.filter(
        vendor__isnull=False,
        status='COMPLETED'
    ).values(
        'vendor__name'
    ).annotate(
        maintenance_count=Count('id'),
        total_cost=Sum('actual_cost'),
        avg_cost=Avg('actual_cost')
    ).order_by('-maintenance_count')
    
    # Upcoming maintenance (next 30 days)
    upcoming_maintenance = MaintenanceSchedule.objects.filter(
        scheduled_date__gte=date.today(),
        scheduled_date__lte=date.today() + timedelta(days=30),
        status='SCHEDULED'
    ).select_related('device', 'vendor').order_by('scheduled_date')
    
    # Device maintenance frequency
    device_maintenance_freq = maintenance_records.values(
        'device__device_id', 'device__device_name'
    ).annotate(
        maintenance_count=Count('id'),
        total_cost=Sum('actual_cost')
    ).order_by('-maintenance_count')[:10]
    
    context = {
        'maintenance_records': maintenance_records[:50],  # Limited for performance
        'maintenance_types': MaintenanceSchedule.MAINTENANCE_TYPES,
        'maintenance_statuses': MaintenanceSchedule.MAINTENANCE_STATUS,
        'vendors': Vendor.objects.filter(is_active=True),
        'total_maintenance': total_maintenance,
        'completed_maintenance': completed_maintenance,
        'pending_maintenance': pending_maintenance,
        'total_cost': total_cost,
        'type_breakdown': type_breakdown,
        'vendor_performance': vendor_performance,
        'upcoming_maintenance': upcoming_maintenance,
        'device_maintenance_freq': device_maintenance_freq,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'maintenance_type': maintenance_type_filter,
            'status': status_filter,
            'vendor': vendor_filter,
        }
    }
    
    return render(request, 'reports/maintenance_report.html', context)

@login_required
def audit_report(request):
    """System audit and compliance report"""
    
    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    action_filter = request.GET.get('action')
    user_filter = request.GET.get('user')
    
    audit_logs = AuditLog.objects.select_related('user')
    
    # Apply filters
    if date_from:
        audit_logs = audit_logs.filter(timestamp__date__gte=date_from)
    
    if date_to:
        audit_logs = audit_logs.filter(timestamp__date__lte=date_to)
    
    if action_filter:
        audit_logs = audit_logs.filter(action=action_filter)
    
    if user_filter:
        audit_logs = audit_logs.filter(user__username__icontains=user_filter)
    
    # Statistics
    total_activities = audit_logs.count()
    unique_users = audit_logs.values('user').distinct().count()
    
    # Activity breakdown
    activity_breakdown = audit_logs.values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # User activity
    user_activity = audit_logs.values(
        'user__username', 'user__first_name', 'user__last_name'
    ).annotate(
        activity_count=Count('id')
    ).order_by('-activity_count')[:10]
    
    # Daily activity (last 30 days)
    daily_activity = []
    for i in range(30):
        day = date.today() - timedelta(days=i)
        count = audit_logs.filter(timestamp__date=day).count()
        daily_activity.append({
            'date': day.strftime('%Y-%m-%d'),
            'count': count
        })
    daily_activity.reverse()
    
    # Recent critical activities
    critical_activities = audit_logs.filter(
        action__in=['DELETE', 'ASSIGN', 'TRANSFER', 'RETURN']
    ).order_by('-timestamp')[:20]
    
    # QR Scan audit
    qr_scan_stats = {
        'total_scans': QRCodeScan.objects.count(),
        'successful_scans': QRCodeScan.objects.filter(verification_success=True).count(),
        'failed_scans': QRCodeScan.objects.filter(verification_success=False).count(),
        'scans_with_discrepancies': QRCodeScan.objects.exclude(discrepancies_found='').count(),
    }
    
    context = {
        'audit_logs': audit_logs[:100],  # Limited for performance
        'audit_actions': AuditLog.ACTION_TYPES,
        'total_activities': total_activities,
        'unique_users': unique_users,
        'activity_breakdown': activity_breakdown,
        'user_activity': user_activity,
        'daily_activity': daily_activity,
        'critical_activities': critical_activities,
        'qr_scan_stats': qr_scan_stats,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'action': action_filter,
            'user': user_filter,
        }
    }
    
    return render(request, 'reports/audit_report.html', context)

@login_required
def warranty_report(request):
    """Warranty status and expiration report"""
    
    # Get devices with warranty information
    devices = Device.objects.select_related(
        'device_type__subcategory__category', 'vendor'
    )
    
    # Warranty categories
    today = date.today()
    
    active_warranty = devices.filter(warranty_end_date__gte=today)
    expired_warranty = devices.filter(warranty_end_date__lt=today)
    expiring_soon = devices.filter(
        warranty_end_date__gte=today,
        warranty_end_date__lte=today + timedelta(days=30)
    )
    expiring_3_months = devices.filter(
        warranty_end_date__gte=today,
        warranty_end_date__lte=today + timedelta(days=90)
    )
    
    # Warranty by vendor
    vendor_warranty_stats = devices.values(
        'vendor__name'
    ).annotate(
        total_devices=Count('id'),
        active_warranties=Count('id', filter=Q(warranty_end_date__gte=today)),
        expired_warranties=Count('id', filter=Q(warranty_end_date__lt=today))
    ).order_by('-total_devices')
    
    # Warranty value analysis
    warranty_value_stats = {
        'active_value': active_warranty.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0,
        'expired_value': expired_warranty.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0,
        'expiring_soon_value': expiring_soon.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0,
    }
    
    context = {
        'active_warranty': active_warranty[:50],
        'expired_warranty': expired_warranty[:50],
        'expiring_soon': expiring_soon,
        'expiring_3_months': expiring_3_months[:50],
        'vendor_warranty_stats': vendor_warranty_stats,
        'warranty_value_stats': warranty_value_stats,
        'warranty_counts': {
            'active': active_warranty.count(),
            'expired': expired_warranty.count(),
            'expiring_soon': expiring_soon.count(),
            'expiring_3_months': expiring_3_months.count(),
        }
    }
    
    return render(request, 'reports/warranty_report.html', context)

@login_required
def department_utilization_report(request):
    """Department-wise device utilization report"""
    
    departments = Department.objects.all()
    department_stats = []
    
    for dept in departments:
        # Get assignments for this department
        dept_assignments = Assignment.objects.filter(
            Q(assigned_to_department=dept) | Q(assigned_to_staff__department=dept)
        )
        
        active_assignments = dept_assignments.filter(is_active=True)
        total_devices = active_assignments.count()
        
        # Device categories in this department
        category_breakdown = active_assignments.values(
            'device__device_type__subcategory__category__name'
        ).annotate(
            count=Count('id')
        )
        
        # Total value of assigned devices
        total_value = active_assignments.aggregate(
            total=Sum('device__purchase_price')
        )['total'] or 0
        
        # Staff with most assignments
        top_staff = dept_assignments.filter(
            assigned_to_staff__isnull=False,
            is_active=True
        ).values(
            'assigned_to_staff__full_name'
        ).annotate(
            device_count=Count('id')
        ).order_by('-device_count')[:5]
        
        department_stats.append({
            'department': dept,
            'total_devices': total_devices,
            'total_value': total_value,
            'category_breakdown': category_breakdown,
            'top_staff': top_staff,
        })
    
    # Sort by device count
    department_stats.sort(key=lambda x: x['total_devices'], reverse=True)
    
    context = {
        'department_stats': department_stats,
    }
    
    return render(request, 'reports/department_utilization.html', context)

# Export functions
def export_inventory_csv(devices):
    """Export inventory data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Subcategory',
        'Brand', 'Model', 'Serial Number', 'Status', 'Condition',
        'Purchase Date', 'Purchase Price', 'Vendor', 'Warranty End Date',
        'Assigned To', 'Department', 'Location'
    ])
    
    for device in devices:
        current_assignment = device.assignments.filter(is_active=True).first()
        
        writer.writerow([
            device.device_id,
            device.asset_tag,
            device.device_name,
            device.device_type.subcategory.category.name,
            device.device_type.subcategory.name,
            device.brand,
            device.model,
            device.serial_number,
            device.get_status_display(),
            device.get_condition_display(),
            device.purchase_date,
            device.purchase_price,
            device.vendor.name,
            device.warranty_end_date,
            str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else '',
            str(current_assignment.assigned_to_department) if current_assignment and current_assignment.assigned_to_department else '',
            str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else '',
        ])
    
    return response

def export_assignments_csv(assignments):
    """Export assignment data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="assignment_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Assignment ID', 'Device ID', 'Device Name', 'Assignment Type',
        'Assigned To Staff', 'Assigned To Department', 'Assigned To Location',
        'Start Date', 'Expected Return Date', 'Actual Return Date',
        'Is Temporary', 'Is Active', 'Purpose', 'Created By'
    ])
    
    for assignment in assignments:
        writer.writerow([
            assignment.assignment_id,
            assignment.device.device_id,
            assignment.device.device_name,
            assignment.get_assignment_type_display(),
            str(assignment.assigned_to_staff) if assignment.assigned_to_staff else '',
            str(assignment.assigned_to_department) if assignment.assigned_to_department else '',
            str(assignment.assigned_to_location) if assignment.assigned_to_location else '',
            assignment.start_date,
            assignment.expected_return_date or '',
            assignment.actual_return_date or '',
            assignment.is_temporary,
            assignment.is_active,
            assignment.purpose,
            assignment.created_by.username if assignment.created_by else '',
        ])
    
    return response

def export_inventory_pdf(devices):
    """Export inventory data to PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
        
        # Create PDF document
        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph("BPS IT Inventory Report", styles['Title'])
        elements.append(title)
        
        # Generate date
        from datetime import datetime
        date_para = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
        elements.append(date_para)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Create table data
        data = [['Device ID', 'Name', 'Category', 'Brand', 'Status', 'Purchase Date']]
        
        for device in devices[:100]:  # Limit to 100 devices for PDF
            data.append([
                device.device_id,
                device.device_name[:20] + "..." if len(device.device_name) > 20 else device.device_name,
                device.device_type.subcategory.category.name,
                device.brand,
                device.get_status_display(),
                str(device.purchase_date),
            ])
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        return response
        
    except ImportError:
        # Fallback to CSV if reportlab is not available
        return export_inventory_csv(devices)

@login_required
def generate_custom_report(request):
    """Generate custom report based on user selections"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        filters = request.POST.dict()
        
        # Create report generation record
        report_gen = ReportGeneration.objects.create(
            template=None,  # Custom report
            generated_by=request.user,
            filters_applied=filters,
            date_range_start=date_from if date_from else None,
            date_range_end=date_to if date_to else None,
            file_format='CSV'
        )
        
        # Redirect to appropriate report with filters
        if report_type == 'inventory':
            return redirect(f"/reports/inventory/?{request.POST.urlencode()}")
        elif report_type == 'assignments':
            return redirect(f"/reports/assignments/?{request.POST.urlencode()}")
        elif report_type == 'maintenance':
            return redirect(f"/reports/maintenance/?{request.POST.urlencode()}")
        elif report_type == 'audit':
            return redirect(f"/reports/audit/?{request.POST.urlencode()}")
    
    context = {
        'categories': DeviceCategory.objects.filter(is_active=True),
        'departments': Department.objects.all(),
        'vendors': Vendor.objects.filter(is_active=True),
        'device_statuses': Device.DEVICE_STATUS,
        'assignment_types': Assignment.ASSIGNMENT_TYPES,
    }
    
    return render(request, 'reports/custom_report.html', context)

# AJAX endpoints
@login_required
def ajax_report_progress(request, report_id):
    """Check report generation progress"""
    try:
        report = ReportGeneration.objects.get(id=report_id)
        data = {
            'status': 'completed' if report.generation_completed else ('failed' if report.generation_failed else 'in_progress'),
            'progress': 100 if report.generation_completed else 50,
            'total_records': report.total_records,
            'error_message': report.error_message if report.generation_failed else None
        }
        return JsonResponse(data)
    except ReportGeneration.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)