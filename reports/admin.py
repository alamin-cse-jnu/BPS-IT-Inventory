# reports/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import (
    ReportTemplate, ReportGeneration, ReportSubscription,
    AnalyticsMetric, DashboardWidget, DataExport
)


# ================================
# CUSTOM FILTERS
# ================================

class ReportStatusFilter(admin.SimpleListFilter):
    title = 'Report Status'
    parameter_name = 'report_status'

    def lookups(self, request, model_admin):
        return (
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('pending', 'Pending'),
            ('processing', 'Processing'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value().upper())


class ReportTypeFilter(admin.SimpleListFilter):
    title = 'Report Type'
    parameter_name = 'report_type'

    def lookups(self, request, model_admin):
        return (
            ('INVENTORY', 'Inventory Reports'),
            ('ASSIGNMENT', 'Assignment Reports'),
            ('MAINTENANCE', 'Maintenance Reports'),
            ('ANALYTICS', 'Analytics Reports'),
            ('AUDIT', 'Audit Reports'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(report_type=self.value())


# ================================
# INLINE ADMIN CLASSES
# ================================

class ReportSubscriptionInline(admin.TabularInline):
    model = ReportSubscription
    extra = 0
    readonly_fields = ('created_at', 'last_generated')
    fields = (
        'user', 'frequency', 'email_delivery', 'is_active',
        'created_at', 'last_generated'
    )


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = (
        'widget_type', 'title', 'position_x', 'position_y',
        'width', 'height', 'is_active'
    )


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_type', 'category', 'usage_count',
        'is_active', 'requires_approval', 'created_by', 'created_at'
    )
    list_filter = (
        ReportTypeFilter, 'category', 'is_active', 'requires_approval', 'created_at'
    )
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'usage_count')
    inlines = [ReportSubscriptionInline, DashboardWidgetInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'report_type', 'category', 'is_active')
        }),
        ('Template Configuration', {
            'fields': ('template_config', 'sql_query'),
            'classes': ('collapse',)
        }),
        ('Report Structure', {
            'fields': ('columns', 'filters', 'sorting', 'grouping'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': (
                'accessible_by_roles', 'requires_approval', 'approval_workflow',
                'max_records_limit', 'execution_timeout'
            ),
            'classes': ('collapse',)
        }),
        ('Scheduling & Automation', {
            'fields': (
                'can_be_scheduled', 'default_frequency', 'auto_cleanup_days'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'usage_count'),
            'classes': ('collapse',)
        }),
    )

    def usage_count(self, obj):
        """Count how many times this template has been used"""
        count = obj.report_generations.count() if hasattr(obj, 'report_generations') else 0
        return format_html(
            '<a href="{}?template__id__exact={}">{} times</a>',
            reverse('admin:reports_reportgeneration_changelist'),
            obj.id,
            count
        )
    usage_count.short_description = 'Usage'

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new template
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'report_name', 'template', 'status', 'generated_by',
        'created_at', 'completion_time', 'file_size_display', 'actions'
    )
    list_filter = (
        ReportStatusFilter, 'template__report_type', 'format',
        'created_at', 'completion_time'
    )
    search_fields = (
        'report_name', 'template__name', 'generated_by__username'
    )
    readonly_fields = (
        'created_at', 'started_at', 'completion_time',
        'execution_time_seconds', 'file_size', 'record_count'
    )
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_name', 'template', 'status', 'format')
        }),
        ('Generation Details', {
            'fields': (
                'generated_by', 'parameters', 'filters_applied'
            )
        }),
        ('Execution Timeline', {
            'fields': (
                'created_at', 'started_at', 'completion_time',
                'execution_time_seconds'
            )
        }),
        ('Results', {
            'fields': (
                'file_path', 'file_size', 'record_count',
                'error_message', 'generation_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Delivery & Access', {
            'fields': (
                'email_sent', 'download_count', 'expires_at',
                'is_public', 'access_token'
            ),
            'classes': ('collapse',)
        }),
    )

    def report_name(self, obj):
        """Display report name with download link if available"""
        if obj.status == 'COMPLETED' and obj.file_path:
            return format_html(
                '<a href="/reports/download/{}" target="_blank">{}</a>',
                obj.id,
                obj.report_name or f"Report #{obj.id}"
            )
        return obj.report_name or f"Report #{obj.id}"
    report_name.short_description = 'Report Name'

    def completion_time(self, obj):
        """Display formatted completion time"""
        if obj.completion_time:
            return obj.completion_time.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    completion_time.short_description = 'Completed At'

    def file_size_display(self, obj):
        """Display formatted file size"""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return '-'
    file_size_display.short_description = 'File Size'

    def actions(self, obj):
        """Custom action links"""
        actions_html = []
        
        if obj.status == 'COMPLETED' and obj.file_path:
            actions_html.append(
                f'<a href="/reports/download/{obj.id}/" target="_blank">Download</a>'
            )
        
        if obj.status == 'FAILED':
            actions_html.append(
                f'<a href="/reports/regenerate/{obj.id}/">Retry</a>'
            )
        
        if obj.email_sent:
            actions_html.append('📧 Sent')
        elif obj.status == 'COMPLETED':
            actions_html.append(
                f'<a href="/reports/email/{obj.id}/">Email</a>'
            )
        
        return format_html(' | '.join(actions_html))
    actions.short_description = 'Actions'

    def has_add_permission(self, request):
        return False


@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'template', 'frequency', 'email_delivery',
        'is_active', 'last_generated', 'next_generation'
    )
    list_filter = ('frequency', 'email_delivery', 'is_active', 'created_at')
    search_fields = ('user__username', 'template__name')
    readonly_fields = ('created_at', 'last_generated', 'generation_count')
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('user', 'template', 'frequency', 'is_active')
        }),
        ('Delivery Options', {
            'fields': ('email_delivery', 'custom_parameters')
        }),
        ('Schedule & Status', {
            'fields': (
                'next_generation', 'last_generated', 'generation_count'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def next_generation(self, obj):
        """Calculate next generation time"""
        if obj.last_generated and obj.is_active:
            from datetime import timedelta
            
            frequency_days = {
                'DAILY': 1,
                'WEEKLY': 7,
                'MONTHLY': 30,
                'QUARTERLY': 90,
            }
            
            if obj.frequency in frequency_days:
                days = frequency_days[obj.frequency]
                next_date = obj.last_generated + timedelta(days=days)
                return next_date.strftime('%Y-%m-%d')
        
        return 'Not scheduled'
    next_generation.short_description = 'Next Generation'


@admin.register(AnalyticsMetric)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = (
        'metric_name', 'metric_type', 'value_display',
        'department', 'location', 'calculated_at'
    )
    list_filter = (
        'metric_type', 'aggregation_period', 'department',
        'location', 'calculated_at'
    )
    search_fields = ('metric_name', 'description')
    readonly_fields = (
        'calculated_at', 'calculation_time_ms', 'data_points_count'
    )
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_name', 'metric_type', 'description')
        }),
        ('Values & Aggregation', {
            'fields': (
                'value', 'aggregation_period', 'period_start', 'period_end'
            )
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
        if obj.metric_type in ['COUNT', 'PERCENTAGE']:
            return f"{obj.value:,.0f}"
        else:
            return f"{obj.value:,.2f}"
    value_display.short_description = 'Value'

    def has_add_permission(self, request):
        return False


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'widget_type', 'template', 'position_display',
        'size_display', 'is_active', 'created_by'
    )
    list_filter = ('widget_type', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'template__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Widget Information', {
            'fields': ('title', 'description', 'widget_type', 'template')
        }),
        ('Layout & Position', {
            'fields': (
                'position_x', 'position_y', 'width', 'height', 'z_index'
            )
        }),
        ('Configuration', {
            'fields': ('widget_config', 'refresh_interval', 'is_active'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('accessible_by_roles', 'requires_data_permission'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def position_display(self, obj):
        """Display widget position"""
        return f"({obj.position_x}, {obj.position_y})"
    position_display.short_description = 'Position'

    def size_display(self, obj):
        """Display widget size"""
        return f"{obj.width} × {obj.height}"
    size_display.short_description = 'Size'

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new widget
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = (
        'export_name', 'export_type', 'status', 'exported_by',
        'created_at', 'completion_time', 'file_size_display'
    )
    list_filter = ('export_type', 'status', 'format', 'created_at')
    search_fields = ('export_name', 'exported_by__username')
    readonly_fields = (
        'created_at', 'completion_time', 'file_size', 'record_count'
    )
    
    fieldsets = (
        ('Export Information', {
            'fields': ('export_name', 'export_type', 'status', 'format')
        }),
        ('Export Details', {
            'fields': ('exported_by', 'query_parameters', 'filters_applied')
        }),
        ('Results', {
            'fields': (
                'file_path', 'file_size', 'record_count',
                'created_at', 'completion_time'
            )
        }),
        ('Access & Security', {
            'fields': ('access_token', 'expires_at', 'download_count'),
            'classes': ('collapse',)
        }),
    )

    def file_size_display(self, obj):
        """Display formatted file size"""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return '-'
    file_size_display.short_description = 'File Size'

    def has_add_permission(self, request):
        return False


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


# Add actions to admin classes
ReportTemplateAdmin.actions = [activate_templates, deactivate_templates]
ReportGenerationAdmin.actions = [delete_completed_reports]

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - Reports"
admin.site.site_title = "BPS Reports Admin"
admin.site.index_title = "Reports & Analytics Management"