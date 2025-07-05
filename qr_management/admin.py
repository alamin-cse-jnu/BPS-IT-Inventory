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
        'timestamp', 'scan_location', 'discrepancy_count'
    )
    list_filter = (
        'scan_type', 'verification_success', 'timestamp', 
        'scan_location', 'device_status_at_scan'
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
        'device', 'scanned_by', 'scan_location', 
        'device_location_at_scan', 'assigned_staff_at_scan'
    )
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'id', 'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Location Data', {
            'fields': (
                'scan_location', 'device_location_at_scan', 'gps_coordinates', 'location_matches'
            )
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'assigned_staff_at_scan'
            )
        }),
        ('Verification Results', {
            'fields': (
                'verification_success', 'discrepancies_found', 'actions_taken',
                'scan_notes', 'has_discrepancies', 'scan_result_display'
            )
        }),
        ('Technical Details', {
            'fields': (
                'ip_address', 'user_agent', 'device_info', 'app_version',
                'scan_duration_ms'
            ),
            'classes': ('collapse',)
        }),
        ('Batch Information', {
            'fields': (
                'batch_scan_id', 'batch_sequence'
            ),
            'classes': ('collapse',)
        })
    )
    
    def device_link(self, obj):
        """Link to device admin page"""
        if obj.device:
            url = reverse('admin:inventory_device_change', args=[obj.device.pk])
            return format_html('<a href="{}">{}</a>', url, obj.device.device_id)
        return "Unknown Device"
    device_link.short_description = 'Device'
    device_link.admin_order_field = 'device__device_id'
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        if obj.verification_success:
            if obj.has_discrepancies:
                return format_html(
                    '<span style="color: orange;">✓ Success (with notes)</span>'
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Success</span>'
                )
        else:
            return format_html(
                '<span style="color: red;">✗ Failed</span>'
            )
    verification_status_display.short_description = 'Status'
    
    def discrepancy_count(self, obj):
        """Count of discrepancies found"""
        if obj.discrepancies_found:
            return len(obj.discrepancies_found.split('\n'))
        return 0
    discrepancy_count.short_description = 'Discrepancies'

# ================================
# QR CODE TEMPLATES
# ================================

@admin.register(QRCodeTemplate)
class QRCodeTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template_type', 'size', 'usage_count', 
        'is_active', 'is_default', 'created_at'
    )
    list_filter = (
        'template_type', 'size', 'is_active', 'is_default', 
        'is_system_template', 'created_at'
    )
    search_fields = ('name', 'description')
    readonly_fields = (
        'id', 'usage_count', 'created_at', 'updated_at'
    )
    actions = ['set_as_default', 'duplicate_template']
    
    fieldsets = (
        ('Template Information', {
            'fields': (
                'id', 'name', 'description', 'template_type'
            )
        }),
        ('QR Code Settings', {
            'fields': (
                'size', 'custom_width', 'custom_height', 'qr_size', 
                'qr_border', 'error_correction'
            )
        }),
        ('Appearance', {
            'fields': (
                'foreground_color', 'background_color', 'include_logo',
                'logo_file', 'logo_size_percentage'
            )
        }),
        ('Template Status', {
            'fields': (
                'is_active', 'is_default', 'is_system_template', 'usage_count'
            )
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def set_as_default(self, request, queryset):
        """Set selected template as default"""
        if queryset.count() == 1:
            QRCodeTemplate.objects.update(is_default=False)
            queryset.update(is_default=True)
            self.message_user(request, 'Template set as default.')
        else:
            self.message_user(request, 'Please select only one template.', level='error')
    set_as_default.short_description = "Set as default template"

# ================================
# QR CODE BATCH GENERATION
# ================================

@admin.register(QRCodeBatch)
class QRCodeBatchAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'generation_type', 'device_count', 'status', 
        'progress_display', 'created_at', 'created_by'
    )
    list_filter = (
        'generation_type', 'status', 'output_format', 'created_at'
    )
    search_fields = ('name', 'created_by__username')
    readonly_fields = (
        'id', 'device_count', 'generated_count', 'progress_percentage',
        'created_at', 'started_at', 'completed_at'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Batch Information', {
            'fields': (
                'id', 'name', 'generation_type', 'template'
            )
        }),
        ('Generation Parameters', {
            'fields': (
                'device_filter', 'device_list', 'output_format'
            )
        }),
        ('Progress Tracking', {
            'fields': (
                'status', 'device_count', 'generated_count',
                'progress_percentage', 'current_device'
            )
        }),
        ('Timeline', {
            'fields': (
                'created_at', 'started_at', 'completed_at'
            )
        }),
        ('Created By', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        })
    )
    
    def progress_display(self, obj):
        """Display progress with progress bar"""
        progress = obj.progress_percentage or 0
        if progress == 100:
            color = 'green'
        elif progress > 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0;">'
            '<div style="width: {}px; background-color: {}; height: 20px; text-align: center; color: white;">{:.0f}%</div>'
            '</div>',
            progress, color, progress
        )
    progress_display.short_description = 'Progress'

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
        ('Additional Data', {
            'fields': ('additional_data',),
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
    
    def has_change_permission(self, request, obj=None):
        return False

# ================================
# QR SCAN LOCATION
# ================================

@admin.register(QRScanLocation)
class QRScanLocationAdmin(admin.ModelAdmin):
    list_display = (
        'scan', 'location_display_short', 'accuracy_level', 'location_source',
        'is_location_verified', 'created_at'
    )
    list_filter = (
        'accuracy_level', 'location_source', 'is_location_verified', 'created_at'
    )
    search_fields = (
        'scan__device__device_id', 'detected_location__name'
    )
    readonly_fields = ('scan', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Scan Reference', {
            'fields': ('scan',)
        }),
        ('GPS Coordinates', {
            'fields': ('latitude', 'longitude', 'altitude')
        }),
        ('Location Accuracy', {
            'fields': ('accuracy_meters', 'accuracy_level', 'location_source')
        }),
        ('Location Mapping', {
            'fields': ('detected_location', 'verified_location')
        }),
        ('Verification', {
            'fields': (
                'is_location_verified', 'verified_by', 'verified_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def location_display_short(self, obj):
        """Short version of location display"""
        if obj.detected_location:
            return obj.detected_location.name
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
        'integration_type', 'status', 'timestamp', 'response_time_ms'
    )
    list_filter = ('integration_type', 'status', 'timestamp')
    search_fields = ('integration_type', 'request_data', 'response_data')
    readonly_fields = (
        'timestamp', 'request_data', 'response_data', 
        'response_time_ms', 'error_message'
    )
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Integration Details', {
            'fields': ('integration_type', 'status', 'timestamp')
        }),
        ('Request Information', {
            'fields': ('request_data',),
            'classes': ('collapse',)
        }),
        ('Response Information', {
            'fields': ('response_data', 'response_time_ms'),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

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

def verify_scan_locations(modeladmin, request, queryset):
    """Mark selected scan locations as verified"""
    updated = queryset.update(
        is_location_verified=True,
        verified_by=request.user,
        verified_at=timezone.now()
    )
    modeladmin.message_user(
        request,
        f'{updated} scan location(s) marked as verified.'
    )
verify_scan_locations.short_description = "Verify selected scan locations"

# Add actions to respective admin classes
QRCodeScanAdmin.actions = [mark_scans_as_verified]
QRCodeBatchAdmin.actions = [cancel_qr_batches]
QRScanLocationAdmin.actions = [verify_scan_locations]