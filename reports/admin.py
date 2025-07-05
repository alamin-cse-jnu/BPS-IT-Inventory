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
    ReportSchedule, ReportGeneration
)

# ================================
# DASHBOARD MANAGEMENT
# ================================

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'owner', 'dashboard_type', 'is_active', 'created_at'
    )
    list_filter = (
        'dashboard_type', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('shared_with_users',)
    
    fieldsets = (
        ('Dashboard Information', {
            'fields': ('name', 'description', 'dashboard_type', 'owner')
        }),
        ('Layout Configuration', {
            'fields': ('layout_config',),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('is_public', 'accessible_by_roles', 'shared_with_users'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default'),
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
        'name', 'widget_type', 'is_active', 'created_by', 'created_at'
    )
    list_filter = (
        'widget_type', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Widget Information', {
            'fields': ('id', 'name', 'description', 'widget_type')
        }),
        ('Configuration', {
            'fields': ('config', 'data_source', 'refresh_interval'),
            'classes': ('collapse',)
        }),
        ('Status & Permissions', {
            'fields': ('is_active', 'is_system_widget', 'created_by'),
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
        'name', 'query_type', 'security_level', 'is_active', 'created_by', 'created_at'
    )
    list_filter = ('query_type', 'security_level', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'last_executed', 'execution_count')
    
    fieldsets = (
        ('Query Information', {
            'fields': ('name', 'description', 'query_type', 'created_by')
        }),
        ('Query Definition', {
            'fields': ('sql_query', 'parameters'),
            'classes': ('collapse',)
        }),
        ('Security & Access', {
            'fields': ('security_level', 'allowed_users', 'allowed_groups'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'timeout_seconds', 'cache_duration'),
            'classes': ('collapse',)
        }),
        ('Execution Statistics', {
            'fields': ('last_executed', 'execution_count'),
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
        'name', 'report_type', 'category', 'is_active', 'is_system_template', 'usage_count', 'created_by'
    )
    list_filter = ('report_type', 'category', 'is_active', 'is_system_template', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'usage_count', 'last_used')
    
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
            'fields': ('usage_count', 'last_used'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT SCHEDULE MANAGEMENT (Previously ScheduledReport)
# ================================

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template', 'frequency', 'is_active', 
        'next_run', 'last_run', 'created_by'
    )
    list_filter = ('frequency', 'is_active', 'created_at', 'next_run')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'created_at', 'updated_at', 'last_run', 
        'next_run', 'run_count'
    )
    filter_horizontal = ('notify_users',)
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('name', 'description', 'template', 'created_by')
        }),
        ('Schedule Configuration', {
            'fields': (
                'frequency', 'time_of_day', 'day_of_week', 'day_of_month',
                'custom_schedule', 'is_active', 'start_date', 'end_date'
            )
        }),
        ('Report Settings', {
            'fields': ('default_format', 'filters'),
            'classes': ('collapse',)
        }),
        ('Recipients', {
            'fields': ('email_recipients', 'notify_users'),
            'classes': ('collapse',)
        }),
        ('Execution Status', {
            'fields': (
                'last_run', 'next_run', 'run_count', 'failure_count'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT GENERATION MANAGEMENT (Previously ReportExecution)
# ================================

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'report_name', 'template', 'status', 'file_format', 
        'generated_by', 'created_at', 'file_size_human'
    )
    list_filter = ('status', 'file_format', 'priority', 'created_at')
    search_fields = ('report_name', 'template__name', 'generated_by__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'file_size', 'file_size_human'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_name', 'template', 'generated_by')
        }),
        ('Generation Settings', {
            'fields': ('file_format', 'priority', 'parameters')
        }),
        ('Status & Timing', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
        ('Output Details', {
            'fields': ('file_path', 'file_size', 'file_size_human'),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id',),
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

# Add actions to the admin classes
DashboardAdmin.actions = [mark_dashboards_as_private]
ReportScheduleAdmin.actions = [activate_scheduled_reports, deactivate_scheduled_reports]