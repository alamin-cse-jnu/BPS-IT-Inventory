# File Location: qr_management/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import QRCodeScan

# ================================
# QR CODE MANAGEMENT ADMIN
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'scan_type', 'scanned_by', 'get_verification_status',
        'get_device_status', 'timestamp', 'get_location_info'
    ]
    list_filter = [
        'scan_type', 'verification_success', 'device_status_at_scan',
        'timestamp', 'device__device_type'
    ]
    search_fields = [
        'device__device_id', 'device__device_name', 'scanned_by__username',
        'ip_address', 'actions_taken'
    ]
    readonly_fields = [
        'timestamp', 'ip_address', 'user_agent', 'gps_coordinates'
    ]
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'device', 'scan_type', 'scanned_by', 'timestamp'
            )
        }),
        ('Device Status at Scan', {
            'fields': (
                'device_status_at_scan', 'assigned_staff_at_scan',
                'device_location_at_scan', 'scan_location'
            )
        }),
        ('Verification Results', {
            'fields': (
                'verification_success', 'discrepancies_found', 'actions_taken'
            )
        }),
        ('Technical Details', {
            'fields': (
                'ip_address', 'user_agent', 'gps_coordinates'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_verification_status(self, obj):
        """Display verification status"""
        try:
            if obj.verification_success:
                return format_html('<span style="color: green;">✅ Success</span>')
            else:
                return format_html('<span style="color: red;">❌ Failed</span>')
        except:
            return format_html('<span style="color: gray;">Unknown</span>')
    get_verification_status.short_description = "Verification"
    
    def get_device_status(self, obj):
        """Display device status at scan"""
        try:
            status = obj.device_status_at_scan
            if status == 'ACTIVE':
                return format_html('<span style="color: green;">🟢 Active</span>')
            elif status == 'INACTIVE':
                return format_html('<span style="color: orange;">🟠 Inactive</span>')
            elif status == 'MAINTENANCE':
                return format_html('<span style="color: blue;">🔵 Maintenance</span>')
            elif status == 'RETIRED':
                return format_html('<span style="color: red;">🔴 Retired</span>')
            else:
                return status
        except:
            return "Unknown"
    get_device_status.short_description = "Device Status"
    
    def get_location_info(self, obj):
        """Display location information"""
        try:
            if obj.scan_location:
                return str(obj.scan_location)
            elif obj.gps_coordinates:
                return f"GPS: {obj.gps_coordinates[:20]}..."
            return "No location"
        except:
            return "Unknown"
    get_location_info.short_description = "Scan Location"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False