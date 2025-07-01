# File Location: reports/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.shortcuts import redirect
from .models import ReportTemplate, ReportGeneration
import json

# ================================
# REPORTING & ANALYTICS ADMIN
# ================================

class ReportGenerationInline(admin.TabularInline):
    """Inline for viewing report generation history"""
    model = ReportGeneration
    extra = 0
    readonly_fields = [
        'generated_by', 'total_records', 'file_format', 'generation_started', 
        'generation_completed', 'generation_failed'
    ]
    fields = [
        'generated_by', 'filters_applied', 'date_range_start', 'date_range_end',
        'total_records', 'file_format', 'generation_started', 'generation_completed'
    ]
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'get_access_info', 'get_usage_count', 
        'get_last_generated', 'is_active', 'created_by'
    ]
    list_filter = [
        'category', 'is_active', 'created_at', 'created_by'
    ]
    search_fields = [
        'name', 'description', 'created_by__username'
    ]
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ReportGenerationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'description')
        }),
        ('Report Configuration', {
            'fields': ('filters', 'columns'),
            'description': 'Configure default filters and columns for this report'
        }),
        ('Advanced Configuration', {
            'fields': ('sql_query',),
            'classes': ('collapse',),
            'description': 'Custom SQL query for complex reports (use with caution)'
        }),
        ('Access Control', {
            'fields': ('accessible_by_roles',),
            'description': 'List of user roles that can access this report'
        }),
        ('Status & Metadata', {
            'fields': ('is_active', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_access_info(self, obj):
        """Display access information"""
        try:
            if obj.accessible_by_roles:
                roles = obj.accessible_by_roles.split(',')
                return f"{len(roles)} roles"
            return "All users"
        except:
            return "Unknown"
    get_access_info.short_description = "Access"
    
    def get_usage_count(self, obj):
        """Display usage count"""
        try:
            return obj.report_generations.count()
        except:
            return 0
    get_usage_count.short_description = "Usage Count"
    
    def get_last_generated(self, obj):
        """Display last generation date"""
        try:
            last_generation = obj.report_generations.order_by('-generation_started').first()
            if last_generation:
                return last_generation.generation_started.strftime('%Y-%m-%d %H:%M')
            return "Never"
        except:
            return "Unknown"
    get_last_generated.short_description = "Last Generated"

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = [
        'template', 'generated_by', 'get_date_range', 'total_records',
        'file_format', 'get_status', 'generation_started'
    ]
    list_filter = [
        'template__category', 'file_format', 'generation_started',
        'generation_completed', 'generation_failed'
    ]
    search_fields = [
        'template__name', 'generated_by__username', 'filters_applied'
    ]
    readonly_fields = [
        'generation_started', 'generation_completed', 'generation_failed'
    ]
    
    fieldsets = (
        ('Report Information', {
            'fields': ('template', 'generated_by')
        }),
        ('Generation Parameters', {
            'fields': (
                'filters_applied', 'date_range_start', 'date_range_end',
                'file_format'
            )
        }),
        ('Results', {
            'fields': ('total_records', 'file_path')
        }),
        ('Timing', {
            'fields': (
                'generation_started', 'generation_completed', 'generation_failed'
            ),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        })
    )
    
    def get_date_range(self, obj):
        """Display date range"""
        try:
            if obj.date_range_start and obj.date_range_end:
                return f"{obj.date_range_start} to {obj.date_range_end}"
            elif obj.date_range_start:
                return f"From {obj.date_range_start}"
            elif obj.date_range_end:
                return f"Until {obj.date_range_end}"
            return "All dates"
        except:
            return "Unknown"
    get_date_range.short_description = "Date Range"
    
    def get_status(self, obj):
        """Display generation status"""
        try:
            if obj.generation_failed:
                return format_html('<span style="color: red;">❌ Failed</span>')
            elif obj.generation_completed:
                return format_html('<span style="color: green;">✅ Completed</span>')
            else:
                return format_html('<span style="color: orange;">🔄 In Progress</span>')
        except:
            return format_html('<span style="color: gray;">Unknown</span>')
    get_status.short_description = "Status"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False