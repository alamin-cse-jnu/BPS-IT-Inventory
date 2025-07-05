from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import date, timedelta
import qrcode
from io import BytesIO
import base64

from .models import (
    Department, Location, DeviceCategory, DeviceSubCategory, 
    DeviceType, Vendor, Staff, Device, Assignment, AuditLog
)

# Import optional models that may not exist
try:
    from .models import AssignmentHistory, MaintenanceSchedule, ServiceRequest, Notification
except ImportError:
    AssignmentHistory = None
    MaintenanceSchedule = None
    ServiceRequest = None
    Notification = None

try:
    from .models import Room, Building, Floor, Organization
except ImportError:
    Room = None
    Building = None
    Floor = None
    Organization = None

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
            return queryset.filter(warranty_end_date__gte=today, warranty_end_date__lte=thirty_days)
        elif self.value() == 'expired':
            return queryset.filter(warranty_end_date__lt=today)


# ================================
# INLINE ADMIN CLASSES
# ================================

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ('created_at', 'assignment_duration')
    fields = (
        'assigned_to_staff', 'assigned_to_department', 'assigned_to_location',
        'is_temporary', 'expected_return_date', 'is_active', 'created_at'
    )

    def assignment_duration(self, obj):
        """Calculate and display assignment duration."""
        if obj.created_at:
            end_date = obj.actual_return_date or timezone.now().date()
            return f"{(end_date - obj.created_at.date()).days} days"
        return '-'
    assignment_duration.short_description = 'Duration'


class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0
    readonly_fields = ('created_at', 'cost_display')
    fields = (
        'maintenance_type', 'scheduled_date', 'status', 'priority',
        'vendor', 'estimated_cost', 'created_at'
    )

    def cost_display(self, obj):
        """Display formatted estimated cost."""
        return f"৳{obj.estimated_cost:,.2f}" if obj.estimated_cost else '-'
    cost_display.short_description = 'Est. Cost'


# ================================
# ORGANIZATION STRUCTURE ADMIN
# ================================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'type', 'contact_email', 'is_active')
    list_filter = ('type', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'contact_email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'address', 'floor_count')
    list_filter = ('organization', 'created_at')
    search_fields = ('name', 'code', 'address')
    readonly_fields = ('created_at', 'updated_at')

    def floor_count(self, obj):
        """Count floors in the building."""
        return obj.floors.count() if hasattr(obj, 'floors') else 0
    floor_count.short_description = 'Floors'


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor_number', 'room_count')
    list_filter = ('building', 'floor_number')
    search_fields = ('name', 'building__name')
    readonly_fields = ('created_at', 'updated_at')

    def room_count(self, obj):
        """Count rooms on the floor."""
        return obj.rooms.count() if hasattr(obj, 'rooms') else 0
    room_count.short_description = 'Rooms'


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_number', 'floor', 'room_type', 'capacity', 'location_count')
    list_filter = ('room_type', 'floor__building', 'floor')
    search_fields = ('name', 'room_number', 'floor__name')
    readonly_fields = ('created_at', 'updated_at')

    def location_count(self, obj):
        """Count locations in the room."""
        return obj.locations.count() if hasattr(obj, 'locations') else 0
    location_count.short_description = 'Locations'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head_of_department', 'staff_count', 'device_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'description', 'head_of_department', 'is_active')}),
        ('Contact Information', {'fields': ('phone', 'email'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def staff_count(self, obj):
        """Count staff members in the department."""
        return obj.staff_members.count() if hasattr(obj, 'staff_members') else 0
    staff_count.short_description = 'Staff'

    def device_count(self, obj):
        """Count devices assigned to the department."""
        return obj.device_assignments.filter(is_active=True).count() if hasattr(obj, 'device_assignments') else 0
    device_count.short_description = 'Assigned Devices'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'building', 'device_count', 'is_active')
    list_filter = ('location_type', 'is_active')
    search_fields = ('name', 'description', 'building')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'location_type', 'description', 'is_active')}),
        ('Physical Location', {'fields': ('building', 'floor', 'room_number')}),
        ('Contact', {'fields': ('contact_person', 'phone', 'email'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def device_count(self, obj):
        """Count devices at the location."""
        return obj.device_assignments.filter(is_active=True).count() if hasattr(obj, 'device_assignments') else 0
    device_count.short_description = 'Devices'


# ================================
# DEVICE CATEGORIZATION ADMIN
# ================================

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'subcategory_count', 'description_short')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def subcategory_count(self, obj):
        """Count subcategories."""
        return obj.subcategories.count()
    subcategory_count.short_description = 'Subcategories'

    def description_short(self, obj):
        """Display shortened description."""
        return f"{obj.description[:50]}{'...' if len(obj.description) > 50 else ''}"
    description_short.short_description = 'Description'


@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'code', 'device_type_count')
    list_filter = ('category',)
    search_fields = ('name', 'code', 'category__name')
    readonly_fields = ('created_at', 'updated_at')

    def device_type_count(self, obj):
        """Count device types."""
        return obj.device_types.count()
    device_type_count.short_description = 'Device Types'


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'model_number', 'device_count')
    list_filter = ('subcategory__category', 'subcategory')
    search_fields = ('name', 'model_number', 'manufacturer')
    readonly_fields = ('created_at', 'updated_at')

    def device_count(self, obj):
        """Count devices of this type."""
        return obj.devices.count()
    device_count.short_description = 'Devices'


