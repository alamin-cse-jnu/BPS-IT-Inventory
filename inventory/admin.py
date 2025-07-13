# inventory/admin.py
# Updated admin configuration with Block support

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import (
    Building, Block, Floor, Department, Room, Location,
    Device, DeviceCategory, DeviceSubCategory, DeviceType,
    Assignment, Staff, Vendor, MaintenanceSchedule, AuditLog
)

# ================================
# LOCATION HIERARCHY ADMIN WITH BLOCK SUPPORT
# ================================

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'get_blocks_count', 'get_floors_count', 'get_departments_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'address')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'address', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
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
    
    def get_departments_count(self, obj):
        count = obj.departments.count()
        if count > 0:
            url = reverse('admin:inventory_department_changelist')
            return format_html(
                '<a href="{}?floor__building__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_departments_count.short_description = 'Departments'

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'building', 'get_floors_count', 'get_departments_count', 'is_active', 'created_at')
    list_filter = ('building', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'building__name', 'description')
    list_select_related = ('building',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('building', 'name', 'code', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
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
    
    def get_departments_count(self, obj):
        count = obj.floors.aggregate(dept_count=Count('departments'))['dept_count'] or 0
        if count > 0:
            url = reverse('admin:inventory_department_changelist')
            return format_html(
                '<a href="{}?floor__block__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_departments_count.short_description = 'Departments'

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'block', 'floor_number', 'get_departments_count', 'get_rooms_count', 'is_active')
    list_filter = ('building', 'block', 'is_active', 'created_at')
    search_fields = ('name', 'building__name', 'block__name')
    list_select_related = ('building', 'block')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location Hierarchy', {
            'fields': ('building', 'block')
        }),
        ('Floor Information', {
            'fields': ('name', 'floor_number', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_departments_count(self, obj):
        count = obj.departments.count()
        if count > 0:
            url = reverse('admin:inventory_department_changelist')
            return format_html(
                '<a href="{}?floor__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_departments_count.short_description = 'Departments'
    
    def get_rooms_count(self, obj):
        count = obj.departments.aggregate(room_count=Count('rooms'))['room_count'] or 0
        if count > 0:
            url = reverse('admin:inventory_room_changelist')
            return format_html(
                '<a href="{}?department__floor__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_rooms_count.short_description = 'Rooms'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'get_hierarchy_path', 'head_of_department', 'get_staff_count', 'get_rooms_count', 'is_active')
    list_filter = ('floor__building', 'floor__block', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'head_of_department', 'floor__building__name', 'floor__block__name')
    list_select_related = ('floor__building', 'floor__block')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location Hierarchy', {
            'fields': ('floor',)
        }),
        ('Department Information', {
            'fields': ('name', 'code', 'head_of_department')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_hierarchy_path(self, obj):
        return f"{obj.floor.building.name} → {obj.floor.block.name} → {obj.floor.name}"
    get_hierarchy_path.short_description = 'Location Path'
    
    def get_staff_count(self, obj):
        count = obj.staff.count()
        if count > 0:
            url = reverse('admin:inventory_staff_changelist')
            return format_html(
                '<a href="{}?department__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_staff_count.short_description = 'Staff'
    
    def get_rooms_count(self, obj):
        count = obj.rooms.count()
        if count > 0:
            url = reverse('admin:inventory_room_changelist')
            return format_html(
                '<a href="{}?department__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_rooms_count.short_description = 'Rooms'

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_name', 'get_hierarchy_path', 'capacity', 'get_locations_count', 'is_active')
    list_filter = ('department__floor__building', 'department__floor__block', 'department', 'is_active', 'created_at')
    search_fields = ('room_number', 'room_name', 'department__name', 'department__floor__building__name')
    list_select_related = ('department__floor__building', 'department__floor__block', 'department')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location Assignment', {
            'fields': ('department',)
        }),
        ('Room Information', {
            'fields': ('room_number', 'room_name', 'capacity')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_hierarchy_path(self, obj):
        return f"{obj.department.floor.building.name} → {obj.department.floor.block.name} → {obj.department.floor.name} → {obj.department.name}"
    get_hierarchy_path.short_description = 'Location Path'
    
    def get_locations_count(self, obj):
        count = obj.locations.count()
        if count > 0:
            url = reverse('admin:inventory_location_changelist')
            return format_html(
                '<a href="{}?room__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_locations_count.short_description = 'Locations'

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('get_location_name', 'get_location_code', 'get_hierarchy_path', 'get_assignments_count', 'is_active')
    list_filter = ('building', 'block', 'floor__building', 'department', 'is_active')
    search_fields = ('building__name', 'block__name', 'floor__name', 'department__name', 'room__room_number', 'description')
    list_select_related = ('building', 'block', 'floor', 'department', 'room')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location Hierarchy', {
            'fields': ('building', 'block', 'floor', 'department', 'room')
        }),
        ('Additional Information', {
            'fields': ('description',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_location_name(self, obj):
        """Build location name from components"""
        return str(obj)
    get_location_name.short_description = 'Location Name'
    
    def get_location_code(self, obj):
        """Build location code from components"""
        parts = [obj.building.code, obj.block.code, str(obj.floor.floor_number), obj.department.code]
        if obj.room:
            parts.append(obj.room.room_number)
        return "-".join(parts)
    get_location_code.short_description = 'Location Code'
    
    def get_hierarchy_path(self, obj):
        """Show full hierarchy path"""
        path = f"{obj.building.name} → {obj.block.name} → {obj.floor.name} → {obj.department.name}"
        if obj.room:
            path += f" → {obj.room.room_number}"
        return path
    get_hierarchy_path.short_description = 'Hierarchy Path'
    
    def get_assignments_count(self, obj):
        """Show count of assignments at this location"""
        count = obj.assignments.filter(status='ASSIGNED').count()
        if count > 0:
            url = reverse('admin:inventory_assignment_changelist')
            return format_html(
                '<a href="{}?location__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_assignments_count.short_description = 'Active Assignments'

# ================================
# STAFF ADMIN WITH DEPARTMENT HIERARCHY
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'employee_id', 'designation', 'get_department_hierarchy', 'get_assignments_count', 'is_active')
    list_filter = ('department__floor__building', 'department__floor__block', 'department', 'is_active', 'joining_date')
    search_fields = ('user__first_name', 'user__last_name', 'employee_id', 'designation', 'department__name')
    list_select_related = ('user', 'department__floor__building', 'department__floor__block')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Employee Details', {
            'fields': ('employee_id', 'designation', 'department', 'phone_number', 'joining_date')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Name'
    
    def get_department_hierarchy(self, obj):
        if obj.department:
            return f"{obj.department.floor.building.name} → {obj.department.floor.block.name} → {obj.department.name}"
        return "-"
    get_department_hierarchy.short_description = 'Department Hierarchy'
    
    def get_assignments_count(self, obj):
        count = obj.assignments.filter(status='ASSIGNED').count()
        if count > 0:
            url = reverse('admin:inventory_assignment_changelist')
            return format_html(
                '<a href="{}?staff__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    get_assignments_count.short_description = 'Active Assignments'

# ================================
# DEVICE ADMIN (Updated with Location Hierarchy)
# ================================

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'device_type', 'brand', 'model', 'get_current_location', 'status', 'created_at')
    list_filter = ('status', 'device_type', 'brand', 'created_at', 'current_location__building', 'current_location__block')
    search_fields = ('asset_tag', 'serial_number', 'model', 'brand')
    list_select_related = ('device_type', 'current_location__building', 'current_location__block', 'current_location__department')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_current_location(self, obj):
        if obj.current_location:
            hierarchy = f"{obj.current_location.building.name} → {obj.current_location.block.name} → {obj.current_location.department.name}"
            if obj.current_location.room:
                hierarchy += f" → {obj.current_location.room.room_number}"
            return hierarchy
        return "-"
    get_current_location.short_description = 'Current Location'

# ================================
# ASSIGNMENT ADMIN (Updated with Location Hierarchy)
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('device', 'staff', 'get_location_hierarchy', 'status', 'assigned_date', 'expected_return_date')
    list_filter = ('status', 'assigned_date', 'location__building', 'location__block', 'location__department')
    search_fields = ('device__asset_tag', 'staff__user__first_name', 'staff__user__last_name', 'staff__employee_id')
    list_select_related = ('device', 'staff__user', 'location__building', 'location__block', 'location__department')
    readonly_fields = ('assigned_date', 'created_at', 'updated_at')
    
    def get_location_hierarchy(self, obj):
        if obj.location:
            hierarchy = f"{obj.location.building.name} → {obj.location.block.name} → {obj.location.department.name}"
            if obj.location.room:
                hierarchy += f" → {obj.location.room.room_number}"
            return hierarchy
        return "-"
    get_location_hierarchy.short_description = 'Assignment Location'

# ================================
#  ADMIN CONFIGURATIONS 
# ================================

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')

@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'description', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'category__name', 'description')

@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'category_name', 'description', 'is_active', 'created_at')
    list_filter = ('subcategory__category', 'subcategory', 'is_active', 'created_at')
    search_fields = ('name', 'subcategory__name', 'description')
    
    def category_name(self, obj):
        return obj.subcategory.category.name if obj.subcategory else '-'
    category_name.short_description = 'Category'

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'email', 'phone', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ('device', 'maintenance_type', 'scheduled_date', 'status', 'vendor')
    list_filter = ('maintenance_type', 'status', 'scheduled_date', 'vendor')
    search_fields = ('device__asset_tag', 'device__serial_number', 'vendor__name')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'get_changes_summary')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'model_name', 'object_id')
    readonly_fields = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'changes')
    
    def get_changes_summary(self, obj):
        if obj.changes:
            try:
                import json
                changes = json.loads(obj.changes)
                return f"{len(changes)} field(s) changed"
            except:
                return "Changes recorded"
        return "-"
    get_changes_summary.short_description = 'Changes'