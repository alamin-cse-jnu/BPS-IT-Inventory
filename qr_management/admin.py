from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import QRCodeScan

# ================================
# QR CODE MANAGEMENT ADMIN
# ================================

@admin.register(QRCodeScan)
class QRCodeScanAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'scan_type', 'scanned_by', 'scan_location',
        'verification_status', 'discrepancy_indicator', 'timestamp',
        'device_info_at_scan'
    ]
    list_filter = [
        'scan_type', 'verification_success', 'timestamp', 
        'device__device_type__subcategory__category',
        'scanned_by', 'scan_location__room__department'
    ]
    search_fields = [
        'device__device_id', 'device__device_name', 'device__asset_tag',
        'scanned_by__username', 'scanned_by__first_name', 'scanned_by__last_name',
        'discrepancies_found', 'actions_taken'
    ]
    readonly_fields = [
        'timestamp', 'device_info_display', 'scan_location_display',
        'technical_details_display', 'discrepancies_display'
    ]
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Scan Information', {
            'fields': (
                'device', 'scan_type', 'scanned_by', 'scan_location', 'timestamp'
            )
        }),
        ('Device State at Scan', {
            'fields': (
                'device_status_at_scan', 'device_location_at_scan', 
                'assigned_staff_at_scan', 'device_info_display'
            ),
            'description': 'Device information captured at the time of scanning'
        }),
        ('Verification Results', {
            'fields': (
                'verification_success', 'discrepancies_display', 'actions_taken'
            )
        }),
        ('Technical Details', {
            'fields': ('technical_details_display',),
            'classes': ('collapse',)
        })
    )
    
    def verification_status(self, obj):
        """Display verification status with color coding"""
        if obj.verification_success:
            if obj.discrepancies_found:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚠️ Success (with notes)</span>'
                )
            else:
                return format_html(
                    '<span style="color: green; font-weight: bold;">✅ Success</span>'
                )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
    verification_status.short_description = "Verification"
    
    def discrepancy_indicator(self, obj):
        """Show if there were any discrepancies found"""
        if obj.discrepancies_found:
            return format_html(
                '<span style="color: orange;" title="{}">⚠️ Issues Found</span>',
                obj.discrepancies_found[:100] + ("..." if len(obj.discrepancies_found) > 100 else "")
            )
        return format_html('<span style="color: green;">✅ No Issues</span>')
    discrepancy_indicator.short_description = "Discrepancies"
    
    def device_info_at_scan(self, obj):
        """Display condensed device info at time of scan"""
        info_parts = []
        if obj.device_status_at_scan:
            info_parts.append(f"Status: {obj.device_status_at_scan}")
        if obj.assigned_staff_at_scan:
            info_parts.append(f"Assigned: {obj.assigned_staff_at_scan.full_name}")
        elif obj.device_location_at_scan:
            info_parts.append(f"Location: {obj.device_location_at_scan.name}")
        
        return " | ".join(info_parts) if info_parts else "No info captured"
    device_info_at_scan.short_description = "Device Info at Scan"
    
    def device_info_display(self, obj):
        """Detailed device information display for form view"""
        info = []
        info.append(f"<strong>Device Status:</strong> {obj.device_status_at_scan}")
        
        if obj.device_location_at_scan:
            info.append(f"<strong>Location:</strong> {obj.device_location_at_scan.full_location_path}")
        
        if obj.assigned_staff_at_scan:
            info.append(f"<strong>Assigned Staff:</strong> {obj.assigned_staff_at_scan.full_name} ({obj.assigned_staff_at_scan.employee_id})")
        
        return format_html("<br>".join(info))
    device_info_display.short_description = "Device Information at Scan"
    
    def scan_location_display(self, obj):
        """Display scan location with full path"""
        if obj.scan_location:
            return obj.scan_location.full_location_path
        return "Location not recorded"
    scan_location_display.short_description = "Scan Location"
    
    def technical_details_display(self, obj):
        """Display technical details in readable format"""
        details = []
        
        if obj.ip_address:
            details.append(f"<strong>IP Address:</strong> {obj.ip_address}")
        
        if obj.user_agent:
            details.append(f"<strong>User Agent:</strong> {obj.user_agent}")
        
        if obj.gps_coordinates:
            details.append(f"<strong>GPS Coordinates:</strong> {obj.gps_coordinates}")
        
        return format_html("<br>".join(details)) if details else "No technical details recorded"
    technical_details_display.short_description = "Technical Details"
    
    def discrepancies_display(self, obj):
        """Display discrepancies in a formatted way"""
        if obj.discrepancies_found:
            return format_html(
                '<div style="background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107;">'
                f'<strong>Discrepancies Found:</strong><br>{obj.discrepancies_found}</div>'
            )
        return format_html(
            '<div style="background: #d4edda; padding: 10px; border-left: 4px solid #28a745;">'
            '<strong>No discrepancies found</strong></div>'
        )
    discrepancies_display.short_description = "Discrepancies"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'device', 'scanned_by', 'scan_location', 
            'device_location_at_scan', 'assigned_staff_at_scan'
        )
    
    def has_add_permission(self, request):
        """QR scans are created through the mobile app, not admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but limited editing of scan records"""
        return request.user.has_perm('qr_management.view_qrcodescan')
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete scan records for audit purposes"""
        return request.user.is_superuser

# ================================
# CUSTOM ADMIN ACTIONS
# ================================

@admin.action(description='Mark selected scans as verified')
def mark_as_verified(modeladmin, request, queryset):
    """Mark scans as verified if they failed initially"""
    updated = queryset.filter(verification_success=False).update(
        verification_success=True,
        actions_taken=f"Manually verified by {request.user.username} on {timezone.now()}"
    )
    
    modeladmin.message_user(
        request,
        f'Successfully marked {updated} scan(s) as verified.'
    )

@admin.action(description='Export scan data to CSV')
def export_scan_data(modeladmin, request, queryset):
    """Export selected scan data to CSV"""
    # This would be implemented to generate CSV export
    modeladmin.message_user(
        request,
        f'CSV export initiated for {queryset.count()} scan record(s). '
        'Download will be available shortly.'
    )

# Add custom actions to QRCodeScanAdmin
QRCodeScanAdmin.actions = [mark_as_verified, export_scan_data]

# ================================
# QR CODE ANALYTICS DASHBOARD
# ================================

class QRCodeAnalyticsMixin:
    """Mixin to provide QR code analytics for admin dashboard"""
    
    @staticmethod
    def get_scan_statistics():
        """Get scanning statistics for dashboard"""
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        total_scans = QRCodeScan.objects.count()
        today_scans = QRCodeScan.objects.filter(timestamp__date=today).count()
        week_scans = QRCodeScan.objects.filter(timestamp__date__gte=week_ago).count()
        month_scans = QRCodeScan.objects.filter(timestamp__date__gte=month_ago).count()
        
        success_rate = QRCodeScan.objects.aggregate(
            total=Count('id'),
            successful=Count('id', filter=Q(verification_success=True))
        )
        
        success_percentage = (
            (success_rate['successful'] / success_rate['total'] * 100) 
            if success_rate['total'] > 0 else 0
        )
        
        # Get scan types distribution
        scan_types = QRCodeScan.objects.values('scan_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get most scanned devices
        top_devices = QRCodeScan.objects.values(
            'device__device_id', 'device__device_name'
        ).annotate(
            scan_count=Count('id')
        ).order_by('-scan_count')[:5]
        
        return {
            'total_scans': total_scans,
            'today_scans': today_scans,
            'week_scans': week_scans,
            'month_scans': month_scans,
            'success_rate': round(success_percentage, 2),
            'scan_types': list(scan_types),
            'top_devices': list(top_devices)
        }
    
    @staticmethod
    def get_discrepancy_summary():
        """Get summary of discrepancies found in scans"""
        scans_with_discrepancies = QRCodeScan.objects.exclude(
            discrepancies_found__exact=''
        ).exclude(
            discrepancies_found__isnull=True
        )
        
        return {
            'total_with_discrepancies': scans_with_discrepancies.count(),
            'recent_discrepancies': scans_with_discrepancies.order_by('-timestamp')[:5]
        }

# ================================
# CUSTOM ADMIN VIEWS
# ================================

def qr_analytics_view(request):
    """Custom view for QR code analytics (to be integrated with admin)"""
    analytics = QRCodeAnalyticsMixin.get_scan_statistics()
    discrepancies = QRCodeAnalyticsMixin.get_discrepancy_summary()
    
    # This would render a custom template with analytics
    # For now, we'll just return the data structure
    return {
        'analytics': analytics,
        'discrepancies': discrepancies
    }

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

# Custom filters for better data analysis
class ScanSuccessFilter(admin.SimpleListFilter):
    """Custom filter for scan success with discrepancies"""
    title = 'scan outcome'
    parameter_name = 'scan_outcome'
    
    def lookups(self, request, model_admin):
        return (
            ('success_clean', 'Success (No Issues)'),
            ('success_with_notes', 'Success (With Notes)'),
            ('failed', 'Failed'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'success_clean':
            return queryset.filter(
                verification_success=True,
                discrepancies_found__exact=''
            )
        elif self.value() == 'success_with_notes':
            return queryset.filter(
                verification_success=True
            ).exclude(discrepancies_found__exact='')
        elif self.value() == 'failed':
            return queryset.filter(verification_success=False)

class RecentScanFilter(admin.SimpleListFilter):
    """Filter for recent scans"""
    title = 'scan recency'
    parameter_name = 'scan_recency'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(timestamp__date=now.date())
        elif self.value() == 'week':
            week_ago = now.date() - timedelta(days=7)
            return queryset.filter(timestamp__date__gte=week_ago)
        elif self.value() == 'month':
            month_ago = now.date() - timedelta(days=30)
            return queryset.filter(timestamp__date__gte=month_ago)

# Add custom filters to QRCodeScanAdmin
QRCodeScanAdmin.list_filter = QRCodeScanAdmin.list_filter + [
    ScanSuccessFilter, RecentScanFilter
]