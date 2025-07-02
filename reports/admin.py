
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q, Sum, Avg
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import json

from .models import (
    ReportTemplate, ReportGeneration, ReportSchedule, ReportAccess,
    Dashboard, DashboardWidget, ReportSubscription, DataExport,
    AnalyticsMetric, CustomQuery, ReportCache
)


# ================================
# CUSTOM FILTERS
# ================================

class ReportTypeFilter(SimpleListFilter):
    title = 'Report Type'
    parameter_name = 'report_type'

    def lookups(self, request, model_admin):
        return [
            ('INVENTORY', 'Inventory Reports'),
            ('ASSIGNMENT', 'Assignment Reports'),
            ('MAINTENANCE', 'Maintenance Reports'),
            ('AUDIT', 'Audit Reports'),
            ('WARRANTY', 'Warranty Reports'),
            ('ANALYTICS', 'Analytics Reports'),
            ('FINANCIAL', 'Financial Reports'),
            ('CUSTOM', 'Custom Reports'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(report_type=self.value())
        return queryset


class ReportStatusFilter(SimpleListFilter):
    title = 'Generation Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('EXPIRED', 'Expired'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class ReportAccessTypeFilter(SimpleListFilter):
    title = 'Access Type'
    parameter_name = 'access_type'

    def lookups(self, request, model_admin):
        return [
            ('VIEW', 'Viewed Online'),
            ('DOWNLOAD', 'Downloaded'),
            ('SHARE', 'Shared'),
            ('PRINT', 'Printed'),
            ('EMAIL', 'Emailed'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(access_type=self.value())
        return queryset


class ScheduleFrequencyFilter(SimpleListFilter):
    title = 'Schedule Frequency'
    parameter_name = 'frequency'

    def lookups(self, request, model_admin):
        return [
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('YEARLY', 'Yearly'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(frequency=self.value())
        return queryset


# ================================
# INLINE ADMIN CLASSES
# ================================

class ReportGenerationInline(admin.TabularInline):
    model = ReportGeneration
    extra = 0
    readonly_fields = ('id', 'generated_by', 'status', 'created_at', 'file_size_human')
    fields = ('id', 'report_name', 'status', 'file_format', 'generated_by', 'created_at')
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('generated_by').order_by('-created_at')[:10]


class ReportScheduleInline(admin.TabularInline):
    model = ReportSchedule
    extra = 0
    readonly_fields = ('id', 'last_run', 'next_run')
    fields = ('name', 'frequency', 'is_active', 'last_run', 'next_run')
    show_change_link = True


class ReportAccessInline(admin.TabularInline):
    model = ReportAccess
    extra = 0
    readonly_fields = ('accessed_by', 'access_type', 'accessed_at', 'ip_address')
    fields = ('accessed_by', 'access_type', 'accessed_at', 'ip_address')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('accessed_by').order_by('-accessed_at')[:10]


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = ('name', 'widget_type', 'position', 'size', 'is_active')
    ordering = ['position']


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'report_type', 'category', 'usage_count',
        'last_used', 'is_active', 'is_system_template', 'actions'
    )
    list_filter = (
        ReportTypeFilter, 'category', 'is_active', 'is_system_template',
        'requires_approval', 'created_at'
    )
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_used', 'usage_count')
    inlines = [ReportGenerationInline, ReportScheduleInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'name', 'description', 'report_type', 'category',
                'is_active', 'is_system_template'
            )
        }),
        ('Configuration', {
            'fields': ('template_config', 'columns', 'filters', 'sorting'),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': ('sql_query', 'requires_approval'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('accessible_by_roles',),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used', 'version'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def actions(self, obj):
        actions_html = []
        
        # Generate report action
        actions_html.append(
            f'<a class="button" href="{reverse("reports:generate_custom_report")}?template_id={obj.id}">Generate</a>'
        )
        
        # Preview action
        if obj.is_active:
            actions_html.append('<a class="button" href="#" onclick="previewTemplate(\'{}\')">Preview</a>'.format(obj.id))
        
        # Clone action
        actions_html.append('<a class="button" href="#" onclick="cloneTemplate(\'{}\')">Clone</a>'.format(obj.id))
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        
        # System templates cannot be modified
        if obj and obj.is_system_template:
            readonly_fields.extend(['name', 'report_type', 'category', 'template_config'])
        
        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of system templates
        if obj and obj.is_system_template:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ReportGeneration)
class ReportGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'report_name', 'template_name', 'generated_by', 'status_display',
        'file_format', 'progress_bar', 'created_at', 'file_size_human', 'actions'
    )
    list_filter = (
        ReportStatusFilter, 'file_format', 'priority', 'created_at',
        'completed_at', 'expires_at'
    )
    search_fields = ('report_name', 'template__name', 'generated_by__username')
    readonly_fields = (
        'id', 'created_at', 'started_at', 'completed_at', 'expires_at',
        'file_size', 'record_count', 'generation_time_seconds',
        'query_time_seconds', 'download_count'
    )
    inlines = [ReportAccessInline]
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'id', 'template', 'report_name', 'generated_by',
                'status', 'file_format', 'priority'
            )
        }),
        ('Parameters', {
            'fields': (
                'filters_applied', 'parameters', 'date_range_start', 'date_range_end'
            ),
            'classes': ('collapse',)
        }),
        ('Progress Tracking', {
            'fields': ('progress_percentage', 'current_step', 'error_message'),
        }),
        ('Timing', {
            'fields': (
                'created_at', 'started_at', 'completed_at', 'expires_at',
                'generation_time_seconds', 'query_time_seconds'
            ),
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': (
                'file_path', 'file_size', 'record_count', 'download_count'
            ),
            'classes': ('collapse',)
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Sharing', {
            'fields': ('is_shared', 'shared_with_users'),
            'classes': ('collapse',)
        }),
    )

    def template_name(self, obj):
        if obj.template:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:reports_reporttemplate_change', args=[obj.template.id]),
                obj.template.name
            )
        return 'Custom Report'
    template_name.short_description = 'Template'

    def status_display(self, obj):
        status_colors = {
            'PENDING': 'orange',
            'PROCESSING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'CANCELLED': 'gray',
            'EXPIRED': 'brown'
        }
        color = status_colors.get(obj.status, 'black')
        
        status_icons = {
            'PENDING': '⏳',
            'PROCESSING': '⚙️',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'CANCELLED': '🚫',
            'EXPIRED': '⏰'
        }
        icon = status_icons.get(obj.status, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def progress_bar(self, obj):
        if obj.status in ['PROCESSING', 'PENDING']:
            return format_html(
                '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
                '<div style="width: {}px; background-color: #007cba; height: 20px; border-radius: 3px; '
                'text-align: center; color: white; font-size: 12px; line-height: 20px;">{}</div></div>',
                obj.progress_percentage, f'{obj.progress_percentage}%'
            )
        elif obj.status == 'COMPLETED':
            return format_html('<span style="color: green;">✅ Complete</span>')
        elif obj.status == 'FAILED':
            return format_html('<span style="color: red;">❌ Failed</span>')
        return '-'
    progress_bar.short_description = 'Progress'

    def actions(self, obj):
        actions_html = []
        
        if obj.status == 'COMPLETED' and obj.file_path:
            actions_html.append(f'<a class="button" href="/reports/download/{obj.id}/">Download</a>')
        
        if obj.status == 'PROCESSING':
            actions_html.append(f'<a class="button" href="#" onclick="cancelReport(\'{obj.id}\')">Cancel</a>')
        
        if obj.status in ['FAILED', 'EXPIRED']:
            actions_html.append(f'<a class="button" href="#" onclick="retryReport(\'{obj.id}\')">Retry</a>')
        
        if obj.is_shared:
            actions_html.append('<span style="color: blue;">🔗 Shared</span>')
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'

    def has_add_permission(self, request):
        return False  # Reports are generated through the system


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template', 'frequency', 'time_of_day',
        'next_run_display', 'is_active', 'run_count', 'actions'
    )
    list_filter = (
        ScheduleFrequencyFilter, 'is_active', 'start_date',
        'end_date', 'created_at'
    )
    search_fields = ('name', 'template__name')
    readonly_fields = (
        'id', 'last_run', 'next_run', 'run_count', 'failure_count',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'template', 'is_active')
        }),
        ('Schedule Configuration', {
            'fields': (
                'frequency', 'time_of_day', 'day_of_week', 'day_of_month',
                'custom_schedule'
            )
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date'),
        }),
        ('Report Settings', {
            'fields': ('default_format', 'filters'),
            'classes': ('collapse',)
        }),
        ('Recipients', {
            'fields': ('email_recipients', 'notify_users'),
            'classes': ('collapse',)
        }),
        ('Execution History', {
            'fields': ('last_run', 'next_run', 'run_count', 'failure_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def next_run_display(self, obj):
        if obj.next_run:
            if obj.next_run < timezone.now():
                return format_html(
                    '<span style="color: red;">⚠️ Overdue: {}</span>',
                    obj.next_run.strftime('%Y-%m-%d %H:%M')
                )
            else:
                return format_html(
                    '<span style="color: green;">📅 {}</span>',
                    obj.next_run.strftime('%Y-%m-%d %H:%M')
                )
        return 'Not scheduled'
    next_run_display.short_description = 'Next Run'

    def actions(self, obj):
        actions_html = []
        
        if obj.is_active:
            actions_html.append(f'<a class="button" href="#" onclick="runNow(\'{obj.id}\')">Run Now</a>')
            actions_html.append(f'<a class="button" href="#" onclick="pauseSchedule(\'{obj.id}\')">Pause</a>')
        else:
            actions_html.append(f'<a class="button" href="#" onclick="resumeSchedule(\'{obj.id}\')">Resume</a>')
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'


@admin.register(ReportAccess)
class ReportAccessAdmin(admin.ModelAdmin):
    list_display = (
        'report_generation', 'accessed_by', 'access_type',
        'accessed_at', 'ip_address', 'user_agent_short'
    )
    list_filter = (ReportAccessTypeFilter, 'accessed_at')
    search_fields = (
        'report_generation__report_name', 'accessed_by__username', 'ip_address'
    )
    readonly_fields = ('accessed_at',)

    def user_agent_short(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + ('...' if len(obj.user_agent) > 50 else '')
        return '-'
    user_agent_short.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False  # Access logs are created automatically


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'dashboard_type', 'owner', 'widget_count',
        'is_active', 'is_public', 'created_at'
    )
    list_filter = ('dashboard_type', 'is_active', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [DashboardWidgetInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'dashboard_type', 'owner')
        }),
        ('Configuration', {
            'fields': ('layout_config', 'theme_config'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('is_active', 'is_public', 'allowed_users', 'allowed_roles'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def widget_count(self, obj):
        count = obj.widgets.count()
        return format_html(
            '<a href="{}?dashboard__id__exact={}">{} widgets</a>',
            reverse('admin:reports_dashboardwidget_changelist'),
            obj.id,
            count
        )
    widget_count.short_description = 'Widgets'


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'dashboard', 'widget_type', 'position', 'size',
        'is_active', 'last_updated'
    )
    list_filter = ('widget_type', 'is_active', 'dashboard__dashboard_type')
    search_fields = ('name', 'dashboard__name')
    readonly_fields = ('id', 'created_at', 'last_updated')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'dashboard', 'name', 'widget_type')
        }),
        ('Layout', {
            'fields': ('position', 'size', 'is_active')
        }),
        ('Configuration', {
            'fields': ('data_source', 'widget_config', 'refresh_interval'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'last_updated'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'report_template', 'subscription_type', 'frequency',
        'is_active', 'last_sent', 'next_send'
    )
    list_filter = ('subscription_type', 'frequency', 'is_active')
    search_fields = ('user__username', 'report_template__name')
    readonly_fields = ('id', 'last_sent', 'next_send', 'send_count', 'created_at')


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'export_type', 'requested_by', 'status',
        'file_format', 'created_at', 'file_size_human', 'actions'
    )
    list_filter = ('export_type', 'status', 'file_format', 'created_at')
    search_fields = ('name', 'requested_by__username')
    readonly_fields = (
        'id', 'created_at', 'started_at', 'completed_at',
        'file_size', 'record_count', 'download_count'
    )

    def actions(self, obj):
        if obj.status == 'COMPLETED' and obj.file_path:
            return format_html(
                '<a class="button" href="/reports/export/download/{}/">Download</a>',
                obj.id
            )
        return '-'
    actions.short_description = 'Actions'


@admin.register(AnalyticsMetric)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = (
        'metric_name', 'metric_type', 'period_start', 'period_end',
        'value', 'department', 'location'
    )
    list_filter = ('metric_type', 'aggregation_period', 'period_start')
    search_fields = ('metric_name',)
    readonly_fields = ('calculated_at', 'calculation_time_ms', 'data_points_count')

    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_name', 'metric_type', 'value', 'unit')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end', 'aggregation_period')
        }),
        ('Scope', {
            'fields': ('department', 'location', 'device_category'),
            'classes': ('collapse',)
        }),
        ('Calculation Details', {
            'fields': (
                'calculated_at', 'calculation_time_ms', 'data_points_count'
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomQuery)
class CustomQueryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'query_type', 'created_by', 'execution_count',
        'is_active', 'last_executed', 'avg_execution_time'
    )
    list_filter = ('query_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = (
        'id', 'execution_count', 'last_executed', 'avg_execution_time',
        'created_at', 'updated_at'
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'query_type', 'is_active')
        }),
        ('Query Definition', {
            'fields': ('sql_query', 'parameters'),
        }),
        ('Execution History', {
            'fields': (
                'execution_count', 'last_executed', 'avg_execution_time'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportCache)
class ReportCacheAdmin(admin.ModelAdmin):
    list_display = (
        'cache_key_short', 'report_template', 'created_at',
        'expires_at', 'hit_count', 'file_size_human', 'is_valid'
    )
    list_filter = ('created_at', 'expires_at')
    search_fields = ('cache_key', 'report_template__name')
    readonly_fields = (
        'cache_key', 'created_at', 'expires_at', 'hit_count',
        'file_size', 'data_hash'
    )

    def cache_key_short(self, obj):
        return obj.cache_key[:20] + '...' if len(obj.cache_key) > 20 else obj.cache_key
    cache_key_short.short_description = 'Cache Key'

    def is_valid(self, obj):
        if obj.expires_at > timezone.now():
            return format_html('<span style="color: green;">✅ Valid</span>')
        else:
            return format_html('<span style="color: red;">❌ Expired</span>')
    is_valid.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # Cache entries are created automatically


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


@admin.action(description='Cancel selected reports')
def cancel_reports(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['PENDING', 'PROCESSING']).update(status='CANCELLED')
    modeladmin.message_user(request, f'{updated} reports were cancelled.')


@admin.action(description='Delete expired reports')
def delete_expired_reports(modeladmin, request, queryset):
    now = timezone.now()
    expired = queryset.filter(expires_at__lt=now)
    count = expired.count()
    expired.delete()
    modeladmin.message_user(request, f'{count} expired reports were deleted.')


@admin.action(description='Clear cache entries')
def clear_cache_entries(modeladmin, request, queryset):
    count = queryset.count()
    queryset.delete()
    modeladmin.message_user(request, f'{count} cache entries were cleared.')


# Add actions to respective admin classes
ReportTemplateAdmin.actions = [activate_templates, deactivate_templates]
ReportGenerationAdmin.actions = [cancel_reports, delete_expired_reports]
ReportCacheAdmin.actions = [clear_cache_entries]


# ================================
# CUSTOM ADMIN VIEWS
# ================================

class ReportAnalyticsView:
    """Custom view for report analytics"""
    
    def get_report_statistics(self):
        """Get comprehensive report statistics"""
        from django.db.models import Count, Avg, Sum
        
        stats = {
            'total_templates': ReportTemplate.objects.count(),
            'active_templates': ReportTemplate.objects.filter(is_active=True).count(),
            'total_generations': ReportGeneration.objects.count(),
            'completed_reports': ReportGeneration.objects.filter(status='COMPLETED').count(),
            'failed_reports': ReportGeneration.objects.filter(status='FAILED').count(),
            'avg_generation_time': ReportGeneration.objects.filter(
                status='COMPLETED',
                generation_time_seconds__isnull=False
            ).aggregate(avg_time=Avg('generation_time_seconds'))['avg_time'],
        }
        
        return stats