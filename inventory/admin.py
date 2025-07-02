
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
import qrcode
from io import BytesIO
import base64

from .models import (
    # Core models
    Device, Staff, Department, Location, Assignment,
    # Category models
    DeviceCategory, DeviceSubcategory, DeviceType,
    # Support models
    Vendor, MaintenanceSchedule, AssignmentHistory,
    AuditLog, ServiceRequest, Notification
)


# ================================
# CUSTOM FILTERS
# ================================

class DeviceStatusFilter(SimpleListFilter):
    title = 'Device Status'
    parameter_name = 'device_status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('maintenance', 'Under Maintenance'),
            ('assigned', 'Assigned'),
            ('available', 'Available'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'assigned':
            return queryset.filter(status='ASSIGNED')
        elif self.value() == 'available':
            return queryset.filter(status='AVAILABLE')
        elif self.value() == 'maintenance':
            return queryset.filter(status='MAINTENANCE')
        elif self.value() == 'active':
            return queryset.filter(status__in=['ASSIGNED', 'AVAILABLE'])
        elif self.value() == 'inactive':
            return queryset.filter(status__in=['RETIRED', 'DISPOSED'])
        return queryset


class WarrantyStatusFilter(SimpleListFilter):
    title = 'Warranty Status'
    parameter_name = 'warranty_status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Under Warranty'),
            ('expiring', 'Expiring Soon (30 days)'),
            ('expired', 'Expired'),
            ('no_warranty', 'No Warranty Info'),
        ]

    def queryset(self, request, queryset):
        today = timezone.now().date()
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
        elif self.value() == 'no_warranty':
            return queryset.filter(warranty_end_date__isnull=True)
        return queryset


class AssignmentStatusFilter(SimpleListFilter):
    title = 'Assignment Status'
    parameter_name = 'assignment_status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active'),
            ('overdue', 'Overdue'),
            ('returned', 'Returned'),
            ('temporary', 'Temporary'),
            ('permanent', 'Permanent'),
        ]

    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'overdue':
            return queryset.filter(
                is_active=True,
                is_temporary=True,
                expected_return_date__lt=today
            )
        elif self.value() == 'returned':
            return queryset.filter(is_active=False)
        elif self.value() == 'temporary':
            return queryset.filter(is_temporary=True)
        elif self.value() == 'permanent':
            return queryset.filter(is_temporary=False)
        return queryset


# ================================
# INLINE ADMIN CLASSES
# ================================

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ('assignment_id', 'created_at', 'updated_at')
    fields = (
        'assignment_id', 'assignment_type', 'assigned_to_staff',
        'assigned_to_department', 'assigned_to_location',
        'start_date', 'expected_return_date', 'is_active', 'created_at'
    )
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
        )


class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = (
        'maintenance_type', 'scheduled_date', 'status',
        'vendor', 'estimated_cost', 'created_at'
    )


class DeviceSubcategoryInline(admin.TabularInline):
    model = DeviceSubcategory
    extra = 0
    fields = ('name', 'description', 'is_active')


class DeviceTypeInline(admin.TabularInline):
    model = DeviceType
    extra = 0
    fields = ('name', 'description', 'specifications', 'is_active')


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'subcategory_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DeviceSubcategoryInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def subcategory_count(self, obj):
        return obj.subcategories.count()
    subcategory_count.short_description = 'Subcategories'


