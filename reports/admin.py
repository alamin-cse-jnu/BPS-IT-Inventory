# reports/admin.py
# Location: bps_inventory/apps/reports/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    Dashboard, DashboardWidget, CustomQuery, ReportTemplate,
    ScheduledReport, ReportExecution
)

# ================================
# DASHBOARD MANAGEMENT
# ================================

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'owner', 'dashboard_type', 'created_at'  # Fixed field names - removed 'is_shared'
    )
    list_filter = (
        'dashboard_type', 'created_at'  # Fixed field names - removed 'is_shared'
    )
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')  # Fixed field names
    filter_horizontal = ('shared_with_users', 'shared_with_departments')
    
    fieldsets = (
        ('Dashboard Information', {
            'fields': ('name', 'description', 'dashboard_type', 'owner')
        }),
        ('Layout Configuration', {
            'fields': ('layout_config', 'theme_settings'),
            'classes': ('collapse',)
        }),
        ('Sharing Settings', {
            'fields': ('shared_with_users', 'shared_with_departments'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# DASHBOARD WIDGET MANAGEMENT
# ================================

@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'dashboard', 'widget_type', 'position_x', 'position_y', 'size_width', 'size_height'
    )
    list_filter = (
        'widget_type', 'dashboard'  # Fixed field names
    )
    search_fields = ('title', 'dashboard__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Widget Information', {
            'fields': ('title', 'dashboard', 'widget_type')
        }),
        ('Position & Size', {
            'fields': ('position_x', 'position_y', 'size_width', 'size_height')
        }),
        ('Configuration', {
            'fields': ('widget_config', 'data_source_config'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# CUSTOM QUERY MANAGEMENT
# ================================

@admin.register(CustomQuery)
class CustomQueryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'query_type', 'created_by', 'is_public', 'execution_count', 'created_at'
    )
    list_filter = ('query_type', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'execution_count')  # Fixed field names
    
    fieldsets = (
        ('Query Information', {
            'fields': ('name', 'description', 'query_type', 'created_by')
        }),
        ('Query Definition', {
            'fields': ('query_sql', 'query_parameters'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('is_public', 'allowed_users', 'allowed_departments'),
            'classes': ('collapse',)
        }),
        ('Execution Stats', {
            'fields': ('execution_count', 'last_executed_at', 'average_execution_time_ms'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT TEMPLATE MANAGEMENT
# ================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_type', 'category', 'is_system_template', 
        'usage_count', 'created_by', 'created_at'
    )
    list_filter = ('report_type', 'category', 'is_system_template', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'usage_count', 'last_used_at')
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'report_type', 'category')
        }),
        ('Template Configuration', {
            'fields': ('template_config', 'default_parameters'),
            'classes': ('collapse',)
        }),
        ('System Settings', {
            'fields': ('is_system_template', 'created_by'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# SCHEDULED REPORT MANAGEMENT
# ================================

@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_template', 'schedule_type', 'is_active', 
        'next_execution', 'last_execution', 'created_by'
    )
    list_filter = ('schedule_type', 'is_active', 'created_at', 'next_execution')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'created_at', 'updated_at', 'last_execution', 
        'next_execution', 'execution_count'
    )
    filter_horizontal = ('recipients',)
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('name', 'description', 'report_template', 'created_by')
        }),
        ('Schedule Configuration', {
            'fields': (
                'schedule_type', 'schedule_config', 'timezone', 
                'is_active', 'start_date', 'end_date'
            )
        }),
        ('Recipients', {
            'fields': ('recipients', 'additional_emails'),
            'classes': ('collapse',)
        }),
        ('Execution Status', {
            'fields': (
                'last_execution', 'next_execution', 'execution_count', 
                'last_execution_status', 'last_error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT EXECUTION MANAGEMENT
# ================================

@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = (
        'scheduled_report', 'execution_type', 'status', 'started_at', 
        'completed_at', 'execution_time_seconds', 'file_size_bytes'
    )
    list_filter = ('execution_type', 'status', 'started_at', 'completed_at')
    search_fields = ('scheduled_report__name', 'executed_by__username')
    readonly_fields = (
        'started_at', 'completed_at', 'execution_time_seconds', 
        'file_size_bytes', 'error_message', 'execution_log'
    )
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Execution Information', {
            'fields': ('scheduled_report', 'execution_type', 'executed_by')
        }),
        ('Execution Status', {
            'fields': ('status', 'started_at', 'completed_at', 'execution_time_seconds')
        }),
        ('Output Details', {
            'fields': ('output_format', 'file_path', 'file_size_bytes'),
            'classes': ('collapse',)
        }),
        ('Parameters Used', {
            'fields': ('parameters_used',),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': ('error_message', 'execution_log'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# ================================
# CUSTOM ADMIN ACTIONS
# ================================

def mark_dashboards_as_private(modeladmin, request, queryset):
    """Mark selected dashboards as private"""
    updated = queryset.update(is_public=False)
    modeladmin.message_user(
        request, 
        f'{updated} dashboard(s) marked as private.'
    )
mark_dashboards_as_private.short_description = "Mark selected dashboards as private"

def activate_scheduled_reports(modeladmin, request, queryset):
    """Activate selected scheduled reports"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f'{updated} scheduled report(s) activated.'
    )
activate_scheduled_reports.short_description = "Activate selected scheduled reports"

def deactivate_scheduled_reports(modeladmin, request, queryset):
    """Deactivate selected scheduled reports"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} scheduled report(s) deactivated.'
    )
deactivate_scheduled_reports.short_description = "Deactivate selected scheduled reports"

# Add actions to respective admin classes
DashboardAdmin.actions = [mark_dashboards_as_private]
ScheduledReportAdmin.actions = [activate_scheduled_reports, deactivate_scheduled_reports]