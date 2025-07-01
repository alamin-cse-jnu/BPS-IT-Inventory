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
        recent_reports = ReportGeneration.objects.filter(
            generated_by=request.user
        ).order_by('-created_at')[:5]
        
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
        purchase_date_from = request.GET.get('purchase_date_from')
        purchase_date_to = request.GET.get('purchase_date_to')
        export_format = request.GET.get('format', 'html')
        
        # Base queryset
        devices = Device.objects.select_related(
            'device_type__subcategory__category',
            'vendor',
            'current_location'
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
        
        if purchase_date_from:
            devices = devices.filter(purchase_date__gte=purchase_date_from)
        
        if purchase_date_to:
            devices = devices.filter(purchase_date__lte=purchase_date_to)
        
        # Statistics
        total_devices = devices.count()
        total_value = devices.aggregate(total=Sum('purchase_price'))['total'] or 0
        
        # Status distribution
        status_breakdown = devices.values('status').annotate(
            count=Count('id'),
            value=Sum('purchase_price')
        ).order_by('status')
        
        # Category breakdown
        category_breakdown = devices.values(
            'device_type__subcategory__category__name'
        ).annotate(
            count=Count('id'),
            value=Sum('purchase_price')
        ).order_by('-count')
        
        # Condition analysis
        condition_breakdown = devices.values('condition').annotate(
            count=Count('id')
        ).order_by('condition')
        
        # Age analysis
        today = timezone.now().date()
        age_analysis = []
        age_ranges = [
            ('0-1 years', 0, 365),
            ('1-3 years', 366, 1095),
            ('3-5 years', 1096, 1825),
            ('5+ years', 1826, 9999)
        ]
        
        for label, min_days, max_days in age_ranges:
            if max_days == 9999:
                count = devices.filter(
                    purchase_date__lte=today - timedelta(days=min_days),
                    purchase_date__isnull=False
                ).count()
            else:
                count = devices.filter(
                    purchase_date__gte=today - timedelta(days=max_days),
                    purchase_date__lte=today - timedelta(days=min_days),
                    purchase_date__isnull=False
                ).count()
            
            age_analysis.append({'label': label, 'count': count})
        
        # Vendor analysis
        vendor_breakdown = devices.filter(vendor__isnull=False).values(
            'vendor__name'
        ).annotate(
            count=Count('id'),
            value=Sum('purchase_price')
        ).order_by('-count')[:10]
        
        # Assignment status
        assigned_devices = devices.filter(status='ASSIGNED').count()
        available_devices = devices.filter(status='AVAILABLE').count()
        utilization_rate = (assigned_devices / total_devices * 100) if total_devices > 0 else 0
        
        # Export options
        if export_format == 'csv':
            return export_inventory_csv(devices)
        elif export_format == 'pdf':
            return export_inventory_pdf(devices)
        
        # Pagination for HTML view
        paginator = Paginator(devices.order_by('-created_at'), 50)
        page_number = request.GET.get('page')
        devices_page = paginator.get_page(page_number)
        
        # Filter options
        categories = DeviceCategory.objects.filter(is_active=True)
        vendors = Vendor.objects.filter(is_active=True)
        
        context = {
            'devices': devices_page,
            'categories': categories,
            'vendors': vendors,
            'device_statuses': Device.STATUS_CHOICES,
            'device_conditions': Device.CONDITION_CHOICES,
            'filters': {
                'category': category,
                'status': status,
                'condition': condition,
                'vendor': vendor,
                'purchase_date_from': purchase_date_from,
                'purchase_date_to': purchase_date_to,
            },
            'stats': {
                'total_devices': total_devices,
                'total_value': total_value,
                'assigned_devices': assigned_devices,
                'available_devices': available_devices,
                'utilization_rate': round(utilization_rate, 1),
            },
            'breakdowns': {
                'status': status_breakdown,
                'category': category_breakdown,
                'condition': condition_breakdown,
                'vendor': vendor_breakdown,
                'age': age_analysis,
            },
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/inventory_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating inventory report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def assignment_report(request):
    """Generate assignment analysis report"""
    try:
        # Filters
        department = request.GET.get('department')
        staff = request.GET.get('staff')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        assignment_type = request.GET.get('assignment_type')
        status = request.GET.get('status')
        
        # Base queryset
        assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
        )
        
        # Apply filters
        if department:
            assignments = assignments.filter(assigned_to_department_id=department)
        
        if staff:
            assignments = assignments.filter(assigned_to_staff_id=staff)
        
        if date_from:
            assignments = assignments.filter(start_date__gte=date_from)
        
        if date_to:
            assignments = assignments.filter(start_date__lte=date_to)
        
        if assignment_type == 'temporary':
            assignments = assignments.filter(is_temporary=True)
        elif assignment_type == 'permanent':
            assignments = assignments.filter(is_temporary=False)
        
        if status == 'active':
            assignments = assignments.filter(is_active=True)
        elif status == 'inactive':
            assignments = assignments.filter(is_active=False)
        
        # Statistics
        total_assignments = assignments.count()
        active_assignments = assignments.filter(is_active=True).count()
        temporary_assignments = assignments.filter(is_temporary=True).count()
        permanent_assignments = assignments.filter(is_temporary=False).count()
        
        # Overdue assignments
        overdue_assignments = assignments.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=timezone.now().date()
        )
        
        # Department breakdown
        dept_breakdown = assignments.values(
            'assigned_to_department__name'
        ).annotate(
            count=Count('id'),
            active_count=Count('id', filter=Q(is_active=True))
        ).order_by('-count')
        
        # Device category breakdown
        category_breakdown = assignments.values(
            'device__device_type__subcategory__category__name'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Assignment duration analysis
        returned_assignments = assignments.filter(
            actual_return_date__isnull=False
        ).extra(
            select={
                'duration': 'julianday(actual_return_date) - julianday(start_date)'
            }
        )
        
        avg_duration = returned_assignments.aggregate(
            avg_duration=Avg('duration')
        )['avg_duration']
        
        # Monthly trends
        monthly_trends = []
        for i in range(12):
            month_start = (timezone.now().date() - timedelta(days=30*i)).replace(day=1)
            if i == 0:
                month_end = timezone.now().date()
            else:
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_count = assignments.filter(
                start_date__gte=month_start,
                start_date__lte=month_end
            ).count()
            
            monthly_trends.append({
                'month': month_start.strftime('%B %Y'),
                'count': month_count
            })
        
        monthly_trends.reverse()
        
        # Most active staff
        staff_activity = assignments.values(
            'assigned_to_staff__first_name',
            'assigned_to_staff__last_name'
        ).annotate(
            assignment_count=Count('id')
        ).order_by('-assignment_count')[:10]
        
        context = {
            'assignments': assignments.order_by('-created_at')[:100],
            'departments': Department.objects.all(),
            'staff_members': Staff.objects.select_related('department'),
            'filters': {
                'department': department,
                'staff': staff,
                'date_from': date_from,
                'date_to': date_to,
                'assignment_type': assignment_type,
                'status': status,
            },
            'stats': {
                'total_assignments': total_assignments,
                'active_assignments': active_assignments,
                'temporary_assignments': temporary_assignments,
                'permanent_assignments': permanent_assignments,
                'overdue_count': overdue_assignments.count(),
                'avg_duration': round(avg_duration or 0, 1),
            },
            'breakdowns': {
                'department': dept_breakdown,
                'category': category_breakdown,
                'monthly_trends': monthly_trends,
                'staff_activity': staff_activity,
            },
            'overdue_assignments': overdue_assignments[:20],
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/assignment_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating assignment report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def maintenance_report(request):
    """Generate maintenance analysis report"""
    try:
        # Filters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        maintenance_type_filter = request.GET.get('maintenance_type')
        status_filter = request.GET.get('status')
        vendor_filter = request.GET.get('vendor')
        
        # Base queryset
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
        in_progress_maintenance = maintenance_records.filter(status='IN_PROGRESS').count()
        
        # Cost analysis
        total_cost = maintenance_records.filter(
            actual_cost__isnull=False
        ).aggregate(total=Sum('actual_cost'))['total'] or 0
        
        # Type breakdown
        type_breakdown = maintenance_records.values('maintenance_type').annotate(
            count=Count('id'),
            avg_cost=Avg('actual_cost')
        ).order_by('-count')
        
        # Vendor performance
        vendor_performance = maintenance_records.filter(
            vendor__isnull=False
        ).values('vendor__name').annotate(
            total_jobs=Count('id'),
            completed_jobs=Count('id', filter=Q(status='COMPLETED')),
            avg_cost=Avg('actual_cost'),
            completion_rate=F('completed_jobs') * 100.0 / F('total_jobs')
        ).order_by('-total_jobs')
        
        # Upcoming maintenance (next 30 days)
        upcoming_maintenance = MaintenanceSchedule.objects.filter(
            scheduled_date__gte=timezone.now().date(),
            scheduled_date__lte=timezone.now().date() + timedelta(days=30),
            status='SCHEDULED'
        ).select_related('device', 'vendor').order_by('scheduled_date')
        
        # Device maintenance frequency
        device_maintenance_freq = maintenance_records.values(
            'device__device_name', 'device__device_id'
        ).annotate(
            maintenance_count=Count('id')
        ).order_by('-maintenance_count')[:10]
        
        # Monthly trends
        monthly_trends = []
        for i in range(12):
            month_start = (timezone.now().date() - timedelta(days=30*i)).replace(day=1)
            if i == 0:
                month_end = timezone.now().date()
            else:
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_count = maintenance_records.filter(
                scheduled_date__gte=month_start,
                scheduled_date__lt=month_end
            ).count()
            monthly_trends.append({
                'month': month_start.strftime('%B %Y'),
                'count': month_count
            })
        
        monthly_trends.reverse()
        
        # Overdue maintenance
        overdue_maintenance = MaintenanceSchedule.objects.filter(
            scheduled_date__lt=date.today(),
            status='SCHEDULED'
        ).select_related('device', 'vendor').order_by('scheduled_date')
        
        context = {
            'maintenance_records': maintenance_records[:50],  # Limited for performance
            'maintenance_types': MaintenanceSchedule.MAINTENANCE_TYPES,
            'maintenance_statuses': MaintenanceSchedule.MAINTENANCE_STATUS,
            'vendors': Vendor.objects.filter(is_active=True),
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'maintenance_type': maintenance_type_filter,
                'status': status_filter,
                'vendor': vendor_filter,
            },
            'stats': {
                'total_maintenance': total_maintenance,
                'completed_maintenance': completed_maintenance,
                'pending_maintenance': pending_maintenance,
                'in_progress_maintenance': in_progress_maintenance,
                'total_cost': total_cost,
                'completion_rate': (completed_maintenance / total_maintenance * 100) if total_maintenance > 0 else 0,
            },
            'breakdowns': {
                'type': type_breakdown,
                'vendor_performance': vendor_performance,
                'device_frequency': device_maintenance_freq,
                'monthly_trends': monthly_trends,
            },
            'upcoming_maintenance': upcoming_maintenance,
            'overdue_maintenance': overdue_maintenance,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/maintenance_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating maintenance report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def audit_report(request):
    """Generate audit trail report"""
    try:
        # Filters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        action_filter = request.GET.get('action')
        user_filter = request.GET.get('user')
        model_filter = request.GET.get('model')
        
        # Base queryset
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
        
        if model_filter:
            audit_logs = audit_logs.filter(model_name=model_filter)
        
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
        
        # Model activity
        model_activity = audit_logs.values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')
        
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
            action__in=['DELETE', 'ASSIGN', 'TRANSFER', 'RETURN', 'LOGIN', 'LOGOUT']
        ).order_by('-timestamp')[:20]
        
        # QR Scan audit
        qr_scan_stats = {}
        try:
            qr_scan_stats = {
                'total_scans': QRCodeScan.objects.count(),
                'successful_scans': QRCodeScan.objects.filter(verification_success=True).count(),
                'failed_scans': QRCodeScan.objects.filter(verification_success=False).count(),
                'scans_with_discrepancies': QRCodeScan.objects.exclude(discrepancies_found='').count(),
            }
        except:
            pass
        
        # Security events
        security_events = audit_logs.filter(
            action__in=['LOGIN_FAILED', 'PERMISSION_DENIED', 'SUSPICIOUS_ACTIVITY']
        ).order_by('-timestamp')[:10]
        
        context = {
            'audit_logs': audit_logs.order_by('-timestamp')[:100],  # Limited for performance
            'audit_actions': ['CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'ASSIGN', 'RETURN', 'TRANSFER'],
            'audit_models': audit_logs.values_list('model_name', flat=True).distinct(),
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'action': action_filter,
                'user': user_filter,
                'model': model_filter,
            },
            'stats': {
                'total_activities': total_activities,
                'unique_users': unique_users,
                'avg_daily_activity': total_activities / 30 if total_activities > 0 else 0,
            },
            'breakdowns': {
                'activity': activity_breakdown,
                'user_activity': user_activity,
                'model_activity': model_activity,
                'daily_activity': daily_activity,
            },
            'critical_activities': critical_activities,
            'security_events': security_events,
            'qr_scan_stats': qr_scan_stats,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/audit_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating audit report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def warranty_report(request):
    """Generate warranty status and expiration report"""
    try:
        # Filters
        vendor_filter = request.GET.get('vendor')
        category_filter = request.GET.get('category')
        status_filter = request.GET.get('warranty_status')
        
        # Base queryset
        devices = Device.objects.select_related(
            'device_type__subcategory__category', 'vendor'
        )
        
        # Apply filters
        if vendor_filter:
            devices = devices.filter(vendor_id=vendor_filter)
        
        if category_filter:
            devices = devices.filter(device_type__subcategory__category_id=category_filter)
        
        today = timezone.now().date()
        
        # Warranty status filtering
        if status_filter == 'expired':
            devices = devices.filter(warranty_end_date__lt=today)
        elif status_filter == 'expiring_30':
            devices = devices.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=today + timedelta(days=30)
            )
        elif status_filter == 'expiring_90':
            devices = devices.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=today + timedelta(days=90)
            )
        elif status_filter == 'active':
            devices = devices.filter(warranty_end_date__gt=today + timedelta(days=90))
        elif status_filter == 'no_warranty':
            devices = devices.filter(warranty_end_date__isnull=True)
        
        # Warranty statistics
        warranty_stats = {
            'total_devices': Device.objects.count(),
            'with_warranty': Device.objects.filter(warranty_end_date__isnull=False).count(),
            'without_warranty': Device.objects.filter(warranty_end_date__isnull=True).count(),
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
            active_warranties=Count('devices', filter=Q(devices__warranty_end_date__gte=today)),
            expiring_soon=Count('devices', filter=Q(
                devices__warranty_end_date__gte=today,
                devices__warranty_end_date__lte=today + timedelta(days=90)
            ))
        ).filter(total_devices__gt=0).order_by('-total_devices')
        
        # Warranty by category
        category_warranty = DeviceCategory.objects.annotate(
            total_devices=Count('subcategories__device_types__devices'),
            expired_warranties=Count(
                'subcategories__device_types__devices',
                filter=Q(subcategories__device_types__devices__warranty_end_date__lt=today)
            ),
            active_warranties=Count(
                'subcategories__device_types__devices',
                filter=Q(subcategories__device_types__devices__warranty_end_date__gte=today)
            )
        ).filter(total_devices__gt=0).order_by('-total_devices')
        
        # Warranty cost implications
        expiring_value = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=today + timedelta(days=90)
        ).aggregate(total_value=Sum('purchase_price'))['total_value'] or 0
        
        expired_value = Device.objects.filter(
            warranty_end_date__lt=today
        ).aggregate(total_value=Sum('purchase_price'))['total_value'] or 0
        
        # Monthly warranty expiration trends
        monthly_expirations = []
        for i in range(12):
            month_start = (today + timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_count = Device.objects.filter(
                warranty_end_date__gte=month_start,
                warranty_end_date__lte=month_end
            ).count()
            
            monthly_expirations.append({
                'month': month_start.strftime('%B %Y'),
                'count': month_count
            })
        
        context = {
            'devices': devices[:100],  # Limited for performance
            'vendors': Vendor.objects.filter(is_active=True),
            'categories': DeviceCategory.objects.filter(is_active=True),
            'warranty_statuses': [
                ('expired', 'Expired'),
                ('expiring_30', 'Expiring in 30 days'),
                ('expiring_90', 'Expiring in 90 days'),
                ('active', 'Active (>90 days)'),
                ('no_warranty', 'No Warranty'),
            ],
            'filters': {
                'vendor': vendor_filter,
                'category': category_filter,
                'warranty_status': status_filter,
            },
            'warranty_stats': warranty_stats,
            'expiring_soon': expiring_soon[:20],
            'recently_expired': recently_expired[:20],
            'vendor_warranty': vendor_warranty,
            'category_warranty': category_warranty,
            'cost_analysis': {
                'expiring_value': expiring_value,
                'expired_value': expired_value,
            },
            'monthly_expirations': monthly_expirations,
            'report_date': today,
        }
        
        return render(request, 'reports/warranty_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating warranty report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def department_utilization_report(request):
    """Generate department utilization report"""
    try:
        # Department filter
        department_filter = request.GET.get('department')
        
        # Base queryset
        departments = Department.objects.prefetch_related(
            'staff_members', 'staff_members__assignments'
        )
        
        if department_filter:
            departments = departments.filter(id=department_filter)
        
        # Calculate utilization metrics for each department
        dept_utilization = []
        
        for dept in departments:
            staff_count = dept.staff_members.count()
            active_assignments = Assignment.objects.filter(
                assigned_to_department=dept,
                is_active=True
            ).count()
            
            total_devices_value = Assignment.objects.filter(
                assigned_to_department=dept,
                is_active=True
            ).aggregate(
                total_value=Sum('device__purchase_price')
            )['total_value'] or 0
            
            # Device categories assigned to this department
            category_breakdown = Assignment.objects.filter(
                assigned_to_department=dept,
                is_active=True
            ).values(
                'device__device_type__subcategory__category__name'
            ).annotate(count=Count('id')).order_by('-count')
            
            dept_utilization.append({
                'department': dept,
                'staff_count': staff_count,
                'active_assignments': active_assignments,
                'devices_per_staff': round(active_assignments / staff_count, 1) if staff_count > 0 else 0,
                'total_value': total_devices_value,
                'avg_value_per_staff': round(total_devices_value / staff_count, 2) if staff_count > 0 else 0,
                'category_breakdown': category_breakdown,
            })
        
        # Sort by utilization metrics
        sort_by = request.GET.get('sort_by', 'active_assignments')
        reverse_sort = request.GET.get('reverse', 'true') == 'true'
        
        if sort_by in ['active_assignments', 'staff_count', 'devices_per_staff', 'total_value']:
            dept_utilization.sort(
                key=lambda x: x[sort_by],
                reverse=reverse_sort
            )
        
        # Overall statistics
        total_staff = Staff.objects.count()
        total_active_assignments = Assignment.objects.filter(is_active=True).count()
        overall_utilization = (total_active_assignments / total_staff) if total_staff > 0 else 0
        
        # Top departments by various metrics
        top_by_assignments = sorted(dept_utilization, key=lambda x: x['active_assignments'], reverse=True)[:5]
        top_by_value = sorted(dept_utilization, key=lambda x: x['total_value'], reverse=True)[:5]
        top_by_efficiency = sorted(dept_utilization, key=lambda x: x['devices_per_staff'], reverse=True)[:5]
        
        # Department growth trends (last 12 months)
        dept_trends = {}
        for dept in departments:
            monthly_data = []
            for i in range(12):
                month_start = (timezone.now().date() - timedelta(days=30*i)).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                assignments_count = Assignment.objects.filter(
                    assigned_to_department=dept,
                    start_date__gte=month_start,
                    start_date__lte=month_end
                ).count()
                
                monthly_data.append({
                    'month': month_start.strftime('%B %Y'),
                    'assignments': assignments_count
                })
            
            monthly_data.reverse()
            dept_trends[dept.id] = monthly_data
        
        context = {
            'departments': departments,
            'dept_utilization': dept_utilization,
            'filters': {
                'department': department_filter,
                'sort_by': sort_by,
                'reverse': reverse_sort,
            },
            'overall_stats': {
                'total_staff': total_staff,
                'total_active_assignments': total_active_assignments,
                'overall_utilization': round(overall_utilization, 2),
            },
            'top_departments': {
                'by_assignments': top_by_assignments,
                'by_value': top_by_value,
                'by_efficiency': top_by_efficiency,
            },
            'dept_trends': dept_trends,
            'report_date': timezone.now().date(),
        }
        
        return render(request, 'reports/department_utilization.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating department utilization report: {str(e)}")
        return redirect('reports:dashboard')

@login_required
def generate_custom_report(request):
    """Generate custom report based on user selections"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        filters = request.POST.dict()
        
        # Create report generation record
        try:
            report_gen = ReportGeneration.objects.create(
                template=None,  # Custom report
                generated_by=request.user,
                filters_applied=filters,
                date_range_start=date_from if date_from else None,
                date_range_end=date_to if date_to else None,
                file_format='CSV'
            )
        except:
            pass  # Skip if model doesn't exist
        
        # Redirect to appropriate report with filters
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
    
    # GET request - show form
    context = {
        'departments': Department.objects.all(),
        'vendors': Vendor.objects.filter(is_active=True),
        'categories': DeviceCategory.objects.filter(is_active=True),
        'staff_members': Staff.objects.select_related('department'),
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
            'progress': report.progress_percentage,
            'file_url': report.file_path.url if report.file_path else None,
            'error_message': report.error_message,
            'completed_at': report.completed_at.isoformat() if report.completed_at else None,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'ERROR'
        }, status=400)

# Export helper functions
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
            device.current_location.name if device.current_location else '',
            str(current_assignment.assigned_to_staff or current_assignment.assigned_to_department) if current_assignment else '',
            device.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response

def export_inventory_pdf(devices):
    """Export inventory data to PDF"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="inventory_report.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        
        # Title
        title = Paragraph("BPS IT Inventory Report", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Date
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
                device.device_type.subcategory.category.name if device.device_type else '',
                device.brand[:15] + "..." if device.brand and len(device.brand) > 15 else (device.brand or ''),
                device.get_status_display(),
                str(device.purchase_date) if device.purchase_date else '',
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