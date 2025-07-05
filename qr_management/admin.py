# qr_management/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import (
    QRCodeScan, QRAnalytics, QRCampaign
)


# ================================
# CUSTOM FILTERS
# ================================

class ScanTypeFilter(admin.SimpleListFilter):
    title = 'Scan Type'
    parameter_name = 'scan_type'

    def lookups(self, request, model_admin):
        return (
            ('VERIFICATION', 'Device Verification'),
            ('INVENTORY', 'Inventory Check'),
            ('ASSIGNMENT', 'Assignment Verification'),
            ('MAINTENANCE', 'Maintenance Scan'),
            ('AUDIT', 'Audit Scan'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(scan_type=self.value())


class VerificationStatusFilter(admin.SimpleListFilter):
    title = 'Verification Status'
    parameter_name = 'verification_status'

    def lookups(self, request, model_admin):
        return (
            ('SUCCESS', 'Successful'),
            ('FAILED', 'Failed'),
            ('WARNING', 'With Warnings'),
            ('ERROR', 'Error'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(verification_status=self.value())


class TimeRangeFilter(admin.SimpleListFilter):
    title = 'Time Range'
    parameter_name = 'time_range'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('quarter', 'This Quarter'),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(timestamp__date=today)
        elif self.value() == 'week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(timestamp__date__gte=week_start)
        elif self.value() == 'month':
            month_start = today.replace(day=1)
            return queryset.filter(timestamp__date__gte=month_start)
        elif self.value() == 'quarter':
            quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            return queryset.filter(timestamp__date__gte=quarter_start)


# ================================
# INLINE ADMIN CLASSES
# ================================

class QRAnalyticsInline(admin.TabularInline):
    model = QRAnalytics
    extra = 0
    readonly_fields = ('calculated_at', 'calculation_time_ms', 'data_points_count')
    fields = (
        'metric_type', 'value', 'aggregation_period',
        'period_start', 'period_end', 'calculated_at'
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-period_start')[:10]


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'scan_type', 'scanned_by', 'timestamp',
        'verification_status', 'location_info', 'device_status_at_scan'
    )
    list_filter = (
        ScanTypeFilter, VerificationStatusFilter, TimeRangeFilter,
        'device_status_at_scan', 'timestamp'
    )
    search_fields = (
        'device__device_id', 'device__device_name', 'device__asset_tag',
        'scanned_by__username', 'scan_notes'
    )
    readonly_fields = (
        'id', 'timestamp', 'response_time_ms', 'scan_metadata'
    )
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'id', 'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Scan Context', {
            'fields': (
                'scan_location', 'device_location_at_scan',
                'assigned_staff_at_scan', 'verification_status'
            )
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'device_condition_at_scan',
                'assignment_status_at_scan'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Details', {
            'fields': (
                'ip_address', 'user_agent', 'response_time_ms',
                'scan_metadata'
            ),
            'classes': ('collapse',)
        }),
        ('Results & Notes', {
            'fields': (
                'verification_result', 'discrepancies_found',
                'scan_notes', 'follow_up_required'
            ),
            'classes': ('collapse',)
        }),
    )

    def location_info(self, obj):
        """Display location information"""
        locations = []
        if obj.scan_location:
            locations.append(f"Scanned at: {obj.scan_location}")
        if obj.device_location_at_scan:
            locations.append(f"Device at: {obj.device_location_at_scan}")
        return " | ".join(locations) if locations else "No location data"
    location_info.short_description = 'Location Info'

    def verification_status(self, obj):
        """Display verification status with icons"""
        status_icons = {
            'SUCCESS': '✅',
            'FAILED': '❌',
            'WARNING': '⚠️',
            'ERROR': '🚫'
        }
        
        if hasattr(obj, 'verification_status') and obj.verification_status:
            icon = status_icons.get(obj.verification_status, '❓')
            return format_html(
                '<span style="color: {};">{} {}</span>',
                'green' if obj.verification_status == 'SUCCESS' else 'red',
                icon,
                obj.get_verification_status_display() if hasattr(obj, 'get_verification_status_display') else obj.verification_status
            )
        return format_html('<span style="color: gray;">No status</span>')
    verification_status.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing but not editing
        return True

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete scan records
        return request.user.is_superuser


@admin.register(QRAnalytics)
class QRAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'metric_type', 'aggregation_period', 'period_start',
        'value_display', 'department', 'location', 'calculated_at'
    )
    list_filter = (
        'metric_type', 'aggregation_period', 'department',
        'location', 'device_category', 'calculated_at'
    )
    search_fields = ('department__name', 'location__name')
    readonly_fields = (
        'calculated_at', 'calculation_time_ms', 'data_points_count'
    )
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_type', 'aggregation_period', 'value')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Scope & Filters', {
            'fields': ('department', 'location', 'device_category')
        }),
        ('Calculation Details', {
            'fields': (
                'calculated_at', 'calculation_time_ms', 'data_points_count'
            ),
            'classes': ('collapse',)
        }),
    )

    def value_display(self, obj):
        """Display formatted metric value"""
        if obj.metric_type in ['SCAN_COUNT', 'DEVICE_COUNT']:
            return f"{obj.value:,.0f}"
        elif obj.metric_type in ['SUCCESS_RATE', 'UTILIZATION_RATE']:
            return f"{obj.value:.1f}%"
        elif obj.metric_type == 'AVERAGE_RESPONSE_TIME':
            return f"{obj.value:.0f}ms"
        else:
            return f"{obj.value:,.2f}"
    value_display.short_description = 'Value'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(QRCampaign)
class QRCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'campaign_type', 'status', 'start_date',
        'end_date', 'progress_display', 'created_by'
    )
    list_filter = (
        'campaign_type', 'status', 'start_date', 'end_date', 'created_at'
    )
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'created_at', 'updated_at', 'completion_percentage',
        'total_scans', 'successful_scans'
    )
    filter_horizontal = ('target_locations', 'target_departments')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('name', 'description', 'campaign_type', 'status')
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at')
        }),
        ('Scope & Targets', {
            'fields': (
                'target_devices', 'target_locations', 'target_departments'
            )
        }),
        ('Team & Assignments', {
            'fields': ('assigned_users', 'campaign_manager'),
            'classes': ('collapse',)
        }),
        ('Progress & Results', {
            'fields': (
                'completion_percentage', 'total_scans', 'successful_scans',
                'campaign_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': ('campaign_config', 'notification_settings'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )

    def progress_display(self, obj):
        """Display campaign progress"""
        if hasattr(obj, 'completion_percentage') and obj.completion_percentage is not None:
            percentage = obj.completion_percentage
            color = 'green' if percentage >= 80 else 'orange' if percentage >= 50 else 'red'
            return format_html(
                '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
                '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                '{}%</div></div>',
                percentage, color, int(percentage)
            )
        return format_html('<span style="color: gray;">Not started</span>')
    progress_display.short_description = 'Progress'

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new campaign
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ================================
# CUSTOM ADMIN VIEWS
# ================================

class QRDashboardAdmin(admin.ModelAdmin):
    """Custom admin view for QR Management Dashboard"""
    
    def changelist_view(self, request, extra_context=None):
        # Get summary statistics
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        stats = {
            'total_scans': QRCodeScan.objects.count(),
            'today_scans': QRCodeScan.objects.filter(timestamp__date=today).count(),
            'week_scans': QRCodeScan.objects.filter(timestamp__date__gte=week_start).count(),
            'month_scans': QRCodeScan.objects.filter(timestamp__date__gte=month_start).count(),
            'success_rate': self.calculate_success_rate(),
            'active_campaigns': QRCampaign.objects.filter(status='ACTIVE').count(),
        }
        
        # Recent scans
        recent_scans = QRCodeScan.objects.select_related(
            'device', 'scanned_by'
        ).order_by('-timestamp')[:10]
        
        # Top scanned devices
        top_devices = QRCodeScan.objects.values(
            'device__device_id', 'device__device_name'
        ).annotate(
            scan_count=Count('id')
        ).order_by('-scan_count')[:10]
        
        extra_context = extra_context or {}
        extra_context.update({
            'stats': stats,
            'recent_scans': recent_scans,
            'top_devices': top_devices,
            'title': 'QR Management Dashboard'
        })
        
        return super().changelist_view(request, extra_context)
    
    def calculate_success_rate(self):
        """Calculate overall success rate"""
        total = QRCodeScan.objects.count()
        if total == 0:
            return 0
        
        # Assuming we have a verification_status field
        successful = QRCodeScan.objects.filter(
            verification_status='SUCCESS'
        ).count() if hasattr(QRCodeScan, 'verification_status') else total
        
        return round((successful / total) * 100, 1)


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Mark selected campaigns as active')
def activate_campaigns(modeladmin, request, queryset):
    updated = queryset.update(status='ACTIVE')
    modeladmin.message_user(request, f'{updated} campaigns were activated.')


@admin.action(description='Mark selected campaigns as completed')
def complete_campaigns(modeladmin, request, queryset):
    updated = queryset.update(status='COMPLETED')
    modeladmin.message_user(request, f'{updated} campaigns were completed.')


@admin.action(description='Export scan data to CSV')
def export_scan_data(modeladmin, request, queryset):
    # This would trigger a CSV export
    count = queryset.count()
    modeladmin.message_user(request, f'Export initiated for {count} scan records.')


@admin.action(description='Delete old scan records (older than 1 year)')
def cleanup_old_scans(modeladmin, request, queryset):
    one_year_ago = timezone.now() - timedelta(days=365)
    old_scans = QRCodeScan.objects.filter(timestamp__lt=one_year_ago)
    count = old_scans.count()
    old_scans.delete()
    modeladmin.message_user(request, f'{count} old scan records were deleted.')


# Add actions to admin classes
QRCampaignAdmin.actions = [activate_campaigns, complete_campaigns]
QRCodeScanAdmin.actions = [export_scan_data, cleanup_old_scans]


# ================================
# REGISTER DASHBOARD VIEW
# ================================

# Register a custom dashboard view
admin.site.register_view('qr_dashboard/', view=QRDashboardAdmin().changelist_view, name='QR Dashboard')


# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - QR Management"
admin.site.site_title = "BPS QR Admin"
admin.site.index_title = "QR Code Management & Analytics"


# ================================
# CUSTOM ADMIN TEMPLATES
# ================================

# Add custom CSS and JavaScript for QR admin
class QRCodeScanAdminMedia:
    css = {
        'all': ('qr_admin/css/qr_admin.css',)
    }
    js = ('qr_admin/js/qr_admin.js',)


# Apply custom media to QR admin classes
QRCodeScanAdmin.Media = QRCodeScanAdminMedia
QRCampaignAdmin.Media = QRCodeScanAdminMedia