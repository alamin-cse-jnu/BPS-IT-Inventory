# qr_management/admin.py
# Location: bps_inventory/apps/qr_management/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import (
    QRCodeTemplate, QRCodeBatch, QRCodeScan, QRCampaign
)

# ================================
# QR CODE TEMPLATE MANAGEMENT
# ================================

@admin.register(QRCodeTemplate)
class QRCodeTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template_type', 'is_active', 'get_created_at', 'created_by'
    )
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('get_created_at', 'updated_at')
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'template_type', 'is_active')
        }),
        ('Template Configuration', {
            'fields': ('template_config',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'get_created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_created_at(self, obj):
        """Get the created_at timestamp"""
        return obj.created_at
    get_created_at.short_description = 'Created At'

# ================================
# QR CODE BATCH MANAGEMENT
# ================================

@admin.register(QRCodeBatch)
class QRCodeBatchAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'get_batch_type', 'get_total_codes', 'get_generated_codes', 
        'status', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('get_created_at', 'get_updated_at', 'get_generated_count', 'get_scan_count', 'get_completion_percentage')
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('name', 'description', 'template', 'status')
        }),
        ('Generation Settings', {
            'fields': ('quantity', 'prefix', 'suffix'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('get_generated_count', 'get_scan_count', 'get_completion_percentage'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'get_created_at', 'get_updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_batch_type(self, obj):
        """Get batch type from template"""
        return obj.template.template_type if obj.template else "No Template"
    get_batch_type.short_description = 'Batch Type'
    
    def get_total_codes(self, obj):
        """Get total number of codes in batch"""
        return obj.quantity or 0
    get_total_codes.short_description = 'Total Codes'
    
    def get_generated_codes(self, obj):
        """Get number of generated codes"""
        return getattr(obj, 'generated_count', 0)
    get_generated_codes.short_description = 'Generated Codes'
    
    def get_created_at(self, obj):
        """Get creation timestamp"""
        return obj.created_at
    get_created_at.short_description = 'Created At'
    
    def get_updated_at(self, obj):
        """Get update timestamp"""
        return obj.updated_at
    get_updated_at.short_description = 'Updated At'
    
    def get_generated_count(self, obj):
        """Get generated count for readonly field"""
        return getattr(obj, 'generated_count', 0)
    get_generated_count.short_description = 'Generated Count'
    
    def get_scan_count(self, obj):
        """Get scan count for readonly field"""
        return getattr(obj, 'scan_count', 0)
    get_scan_count.short_description = 'Scan Count'
    
    def get_completion_percentage(self, obj):
        """Calculate completion percentage"""
        if obj.quantity and hasattr(obj, 'generated_count'):
            return f"{(obj.generated_count / obj.quantity * 100):.1f}%"
        return "0%"
    get_completion_percentage.short_description = 'Completion %'

# ================================
# QR CODE SCAN MANAGEMENT
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'scanned_by', 'timestamp', 'verification_success', 'get_discrepancy_count'
    )
    list_filter = ('verification_success', 'timestamp', 'scan_type')
    search_fields = (
        'device__device_id', 'scanned_by__username', 'device_location_at_scan__name'
    )
    readonly_fields = ('timestamp', 'gps_coordinates', 'device_info')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Scan Information', {
            'fields': ('device', 'scanned_by', 'timestamp', 'scan_type')
        }),
        ('Scan Results', {
            'fields': ('verification_success', 'discrepancies_found', 'scan_notes'),
            'classes': ('collapse',)
        }),
        ('Location & Metadata', {
            'fields': ('gps_coordinates', 'device_info'),
            'classes': ('collapse',)
        })
    )
    
    def get_discrepancy_count(self, obj):
        """Calculate discrepancy count based on scan results"""
        return len(obj.discrepancies_found.strip()) if obj.discrepancies_found else 0
    get_discrepancy_count.short_description = 'Discrepancy Count'

# ================================
# QR CAMPAIGN MANAGEMENT
# ================================

@admin.register(QRCampaign)
class QRCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'campaign_type', 'status', 'start_date', 'end_date',
        'get_batches_count'
    )
    list_filter = ('campaign_type', 'status', 'start_date', 'end_date')
    search_fields = ('name', 'description')
    readonly_fields = ('get_created_at', 'get_campaign_stats')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('name', 'description', 'campaign_type', 'status')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('get_campaign_stats',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'get_created_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_batches_count(self, obj):
        """Get number of batches in campaign"""
        return obj.batches.count() if hasattr(obj, 'batches') else 0
    get_batches_count.short_description = 'Batches'
    
    def get_created_at(self, obj):
        """Get creation timestamp"""
        return obj.created_at
    get_created_at.short_description = 'Created At'
    
    def get_campaign_stats(self, obj):
        """Get campaign statistics"""
        stats = {
            'batches': getattr(obj, 'batches_count', 0),
            'total_codes': getattr(obj, 'total_codes', 0),
            'scanned_codes': getattr(obj, 'scanned_codes', 0),
        }
        return f"Batches: {stats['batches']}, Codes: {stats['total_codes']}, Scanned: {stats['scanned_codes']}"
    get_campaign_stats.short_description = 'Statistics'

# ================================
# ADMIN ACTIONS
# ================================

def activate_templates(modeladmin, request, queryset):
    """Activate selected templates"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f'{updated} template(s) activated.'
    )
activate_templates.short_description = "Activate selected templates"

def deactivate_templates(modeladmin, request, queryset):
    """Deactivate selected templates"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} template(s) deactivated.'
    )
deactivate_templates.short_description = "Deactivate selected templates"

def mark_scans_as_valid(modeladmin, request, queryset):
    """Mark selected scans as valid"""
    updated = queryset.update(verification_success=True)
    modeladmin.message_user(
        request,
        f'{updated} scan(s) marked as valid.'
    )
mark_scans_as_valid.short_description = "Mark selected scans as valid"

# Add actions to admin classes
QRCodeTemplateAdmin.actions = [activate_templates, deactivate_templates]
QRCodeScanAdmin.actions = [mark_scans_as_valid]