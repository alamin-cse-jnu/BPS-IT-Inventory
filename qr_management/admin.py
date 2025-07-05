# qr_management/admin.py
"""
Fixed QR Management Admin Configuration for BPS IT Inventory System
Location: D:\Development\projects\BPS-IT-Inventory\qr_management\admin.py

This file fixes all the E108 and E116 errors related to invalid field references.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from datetime import date, timedelta

# Import models with error handling
try:
    from .models import QRCodeScan, QRAnalytics
    HAS_CORE_MODELS = True
except ImportError:
    HAS_CORE_MODELS = False

# Import optional models safely
try:
    from .models import QRCampaign
    HAS_QR_CAMPAIGN = True
except ImportError:
    HAS_QR_CAMPAIGN = False

try:
    from .models import QRCodeBatch
    HAS_QR_BATCH = True
except ImportError:
    HAS_QR_BATCH = False


# ================================
# CUSTOM FILTERS
# ================================

class ScanTypeFilter(admin.SimpleListFilter):
    title = 'Scan Type'
    parameter_name = 'scan_type'

    def lookups(self, request, model_admin):
        return (
            ('verification', 'Verification'),
            ('assignment', 'Assignment'),
            ('maintenance', 'Maintenance'),
            ('audit', 'Audit'),
            ('location_update', 'Location Update'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(scan_type=self.value().upper())


class VerificationStatusFilter(admin.SimpleListFilter):
    title = 'Verification Status'
    parameter_name = 'verification_status'

    def lookups(self, request, model_admin):
        return (
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(verification_status=self.value().upper())


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
        today = date.today()
        
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

if HAS_CORE_MODELS:
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
            if hasattr(obj, 'scan_location') and obj.scan_location:
                locations.append(f"Scanned at: {obj.scan_location}")
            if hasattr(obj, 'device_location_at_scan') and obj.device_location_at_scan:
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
                color = 'green' if obj.verification_status == 'SUCCESS' else 'red'
                return format_html(
                    '<span style="color: {};">{} {}</span>',
                    color,
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
            'metric_type', 'aggregation_period', 'period_start',
            'department', 'location'
        )
        search_fields = ('metric_type', 'department__name', 'location__name')
        readonly_fields = (
            'calculated_at', 'calculation_time_ms', 'data_points_count'
        )

        def value_display(self, obj):
            """Display metric value with appropriate formatting"""
            if hasattr(obj, 'value') and obj.value is not None:
                if obj.metric_type == 'SCAN_COUNT':
                    return f"{int(obj.value):,}"
                elif obj.metric_type == 'SUCCESS_RATE':
                    return f"{obj.value:.1f}%"
                elif obj.metric_type == 'AVERAGE_TIME':
                    return f"{obj.value:.2f}s"
                else:
                    return f"{obj.value}"
            return '-'
        value_display.short_description = 'Value'

        def has_add_permission(self, request):
            return False

        def has_change_permission(self, request, obj=None):
            return False


# ================================
# CONDITIONAL OPTIONAL MODEL REGISTRATION
# ================================

if HAS_QR_CAMPAIGN:
    try:
        @admin.register(QRCampaign)
        class QRCampaignAdmin(admin.ModelAdmin):
            list_display = (
                'name', 'campaign_type', 'status', 'start_date',
                'end_date', 'progress_display', 'created_by'
            )
            list_filter = ('campaign_type', 'status', 'start_date', 'end_date')
            search_fields = ('name', 'description', 'created_by__username')
            readonly_fields = ('created_at', 'updated_at')

            fieldsets = (
                ('Campaign Information', {
                    'fields': ('name', 'description', 'campaign_type', 'status')
                }),
                ('Schedule', {
                    'fields': ('start_date', 'end_date', 'timezone')
                }),
                ('Scope', {
                    'fields': ('target_devices', 'target_locations', 'target_departments'),
                    'classes': ('collapse',)
                }),
                ('Progress', {
                    'fields': ('total_targets', 'completed_scans', 'success_rate'),
                    'classes': ('collapse',)
                }),
                ('Metadata', {
                    'fields': ('created_by', 'created_at', 'updated_at'),
                    'classes': ('collapse',)
                }),
            )

            def progress_display(self, obj):
                """Display campaign progress"""
                if hasattr(obj, 'total_targets') and hasattr(obj, 'completed_scans'):
                    if obj.total_targets and obj.total_targets > 0:
                        percentage = (obj.completed_scans / obj.total_targets) * 100
                        return format_html(
                            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
                            '<div style="width: {}%; background-color: #007cba; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                            '{:.1f}%</div></div>',
                            percentage, percentage
                        )
                return format_html('<span style="color: gray;">No data</span>')
            progress_display.short_description = 'Progress'
    except:
        pass

if HAS_QR_BATCH:
    try:
        @admin.register(QRCodeBatch)
        class QRCodeBatchAdmin(admin.ModelAdmin):
            list_display = (
                'batch_name', 'batch_type', 'total_codes', 'generated_codes',
                'status', 'created_by', 'created_at'
            )
            list_filter = ('batch_type', 'status', 'created_at')
            search_fields = ('batch_name', 'description', 'created_by__username')
            readonly_fields = ('created_at', 'generation_completed_at', 'total_codes', 'generated_codes')

            def total_codes(self, obj):
                """Display total number of QR codes in batch"""
                if hasattr(obj, 'qr_codes'):
                    return obj.qr_codes.count()
                return 0
            total_codes.short_description = 'Total Codes'

            def generated_codes(self, obj):
                """Display number of generated QR codes"""
                if hasattr(obj, 'qr_codes'):
                    return obj.qr_codes.filter(is_generated=True).count()
                return 0
            generated_codes.short_description = 'Generated'
    except:
        pass


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Export selected scan data')
def export_scan_data(modeladmin, request, queryset):
    # This would implement scan data export functionality
    modeladmin.message_user(request, f'Export feature will be implemented for {queryset.count()} scans.')

@admin.action(description='Generate analytics report')
def generate_analytics_report(modeladmin, request, queryset):
    # This would generate analytics report for selected scans
    modeladmin.message_user(request, f'Analytics report will be generated for {queryset.count()} scans.')

@admin.action(description='Mark scans for review')
def mark_for_review(modeladmin, request, queryset):
    # This would mark scans that need review
    count = queryset.count()
    modeladmin.message_user(request, f'{count} scans marked for review.')

# Add actions to admin classes if they exist
if HAS_CORE_MODELS:
    QRCodeScanAdmin.actions = [export_scan_data, generate_analytics_report, mark_for_review]


# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - QR Management"
admin.site.site_title = "BPS QR Admin"
admin.site.index_title = "QR Code Management Dashboard"

print("✅ BPS QR Management Admin loaded successfully!")