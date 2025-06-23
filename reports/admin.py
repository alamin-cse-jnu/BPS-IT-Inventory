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
        'name', 'category', 'access_info', 'usage_count', 
        'last_generated', 'is_active', 'created_by'
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
        ('Status & Audit', {
            'fields': ('is_active', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def access_info(self, obj):
        """Display access control information"""
        if not obj.accessible_by_roles:
            return format_html('<span style="color: red;">❌ No Access Defined</span>')
        
        roles = obj.accessible_by_roles
        if isinstance(roles, list) and len(roles) > 0:
            role_count = len(roles)
            if role_count == 1:
                return format_html(f'<span style="color: green;">✅ {roles[0]}</span>')
            else:
                return format_html(f'<span style="color: blue;">👥 {role_count} Roles</span>')
        
        return format_html('<span style="color: orange;">⚠️ Check Configuration</span>')
    access_info.short_description = "Access Control"
    
    def usage_count(self, obj):
        """Display how many times this report has been generated"""
        count = obj.generations.count()
        if count == 0:
            return "Never used"
        elif count < 10:
            return format_html(f'<span style="color: orange;">{count} times</span>')
        else:
            return format_html(f'<span style="color: green;">{count} times</span>')
    usage_count.short_description = "Usage"
    
    def last_generated(self, obj):
        """Display when this report was last generated"""
        last_generation = obj.generations.order_by('-generation_started').first()
        if last_generation:
            if last_generation.generation_failed:
                return format_html(
                    f'<span style="color: red;">❌ Failed on {last_generation.generation_started.date()}</span>'
                )
            elif last_generation.generation_completed:
                return format_html(
                    f'<span style="color: green;">✅ {last_generation.generation_completed.date()}</span>'
                )
            else:
                return format_html(
                    f'<span style="color: orange;">⏳ In Progress</span>'
                )
        return "Never generated"
    last_generated.short_description = "Last Generated"
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('generations')

@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = [
        'template', 'generated_by', 'generation_status', 'total_records',
        'file_format', 'date_range_display', 'generation_time',
        'download_link'
    ]
    list_filter = [
        'template__category', 'template', 'file_format', 'generation_failed',
        'generation_started', 'generated_by'
    ]
    search_fields = [
        'template__name', 'generated_by__username', 'generated_by__first_name',
        'generated_by__last_name'
    ]
    readonly_fields = [
        'generation_started', 'generation_completed', 'generation_time_display',
        'filters_display', 'error_message_display'
    ]
    
    fieldsets = (
        ('Report Information', {
            'fields': ('template', 'generated_by', 'file_format')
        }),
        ('Generation Parameters', {
            'fields': (
                'filters_display', 'date_range_start', 'date_range_end'
            )
        }),
        ('Generation Results', {
            'fields': (
                'total_records', 'file_path', 'generation_started',
                'generation_completed', 'generation_time_display'
            )
        }),
        ('Error Information', {
            'fields': ('generation_failed', 'error_message_display'),
            'classes': ('collapse',)
        })
    )
    
    def generation_status(self, obj):
        """Display generation status with color coding"""
        if obj.generation_failed:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
        elif obj.generation_completed:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Completed</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ In Progress</span>'
            )
    generation_status.short_description = "Status"
    
    def date_range_display(self, obj):
        """Display the date range for the report"""
        if obj.date_range_start and obj.date_range_end:
            return f"{obj.date_range_start} to {obj.date_range_end}"
        elif obj.date_range_start:
            return f"From {obj.date_range_start}"
        elif obj.date_range_end:
            return f"Until {obj.date_range_end}"
        else:
            return "All dates"
    date_range_display.short_description = "Date Range"
    
    def generation_time(self, obj):
        """Display how long the generation took"""
        if obj.generation_completed and obj.generation_started:
            duration = obj.generation_completed - obj.generation_started
            total_seconds = duration.total_seconds()
            if total_seconds < 60:
                return f"{total_seconds:.1f} seconds"
            else:
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                return f"{minutes}m {seconds}s"
        return "N/A"
    generation_time.short_description = "Generation Time"
    
    def generation_time_display(self, obj):
        """Readonly field for generation time in detail view"""
        return self.generation_time(obj)
    generation_time_display.short_description = "Generation Time"
    
    def filters_display(self, obj):
        """Display applied filters in a readable format"""
        if obj.filters_applied:
            try:
                filters = obj.filters_applied
                if isinstance(filters, dict) and filters:
                    formatted_filters = []
                    for key, value in filters.items():
                        formatted_filters.append(f"{key}: {value}")
                    return "\n".join(formatted_filters)
                else:
                    return "No filters applied"
            except:
                return "Invalid filter format"
        return "No filters applied"
    filters_display.short_description = "Applied Filters"
    
    def error_message_display(self, obj):
        """Display error message if generation failed"""
        if obj.generation_failed and obj.error_message:
            return format_html(
                '<div style="background: #ffebee; padding: 10px; border-left: 4px solid #f44336;">'
                f'<strong>Error:</strong><br>{obj.error_message}</div>'
            )
        return "No errors"
    error_message_display.short_description = "Error Details"
    
    def download_link(self, obj):
        """Provide download link for completed reports"""
        if obj.generation_completed and obj.file_path:
            return format_html(
                '<a href="#" onclick="alert(\'Download functionality to be implemented\');" '
                'style="color: #007cba; text-decoration: none;">📥 Download</a>'
            )
        return "N/A"
    download_link.short_description = "Download"
    
    def has_add_permission(self, request):
        """Prevent manual creation of report generations"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but not editing of report generations"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of old report files"""
        return request.user.is_superuser

# ================================
# CUSTOM ADMIN ACTIONS
# ================================

@admin.action(description='Generate selected reports')
def generate_reports(modeladmin, request, queryset):
    """Custom admin action to generate reports"""
    for template in queryset:
        if template.is_active:
            # Create a new report generation record
            generation = ReportGeneration.objects.create(
                template=template,
                generated_by=request.user,
                file_format='PDF',  # Default format
                filters_applied=template.filters or {}
            )
            # In a real implementation, you would trigger the report generation process here
            # For now, we just create the record
    
    count = queryset.filter(is_active=True).count()
    modeladmin.message_user(
        request,
        f'Initiated generation for {count} active report template(s). '
        'Check the Report Generation section for progress.'
    )

# Add the custom action to ReportTemplateAdmin
ReportTemplateAdmin.actions = [generate_reports]

# ================================
# ADMIN SITE CUSTOMIZATION FOR REPORTS
# ================================

def get_report_dashboard_stats():
    """Get statistics for the admin dashboard"""
    total_templates = ReportTemplate.objects.count()
    active_templates = ReportTemplate.objects.filter(is_active=True).count()
    total_generations = ReportGeneration.objects.count()
    failed_generations = ReportGeneration.objects.filter(generation_failed=True).count()
    
    return {
        'total_templates': total_templates,
        'active_templates': active_templates,
        'total_generations': total_generations,
        'failed_generations': failed_generations,
        'success_rate': (
            ((total_generations - failed_generations) / total_generations * 100) 
            if total_generations > 0 else 0
        )
    }

# Add custom admin index template context
def admin_index_context(request):
    """Add custom context to admin index page"""
    if request.path == '/admin/':
        stats = get_report_dashboard_stats()
        return {
            'report_stats': stats
        }
    return {}