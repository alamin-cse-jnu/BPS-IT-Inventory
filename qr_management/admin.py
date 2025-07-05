# qr_management/admin.py
# Location: bps_inventory/apps/qr_management/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from .models import (
    QRCodeScan, QRScanLocation, QRCodeBatch, QRVerificationRule,
    QRAnalytics, QRCampaign, QRIntegrationLog
)

# ================================
# QR CODE SCAN MANAGEMENT
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'scan_type', 'scanned_by', 'verification_status', 
        'timestamp', 'scan_location', 'discrepancy_count'
    )
    list_filter = (
        'scan_type', 'verification_status', 'timestamp', 
        'scan_location', 'device_status_at_scan'
    )
    search_fields = (
        'device__device_id', 'device__device_name', 
        'scanned_by__username', 'scanned_by__first_name', 'scanned_by__last_name'
    )
    date_hierarchy = 'timestamp'
    readonly_fields = (
        'timestamp', 'verification_details', 'response_time_ms'
    )
    list_select_related = (
        'device', 'scanned_by', 'scan_location', 
        'device_location_at_scan', 'assigned_staff_at_scan'
    )
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Location Data', {
            'fields': (
                'scan_location', 'device_location_at_scan'
            )
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'assigned_staff_at_scan'
            )
        }),
        ('Verification Results', {
            'fields': (
                'verification_status', 'verification_details', 
                'discrepancies_found', 'action_required'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': ('response_time_ms',),
            'classes': ('collapse',)
        }),
        ('Additional Context', {
            'fields': ('notes', 'metadata'),
            'classes': ('collapse',)
        })
    )
    
    def discrepancy_count(self, obj):
        if obj.discrepancies_found:
            count = len(obj.discrepancies_found)
            if count > 0:
                return format_html(
                    '<span style="color: red; font-weight: bold;">{}</span>',
                    count
                )
        return 0
    discrepancy_count.short_description = 'Discrepancies'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'device', 'scanned_by', 'scan_location'
        )

@admin.register(QRScanLocation)
class QRScanLocationAdmin(admin.ModelAdmin):
    list_display = (
        'scan', 'latitude', 'longitude', 'accuracy_level', 
        'location_source', 'detected_location', 'is_location_verified'
    )
    list_filter = (
        'accuracy_level', 'location_source', 'is_location_verified'
    )
    search_fields = (
        'scan__device__device_id', 'detected_location__name',
        'verified_location__name'
    )
    readonly_fields = ('accuracy_meters', 'location_timestamp')
    
    fieldsets = (
        ('GPS Coordinates', {
            'fields': (
                'latitude', 'longitude', 'altitude'
            )
        }),
        ('Location Accuracy', {
            'fields': (
                'accuracy_meters', 'accuracy_level', 'location_source'
            )
        }),
        ('Location Mapping', {
            'fields': (
                'detected_location', 'verified_location', 'is_location_verified'
            )
        }),
        ('Timing', {
            'fields': ('location_timestamp',),
            'classes': ('collapse',)
        })
    )

# ================================
# QR CODE BATCH MANAGEMENT
# ================================

