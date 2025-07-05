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
    QRAnalytics, QRCampaign, QRIntegrationLog, QRCodeTemplate
)

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

admin.site.site_header = "BPS QR Management System"
admin.site.site_title = "QR Admin"
admin.site.index_title = "QR Code Management Dashboard"

# ================================
# QR CODE SCAN MANAGEMENT
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = (
        'device_link', 'scan_type', 'scanned_by', 'verification_status_display', 
        'timestamp', 'discrepancy_count'
    )
    list_filter = (
        'scan_type', 'verification_success', 'timestamp', 
        'device_status_at_scan'
    )
    search_fields = (
        'device__device_id', 'device__device_name', 
        'scanned_by__username', 'scanned_by__first_name', 'scanned_by__last_name'
    )
    date_hierarchy = 'timestamp'
    readonly_fields = (
        'id', 'timestamp', 'has_discrepancies', 'scan_result_display', 'location_matches'
    )
    list_select_related = (
        'device', 'scanned_by', 'device_location_at_scan', 'assigned_staff_at_scan'
    )
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'id', 'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Location Data', {
            'fields': (
                'device_location_at_scan', 'gps_coordinates', 'location_matches'
            )
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'assigned_staff_at_scan', 
                'device_condition_at_scan'
            ),
            'classes': ('collapse',)
        }),
        ('Verification Results', {
            'fields': (
                'verification_success', 'discrepancy_details', 'has_discrepancies',
                'scan_result_display'
            )
        }),
        ('Additional Data', {
            'fields': ('additional_scan_data', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def device_link(self, obj):
        if obj.device:
            url = reverse('admin:inventory_device_change', args=[obj.device.pk])
            return format_html('<a href="{}">{}</a>', url, obj.device.device_id)
        return "No Device"
    device_link.short_description = 'Device'
    
    def verification_status_display(self, obj):
        if obj.verification_success:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Failed</span>')
    verification_status_display.short_description = 'Status'

# ================================
# QR SCAN LOCATION MANAGEMENT
# ================================

@admin.register(QRScanLocation)
class QRScanLocationAdmin(admin.ModelAdmin):
    list_display = (
        'scan', 'location_display_short', 'accuracy_level', 
        'location_source'
    )
    list_filter = (
        'accuracy_level', 'location_source'
    )
    search_fields = (
        'scan__device__device_id', 'detected_location__location_name'
    )
    readonly_fields = (
        'scan', 'latitude', 'longitude', 'altitude', 'accuracy_meters'
    )
    
    fieldsets = (
        ('Scan Reference', {
            'fields': ('scan',)
        }),
        ('GPS Coordinates', {
            'fields': (
                'latitude', 'longitude', 'altitude', 
                'accuracy_meters', 'accuracy_level', 'location_source'
            )
        }),
        ('Location Mapping', {
            'fields': (
                'detected_location', 'verified_location'
            )
        }),
        ('Environmental Data', {
            'fields': ('environmental_data',),
            'classes': ('collapse',)
        })
    )
    
    def location_display_short(self, obj):
        """Short version of location display"""
        if obj.detected_location:
            return obj.detected_location.location_name
        elif obj.latitude and obj.longitude:
            return f"GPS: {obj.latitude:.4f}, {obj.longitude:.4f}"
        return "Unknown"
    location_display_short.short_description = 'Location'

# ================================
# QR INTEGRATION LOGS
# ================================

@admin.register(QRIntegrationLog)
class QRIntegrationLogAdmin(admin.ModelAdmin):
    list_display = (
        'integration_type', 'status', 'created_at', 'response_time_ms'
    )
    list_filter = ('integration_type', 'status', 'created_at')
    search_fields = ('integration_type', 'endpoint', 'error_message')
    readonly_fields = (
        'created_at', 'request_data', 'response_data', 
        'response_time_ms', 'error_message'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Integration Details', {
            'fields': ('integration_type', 'status', 'created_at')
        }),
        ('Request Information', {
            'fields': ('endpoint', 'method', 'request_data'),
            'classes': ('collapse',)
        }),
        ('Response Information', {
            'fields': ('response_data', 'response_time_ms', 'records_processed'),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': ('error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('User Context', {
            'fields': ('user', 'ip_address', 'user_agent'),
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
        'name', 'campaign_type', 'status', 'start_date', 
        'end_date', 'created_by'
    )
    list_filter = ('campaign_type', 'status', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at'
    )
    filter_horizontal = ('target_locations', 'target_departments')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('id', 'name', 'description', 'campaign_type', 'status')
        }),
        ('Campaign Period', {
            'fields': ('start_date', 'end_date', 'timezone')
        }),
        ('Target Scope', {
            'fields': ('target_devices', 'target_locations', 'target_departments')
        }),
        ('Created By', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# QR VERIFICATION RULES
# ================================

@admin.register(QRVerificationRule)
class QRVerificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'rule_type', 'is_active', 'created_at'
    )
    list_filter = ('rule_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Rule Information', {
            'fields': (
                'id', 'name', 'description', 'rule_type'
            )
        }),
        ('Rule Configuration', {
            'fields': ('rule_config',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
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
        'department', 'location'
    )
    search_fields = ('metric_type', 'department__name', 'location__location_name')
    readonly_fields = (
        'calculated_at', 'calculation_time_ms', 'data_points_count'
    )
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Analytics Information', {
            'fields': (
                'metric_type', 'aggregation_period', 'metric_value'
            )
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Scope', {
            'fields': ('department', 'location', 'device_category'),
            'classes': ('collapse',)
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

# ================================
# QR CODE BATCH
# ================================

@admin.register(QRCodeBatch)
class QRCodeBatchAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'batch_type', 'total_codes', 'generated_codes', 
        'status', 'created_at'
    )
    list_filter = ('batch_type', 'status', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = (
        'id', 'generated_codes', 'failed_codes', 'progress_percentage',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Batch Information', {
            'fields': (
                'id', 'name', 'description', 'batch_type'
            )
        }),
        ('Generation Settings', {
            'fields': (
                'total_codes', 'generation_config', 'template'
            )
        }),
        ('Progress Tracking', {
            'fields': (
                'status', 'generated_codes', 'failed_codes', 'progress_percentage'
            )
        }),
        ('Output', {
            'fields': ('output_file', 'generation_log'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# QR CODE TEMPLATE
# ================================

@admin.register(QRCodeTemplate)
class QRCodeTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template_type', 'is_active', 'usage_count', 'created_at'
    )
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('usage_count', 'last_used', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'template_type')
        }),
        ('Template Configuration', {
            'fields': ('template_config', 'style_config'),
            'classes': ('collapse',)
        }),
        ('Status & Usage', {
            'fields': ('is_active', 'usage_count', 'last_used'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# ADMIN ACTIONS
# ================================

def mark_scans_as_verified(modeladmin, request, queryset):
    """Mark selected scans as verified"""
    updated = queryset.update(verification_success=True)
    modeladmin.message_user(
        request, 
        f'{updated} scan(s) marked as verified.'
    )
mark_scans_as_verified.short_description = "Mark selected scans as verified"

def cancel_qr_batches(modeladmin, request, queryset):
    """Cancel selected QR batches"""
    updated = queryset.filter(status__in=['PENDING', 'PROCESSING']).update(status='CANCELLED')
    modeladmin.message_user(
        request,
        f'{updated} QR batch(es) cancelled.'
    )
cancel_qr_batches.short_description = "Cancel selected QR batches"

def activate_campaigns(modeladmin, request, queryset):
    """Activate selected campaigns"""
    updated = queryset.update(status='ACTIVE')
    modeladmin.message_user(
        request,
        f'{updated} campaign(s) activated.'
    )
activate_campaigns.short_description = "Activate selected campaigns"

# Add actions to admin classes
QRCodeScanAdmin.actions = [mark_scans_as_verified]
QRCodeBatchAdmin.actions = [cancel_qr_batches]
QRCampaignAdmin.actions = [activate_campaigns]