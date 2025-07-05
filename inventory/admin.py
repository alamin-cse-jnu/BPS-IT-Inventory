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
            url = reverse('admin:inventory_devicesubCategory_changelist')
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
    device_count.short_description = 'Devices'

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
# ORGANIZATIONAL STRUCTURE
# ================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'staff_count', 'active_assignments', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def staff_count(self, obj):
        count = obj.staff_members.count()
        if count > 0:
            url = reverse('admin:inventory_staff_changelist')
            return format_html(
                '<a href="{}?department__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    staff_count.short_description = 'Staff'

    def active_assignments(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    active_assignments.short_description = 'Active Assignments'

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'parent_location', 'device_count', 'is_active')
    list_filter = ('location_type', 'is_active', 'parent_location')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('parent_location',)

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    device_count.short_description = 'Devices'

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
        'warranty_end_date', 'device_condition', 'is_critical'
    )
    search_fields = (
        'device_id', 'device_name', 'asset_tag', 'serial_number', 
        'model', 'brand'
    )
    readonly_fields = ('created_at', 'updated_at', 'warranty_status', 'age_display')
    date_hierarchy = 'purchase_date'
    list_select_related = ('device_type', 'vendor', 'location', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('device_id', 'device_name', 'device_type', 'status')
        }),
        ('Hardware Details', {
            'fields': (
                'brand', 'model', 'serial_number', 'asset_tag',
                'device_condition', 'is_critical'
            )
        }),
        ('Technical Specifications', {
            'fields': (
                'processor', 'memory_ram', 'storage_capacity', 'operating_system'
            )
        }),
        ('Location & Assignment', {
            'fields': ('location',)
        }),
        ('Financial Information', {
            'fields': (
                'vendor', 'purchase_date', 'purchase_price', 
                'warranty_start_date', 'warranty_end_date', 'warranty_provider'
            )
        }),
        ('Lifecycle Management', {
            'fields': (
                'expected_life_years', 'disposal_date', 'disposal_method',
                'age_display'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('qr_code', 'notes'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def current_assignment(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            if assignment.assigned_to_staff:
                return assignment.assigned_to_staff.user.get_full_name()
            elif assignment.assigned_to_department:
                return f"Dept: {assignment.assigned_to_department.name}"
            elif assignment.assigned_to_location:
                return f"Loc: {assignment.assigned_to_location.name}"
        return '-'
    current_assignment.short_description = 'Current Assignment'
    
    def warranty_status(self, obj):
        if obj.warranty_end_date:
            days_remaining = (obj.warranty_end_date - timezone.now().date()).days
            if days_remaining > 30:
                return format_html('<span style="color: green;">Valid ({} days)</span>', days_remaining)
            elif days_remaining > 0:
                return format_html('<span style="color: orange;">Expiring ({} days)</span>', days_remaining)
            else:
                return format_html('<span style="color: red;">Expired</span>')
        return 'N/A'
    warranty_status.short_description = 'Warranty'
    
    def age_display(self, obj):
        if obj.purchase_date:
            age = timezone.now().date() - obj.purchase_date
            years = age.days / 365.25
            return f"{years:.1f} years"
        return 'Unknown'
    age_display.short_description = 'Age'

# ================================
# ASSIGNMENT MANAGEMENT
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment_id', 'device', 'assignment_target', 'assignment_type',
        'assignment_date', 'expected_return_date', 'status_display', 'is_active'
    )
    list_filter = (
        'assignment_type', 'is_active', 'is_temporary', 
        'assignment_date', 'expected_return_date'
    )
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__first_name', 'assigned_to_staff__user__last_name',
        'assigned_to_department__name', 'assigned_to_location__name'
    )
    date_hierarchy = 'assignment_date'
    readonly_fields = ('created_at', 'updated_at', 'status_display')
    list_select_related = (
        'device', 'assigned_to_staff__user', 'assigned_to_department', 
        'assigned_to_location', 'assigned_by'
    )
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'device', 'assignment_type', 'is_active', 'is_temporary'
            )
        }),
        ('Assignment Target', {
            'fields': (
                'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
            )
        }),
        ('Dates and Duration', {
            'fields': (
                'assignment_date', 'expected_return_date', 'actual_return_date'
            )
        }),
        ('Assignment Context', {
            'fields': ('purpose', 'notes', 'assigned_by'),
            'classes': ('collapse',)
        }),
        ('Status and Tracking', {
            'fields': ('status_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def assignment_target(self, obj):
        if obj.assigned_to_staff:
            return f"Staff: {obj.assigned_to_staff.user.get_full_name()}"
        elif obj.assigned_to_department:
            return f"Dept: {obj.assigned_to_department.name}"
        elif obj.assigned_to_location:
            return f"Location: {obj.assigned_to_location.name}"
        return 'Unassigned'
    assignment_target.short_description = 'Assigned To'
    
    def status_display(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: gray;">Inactive</span>')
        elif obj.is_temporary and obj.expected_return_date:
            if obj.expected_return_date < timezone.now().date():
                return format_html('<span style="color: red;">Overdue</span>')
            elif obj.expected_return_date <= timezone.now().date() + timedelta(days=7):
                return format_html('<span style="color: orange;">Due Soon</span>')
        return format_html('<span style="color: green;">Active</span>')
    status_display.short_description = 'Status'

@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'assignment', 'action', 'action_date', 'performed_by', 'previous_status', 'new_status'
    )
    list_filter = ('action', 'action_date', 'previous_status', 'new_status')
    search_fields = (
        'assignment__device__device_id', 'assignment__device__device_name',
        'performed_by__username', 'notes'
    )
    date_hierarchy = 'action_date'
    readonly_fields = ('action_date',)

# ================================
# MAINTENANCE MANAGEMENT
# ================================

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'maintenance_type', 'scheduled_date', 'status', 
        'assigned_technician', 'priority', 'created_at'
    )
    list_filter = (
        'maintenance_type', 'status', 'priority', 'scheduled_date', 'created_at'
    )
    search_fields = (
        'device__device_id', 'device__device_name', 
        'assigned_technician__username', 'description'
    )
    date_hierarchy = 'scheduled_date'
    readonly_fields = ('created_at', 'updated_at')

# ================================
# SYSTEM MANAGEMENT
# ================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_repr', 'ip_address')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'object_repr', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'description', 'is_active', 'updated_at', 'updated_by')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at')

# ================================
# ADMIN CUSTOMIZATION
# ================================

admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Inventory Management Dashboard"