@admin.register(QRCodeBatch)
class QRCodeBatchAdmin(admin.ModelAdmin):
    list_display = (
        'batch_id', 'batch_name', 'batch_type', 'total_codes', 
        'scan_count', 'success_rate', 'created_at', 'is_active'
    )
    list_filter = (
        'batch_type', 'is_active', 'created_at', 'expires_at'
    )
    search_fields = (
        'batch_id', 'batch_name', 'description', 'created_by__username'
    )
    readonly_fields = (
        'batch_id', 'total_codes', 'scan_count', 'success_rate',
        'created_at', 'updated_at'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Batch Information', {
            'fields': (
                'batch_id', 'batch_name', 'description', 'batch_type'
            )
        }),
        ('Batch Configuration', {
            'fields': (
                'device_filter_criteria', 'qr_code_format', 'encoding_options'
            )
        }),
        ('Validity and Expiration', {
            'fields': (
                'is_active', 'expires_at', 'max_scans_per_code'
            )
        }),
        ('Statistics', {
            'fields': (
                'total_codes', 'scan_count', 'success_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def scan_count(self, obj):
        # This would need to be calculated based on related scans
        return obj.qr_scans.count() if hasattr(obj, 'qr_scans') else 0
    scan_count.short_description = 'Total Scans'
    
    def success_rate(self, obj):
        total_scans = self.scan_count(obj)
        if total_scans > 0:
            successful_scans = obj.qr_scans.filter(
                verification_status='SUCCESS'
            ).count() if hasattr(obj, 'qr_scans') else 0
            rate = (successful_scans / total_scans) * 100
            return f"{rate:.1f}%"
        return "N/A"
    success_rate.short_description = 'Success Rate'

# ================================
# QR VERIFICATION RULES
# ================================

@admin.register(QRVerificationRule)
class QRVerificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        'rule_name', 'rule_type', 'trigger_condition', 
        'is_active', 'execution_count', 'created_at'
    )
    list_filter = (
        'rule_type', 'is_active', 'created_at'
    )
    search_fields = ('rule_name', 'description')
    readonly_fields = (
        'execution_count', 'last_executed', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('rule_name', 'description', 'rule_type', 'is_active')
        }),
        ('Rule Logic', {
            'fields': (
                'trigger_condition', 'rule_logic', 'action_to_take'
            )
        }),
        ('Execution Settings', {
            'fields': ('priority', 'max_executions_per_day'),
            'classes': ('collapse',)
        }),
        ('Performance Tracking', {
            'fields': (
                'execution_count', 'last_executed'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# QR ANALYTICS
# ================================

@admin.register(QRAnalytics)
class QRAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'metric_type', 'aggregation_period', 'period_start', 'period_end',
        'metric_value', 'department', 'location', 'calculated_at'
    )
    list_filter = (
        'metric_type', 'aggregation_period', 'period_start',
        'department', 'location', 'device_category'
    )
    search_fields = (
        'department__name', 'location__name', 'device_category__name'
    )
    readonly_fields = (
        'calculated_at', 'calculation_time_ms', 'data_points_count'
    )
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Metric Information', {
            'fields': (
                'metric_type', 'aggregation_period', 
                'period_start', 'period_end', 'metric_value'
            )
        }),
        ('Scope Filters', {
            'fields': (
                'department', 'location', 'device_category'
            )
        }),
        ('Calculation Metadata', {
            'fields': (
                'calculated_at', 'calculation_time_ms', 'data_points_count'
            ),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# ================================
# QR CAMPAIGNS
# ================================

@admin.register(QRCampaign)
class QRCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'campaign_type', 'status', 'start_date', 'end_date',
        'progress_percentage', 'total_targets', 'completed_scans'
    )
    list_filter = (
        'campaign_type', 'status', 'start_date', 'end_date', 'created_at'
    )
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'id', 'progress_percentage', 'total_targets', 'completed_scans',
        'created_at', 'updated_at'
    )
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Campaign Information', {
            'fields': (
                'id', 'name', 'description', 'campaign_type', 'status'
            )
        }),
        ('Campaign Timeline', {
            'fields': ('start_date', 'end_date')
        }),
        ('Target Configuration', {
            'fields': (
                'target_devices', 'target_locations', 'target_departments'
            )
        }),
        ('Progress Tracking', {
            'fields': (
                'progress_percentage', 'total_targets', 'completed_scans'
            ),
            'classes': ('collapse',)
        }),
        ('Campaign Settings', {
            'fields': (
                'verification_requirements', 'completion_criteria',
                'notification_settings'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def total_targets(self, obj):
        if obj.target_devices:
            return len(obj.target_devices)
        return 0
    total_targets.short_description = 'Target Count'
    
    def completed_scans(self, obj):
        # This would need to be calculated based on campaign scans
        return 0  # Placeholder
    completed_scans.short_description = 'Completed'

# ================================
# QR INTEGRATIONS
# ================================

@admin.register(QRIntegrationLog)
class QRIntegrationLogAdmin(admin.ModelAdmin):
    list_display = (
        'integration_type', 'status', 'endpoint', 'method',
        'response_time_ms', 'records_processed', 'created_at'
    )
    list_filter = (
        'integration_type', 'status', 'method', 'created_at'
    )
    search_fields = ('endpoint', 'error_message', 'user__username')
    readonly_fields = ('id', 'response_time_ms', 'created_at')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False  # Log entries should not be manually created
    
    def has_change_permission(self, request, obj=None):
        return False  # Log entries should not be modified

# ================================
# CUSTOM ADMIN ACTIONS
# ================================

def mark_scans_as_verified(modeladmin, request, queryset):
    """Custom action to mark selected scans as verified"""
    updated = queryset.update(verification_status='SUCCESS')
    modeladmin.message_user(
        request, 
        f'{updated} scans were marked as verified.'
    )
mark_scans_as_verified.short_description = "Mark selected scans as verified"

def export_scan_data(modeladmin, request, queryset):
    """Custom action to export scan data"""
    # Implementation would create CSV export
    modeladmin.message_user(
        request, 
        f'Export functionality would export {queryset.count()} records.'
    )
export_scan_data.short_description = "Export scan data to CSV"

# Add custom actions to QRCodeScan admin
QRCodeScanAdmin.actions = [mark_scans_as_verified, export_scan_data]

# ================================
# ADMIN CUSTOMIZATION
# ================================

admin.site.site_header = "BPS IT Inventory - QR Management"
admin.site.site_title = "BPS QR Admin"
admin.site.index_title = "QR Code Management Dashboard"