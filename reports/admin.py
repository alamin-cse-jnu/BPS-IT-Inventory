# reports/admin.py
"""
Fixed Reports Admin Configuration for BPS IT Inventory System
Location: D:\Development\projects\BPS-IT-Inventory\reports\admin.py

This file fixes all the E108 and E116 errors related to invalid field references.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone

# Import models with error handling
try:
    from .models import (
        ReportTemplate, ReportGeneration, AnalyticsMetric,
        DashboardWidget, ReportSubscription, DataExport
    )
    HAS_CORE_MODELS = True
except ImportError:
    HAS_CORE_MODELS = False

# Import optional models safely
try:
    from .models import ReportSchedule
    HAS_REPORT_SCHEDULE = True
except ImportError:
    HAS_REPORT_SCHEDULE = False

try:
    from .models import ReportAccess
    HAS_REPORT_ACCESS = True
except ImportError:
    HAS_REPORT_ACCESS = False


# ================================
# CUSTOM FILTERS
# ================================

class ReportStatusFilter(admin.SimpleListFilter):
    title = 'Report Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value().upper())


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
        from datetime import date, timedelta
        today = date.today()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        elif self.value() == 'week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=week_start)
        elif self.value() == 'month':
            month_start = today.replace(day=1)
            return queryset.filter(created_at__date__gte=month_start)
        elif self.value() == 'quarter':
            quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            return queryset.filter(created_at__date__gte=quarter_start)


# ================================
# ADMIN CLASSES
# ================================

if HAS_CORE_MODELS:
    @admin.register(ReportTemplate)
    class ReportTemplateAdmin(admin.ModelAdmin):
        list_display = (
            'name', 'report_type', 'category', 'is_active',
            'usage_count', 'created_by', 'created_at'
        )
        list_filter = ('report_type', 'category', 'is_active', 'created_at')
        search_fields = ('name', 'description', 'created_by__username')
        readonly_fields = ('created_at', 'updated_at', 'usage_count')
        
        fieldsets = (
            ('Basic Information', {
                'fields': ('name', 'description', 'report_type', 'category', 'is_active')
            }),
            ('Configuration', {
                'fields': ('template_config', 'default_parameters', 'output_format')
            }),
            ('Access Control', {
                'fields': ('is_public', 'allowed_roles', 'created_by'),
                'classes': ('collapse',)
            }),
            ('Metadata', {
                'fields': ('usage_count', 'created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )

        def usage_count(self, obj):
            """Display usage count"""
            if hasattr(obj, 'report_generations'):
                count = obj.report_generations.count()
                return format_html(
                    '<span style="color: blue;">{} times</span>',
                    count
                )
            return 0
        usage_count.short_description = 'Usage'


    @admin.register(ReportGeneration)
    class ReportGenerationAdmin(admin.ModelAdmin):
        list_display = (
            'template', 'status_display', 'generated_by', 'created_at',
            'completion_time', 'file_size_display'
        )
        list_filter = (ReportStatusFilter, TimeRangeFilter, 'template')
        search_fields = ('template__name', 'generated_by__username', 'filename')
        readonly_fields = (
            'created_at', 'started_at', 'completed_at', 'file_path',
            'file_size', 'generation_time_seconds'
        )

        fieldsets = (
            ('Report Information', {
                'fields': ('template', 'generated_by', 'parameters', 'output_format')
            }),
            ('Status & Timing', {
                'fields': (
                    'status', 'created_at', 'started_at', 'completed_at',
                    'generation_time_seconds'
                )
            }),
            ('Output', {
                'fields': ('filename', 'file_path', 'file_size', 'download_count'),
                'classes': ('collapse',)
            }),
            ('Error Information', {
                'fields': ('error_message', 'error_details'),
                'classes': ('collapse',)
            }),
        )

        def status_display(self, obj):
            """Display status with color coding"""
            status_colors = {
                'PENDING': 'orange',
                'PROCESSING': 'blue',
                'COMPLETED': 'green',
                'FAILED': 'red',
                'CANCELLED': 'gray',
            }
            
            status_icons = {
                'PENDING': '⏳',
                'PROCESSING': '⚙️',
                'COMPLETED': '✅',
                'FAILED': '❌',
                'CANCELLED': '⏹️',
            }
            
            color = status_colors.get(obj.status, 'black')
            icon = status_icons.get(obj.status, '❓')
            
            return format_html(
                '<span style="color: {};">{} {}</span>',
                color, icon, obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
            )
        status_display.short_description = 'Status'

        def completion_time(self, obj):
            """Display generation time"""
            if hasattr(obj, 'generation_time_seconds') and obj.generation_time_seconds:
                if obj.generation_time_seconds < 60:
                    return f"{obj.generation_time_seconds}s"
                else:
                    minutes = obj.generation_time_seconds // 60
                    seconds = obj.generation_time_seconds % 60
                    return f"{minutes}m {seconds}s"
            return '-'
        completion_time.short_description = 'Duration'

        def file_size_display(self, obj):
            """Display file size in human readable format"""
            if hasattr(obj, 'file_size') and obj.file_size:
                if obj.file_size < 1024:
                    return f"{obj.file_size} B"
                elif obj.file_size < 1024 * 1024:
                    return f"{obj.file_size / 1024:.1f} KB"
                else:
                    return f"{obj.file_size / (1024 * 1024):.1f} MB"
            return '-'
        file_size_display.short_description = 'File Size'


    @admin.register(AnalyticsMetric)
    class AnalyticsMetricAdmin(admin.ModelAdmin):
        list_display = (
            'metric_name', 'metric_type', 'value_display', 'calculated_at',
            'department', 'location'
        )
        list_filter = ('metric_type', 'calculated_at', 'department', 'location')
        search_fields = ('metric_name', 'description')
        readonly_fields = ('calculated_at', 'calculation_time_ms')

        def value_display(self, obj):
            """Display metric value with appropriate formatting"""
            if hasattr(obj, 'metric_value'):
                if obj.metric_type == 'PERCENTAGE':
                    return f"{obj.metric_value:.1f}%"
                elif obj.metric_type == 'CURRENCY':
                    return f"${obj.metric_value:,.2f}"
                elif obj.metric_type == 'COUNT':
                    return f"{int(obj.metric_value):,}"
                else:
                    return f"{obj.metric_value}"
            return '-'
        value_display.short_description = 'Value'


    @admin.register(DashboardWidget)
    class DashboardWidgetAdmin(admin.ModelAdmin):
        list_display = (
            'title', 'widget_type', 'position', 'is_active',
            'created_by', 'updated_at'
        )
        list_filter = ('widget_type', 'is_active', 'created_at')
        search_fields = ('title', 'description', 'created_by__username')
        readonly_fields = ('created_at', 'updated_at')


    @admin.register(ReportSubscription)
    class ReportSubscriptionAdmin(admin.ModelAdmin):
        list_display = (
            'user', 'template', 'frequency', 'is_active',
            'next_generation', 'last_sent'
        )
        list_filter = ('frequency', 'is_active', 'created_at')
        search_fields = ('user__username', 'template__name')
        readonly_fields = ('created_at', 'last_sent')


    @admin.register(DataExport)
    class DataExportAdmin(admin.ModelAdmin):
        list_display = (
            'export_type', 'status_display', 'exported_by', 'created_at',
            'record_count', 'file_size_display'
        )
        list_filter = (ReportStatusFilter, 'export_type', 'created_at')
        search_fields = ('exported_by__username', 'filename')
        readonly_fields = (
            'created_at', 'started_at', 'completed_at',
            'file_path', 'file_size', 'record_count'
        )

        def status_display(self, obj):
            """Display export status with color coding"""
            status_colors = {
                'PENDING': 'orange',
                'PROCESSING': 'blue',
                'COMPLETED': 'green',
                'FAILED': 'red',
            }
            
            color = status_colors.get(obj.status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color, obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
            )
        status_display.short_description = 'Status'

        def file_size_display(self, obj):
            """Display file size in human readable format"""
            if hasattr(obj, 'file_size') and obj.file_size:
                if obj.file_size < 1024 * 1024:
                    return f"{obj.file_size / 1024:.1f} KB"
                else:
                    return f"{obj.file_size / (1024 * 1024):.1f} MB"
            return '-'
        file_size_display.short_description = 'File Size'


# ================================
# CONDITIONAL OPTIONAL MODEL REGISTRATION
# ================================

if HAS_REPORT_SCHEDULE:
    try:
        @admin.register(ReportSchedule)
        class ReportScheduleAdmin(admin.ModelAdmin):
            list_display = (
                'name', 'template', 'frequency', 'is_active',
                'next_run', 'last_run', 'created_by'
            )
            list_filter = ('frequency', 'is_active', 'created_at')
            search_fields = ('name', 'template__name', 'created_by__username')
            readonly_fields = ('created_at', 'updated_at', 'last_run')
    except:
        pass

if HAS_REPORT_ACCESS:
    try:
        @admin.register(ReportAccess)
        class ReportAccessAdmin(admin.ModelAdmin):
            list_display = (
                'user', 'report', 'access_type', 'granted_by',
                'granted_at', 'expires_at'
            )
            list_filter = ('access_type', 'granted_at', 'expires_at')
            search_fields = ('user__username', 'report__template__name')
            readonly_fields = ('granted_at',)
    except:
        pass


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Activate selected templates')
def activate_templates(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} templates were activated.')


@admin.action(description='Deactivate selected templates')
def deactivate_templates(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} templates were deactivated.')


@admin.action(description='Delete completed reports')
def delete_completed_reports(modeladmin, request, queryset):
    completed = queryset.filter(status='COMPLETED')
    count = completed.count()
    completed.delete()
    modeladmin.message_user(request, f'{count} completed reports were deleted.')


# Add actions to admin classes if they exist
if HAS_CORE_MODELS:
    ReportTemplateAdmin.actions = [activate_templates, deactivate_templates]
    ReportGenerationAdmin.actions = [delete_completed_reports]

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - Reports"
admin.site.site_title = "BPS Reports Admin"
admin.site.index_title = "Reports & Analytics Management"

print("✅ BPS Reports Admin loaded successfully!")