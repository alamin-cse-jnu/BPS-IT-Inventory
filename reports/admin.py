# reports/admin.py
# Location: bps_inventory/apps/reports/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    ReportTemplate, ReportGeneration, ReportSchedule, ReportAccess,
    Dashboard, DashboardWidget, CustomQuery, ReportCache, 
    ReportSubscription
)

# ================================
# REPORT TEMPLATE MANAGEMENT
# ================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_type', 'category', 'usage_count', 
        'last_used', 'is_active', 'is_system_template'
    )
    list_filter = (
        'report_type', 'category', 'is_active', 'is_system_template',
        'created_at', 'last_used'
    )
    search_fields = ('name', 'description')
    readonly_fields = (
        'created_at', 'updated_at', 'last_used', 'usage_count'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'report_type', 'category')
        }),
        ('Template Configuration', {
            'fields': ('template_config', 'columns', 'filters', 'sorting'),
            'classes': ('collapse',)
        }),
        ('Advanced Settings', {
            'fields': ('sql_query',),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('accessible_by_roles', 'requires_approval'),
            'classes': ('collapse',)
        }),
        ('Template Metadata', {
            'fields': (
                'is_active', 'is_system_template', 'version',
                'usage_count', 'last_used'
            )
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'report_name', 'template', 'generated_by', 'status', 
        'file_format', 'progress_percentage', 'created_at', 'file_size_display'
    )
    list_filter = (
        'status', 'file_format', 'priority', 'template', 'created_at'
    )
    search_fields = (
        'report_name', 'template__name', 'generated_by__username'
    )
    readonly_fields = (
        'created_at', 'started_at', 'completed_at', 'generation_time_seconds',
        'query_time_seconds', 'file_size_display', 'download_count'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('template', 'report_name', 'generated_by', 'status')
        }),
        ('Generation Parameters', {
            'fields': (
                'file_format', 'priority', 'filters_applied', 'parameters',
                'date_range_start', 'date_range_end'
            )
        }),
        ('Progress Tracking', {
            'fields': ('progress_percentage', 'current_step'),
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': (
                'file_path', 'file_size_display', 'record_count', 
                'download_count', 'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'created_at', 'started_at', 'completed_at',
                'generation_time_seconds', 'query_time_seconds'
            ),
            'classes': ('collapse',)
        }),
        ('Sharing', {
            'fields': ('is_shared', 'shared_with_users'),
            'classes': ('collapse',)
        })
    )
    
    def file_size_display(self, obj):
        if obj.file_size:
            return obj.file_size_human
        return 'N/A'
    file_size_display.short_description = 'File Size'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'template', 'generated_by'
        ).prefetch_related('shared_with_users')

