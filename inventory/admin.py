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
    AssignmentHistory, Building, Floor, Room, Block
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

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'get_blocks_count', 'get_floors_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'address')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_floors_count(self, obj):
        count = obj.floors.count()
        if count > 0:
            url = reverse('admin:inventory_floor_changelist')
            return format_html(
                '<a href="{}?building__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_floors_count.short_description = 'Floors'

    def get_blocks_count(self, obj):
        count = obj.blocks.count()
        if count > 0:
            url = reverse('admin:inventory_block_changelist')
            return format_html(
                '<a href="{}?building__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_blocks_count.short_description = 'Blocks'

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'building', 'get_floors_count', 'is_active', 'created_at')
    list_filter = ('building', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'building__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('building',)
    
    fieldsets = (
        ('Block Information', {
            'fields': ('building', 'name', 'code', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_floors_count(self, obj):
        count = obj.floors.count()
        if count > 0:
            url = reverse('admin:inventory_floor_changelist')
            return format_html(
                '<a href="{}?block__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_floors_count.short_description = 'Floors'

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'block', 'floor_number', 'get_departments_count', 'is_active')
    list_filter = ('building', 'block', 'is_active', 'created_at')
    search_fields = ('name', 'building__name', 'block__name')
    list_select_related = ('building', 'block')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_departments_count(self, obj):
        return obj.departments.count()
    get_departments_count.short_description = 'Departments'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'floor', 'head_of_department', 'is_active')
    list_filter = ('floor__building', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'head_of_department')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_name', 'department', 'capacity', 'is_active')
    list_filter = ('department', 'is_active', 'created_at')
    search_fields = ('room_number', 'room_name', 'department__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('get_location_name', 'get_location_code', 'get_location_type', 'is_active')
    list_filter = ('building', 'block', 'floor', 'is_active')
    search_fields = ('building__name', 'block__name', 'floor__name', 'department__name', 'description')
    list_select_related = ('building', 'block', 'floor', 'department', 'room')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_location_name(self, obj):
        """Build location name from components"""
        return str(obj)
    get_location_name.short_description = 'Location Name'
    
    def get_location_code(self, obj):
        """Build location code from components"""
        return f"{obj.building.code}-{obj.block.code}-{obj.floor.floor_number}-{obj.department.code}"
    get_location_code.short_description = 'Location Code'
    
    def get_location_type(self, obj):
        """Determine location type based on room presence"""
        return "Room" if obj.room else "Department"
    get_location_type.short_description = 'Location Type'

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
    readonly_fields = ('created_at', 'updated_at', 'warranty_days_remaining', 'age_display')
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
            'fields': ('processor', 'memory_ram', 'storage_capacity', 'operating_system'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'age_display'),
            'classes': ('collapse',)
        })
    )
    
    def age_display(self, obj):
        """Display device age in years"""
        age = obj.age_in_years
        return f"{age:.2f} years" if age is not None else "N/A"
    age_display.short_description = 'Device Age'
    
    def assigned_display(self, obj):
        """Show current assignment status"""
        current_assignment = Assignment.objects.filter(
            device=obj, is_active=True
        ).first()
        
        if current_assignment:
            if current_assignment.assigned_to_staff:
                return format_html(
                    '<span style="color: green;">Staff: {}</span>',
                    current_assignment.assigned_to_staff.user.get_full_name()
                )
            elif current_assignment.assigned_to_department:
                return format_html(
                    '<span style="color: blue;">Dept: {}</span>',
                    current_assignment.assigned_to_department.name
                )
            elif current_assignment.assigned_to_location:
                return format_html(
                    '<span style="color: orange;">Location: {}</span>',
                    current_assignment.assigned_to_location
                )
        return format_html('<span style="color: gray;">Unassigned</span>')
    assigned_display.short_description = 'Assignment'
    
    def warranty_status(self, obj):
        """Show warranty status with color coding"""
        if obj.warranty_end_date:
            days_remaining = (obj.warranty_end_date - timezone.now().date()).days
            if days_remaining < 0:
                return format_html('<span style="color: red;">Expired</span>')
            elif days_remaining < 30:
                return format_html('<span style="color: orange;">Expiring Soon</span>')
            else:
                return format_html('<span style="color: green;">Active</span>')
        return format_html('<span style="color: gray;">No Warranty</span>')
    warranty_status.short_description = 'Warranty'

# ================================
# ASSIGNMENT MANAGEMENT
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment_id', 'device', 'get_assigned_to', 'assignment_type', 
        'get_assigned_date', 'is_active'
    )
    list_filter = (
        'assignment_type', 'is_active', 'start_date'
    )
    search_fields = (
        'assignment_id', 'device__device_id', 'device__device_name',
        'assigned_to_staff__user__username', 'assigned_to_department__name'
    )
    readonly_fields = ('assignment_id', 'created_at', 'updated_at')
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'assignment_id', 'device', 'assignment_type', 'start_date', 'end_date'
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
    
    def get_assigned_to(self, obj):
        """Get the assignment target"""
        if obj.assigned_to_staff:
            return f"Staff: {obj.assigned_to_staff.user.get_full_name()}"
        elif obj.assigned_to_department:
            return f"Department: {obj.assigned_to_department.name}"
        elif obj.assigned_to_location:
            return f"Location: {obj.assigned_to_location}"
        return "No assignment"
    get_assigned_to.short_description = 'Assigned To'
    
    def get_assigned_date(self, obj):
        """Get the assignment start date"""
        return obj.start_date
    get_assigned_date.short_description = 'Assigned Date'

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
        'user', 'employee_id', 'department', 'designation', 'is_active'
    )
    list_filter = ('department', 'employment_type', 'is_active')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'employee_id', 'designation'
    )
    readonly_fields = ('created_at', 'updated_at')

# ================================
# VENDOR MANAGEMENT
# ================================

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'email', 'phone', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# MAINTENANCE SCHEDULE
# ================================

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'maintenance_type', 'status', 'get_scheduled_date', 'created_at'
    )
    list_filter = (
        'maintenance_type', 'status', 'next_due_date', 'created_at'
    )
    search_fields = ('device__device_id', 'device__device_name')
    date_hierarchy = 'next_due_date'
    readonly_fields = ('created_at', 'updated_at')
    
    def get_scheduled_date(self, obj):
        """Get the scheduled date (next_due_date field)"""
        return obj.next_due_date
    get_scheduled_date.short_description = 'Scheduled Date'

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