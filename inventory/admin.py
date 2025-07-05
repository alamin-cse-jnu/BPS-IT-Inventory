# inventory/admin.py
# Location: bps_inventory/apps/inventory/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    DeviceCategory, DeviceSubCategory, DeviceType, Device, 
    Assignment, Staff, Department, Location, Vendor, 
    MaintenanceSchedule, AuditLog, SystemConfiguration,
    AssignmentHistory
)

# ================================
# DEVICE CATEGORY MANAGEMENT
# ================================

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory_count', 'device_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def subcategory_count(self, obj):
        count = obj.subcategories.count()
        if count > 0:
            url = reverse('admin:inventory_devicesubcategory_changelist')
            return format_html(
                '<a href="{}?category__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    subcategory_count.short_description = 'Subcategories'
    
    def device_count(self, obj):
        count = Device.objects.filter(device_type__subcategory__category=obj).count()
        return count
    device_count.short_description = 'Total Devices'

@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'device_type_count', 'device_count', 'is_active')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def device_type_count(self, obj):
        return obj.device_types.count()
    device_type_count.short_description = 'Device Types'
    
    def device_count(self, obj):
        return Device.objects.filter(device_type__subcategory=obj).count()
    device_count.short_description = 'Total Devices'

@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'device_count', 'is_active')
    list_filter = ('subcategory', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'subcategory__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def device_count(self, obj):
        return obj.devices.count()
    device_count.short_description = 'Devices'

# ================================
# LOCATION MANAGEMENT
# ================================

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('location_name', 'location_code', 'location_type', 'is_active')
    list_filter = ('location_type', 'is_active')
    search_fields = ('location_name', 'location_code', 'description')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# DEVICE MANAGEMENT
# ================================

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'device_id', 'device_name', 'device_type', 'brand', 'model', 
        'status', 'assigned_display', 'warranty_status'
    )
    list_filter = (
        'status', 'device_type', 'brand', 'purchase_date', 'warranty_end_date'
    )
    search_fields = (
        'device_id', 'device_name', 'asset_tag', 'serial_number', 'brand', 'model'
    )
    readonly_fields = ('created_at', 'updated_at', 'age_display', 'warranty_days_remaining')
    list_select_related = ('device_type', 'vendor')
    
    fieldsets = (
        ('Device Information', {
            'fields': (
                'device_id', 'device_name', 'asset_tag', 'serial_number'
            )
        }),
        ('Classification', {
            'fields': ('device_type', 'brand', 'model', 'status')
        }),
        ('Financial Information', {
            'fields': (
                'purchase_price', 'purchase_date', 'vendor'
            ),
            'classes': ('collapse',)
        }),
        ('Warranty Information', {
            'fields': (
                'warranty_start_date', 'warranty_end_date', 
                'warranty_provider', 'warranty_days_remaining'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Specifications', {
            'fields': ('specifications',),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'qr_code'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': (
                'created_by', 'updated_by', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def assigned_display(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            if assignment.assigned_to_staff:
                return f"Staff: {assignment.assigned_to_staff}"
            elif assignment.assigned_to_department:
                return f"Dept: {assignment.assigned_to_department}"
            elif assignment.assigned_to_location:
                return f"Location: {assignment.assigned_to_location}"
        return "Unassigned"
    assigned_display.short_description = 'Current Assignment'
    
    def warranty_status(self, obj):
        if obj.is_under_warranty:
            return format_html(
                '<span style="color: green;">✓ Active ({} days)</span>',
                obj.warranty_days_remaining
            )
        return format_html('<span style="color: red;">✗ Expired</span>')
    warranty_status.short_description = 'Warranty'
    
    def age_display(self, obj):
        if obj.age_in_years:
            return f"{obj.age_in_years:.1f} years"
        return "Unknown"
    age_display.short_description = 'Age'

# ================================
# ASSIGNMENT MANAGEMENT
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment_id', 'device', 'assigned_target', 'assignment_type',
        'assigned_date', 'is_active'
    )
    list_filter = (
        'assignment_type', 'is_active', 'assigned_date'
    )
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__username', 'assigned_to_department__name'
    )
    readonly_fields = ('assignment_id', 'created_at', 'updated_at')
    date_hierarchy = 'assigned_date'
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'assignment_id', 'device', 'assignment_type', 'assigned_date'
            )
        }),
        ('Assignment Targets', {
            'fields': (
                'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
            )
        }),
        ('Assignment Management', {
            'fields': (
                'assigned_by', 'is_active', 'notes'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def assigned_target(self, obj):
        if obj.assigned_to_staff:
            return f"Staff: {obj.assigned_to_staff}"
        elif obj.assigned_to_department:
            return f"Department: {obj.assigned_to_department}"
        elif obj.assigned_to_location:
            return f"Location: {obj.assigned_to_location}"
        return "No assignment"
    assigned_target.short_description = 'Assigned To'

# ================================
# ASSIGNMENT HISTORY MANAGEMENT
# ================================

@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'assignment', 'change_type', 'changed_by', 'timestamp'
    )
    list_filter = ('change_type', 'timestamp')
    search_fields = ('assignment__device__device_id', 'changed_by__username')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)

# ================================
# STAFF MANAGEMENT
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'employee_id', 'department', 'position', 'is_active'
    )
    list_filter = ('department', 'position', 'is_active')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'employee_id', 'position'
    )
    readonly_fields = ('created_at', 'updated_at')

# ================================
# DEPARTMENT MANAGEMENT
# ================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# VENDOR MANAGEMENT
# ================================

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# MAINTENANCE SCHEDULE
# ================================

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'maintenance_type', 'status', 'scheduled_date', 'created_at'
    )
    list_filter = (
        'maintenance_type', 'status', 'scheduled_date', 'created_at'
    )
    search_fields = ('device__device_id', 'device__device_name')
    date_hierarchy = 'scheduled_date'
    readonly_fields = ('created_at', 'updated_at')

# ================================
# SYSTEM CONFIGURATION
# ================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)

# ================================
# AUDIT LOG
# ================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_repr', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'object_repr', 'model_name')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'object_repr', 'changes', 'timestamp', 'ip_address')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# ================================
# ADMIN ACTIONS
# ================================

def mark_devices_as_available(modeladmin, request, queryset):
    """Mark selected devices as available"""
    updated = queryset.update(status='AVAILABLE')
    modeladmin.message_user(
        request, 
        f'{updated} device(s) marked as available.'
    )
mark_devices_as_available.short_description = "Mark selected devices as available"

def mark_devices_as_maintenance(modeladmin, request, queryset):
    """Mark selected devices as under maintenance"""
    updated = queryset.update(status='MAINTENANCE')
    modeladmin.message_user(
        request,
        f'{updated} device(s) marked as under maintenance.'
    )
mark_devices_as_maintenance.short_description = "Mark selected devices as under maintenance"

def deactivate_assignments(modeladmin, request, queryset):
    """Deactivate selected assignments"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} assignment(s) deactivated.'
    )
deactivate_assignments.short_description = "Deactivate selected assignments"

# Add actions to admin classes
DeviceAdmin.actions = [mark_devices_as_available, mark_devices_as_maintenance]
AssignmentAdmin.actions = [deactivate_assignments]