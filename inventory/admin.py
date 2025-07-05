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
    list_display = ('name', 'subcategory', 'code', 'device_count', 'is_active')
    list_filter = ('subcategory', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def device_count(self, obj):
        return obj.devices.count()
    device_count.short_description = 'Devices'

# ================================
# LOCATION MANAGEMENT
# ================================

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'location_type', 'parent_location', 'device_count', 'created_at'  # Fixed field names
    )
    list_filter = (
        'location_type', 'created_at'  # Removed non-existent 'parent_location' from filter
    )
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def device_count(self, obj):
        return Assignment.objects.filter(
            assigned_to_location=obj, is_active=True
        ).count()
    device_count.short_description = 'Assigned Devices'

# ================================
# STAFF MANAGEMENT
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id', 'full_name', 'designation', 'department', 
        'phone_number', 'assignment_count', 'is_active'
    )
    list_filter = ('department', 'is_active', 'employment_type', 'created_at')
    search_fields = (
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'phone_number'
    )
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user', 'department')

    def full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return obj.employee_id
    full_name.short_description = 'Full Name'

    def assignment_count(self, obj):
        count = obj.device_assignments.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:inventory_assignment_changelist')
            return format_html(
                '<a href="{}?assigned_to_staff__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    assignment_count.short_description = 'Active Assignments'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'staff_count', 'device_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def staff_count(self, obj):
        return obj.staff_members.filter(is_active=True).count()
    staff_count.short_description = 'Staff'
    
    def device_count(self, obj):
        return Assignment.objects.filter(
            assigned_to_department=obj, is_active=True
        ).count()
    device_count.short_description = 'Devices'

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'phone', 'email', 'device_count', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')

    def device_count(self, obj):
        return obj.devices.count()
    device_count.short_description = 'Devices'

# ================================
# DEVICE MANAGEMENT
# ================================

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'device_id', 'device_name', 'device_type', 'status', 
        'current_assignment', 'warranty_status', 'purchase_date'
    )
    list_filter = (
        'status', 'device_type', 'vendor', 'purchase_date', 
        'warranty_end_date', 'device_condition'
    )
    search_fields = (
        'device_id', 'device_name', 'asset_tag', 'serial_number'
    )
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    date_hierarchy = 'purchase_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'device_id', 'device_name', 'device_type', 'status', 
                'device_condition', 'asset_tag', 'serial_number'
            )
        }),
        ('Hardware Details', {
            'fields': ('manufacturer', 'model', 'specifications'),
            'classes': ('collapse',)
        }),
        ('Financial Information', {
            'fields': (
                'vendor', 'purchase_date', 'purchase_price', 
                'warranty_start_date', 'warranty_end_date'
            ),
            'classes': ('collapse',)
        }),
        ('Lifecycle', {
            'fields': ('expected_life_years', 'disposal_date', 'disposal_method'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes', 'qr_code'),
            'classes': ('collapse',)
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def current_assignment(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            if assignment.assigned_to_staff:
                return assignment.assigned_to_staff
            elif assignment.assigned_to_department:
                return assignment.assigned_to_department
            elif assignment.assigned_to_location:
                return assignment.assigned_to_location
        return "Unassigned"
    current_assignment.short_description = 'Current Assignment'
    
    def warranty_status(self, obj):
        if obj.warranty_end_date:
            days_remaining = obj.warranty_days_remaining
            if days_remaining > 0:
                return format_html(
                    '<span style="color: green;">{} days</span>',
                    days_remaining
                )
            else:
                return format_html('<span style="color: red;">Expired</span>')
        return "No warranty"
    warranty_status.short_description = 'Warranty'

# ================================
# ASSIGNMENT MANAGEMENT
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment_id', 'device', 'assigned_target', 'assignment_type', 
        'start_date', 'is_active'  # Fixed field names
    )
    list_filter = (
        'assignment_type', 'is_active', 'start_date'  # Fixed field names
    )
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__first_name', 'assigned_to_staff__user__last_name'
    )
    date_hierarchy = 'start_date'  # Fixed field name
    readonly_fields = ('created_at', 'updated_at')
    
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
        'assignment', 'created_at'  # Simplified to only show existing fields
    )
    list_filter = ('created_at',)  # Simplified filter
    search_fields = ('assignment__device__device_id',)
    date_hierarchy = 'created_at'  # Fixed field name
    readonly_fields = ('created_at',)

# ================================
# MAINTENANCE SCHEDULE
# ================================

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'maintenance_type', 'created_at', 'status'  # Fixed field names
    )
    list_filter = (
        'maintenance_type', 'status', 'created_at'  # Fixed field names
    )
    search_fields = ('device__device_id', 'device__device_name')
    date_hierarchy = 'created_at'  # Fixed field name
    readonly_fields = ('created_at', 'updated_at')

# ================================
# SYSTEM CONFIGURATION
# ================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at')  # Removed non-existent fields

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