# ================================
# STAFF & VENDOR ADMIN
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'designation', 'department', 'phone_number', 'is_active')
    list_filter = ('department', 'designation', 'is_active', 'joining_date', 'employment_type')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Personal Information', {'fields': ('user', 'employee_id', 'phone_number')}),
        ('Employment Details', {'fields': ('designation', 'department', 'employment_type', 'joining_date', 'leaving_date', 'is_active')}),
        ('Location', {'fields': ('office_location',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def full_name(self, obj):
        """Display staff full name."""
        return obj.user.get_full_name() if obj.user else obj.employee_id
    full_name.short_description = 'Full Name'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'phone', 'email', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'vendor_type', 'is_active')}),
        ('Contact Information', {'fields': ('contact_person', 'phone', 'email', 'website', 'address')}),
        ('Business Details', {'fields': ('tax_id',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ================================
# DEVICE ADMIN
# ================================

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
    search_fields = ('device_id', 'asset_tag', 'device_name', 'serial_number')
    readonly_fields = (
        'device_id', 'qr_code_image', 'age_in_years',
        'warranty_days_remaining', 'created_at', 'updated_at'
    )
    inlines = [AssignmentInline] + ([MaintenanceInline] if MaintenanceSchedule else [])
    fieldsets = (
        ('Basic Information', {
            'fields': ('device_id', 'asset_tag', 'device_name', 'device_type', 'serial_number', 'status')
        }),
        ('Technical Details', {'fields': ('brand', 'model')}),
        ('Purchase Information', {
            'fields': ('vendor', 'purchase_date', 'purchase_price', 'warranty_start_date', 'warranty_end_date')
        }),
        ('QR Code & Tracking', {'fields': ('qr_code_image', 'qr_code'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'), 'classes': ('collapse',)}),
    )

    def current_assignment(self, obj):
        """Display current assignment information."""
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
        """Display warranty status with color coding."""
        if not obj.warranty_end_date:
            return format_html('<span style="color: gray;">No Warranty</span>')
        today = timezone.now().date()
        days_remaining = (obj.warranty_end_date - today).days
        if days_remaining > 30:
            return format_html('<span style="color: green;">✅ {} days</span>', days_remaining)
        elif days_remaining > 0:
            return format_html('<span style="color: orange;">⚠️ {} days</span>', days_remaining)
        return format_html('<span style="color: red;">❌ Expired</span>')
    warranty_status.short_description = 'Warranty'

    def qr_code_image(self, obj):
        """Generate and display QR code."""
        if not obj.device_id:
            return "No Device ID"
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr_data = {"deviceId": obj.device_id, "verifyUrl": f"/verify/{obj.device_id}/"}
            qr.add_data(str(qr_data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return format_html('<img src="data:image/png;base64,{}" style="width: 150px; height: 150px;" />', img_str)
        except Exception as e:
            return f"Error generating QR: {str(e)}"
    qr_code_image.short_description = 'QR Code'

    def age_in_years(self, obj):
        """Calculate device age in years."""
        if obj.purchase_date:
            age = (timezone.now().date() - obj.purchase_date).days / 365.25
            return f"{age:.1f} years"
        return '-'
    age_in_years.short_description = 'Age'

    def warranty_days_remaining(self, obj):
        """Calculate remaining warranty days."""
        if obj.warranty_end_date:
            days = (obj.warranty_end_date - timezone.now().date()).days
            return f"{days} days" if days > 0 else "Expired"
        return 'No warranty'
    warranty_days_remaining.short_description = 'Warranty Remaining'

    def actions(self, obj):
        """Provide custom action links."""
        actions_html = [f'<a href="/inventory/device/{obj.device_id}/qr/" target="_blank">QR</a>']
        if not obj.assignments.filter(is_active=True).exists():
            actions_html.append(f'<a href="/inventory/device/{obj.device_id}/assign/">Assign</a>')
        return format_html(' | '.join(actions_html))
    actions.short_description = 'Actions'


# ================================
# ASSIGNMENT ADMIN
# ================================

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'device', 'assigned_to_staff', 'assigned_to_department',
        'assigned_to_location', 'start_date', 'is_temporary',
        'expected_return_date', 'is_active', 'assignment_status'
    )
    list_filter = (
        'is_active', 'is_temporary', 'start_date',
        'assigned_to_department', 'expected_return_date', 'assignment_type'
    )
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__first_name', 'assigned_to_staff__user__last_name',
        'assigned_to_department__name'
    )
    readonly_fields = ('created_at', 'updated_at', 'assignment_duration')
    fieldsets = (
        ('Assignment Details', {
            'fields': ('device', 'assigned_to_staff', 'assigned_to_department', 'assigned_to_location', 'created_by', 'assignment_type')
        }),
        ('Timeline', {'fields': ('start_date', 'is_temporary', 'expected_return_date', 'actual_return_date', 'is_active')}),
        ('Additional Information', {'fields': ('purpose', 'notes'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def assignment_status(self, obj):
        """Display assignment status with icons."""
        if not obj.is_active:
            return format_html('<span style="color: gray;">📋 Returned</span>')
        if obj.is_temporary and obj.expected_return_date:
            if obj.expected_return_date < timezone.now().date():
                return format_html('<span style="color: red;">⏰ Overdue</span>')
            return format_html('<span style="color: blue;">⏳ Temporary</span>')
        return format_html('<span style="color: green;">✅ Active</span>')
    assignment_status.short_description = 'Status'

    def assignment_duration(self, obj):
        """Calculate assignment duration."""
        if obj.start_date:
            end_date = obj.actual_return_date or timezone.now().date()
            return f"{(end_date - obj.start_date).days} days"
        return '-'
    assignment_duration.short_description = 'Duration'


# ================================
# MAINTENANCE ADMIN
# ================================

if MaintenanceSchedule:
    @admin.register(MaintenanceSchedule)
    class MaintenanceScheduleAdmin(admin.ModelAdmin):
        list_display = (
            'device', 'maintenance_type', 'scheduled_date', 'status',
            'priority', 'vendor', 'cost_display', 'completion_status'
        )
        list_filter = ('status', 'priority', 'maintenance_type', 'scheduled_date', 'vendor')
        search_fields = ('device__device_id', 'device__device_name', 'description')
        readonly_fields = ('created_at', 'updated_at')
        fieldsets = (
            ('Maintenance Details', {'fields': ('device', 'maintenance_type', 'description', 'priority', 'status')}),
            ('Scheduling', {'fields': ('scheduled_date', 'estimated_duration', 'completion_date')}),
            ('Vendor & Cost', {'fields': ('vendor', 'estimated_cost', 'actual_cost')}),
            ('Results', {'fields': ('maintenance_notes', 'next_maintenance_date'), 'classes': ('collapse',)}),
            ('Audit', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
        )

        def cost_display(self, obj):
            """Display formatted estimated cost."""
            return f"৳{obj.estimated_cost:,.2f}" if obj.estimated_cost else '-'
        cost_display.short_description = 'Est. Cost'

        def completion_status(self, obj):
            """Display maintenance completion status."""
            if obj.status == 'COMPLETED':
                return format_html('<span style="color: green;">✅ Completed</span>')
            if obj.status == 'IN_PROGRESS':
                return format_html('<span style="color: blue;">🔧 In Progress</span>')
            if obj.status == 'SCHEDULED':
                if obj.scheduled_date < timezone.now().date():
                    return format_html('<span style="color: red;">⏰ Overdue</span>')
                return format_html('<span style="color: orange;">📅 Scheduled</span>')
            return format_html('<span style="color: gray;">⏸️ {}</span>', obj.get_status_display())
        completion_status.short_description = 'Completion'


# ================================
# HISTORY & AUDIT ADMIN
# ================================

if AssignmentHistory:
    @admin.register(AssignmentHistory)
    class AssignmentHistoryAdmin(admin.ModelAdmin):
        list_display = (
            'device', 'action', 'timestamp', 'old_staff', 'new_staff',
            'old_location', 'new_location', 'changed_by'
        )
        list_filter = ('action', 'timestamp')
        search_fields = ('device__device_id', 'reason')
        readonly_fields = ('timestamp',)

        def has_add_permission(self, request):
            return False


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
# SERVICE & NOTIFICATION ADMIN
# ================================

if ServiceRequest:
    @admin.register(ServiceRequest)
    class ServiceRequestAdmin(admin.ModelAdmin):
        list_display = ('request_id', 'device', 'request_type', 'status', 'requested_by', 'created_at', 'priority')
        list_filter = ('request_type', 'status', 'priority', 'created_at')
        search_fields = ('request_id', 'device__device_id', 'title', 'description')
        readonly_fields = ('request_id', 'created_at', 'updated_at')


if Notification:
    @admin.register(Notification)
    class NotificationAdmin(admin.ModelAdmin):
        list_display = ('title', 'notification_type', 'recipient', 'is_read', 'created_at', 'expires_at')
        list_filter = ('notification_type', 'is_read', 'created_at', 'priority')
        search_fields = ('title', 'message', 'recipient__username')
        readonly_fields = ('created_at',)


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Mark selected devices as available')
def mark_devices_available(modeladmin, request, queryset):
    updated = queryset.update(status='AVAILABLE')
    modeladmin.message_user(request, f'{updated} devices marked as available.')


@admin.action(description='Generate QR codes for selected devices')
def generate_qr_codes(modeladmin, request, queryset):
    count = queryset.filter(device_id__isnull=False).count()
    modeladmin.message_user(request, f'QR codes available for {count} devices.')


DeviceAdmin.actions = [mark_devices_available, generate_qr_codes]

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Inventory Management Dashboard"