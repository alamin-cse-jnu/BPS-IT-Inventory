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
            'fields': ('config', 'data_source'),
            'classes': ('collapse',)
        }),
        ('Display Settings', {
            'fields': ('is_active', 'refresh_interval'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# CUSTOM QUERY MANAGEMENT
# ================================

@admin.register(CustomQuery)
class CustomQueryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'query_type', 'is_active', 'created_by', 'created_at'
    )
    list_filter = (
        'query_type', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'last_executed')
    
    fieldsets = (
        ('Query Information', {
            'fields': ('name', 'description', 'query_type')
        }),
        ('Query Configuration', {
            'fields': ('sql_query', 'parameters'),
            'classes': ('collapse',)
        }),
        ('Execution Settings', {
            'fields': ('is_active', 'timeout_seconds'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'last_executed'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT TEMPLATE MANAGEMENT
# ================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_type', 'is_active', 'created_by', 'created_at'
    )
    list_filter = (
        'report_type', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'report_type')
        }),
        ('Template Configuration', {
            'fields': ('template_config', 'sql_query', 'columns', 'filters', 'sorting'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_system_template'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# REPORT SCHEDULE MANAGEMENT
# ================================

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'get_report_template', 'frequency', 'is_active', 
        'next_run', 'last_run'
    )
    list_filter = (
        'frequency', 'is_active', 'next_run', 'last_run'
    )
    search_fields = ('name', 'template__name')
    readonly_fields = ('created_at', 'updated_at', 'last_run', 'next_run')
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('name', 'template', 'frequency')
        }),
        ('Schedule Configuration', {
            'fields': ('time_of_day', 'day_of_week', 'day_of_month', 'custom_schedule', 'filters'),
            'classes': ('collapse',)
        }),
        ('Recipients', {
            'fields': ('email_recipients', 'notify_users'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'last_run', 'next_run'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_report_template(self, obj):
        return obj.template.name if obj.template else 'N/A'
    get_report_template.short_description = 'Report Template'

# ================================
# REPORT GENERATION MANAGEMENT
# ================================

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'get_report_name', 'get_report_template', 'status', 'get_requested_by', 
        'get_requested_at', 'get_completed_at'
    )
    list_filter = (
        'status', 'created_at', 'completed_at'
    )
    search_fields = (
        'report_name', 'generated_by__username', 'file_path'
    )
    readonly_fields = ('created_at', 'completed_at', 'generation_time_seconds', 'file_size')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('template', 'generated_by', 'status')
        }),
        ('Generation Details', {
            'fields': ('report_name', 'file_format', 'filters_applied', 'parameters'),
            'classes': ('collapse',)
        }),
        ('Execution Information', {
            'fields': ('created_at', 'completed_at', 'generation_time_seconds'),
            'classes': ('collapse',)
        }),
        ('Output Details', {
            'fields': ('file_size', 'download_count'),
            'classes': ('collapse',)
        })
    )
    
    def get_report_name(self, obj):
        """Get a display name for the report"""
        if obj.template:
            timestamp = obj.created_at.strftime('%Y-%m-%d %H:%M')
            return f"{obj.template.name} ({timestamp})"
        return f"Report {obj.id}"
    get_report_name.short_description = 'Report Name'
    
    def get_report_template(self, obj):
        return obj.template.name if obj.template else 'N/A'
    get_report_template.short_description = 'Report Template'
    
    def get_requested_by(self, obj):
        return obj.generated_by.username if obj.generated_by else 'N/A'
    get_requested_by.short_description = 'Requested By'
    
    def get_requested_at(self, obj):
        """Get the requested timestamp"""
        return obj.created_at
    get_requested_at.short_description = 'Requested At'
    
    def get_completed_at(self, obj):
        """Get the completion timestamp"""
        return obj.completed_at
    get_completed_at.short_description = 'Completed At'
    
    def has_add_permission(self, request):
        return False

# ================================
# ADMIN ACTIONS
# ================================

def activate_dashboards(modeladmin, request, queryset):
    """Activate selected dashboards"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f'{updated} dashboard(s) activated.'
    )
activate_dashboards.short_description = "Activate selected dashboards"

def deactivate_dashboards(modeladmin, request, queryset):
    """Deactivate selected dashboards"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} dashboard(s) deactivated.'
    )
deactivate_dashboards.short_description = "Deactivate selected dashboards"

def activate_widgets(modeladmin, request, queryset):
    """Activate selected widgets"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f'{updated} widget(s) activated.'
    )
activate_widgets.short_description = "Activate selected widgets"

def activate_schedules(modeladmin, request, queryset):
    """Activate selected schedules"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f'{updated} schedule(s) activated.'
    )
activate_schedules.short_description = "Activate selected schedules"

def deactivate_schedules(modeladmin, request, queryset):
    """Deactivate selected schedules"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} schedule(s) deactivated.'
    )
deactivate_schedules.short_description = "Deactivate selected schedules"

# Add actions to admin classes
DashboardAdmin.actions = [activate_dashboards, deactivate_dashboards]
DashboardWidgetAdmin.actions = [activate_widgets]
ReportScheduleAdmin.actions = [activate_schedules, deactivate_schedules]