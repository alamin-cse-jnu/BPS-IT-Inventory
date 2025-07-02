# qr_management/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q, Sum, Avg
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
import qrcode
from io import BytesIO
import base64
import json

from .models import (
    QRCodeScan, QRAnalytics, QRCampaign, QRMobileSession,
    QRBulkVerification, QRCodeTemplate, QRPrintJob,
    QRVerificationRule, QRScanLocation, QRCodeBatch
)


# ================================
# CUSTOM FILTERS
# ================================

class ScanTypeFilter(SimpleListFilter):
    title = 'Scan Type'
    parameter_name = 'scan_type'

    def lookups(self, request, model_admin):
        return [
            ('VERIFICATION', 'Device Verification'),
            ('INVENTORY', 'Inventory Check'),
            ('ASSIGNMENT', 'Assignment Verification'),
            ('MAINTENANCE', 'Maintenance Scan'),
            ('AUDIT', 'Audit Scan'),
            ('BATCH_VERIFICATION', 'Batch Verification'),
            ('MOBILE_SCAN', 'Mobile App Scan'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(scan_type=self.value())
        return queryset


class VerificationStatusFilter(SimpleListFilter):
    title = 'Verification Status'
    parameter_name = 'verification_status'

    def lookups(self, request, model_admin):
        return [
            ('SUCCESS', 'Verification Successful'),
            ('FAILED', 'Verification Failed'),
            ('WARNING', 'Verification with Warnings'),
            ('ERROR', 'Scan Error'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(verification_status=self.value())
        return queryset


class CampaignStatusFilter(SimpleListFilter):
    title = 'Campaign Status'
    parameter_name = 'campaign_status'

    def lookups(self, request, model_admin):
        return [
            ('PLANNED', 'Planned'),
            ('ACTIVE', 'Active'),
            ('PAUSED', 'Paused'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class TimeRangeFilter(SimpleListFilter):
    title = 'Time Range'
    parameter_name = 'time_range'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('quarter', 'This Quarter'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        today = now.date()
        
        if self.value() == 'today':
            return queryset.filter(timestamp__date=today)
        elif self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(timestamp__date=yesterday)
        elif self.value() == 'week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(timestamp__date__gte=week_start)
        elif self.value() == 'month':
            month_start = today.replace(day=1)
            return queryset.filter(timestamp__date__gte=month_start)
        elif self.value() == 'quarter':
            quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            return queryset.filter(timestamp__date__gte=quarter_start)
        return queryset


# ================================
# INLINE ADMIN CLASSES
# ================================

class QRCodeScanInline(admin.TabularInline):
    model = QRCodeScan
    extra = 0
    readonly_fields = ('id', 'timestamp', 'scanned_by', 'verification_status')
    fields = ('scan_type', 'scanned_by', 'verification_status', 'timestamp')
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('scanned_by').order_by('-timestamp')[:10]


class QRAnalyticsInline(admin.TabularInline):
    model = QRAnalytics
    extra = 0
    readonly_fields = ('period_start', 'period_end', 'value', 'calculated_at')
    fields = ('metric_type', 'period_start', 'value', 'calculated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-period_start')[:5]


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'scan_type', 'scanned_by', 'verification_status_display',
        'timestamp', 'scan_location', 'device_status_at_scan', 'actions'
    )
    list_filter = (
        ScanTypeFilter, VerificationStatusFilter, TimeRangeFilter,
        'timestamp', 'device_status_at_scan'
    )
    search_fields = (
        'device__device_id', 'device__device_name', 'scanned_by__username',
        'scan_location__name', 'notes'
    )
    readonly_fields = (
        'id', 'timestamp', 'device_status_at_scan', 'device_location_at_scan',
        'assigned_staff_at_scan', 'assigned_department_at_scan'
    )
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'id', 'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Location Information', {
            'fields': ('scan_location', 'gps_coordinates'),
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'device_location_at_scan',
                'assigned_staff_at_scan', 'assigned_department_at_scan'
            ),
            'classes': ('collapse',)
        }),
        ('Verification Results', {
            'fields': (
                'verification_status', 'verification_data', 'discrepancies_found'
            ),
        }),
        ('Additional Information', {
            'fields': ('notes', 'follow_up_required', 'follow_up_notes'),
            'classes': ('collapse',)
        }),
    )

    def verification_status_display(self, obj):
        status_colors = {
            'SUCCESS': 'green',
            'FAILED': 'red',
            'WARNING': 'orange',
            'ERROR': 'purple'
        }
        color = status_colors.get(obj.verification_status, 'black')
        
        status_icons = {
            'SUCCESS': '✅',
            'FAILED': '❌',
            'WARNING': '⚠️',
            'ERROR': '🔴'
        }
        icon = status_icons.get(obj.verification_status, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_verification_status_display()
        )
    verification_status_display.short_description = 'Status'

    def actions(self, obj):
        actions_html = []
        
        # View device details
        actions_html.append(
            f'<a class="button" href="{reverse("inventory:device_detail", args=[obj.device.device_id])}">View Device</a>'
        )
        
        # If follow-up required, show follow-up action
        if obj.follow_up_required:
            actions_html.append('<span style="color: orange;">📋 Follow-up Required</span>')
        
        # View verification details
        actions_html.append(
            f'<a class="button" href="{reverse("qr_management:qr_scan_detail", args=[obj.pk])}">Details</a>'
        )
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'

    def has_add_permission(self, request):
        return False  # QR scans are created automatically


@admin.register(QRAnalytics)
class QRAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'metric_type', 'aggregation_period', 'period_start', 'period_end',
        'value', 'department', 'location', 'calculated_at'
    )
    list_filter = (
        'metric_type', 'aggregation_period', 'department',
        'location', 'period_start'
    )
    search_fields = ('metric_type',)
    readonly_fields = (
        'calculated_at', 'calculation_time_ms', 'data_points_count'
    )

    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_type', 'value', 'aggregation_period')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Scope', {
            'fields': ('department', 'location', 'device_category'),
        }),
        ('Calculation Details', {
            'fields': (
                'calculated_at', 'calculation_time_ms', 'data_points_count'
            ),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False  # Analytics are calculated automatically


@admin.register(QRCampaign)
class QRCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'campaign_type', 'status_display', 'progress_display',
        'start_date', 'end_date', 'target_count', 'actions'
    )
    list_filter = (
        CampaignStatusFilter, 'campaign_type', 'start_date', 'end_date'
    )
    search_fields = ('name', 'description')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'completed_at',
        'devices_scanned', 'success_rate'
    )
    filter_horizontal = ('target_locations', 'target_departments', 'assigned_users')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': (
                'id', 'name', 'description', 'campaign_type', 'status'
            )
        }),
        ('Campaign Scope', {
            'fields': (
                'target_devices', 'target_locations', 'target_departments'
            ),
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'estimated_duration'),
        }),
        ('Execution', {
            'fields': ('assigned_users', 'verification_rules'),
            'classes': ('collapse',)
        }),
        ('Progress Tracking', {
            'fields': (
                'devices_scanned', 'success_rate', 'completion_percentage'
            ),
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': ('campaign_results', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_display(self, obj):
        status_colors = {
            'PLANNED': 'blue',
            'ACTIVE': 'green',
            'PAUSED': 'orange',
            'COMPLETED': 'gray',
            'CANCELLED': 'red'
        }
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def progress_display(self, obj):
        if hasattr(obj, 'completion_percentage') and obj.completion_percentage is not None:
            percentage = obj.completion_percentage
            return format_html(
                '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px; overflow: hidden;">'
                '<div style="width: {}px; background-color: #007cba; height: 20px; '
                'text-align: center; color: white; font-size: 12px; line-height: 20px; '
                'transition: width 0.3s ease;">{}</div></div>',
                percentage, f'{percentage}%'
            )
        return '-'