
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
from django.contrib.auth.models import User
from qr_management.models import QRCodeScan
from .models import ReportTemplate, ReportGeneration


@login_required
def reports_dashboard(request):
    """Main reports dashboard"""
    try:
        # Quick statistics for dashboard
        stats = {
            'total_devices': Device.objects.count(),
            'total_assignments': Assignment.objects.count(),
            'active_assignments': Assignment.objects.filter(is_active=True).count(),
            'pending_maintenance': MaintenanceSchedule.objects.filter(status='SCHEDULED').count(),
            'overdue_assignments': Assignment.objects.filter(
                is_temporary=True,
                is_active=True,
                expected_return_date__lt=timezone.now().date()
            ).count(),
            'warranty_expiring': Device.objects.filter(
                warranty_end_date__gte=timezone.now().date(),
                warranty_end_date__lte=timezone.now().date() + timedelta(days=30)
            ).count(),
        }
        
        # Recent report generations
        try:
            recent_reports = ReportGeneration.objects.filter(
                generated_by=request.user
            ).order_by('-created_at')[:5]
        except:
            recent_reports = []
        
        context = {
            'stats': stats,
            'recent_reports': recent_reports,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading reports dashboard: {str(e)}")
        return render(request, 'reports/dashboard.html', {})

@login_required
def inventory_report(request):
    """Generate comprehensive inventory report"""
    try:
        # Get filter parameters
        category = request.GET.get('category')
        status = request.GET.get('status')
        condition = request.GET.get('condition')
        vendor = request.GET.get('vendor')
        purchase_year = request.GET.get('purchase_year')
        
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
        if purchase_year:
            devices = devices.filter(purchase_date__year=purchase_year)
        
        # Statistics
        total_devices = devices.count()
        total_value = devices.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        
        # Category breakdown
        category_stats = devices.values(
            'device_type__subcategory__category__name'
        ).annotate(
            count=Count('id'),
            value=Sum('purchase_price')
        ).order_by('-count')
        
        # Status distribution
        status_stats = devices.values('status').annotate(count=Count('id'))
        
        context = {
            'devices': devices[:100],  # Limit for display
            'total_devices': total_devices,
            'total_value': total_value,
            'category_stats': category_stats,
            'status_stats': status_stats,
            'categories': DeviceCategory.objects.filter(is_active=True),
            'vendors': Vendor.objects.filter(is_active=True),
            'filters': {
                'category': category,
                'status': status,
                'condition': condition,
                'vendor': vendor,
                'purchase_year': purchase_year,
            }
        }
        
        return render(request, 'reports/inventory_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating inventory report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def assignment_report(request):
    """Generate assignment analysis report"""
    try:
        # Get filter parameters
        department = request.GET.get('department')
        assignment_type = request.GET.get('assignment_type')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff__department', 'assigned_to_department'
        )
        
        # Apply filters
        if department:
            assignments = assignments.filter(
                Q(assigned_to_department_id=department) |
                Q(assigned_to_staff__department_id=department)
            )
        if assignment_type:
            if assignment_type == 'temporary':
                assignments = assignments.filter(is_temporary=True)
            elif assignment_type == 'permanent':
                assignments = assignments.filter(is_temporary=False)
        if date_from:
            assignments = assignments.filter(start_date__gte=date_from)
        if date_to:
            assignments = assignments.filter(start_date__lte=date_to)
        
        # Statistics
        total_assignments = assignments.count()
        active_assignments = assignments.filter(is_active=True).count()
        overdue_assignments = assignments.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=timezone.now().date()
        ).count()
        
        # Department breakdown
        dept_stats = assignments.values(
            'assigned_to_department__name'
        ).annotate(
            count=Count('id'),
            active_count=Count('id', filter=Q(is_active=True))
        ).order_by('-count')
        
        # Assignment trends (last 6 months)
        six_months_ago = timezone.now().date() - timedelta(days=180)
        monthly_trends = []
        for i in range(6):
            month_start = six_months_ago + timedelta(days=i*30)
            month_end = month_start + timedelta(days=30)
            month_assignments = assignments.filter(
                start_date__gte=month_start,
                start_date__lt=month_end
            ).count()
            monthly_trends.append({
                'month': month_start.strftime('%Y-%m'),
                'count': month_assignments
            })
        
        context = {
            'assignments': assignments[:50],  # Limit for display
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'overdue_assignments': overdue_assignments,
            'dept_stats': dept_stats,
            'monthly_trends': monthly_trends,
            'departments': Department.objects.all(),
            'filters': {
                'department': department,
                'assignment_type': assignment_type,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'reports/assignment_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating assignment report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def maintenance_report(request):
    """Generate maintenance analysis report"""
    try:
        # Get filter parameters
        status = request.GET.get('status')
        device_category = request.GET.get('device_category')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        maintenance = MaintenanceSchedule.objects.select_related(
            'device', 'vendor'
        )
        
        # Apply filters
        if status:
            maintenance = maintenance.filter(status=status)
        if device_category:
            maintenance = maintenance.filter(
                device__device_type__subcategory__category_id=device_category
            )
        if date_from:
            maintenance = maintenance.filter(scheduled_date__gte=date_from)
        if date_to:
            maintenance = maintenance.filter(scheduled_date__lte=date_to)
        
        # Statistics
        total_maintenance = maintenance.count()
        scheduled = maintenance.filter(status='SCHEDULED').count()
        in_progress = maintenance.filter(status='IN_PROGRESS').count()
        completed = maintenance.filter(status='COMPLETED').count()
        overdue = maintenance.filter(
            status='SCHEDULED',
            scheduled_date__lt=timezone.now().date()
        ).count()
        
        # Cost analysis
        total_cost = maintenance.aggregate(Sum('cost'))['cost__sum'] or 0
        avg_cost = maintenance.aggregate(Avg('cost'))['cost__avg'] or 0
        
        # Vendor performance
        vendor_stats = maintenance.values(
            'vendor__name'
        ).annotate(
            count=Count('id'),
            completed_count=Count('id', filter=Q(status='COMPLETED')),
            total_cost=Sum('cost'),
            avg_cost=Avg('cost')
        ).order_by('-count')
        
        # Monthly maintenance trends
        monthly_stats = maintenance.extra(
            select={'month': "DATE_FORMAT(scheduled_date, '%%Y-%%m')"}
        ).values('month').annotate(
            count=Count('id'),
            cost=Sum('cost')
        ).order_by('month')
        
        context = {
            'maintenance': maintenance[:50],  # Limit for display
            'total_maintenance': total_maintenance,
            'scheduled': scheduled,
            'in_progress': in_progress,
            'completed': completed,
            'overdue': overdue,
            'total_cost': total_cost,
            'avg_cost': avg_cost,
            'vendor_stats': vendor_stats,
            'monthly_stats': monthly_stats,
            'categories': DeviceCategory.objects.filter(is_active=True),
            'filters': {
                'status': status,
                'device_category': device_category,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'reports/maintenance_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating maintenance report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def audit_report(request):
    """Generate audit trail report"""
    try:
        # Get filter parameters
        action = request.GET.get('action')
        user = request.GET.get('user')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        model_name = request.GET.get('model_name')
        
        # Base queryset
        audit_logs = AuditLog.objects.select_related('user')
        
        # Apply filters
        if action:
            audit_logs = audit_logs.filter(action=action)
        if user:
            audit_logs = audit_logs.filter(user_id=user)
        if date_from:
            audit_logs = audit_logs.filter(timestamp__date__gte=date_from)
        if date_to:
            audit_logs = audit_logs.filter(timestamp__date__lte=date_to)
        if model_name:
            audit_logs = audit_logs.filter(model_name=model_name)
        
        # Statistics
        total_logs = audit_logs.count()
        
        # Action breakdown
        action_stats = audit_logs.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # User activity
        user_stats = audit_logs.values(
            'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:20]
        
        # Daily activity trends (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        daily_stats = audit_logs.filter(
            timestamp__date__gte=thirty_days_ago
        ).extra(
            select={'day': "DATE(timestamp)"}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        # Model activity
        model_stats = audit_logs.values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Paginate audit logs for display
        paginator = Paginator(audit_logs.order_by('-timestamp'), 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'total_logs': total_logs,
            'action_stats': action_stats,
            'user_stats': user_stats,
            'daily_stats': daily_stats,
            'model_stats': model_stats,
            'available_actions': audit_logs.values_list('action', flat=True).distinct(),
            'available_models': audit_logs.values_list('model_name', flat=True).distinct(),
            'users': User.objects.filter(is_active=True),
            'filters': {
                'action': action,
                'user': user,
                'date_from': date_from,
                'date_to': date_to,
                'model_name': model_name,
            }
        }
        
        return render(request, 'reports/audit_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating audit report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def warranty_report(request):
    """Generate warranty analysis report"""
    try:
        # Get filter parameters
        status = request.GET.get('status')  # active, expired, expiring
        vendor = request.GET.get('vendor')
        category = request.GET.get('category')
        
        # Base queryset
        devices = Device.objects.select_related(
            'vendor', 'device_type__subcategory__category'
        ).exclude(warranty_end_date__isnull=True)
        
        # Apply filters
        today = timezone.now().date()
        if status == 'active':
            devices = devices.filter(warranty_end_date__gt=today)
        elif status == 'expired':
            devices = devices.filter(warranty_end_date__lt=today)
        elif status == 'expiring':
            thirty_days = today + timedelta(days=30)
            devices = devices.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=thirty_days
            )
        
        if vendor:
            devices = devices.filter(vendor_id=vendor)
        if category:
            devices = devices.filter(device_type__subcategory__category_id=category)
        
        # Statistics
        total_devices = devices.count()
        active_warranties = devices.filter(warranty_end_date__gt=today).count()
        expired_warranties = devices.filter(warranty_end_date__lt=today).count()
        expiring_soon = devices.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=30)
        ).count()
        
        # Vendor breakdown
        vendor_stats = devices.values(
            'vendor__name'
        ).annotate(
            count=Count('id'),
            active_count=Count('id', filter=Q(warranty_end_date__gt=today)),
            expired_count=Count('id', filter=Q(warranty_end_date__lt=today))
        ).order_by('-count')
        
        # Warranty expiration timeline (next 12 months)
        expiration_timeline = []
        for i in range(12):
            month_start = today + timedelta(days=i*30)
            month_end = month_start + timedelta(days=30)
            month_count = devices.filter(
                warranty_end_date__gte=month_start,
                warranty_end_date__lt=month_end
            ).count()
            expiration_timeline.append({
                'month': month_start.strftime('%Y-%m'),
                'count': month_count
            })
        
        context = {
            'devices': devices[:50],  # Limit for display
            'total_devices': total_devices,
            'active_warranties': active_warranties,
            'expired_warranties': expired_warranties,
            'expiring_soon': expiring_soon,
            'vendor_stats': vendor_stats,
            'expiration_timeline': expiration_timeline,
            'vendors': Vendor.objects.filter(is_active=True),
            'categories': DeviceCategory.objects.filter(is_active=True),
            'filters': {
                'status': status,
                'vendor': vendor,
                'category': category,
            }
        }
        
        return render(request, 'reports/warranty_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating warranty report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def department_utilization_report(request):
    """Generate department utilization analysis report"""
    try:
        # Get filter parameters
        department = request.GET.get('department')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset
        departments = Department.objects.all()
        
        if department:
            departments = departments.filter(id=department)
        
        # Calculate utilization stats for each department
        dept_stats = []
        for dept in departments:
            # Get staff in department
            staff_count = Staff.objects.filter(department=dept, is_active=True).count()
            
            # Get assignments to department and staff
            dept_assignments = Assignment.objects.filter(
                Q(assigned_to_department=dept) | Q(assigned_to_staff__department=dept)
            )
            
            if date_from:
                dept_assignments = dept_assignments.filter(start_date__gte=date_from)
            if date_to:
                dept_assignments = dept_assignments.filter(start_date__lte=date_to)
            
            active_assignments = dept_assignments.filter(is_active=True).count()
            total_assignments = dept_assignments.count()
            
            # Calculate device value
            assigned_devices = Device.objects.filter(
                assignments__in=dept_assignments.filter(is_active=True)
            ).distinct()
            total_value = assigned_devices.aggregate(
                Sum('purchase_price')
            )['purchase_price__sum'] or 0
            
            # Device type breakdown
            device_types = assigned_devices.values(
                'device_type__subcategory__category__name'
            ).annotate(count=Count('id')).order_by('-count')
            
            dept_stats.append({
                'department': dept,
                'staff_count': staff_count,
                'active_assignments': active_assignments,
                'total_assignments': total_assignments,
                'total_value': total_value,
                'avg_value_per_staff': total_value / staff_count if staff_count > 0 else 0,
                'device_types': device_types,
                'utilization_rate': (active_assignments / staff_count * 100) if staff_count > 0 else 0
            })
        
        # Sort by utilization rate
        dept_stats.sort(key=lambda x: x['utilization_rate'], reverse=True)
        
        # Overall statistics
        total_staff = sum(d['staff_count'] for d in dept_stats)
        total_active_assignments = sum(d['active_assignments'] for d in dept_stats)
        total_value = sum(d['total_value'] for d in dept_stats)
        
        context = {
            'dept_stats': dept_stats,
            'total_staff': total_staff,
            'total_active_assignments': total_active_assignments,
            'total_value': total_value,
            'avg_utilization': (total_active_assignments / total_staff * 100) if total_staff > 0 else 0,
            'departments': Department.objects.all(),
            'filters': {
                'department': department,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'reports/department_utilization_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating department utilization report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def generate_custom_report(request):
    """Generate custom report based on user parameters"""
    if request.method == 'POST':
        try:
            report_type = request.POST.get('report_type')
            
            # Redirect to specific report with filters
            if report_type == 'inventory':
                return redirect(f"/reports/inventory/?{request.POST.urlencode()}")
            elif report_type == 'assignments':
                return redirect(f"/reports/assignments/?{request.POST.urlencode()}")
            elif report_type == 'maintenance':
                return redirect(f"/reports/maintenance/?{request.POST.urlencode()}")
            elif report_type == 'audit':
                return redirect(f"/reports/audit/?{request.POST.urlencode()}")
            elif report_type == 'warranty':
                return redirect(f"/reports/warranty/?{request.POST.urlencode()}")
            elif report_type == 'department':
                return redirect(f"/reports/department-utilization/?{request.POST.urlencode()}")
            else:
                messages.error(request, 'Invalid report type selected.')
                
        except Exception as e:
            messages.error(request, f"Error generating custom report: {str(e)}")
    
    # GET request - show form
    context = {
        'departments': Department.objects.all(),
        'vendors': Vendor.objects.filter(is_active=True),
        'categories': DeviceCategory.objects.filter(is_active=True),
        'staff_members': Staff.objects.select_related('department'),
        'report_types': [
            ('inventory', 'Inventory Report'),
            ('assignments', 'Assignment Report'),
            ('maintenance', 'Maintenance Report'),
            ('audit', 'Audit Report'),
            ('warranty', 'Warranty Report'),
            ('department', 'Department Utilization Report'),
        ]
    }
    
    return render(request, 'reports/custom_report.html', context)

@login_required
@require_http_methods(["GET"])
def ajax_report_progress(request, report_id):
    """Get report generation progress via AJAX"""
    try:
        report = get_object_or_404(ReportGeneration, id=report_id, generated_by=request.user)
        
        data = {
            'status': report.status,
            'progress': getattr(report, 'progress_percentage', 0),
            'file_url': report.file_path.url if hasattr(report, 'file_path') and report.file_path else None,
            'error_message': getattr(report, 'error_message', None),
            'completed_at': report.completed_at.isoformat() if hasattr(report, 'completed_at') and report.completed_at else None,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'ERROR'
        }, status=400)

# ================================
# EXPORT HELPER FUNCTIONS
# ================================

def export_inventory_csv(devices):
    """Export inventory data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Device ID', 'Asset Tag', 'Device Name', 'Category', 'Type',
        'Brand', 'Model', 'Serial Number', 'Status', 'Condition',
        'Purchase Date', 'Purchase Price', 'Vendor', 'Warranty End',
        'Current Location', 'Current Assignment', 'Created Date'
    ])
    
    for device in devices:
        current_assignment = device.assignments.filter(is_active=True).first()
        
        writer.writerow([
            device.device_id,
            device.asset_tag,
            device.device_name,
            device.device_type.subcategory.category.name if device.device_type else '',
            device.device_type.name if device.device_type else '',
            device.brand,
            device.model,
            device.serial_number,
            device.get_status_display(),
            device.get_condition_display(),
            device.purchase_date.strftime('%Y-%m-%d') if device.purchase_date else '',
            device.purchase_price,
            device.vendor.name if device.vendor else '',
            device.warranty_end_date.strftime('%Y-%m-%d') if device.warranty_end_date else '',
            str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else '',
            str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else '',
            device.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response