@admin.register(DeviceSubcategory)
class DeviceSubcategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'device_type_count', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DeviceTypeInline]
    
    fieldsets = (
        (None, {
            'fields': ('category', 'name', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def device_type_count(self, obj):
        return obj.device_types.count()
    device_type_count.short_description = 'Device Types'


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'category_name', 'device_count', 'is_active')
    list_filter = ('subcategory__category', 'subcategory', 'is_active')
    search_fields = ('name', 'description', 'subcategory__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('subcategory', 'name', 'description', 'is_active')
        }),
        ('Specifications', {
            'fields': ('specifications',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def category_name(self, obj):
        return obj.subcategory.category.name if obj.subcategory else '-'
    category_name.short_description = 'Category'

    def device_count(self, obj):
        return obj.devices.count()
    device_count.short_description = 'Devices'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'staff_count', 'device_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('authorized_staff',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'head_of_department', 'is_active')
        }),
        ('Authorization', {
            'fields': ('authorized_staff',),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'location'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def staff_count(self, obj):
        return obj.staff_members.count()
    staff_count.short_description = 'Staff Count'

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    device_count.short_description = 'Assigned Devices'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'building', 'floor', 'device_count', 'is_active')
    list_filter = ('location_type', 'building', 'floor', 'is_active')
    search_fields = ('name', 'description', 'building', 'room_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'location_type', 'description', 'is_active')
        }),
        ('Physical Location', {
            'fields': ('building', 'floor', 'room_number', 'coordinates'),
        }),
        ('Contact', {
            'fields': ('contact_person', 'phone', 'email'),
            'classes': ('collapse',)
        }),
        ('Environmental', {
            'fields': ('environmental_conditions',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count()
    device_count.short_description = 'Devices'


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'designation', 'department', 'phone', 'is_active')
    list_filter = ('department', 'designation', 'is_active', 'joining_date')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('employee_id', 'first_name', 'last_name', 'email', 'phone')
        }),
        ('Employment Details', {
            'fields': ('designation', 'department', 'reporting_manager', 'joining_date', 'is_active')
        }),
        ('System Access', {
            'fields': ('user_account', 'security_clearance'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('emergency_contact', 'address', 'employee_photo'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Full Name'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'phone', 'email', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'vendor_type', 'description', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'phone', 'email', 'website', 'address')
        }),
        ('Business Details', {
            'fields': ('tax_id', 'registration_number', 'bank_details'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('rating', 'performance_notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'device_id', 'device_name', 'device_type', 'status',
        'current_assignment', 'warranty_status', 'actions'
    )
    list_filter = (
        DeviceStatusFilter, WarrantyStatusFilter, 'device_type',
        'vendor', 'purchase_date', 'created_at'
    )
    search_fields = (
        'device_id', 'asset_tag', 'device_name', 'serial_number',
        'mac_address', 'ip_address'
    )
    readonly_fields = (
        'device_id', 'qr_code_image', 'age_in_years',
        'warranty_days_remaining', 'created_at', 'updated_at'
    )
    inlines = [AssignmentInline, MaintenanceInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'device_id', 'asset_tag', 'device_name', 'device_type',
                'status', 'qr_code_image'
            )
        }),
        ('Technical Specifications', {
            'fields': (
                'brand', 'model', 'serial_number', 'mac_address',
                'ip_address', 'specifications'
            )
        }),
        ('Procurement Information', {
            'fields': (
                'vendor', 'purchase_date', 'purchase_order_number',
                'purchase_price', 'age_in_years'
            )
        }),
        ('Warranty Information', {
            'fields': (
                'warranty_start_date', 'warranty_end_date',
                'warranty_type', 'warranty_days_remaining'
            )
        }),
        ('Additional Details', {
            'fields': ('notes', 'custom_fields'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_assignment(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            if assignment.assigned_to_staff:
                return format_html(
                    '<a href="{}">{}</a>',
                    reverse('admin:inventory_assignment_change', args=[assignment.pk]),
                    assignment.assigned_to_staff
                )
            elif assignment.assigned_to_department:
                return format_html(
                    '<a href="{}">{}</a>',
                    reverse('admin:inventory_assignment_change', args=[assignment.pk]),
                    assignment.assigned_to_department
                )
            elif assignment.assigned_to_location:
                return format_html(
                    '<a href="{}">{}</a>',
                    reverse('admin:inventory_assignment_change', args=[assignment.pk]),
                    assignment.assigned_to_location
                )
        return '-'
    current_assignment.short_description = 'Current Assignment'

    def warranty_status(self, obj):
        if obj.is_under_warranty:
            days_remaining = obj.warranty_days_remaining
            if days_remaining <= 30:
                return format_html(
                    '<span style="color: orange;">Expiring ({} days)</span>',
                    days_remaining
                )
            else:
                return format_html(
                    '<span style="color: green;">Active ({} days)</span>',
                    days_remaining
                )
        else:
            return format_html('<span style="color: red;">Expired</span>')
    warranty_status.short_description = 'Warranty'

    def qr_code_image(self, obj):
        if obj.device_id:
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr_data = {
                "deviceId": obj.device_id,
                "verifyUrl": f"/verify/{obj.device_id}/"
            }
            qr.add_data(str(qr_data))
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return format_html(
                '<img src="data:image/png;base64,{}" width="100" height="100" />',
                img_str
            )
        return '-'
    qr_code_image.short_description = 'QR Code'

    def actions(self, obj):
        return format_html(
            '<a class="button" href="{}">View Details</a> '
            '<a class="button" href="{}">QR Code</a>',
            reverse('inventory:device_detail', args=[obj.device_id]),
            reverse('inventory:device_qr_code', args=[obj.device_id])
        )
    actions.short_description = 'Actions'


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'assignment_id', 'device', 'assignment_target', 'assignment_type',
        'start_date', 'expected_return_date', 'status_display', 'actions'
    )
    list_filter = (
        AssignmentStatusFilter, 'assignment_type', 'is_temporary',
        'start_date', 'expected_return_date'
    )
    search_fields = (
        'assignment_id', 'device__device_id', 'device__device_name',
        'assigned_to_staff__first_name', 'assigned_to_staff__last_name',
        'assigned_to_department__name'
    )
    readonly_fields = ('assignment_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'assignment_id', 'device', 'assignment_type',
                'start_date', 'expected_return_date', 'actual_return_date'
            )
        }),
        ('Assignment Target', {
            'fields': (
                'assigned_to_staff', 'assigned_to_department', 'assigned_to_location'
            )
        }),
        ('Additional Information', {
            'fields': ('purpose', 'notes', 'is_active', 'is_temporary'),
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def assignment_target(self, obj):
        if obj.assigned_to_staff:
            return format_html(
                '👤 <a href="{}">{}</a>',
                reverse('admin:inventory_staff_change', args=[obj.assigned_to_staff.pk]),
                obj.assigned_to_staff
            )
        elif obj.assigned_to_department:
            return format_html(
                '🏢 <a href="{}">{}</a>',
                reverse('admin:inventory_department_change', args=[obj.assigned_to_department.pk]),
                obj.assigned_to_department
            )
        elif obj.assigned_to_location:
            return format_html(
                '📍 <a href="{}">{}</a>',
                reverse('admin:inventory_location_change', args=[obj.assigned_to_location.pk]),
                obj.assigned_to_location
            )
        return '-'
    assignment_target.short_description = 'Assigned To'

    def status_display(self, obj):
        if obj.is_active:
            if obj.is_overdue:
                return format_html('<span style="color: red;">⚠️ Overdue</span>')
            else:
                return format_html('<span style="color: green;">✅ Active</span>')
        else:
            return format_html('<span style="color: gray;">📋 Returned</span>')
    status_display.short_description = 'Status'

    def actions(self, obj):
        actions_html = []
        if obj.is_active:
            if obj.is_temporary:
                actions_html.append(
                    f'<a class="button" href="{reverse("inventory:assignment_return", args=[obj.pk])}">Return</a>'
                )
            actions_html.append(
                f'<a class="button" href="{reverse("inventory:assignment_transfer", args=[obj.pk])}">Transfer</a>'
            )
        
        actions_html.append(
            f'<a class="button" href="{reverse("inventory:assignment_detail", args=[obj.pk])}">View</a>'
        )
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'maintenance_type', 'scheduled_date', 'status',
        'vendor', 'estimated_cost', 'completion_date'
    )
    list_filter = ('maintenance_type', 'status', 'scheduled_date', 'vendor')
    search_fields = ('device__device_id', 'device__device_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Maintenance Details', {
            'fields': (
                'device', 'maintenance_type', 'description', 'priority', 'status'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_date', 'estimated_duration', 'completion_date'
            )
        }),
        ('Vendor & Cost', {
            'fields': (
                'vendor', 'estimated_cost', 'actual_cost'
            )
        }),
        ('Results', {
            'fields': ('maintenance_notes', 'next_maintenance_date'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'action', 'timestamp', 'old_staff', 'new_staff',
        'old_location', 'new_location', 'changed_by'
    )
    list_filter = ('action', 'timestamp')
    search_fields = ('device__device_id', 'reason')
    readonly_fields = ('timestamp',)


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


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_id', 'device', 'request_type', 'status',
        'requested_by', 'created_at', 'priority'
    )
    list_filter = ('request_type', 'status', 'priority', 'created_at')
    search_fields = ('request_id', 'device__device_id', 'title', 'description')
    readonly_fields = ('request_id', 'created_at', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'notification_type', 'recipient', 'is_read',
        'created_at', 'expires_at'
    )
    list_filter = ('notification_type', 'is_read', 'created_at', 'priority')
    search_fields = ('title', 'message', 'recipient__username')
    readonly_fields = ('created_at',)


# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

# Customize admin site header and title
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Inventory Management Dashboard"