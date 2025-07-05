# inventory/admin.py
"""
Simple, working admin configuration for BPS IT Inventory System
This version avoids all the complex conditional logic and just works
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import date, timedelta

# Core models that always exist
from .models import (
    Department, Location, DeviceCategory, DeviceSubCategory, 
    DeviceType, Vendor, Staff, Device, Assignment, AuditLog
)

# Import optional models safely
try:
    from .models import MaintenanceSchedule
    HAS_MAINTENANCE = True
except ImportError:
    HAS_MAINTENANCE = False

try:
    from .models import AssignmentHistory
    HAS_ASSIGNMENT_HISTORY = True
except ImportError:
    HAS_ASSIGNMENT_HISTORY = False

try:
    from .models import ServiceRequest
    HAS_SERVICE_REQUEST = True
except ImportError:
    HAS_SERVICE_REQUEST = False

try:
    from .models import Notification
    HAS_NOTIFICATION = True
except ImportError:
    HAS_NOTIFICATION = False

try:
    from .models import Room, Building, Floor
    HAS_BUILDING_MODELS = True
except ImportError:
    HAS_BUILDING_MODELS = False

try:
    from .models import DeviceMovement, DeviceHistory
    HAS_DEVICE_TRACKING = True
except ImportError:
    HAS_DEVICE_TRACKING = False


# ================================
# CUSTOM FILTERS
# ================================

class DeviceStatusFilter(admin.SimpleListFilter):
    title = 'Device Status'
    parameter_name = 'device_status'

    def lookups(self, request, model_admin):
        return (
            ('available', 'Available'),
            ('assigned', 'Assigned'),
            ('maintenance', 'Under Maintenance'),
            ('retired', 'Retired'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value().upper())


class WarrantyStatusFilter(admin.SimpleListFilter):
    title = 'Warranty Status'
    parameter_name = 'warranty_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Under Warranty'),
            ('expiring', 'Expiring Soon (30 days)'),
            ('expired', 'Expired'),
        )

    def queryset(self, request, queryset):
        today = date.today()
        thirty_days = today + timedelta(days=30)
        
        if self.value() == 'active':
            return queryset.filter(warranty_end_date__gte=today)
        elif self.value() == 'expiring':
            return queryset.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=thirty_days
            )
        elif self.value() == 'expired':
            return queryset.filter(warranty_end_date__lt=today)


# ================================
# INLINE ADMIN CLASSES
# ================================

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ('created_at',)
    fields = (
        'assigned_to_staff', 'assigned_to_department', 'assigned_to_location',
        'is_active', 'created_at'
    )


# ================================
# DEVICE CATEGORIZATION ADMIN
# ================================

class DeviceSubCategoryInline(admin.TabularInline):
    model = DeviceSubCategory
    extra = 0
    fields = ('name', 'description', 'is_active')


class DeviceTypeInline(admin.TabularInline):
    model = DeviceType
    extra = 0
    fields = ('name', 'description', 'is_active')


@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description_short', 'subcategory_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DeviceSubCategoryInline]

    def subcategory_count(self, obj):
        return obj.subcategories.count()
    subcategory_count.short_description = 'Subcategories'
    
    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_short.short_description = 'Description'


@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'device_type_count', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DeviceTypeInline]

    def device_type_count(self, obj):
        return obj.device_types.count()
    device_type_count.short_description = 'Device Types'


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'category_name', 'device_count', 'is_active')
    list_filter = ('subcategory__category', 'subcategory', 'is_active')
    search_fields = ('name', 'description', 'subcategory__name')
    readonly_fields = ('created_at', 'updated_at')

    def category_name(self, obj):
        return obj.subcategory.category.name if obj.subcategory else '-'
    category_name.short_description = 'Category'

    def device_count(self, obj):
        return obj.devices.count()
    device_count.short_description = 'Devices'


# ================================
# DEPARTMENT & LOCATION ADMIN
# ================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'staff_count', 'device_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def staff_count(self, obj):
        return obj.staff_members.count()
    staff_count.short_description = 'Staff'

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    device_count.short_description = 'Assigned Devices'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'device_count', 'is_active')
    list_filter = ('location_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    device_count.short_description = 'Devices'


# ================================
# STAFF & VENDOR ADMIN
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'designation', 'department', 'phone_number', 'is_active')
    list_filter = ('department', 'is_active', 'employment_type')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def full_name(self, obj):
        return obj.user.get_full_name() if obj.user else obj.employee_id
    full_name.short_description = 'Full Name'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'phone', 'email', 'is_active')
    list_filter = ('vendor_type', 'is_active')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')


# ================================
# DEVICE ADMIN
# ================================

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'device_id', 'device_name', 'device_type', 'status',
        'current_assignment', 'warranty_status'
    )
    list_filter = (
        DeviceStatusFilter, WarrantyStatusFilter, 'device_type',
        'vendor', 'purchase_date'
    )
    search_fields = (
        'device_id', 'asset_tag', 'device_name', 'serial_number'
    )
    readonly_fields = ('device_id', 'created_at', 'updated_at')
    inlines = [AssignmentInline]

    def current_assignment(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            if assignment.assigned_to_staff:
                return format_html(
                    '<a href="{}">{}</a>',
                    reverse('admin:inventory_assignment_change', args=[assignment.assignment_id]),
                    assignment.assigned_to_staff
                )
            elif assignment.assigned_to_location:
                return f"Location: {assignment.assigned_to_location}"
        return format_html('<span style="color: gray;">Unassigned</span>')
    current_assignment.short_description = 'Current Assignment'

    def warranty_status(self, obj):
        if not obj.warranty_end_date:
            return format_html('<span style="color: gray;">No Warranty</span>')
        
        today = timezone.now().date()
        days_remaining = (obj.warranty_end_date - today).days
        
        if days_remaining > 30:
            return format_html('<span style="color: green;">✅ {} days</span>', days_remaining)
        elif days_remaining > 0:
            return format_html('<span style="color: orange;">⚠️ {} days</span>', days_remaining)
        else:
            return format_html('<span style="color: red;">❌ Expired</span>')
    warranty_status.short_description = 'Warranty'


# ================================
# ASSIGNMENT ADMIN
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'assigned_to_staff', 'assigned_to_department',
        'assigned_to_location', 'start_date', 'is_active', 'assignment_status'
    )
    list_filter = ('is_active', 'start_date', 'assigned_to_department')
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__first_name', 'assigned_to_staff__user__last_name'
    )
    readonly_fields = ('created_at', 'updated_at')

    def assignment_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: gray;">📋 Returned</span>')
        else:
            return format_html('<span style="color: green;">✅ Active</span>')
    assignment_status.short_description = 'Status'


# ================================
# AUDIT LOG ADMIN
# ================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_repr')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'object_repr', 'model_name')
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# ================================
# CONDITIONAL OPTIONAL MODEL REGISTRATION
# ================================

# Only register models that exist
if HAS_BUILDING_MODELS:
    try:
        @admin.register(Building)
        class BuildingAdmin(admin.ModelAdmin):
            list_display = ('name', 'floor_count')
            search_fields = ('name',)

            def floor_count(self, obj):
                return obj.floors.count() if hasattr(obj, 'floors') else 0
            floor_count.short_description = 'Floors'

        @admin.register(Floor)
        class FloorAdmin(admin.ModelAdmin):
            list_display = ('name', 'building', 'room_count')
            list_filter = ('building',)
            search_fields = ('name',)

            def room_count(self, obj):
                return obj.rooms.count() if hasattr(obj, 'rooms') else 0
            room_count.short_description = 'Rooms'

        @admin.register(Room)
        class RoomAdmin(admin.ModelAdmin):
            list_display = ('name', 'floor')
            list_filter = ('floor',)
            search_fields = ('name',)
    except:
        pass

if HAS_MAINTENANCE:
    try:
        @admin.register(MaintenanceSchedule)
        class MaintenanceScheduleAdmin(admin.ModelAdmin):
            list_display = ('device', 'maintenance_type', 'scheduled_date', 'status')
            list_filter = ('status', 'maintenance_type', 'scheduled_date')
            search_fields = ('device__device_id', 'device__device_name')
    except:
        pass

if HAS_ASSIGNMENT_HISTORY:
    try:
        @admin.register(AssignmentHistory)
        class AssignmentHistoryAdmin(admin.ModelAdmin):
            list_display = ('device', 'action', 'timestamp', 'changed_by')
            list_filter = ('action', 'timestamp')
            search_fields = ('device__device_id',)
            readonly_fields = ('timestamp',)
            
            def has_add_permission(self, request):
                return False
    except:
        pass

if HAS_SERVICE_REQUEST:
    try:
        @admin.register(ServiceRequest)
        class ServiceRequestAdmin(admin.ModelAdmin):
            list_display = ('device', 'status', 'created_at')
            list_filter = ('status', 'created_at')
            search_fields = ('device__device_id',)
    except:
        pass

if HAS_NOTIFICATION:
    try:
        @admin.register(Notification)
        class NotificationAdmin(admin.ModelAdmin):
            list_display = ('recipient', 'is_read', 'created_at')
            list_filter = ('is_read', 'created_at')
            search_fields = ('recipient__username',)
    except:
        pass

if HAS_DEVICE_TRACKING:
    try:
        @admin.register(DeviceMovement)
        class DeviceMovementAdmin(admin.ModelAdmin):
            list_display = ('device', 'from_location', 'to_location', 'movement_date')
            list_filter = ('movement_date',)
            search_fields = ('device__device_id',)
            readonly_fields = ('movement_date',)

        @admin.register(DeviceHistory)
        class DeviceHistoryAdmin(admin.ModelAdmin):
            list_display = ('device', 'action', 'changed_at', 'changed_by')
            list_filter = ('action', 'changed_at')
            search_fields = ('device__device_id',)
            readonly_fields = ('changed_at',)
            
            def has_add_permission(self, request):
                return False
    except:
        pass


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Mark selected devices as available')
def mark_devices_available(modeladmin, request, queryset):
    updated = queryset.update(status='AVAILABLE')
    modeladmin.message_user(request, f'{updated} devices marked as available.')

DeviceAdmin.actions = [mark_devices_available]


# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Inventory Management Dashboard"

print("✅ BPS Inventory Admin loaded successfully!")