# ================================
# REPORT SCHEDULING
# ================================

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template', 'frequency', 'time_of_day', 
        'is_active', 'last_run', 'next_run', 'run_count'
    )
    list_filter = (
        'frequency', 'is_active', 'created_at', 'last_run'
    )
    search_fields = ('name', 'template__name')
    readonly_fields = (
        'last_run', 'next_run', 'run_count', 'failure_count',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('name', 'template', 'is_active')
        }),
        ('Schedule Configuration', {
            'fields': (
                'frequency', 'time_of_day', 'day_of_week', 
                'day_of_month', 'custom_schedule'
            )
        }),
        ('Report Settings', {
            'fields': ('default_format', 'filters')
        }),
        ('Recipients', {
            'fields': ('email_recipients', 'notify_users')
        }),
        ('Execution Status', {
            'fields': (
                'last_run', 'next_run', 'run_count', 'failure_count'
            ),
            'classes': ('collapse',)
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'report_template', 'frequency', 'delivery_method',
        'is_active', 'last_generated', 'generation_count'
    )
    list_filter = (
        'frequency', 'delivery_method', 'is_active', 'created_at'
    )
    search_fields = (
        'user__username', 'user__email', 'report_template__name'
    )
    readonly_fields = (
        'last_generated', 'next_scheduled', 'generation_count',
        'failure_count', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('user', 'report_template', 'is_active')
        }),
        ('Schedule Configuration', {
            'fields': (
                'frequency', 'delivery_time', 'day_of_week', 'day_of_month'
            )
        }),
        ('Delivery Settings', {
            'fields': (
                'delivery_method', 'email_recipients', 'export_format',
                'include_charts', 'include_raw_data'
            )
        }),
        ('Filter Parameters', {
            'fields': ('filter_parameters',),
            'classes': ('collapse',)
        }),
        ('Status Tracking', {
            'fields': (
                'last_generated', 'next_scheduled', 'generation_count',
                'failure_count', 'last_error'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# DASHBOARD MANAGEMENT
# ================================

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'dashboard_type', 'owner', 'widget_count', 
        'is_shared', 'is_active', 'last_accessed'
    )
    list_filter = (
        'dashboard_type', 'is_shared', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = (
        'last_accessed', 'access_count', 'created_at', 'updated_at'
    )
    
    def widget_count(self, obj):
        count = obj.widgets.count()
        if count > 0:
            url = reverse('admin:reports_dashboardwidget_changelist')
            return format_html(
                '<a href="{}?dashboard__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    widget_count.short_description = 'Widgets'

@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'dashboard', 'widget_type', 'position_x', 
        'position_y', 'size_width', 'size_height', 'is_active'
    )
    list_filter = ('widget_type', 'dashboard', 'is_active')
    search_fields = ('title', 'dashboard__name')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# ANALYTICS & ACCESS
# ================================

@admin.register(ReportAccess)
class ReportAccessAdmin(admin.ModelAdmin):
    list_display = (
        'report_generation', 'accessed_by', 'access_type', 
        'accessed_at', 'ip_address'
    )
    list_filter = ('access_type', 'accessed_at')
    search_fields = (
        'accessed_by__username', 'report_generation__report_name',
        'ip_address'
    )
    date_hierarchy = 'accessed_at'
    readonly_fields = ('accessed_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(CustomQuery)
class CustomQueryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'query_type', 'security_level', 'execution_count',
        'is_active', 'created_by', 'created_at'
    )
    list_filter = (
        'query_type', 'security_level', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'execution_count', 'last_executed', 'average_execution_time',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Query Information', {
            'fields': ('name', 'description', 'query_type', 'is_active')
        }),
        ('Query Definition', {
            'fields': ('sql_query',)
        }),
        ('Security & Access', {
            'fields': (
                'security_level', 'allowed_users', 'allowed_groups'
            )
        }),
        ('Execution Settings', {
            'fields': ('timeout_seconds', 'max_rows'),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'execution_count', 'last_executed', 'average_execution_time'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(ReportCache)
class ReportCacheAdmin(admin.ModelAdmin):
    list_display = (
        'cache_key', 'report_template', 'user', 'file_format',
        'file_size_display', 'status', 'hit_count', 'expires_at'
    )
    list_filter = ('status', 'file_format', 'created_at', 'expires_at')
    search_fields = ('cache_key', 'report_template__name', 'user__username')
    readonly_fields = (
        'cache_key', 'parameters_hash', 'data_hash', 
        'created_at', 'last_accessed', 'hit_count', 'generation_time'
    )
    
    def file_size_display(self, obj):
        if obj.file_size:
            for unit in ['bytes', 'KB', 'MB', 'GB']:
                if obj.file_size < 1024.0:
                    return f"{obj.file_size:.1f} {unit}"
                obj.file_size /= 1024.0
            return f"{obj.file_size:.1f} TB"
        return 'N/A'
    file_size_display.short_description = 'File Size'
    
    def has_add_permission(self, request):
        return False

# ================================
# ADMIN CUSTOMIZATION
# ================================

admin.site.site_header = "BPS IT Inventory - Reports Management"
admin.site.site_title = "BPS Reports Admin"
admin.site.index_title = "Reports & Analytics Dashboard"