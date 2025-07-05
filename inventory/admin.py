# inventory/admin.py
"""
Corrected admin configuration for BPS IT Inventory System
This version includes comprehensive error handling and conditional registration
"""

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

# Core models that should always exist
from .models import (
    Department, Location, DeviceCategory, DeviceSubCategory, 
    DeviceType, Vendor, Staff, Device, Assignment, AuditLog
)

# Optional models - import with error handling
OPTIONAL_MODELS = {}

# Try to import optional models
optional_model_names = [
    'AssignmentHistory', 'MaintenanceSchedule', 'ServiceRequest', 
    'Notification', 'Room', 'Building', 'Floor', 'Organization',
    'DeviceMovement', 'DeviceHistory'
]

for model_name in optional_model_names:
    try:
        model = getattr(__import__('inventory.models', fromlist=[model_name]), model_name)
        OPTIONAL_MODELS[model_name] = model
        globals()[model_name] = model
    except (ImportError, AttributeError):
        OPTIONAL_MODELS[model_name] = None
        globals()[model_name] = None

print(f"📋 Loaded models: {[k for k, v in OPTIONAL_MODELS.items() if v is not None]}")
print(f"❌ Missing models: {[k for k, v in OPTIONAL_MODELS.items() if v is None]}")


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
    readonly_fields = ('created_at', 'assignment_duration')
    fields = (
        'assigned_to_staff', 'assigned_to_department', 'assigned_to_location',
        'is_temporary', 'expected_return_date', 'is_active', 'created_at'
    )

    def assignment_duration(self, obj):
        """Calculate assignment duration"""
        if obj.created_at:
            end_date = obj.actual_return_date or timezone.now().date()
            duration = (end_date - obj.created_at.date()).days
            return f"{duration} days"
        return '-'
    assignment_duration.short_description = 'Duration'


# Conditional inline for MaintenanceSchedule
class MaintenanceInline(admin.TabularInline):
    extra = 0
    readonly_fields = ('created_at', 'cost_display')
    
    def cost_display(self, obj):
        """Display formatted cost"""
        if hasattr(obj, 'estimated_cost') and obj.estimated_cost:
            return f"৳{obj.estimated_cost:,.2f}"
        return '-'
    cost_display.short_description = 'Est. Cost'

if OPTIONAL_MODELS['MaintenanceSchedule']:
    MaintenanceInline.model = OPTIONAL_MODELS['MaintenanceSchedule']
    MaintenanceInline.fields = (
        'maintenance_type', 'scheduled_date', 'status', 'priority',
        'vendor', 'estimated_cost', 'created_at'
    )
else:
    MaintenanceInline = None


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
    list_display = ('name', 'description_short', 'subcategory_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DeviceSubCategoryInline]
    
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
    
    def description_short(self, obj):
        return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
    description_short.short_description = 'Description'


@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
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
            'fields': ('specifications_template',) if hasattr(DeviceType, 'specifications_template') else (),
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


# ================================
# DEPARTMENT & LOCATION ADMIN
# ================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'staff_count', 'device_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        basic_fields = ['name', 'description', 'is_active']
        
        # Add optional fields if they exist
        for field in ['head_of_department', 'code']:
            if hasattr(Department, field):
                basic_fields.append(field)
        
        fieldsets = [
            (None, {
                'fields': basic_fields
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]
        
        return fieldsets

    def staff_count(self, obj):
        return obj.staff_members.count() if hasattr(obj, 'staff_members') else 0
    staff_count.short_description = 'Staff'

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count() if hasattr(obj, 'device_assignments') else 0
    device_count.short_description = 'Assigned Devices'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'device_count', 'is_active')
    list_filter = ('location_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        basic_fields = ['name', 'location_type', 'description', 'is_active']
        
        fieldsets = [
            (None, {
                'fields': basic_fields
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            })
        ]
        
        return fieldsets

    def device_count(self, obj):
        return obj.device_assignments.filter(is_active=True).count() if hasattr(obj, 'device_assignments') else 0
    device_count.short_description = 'Devices'


# ================================
# STAFF & VENDOR ADMIN
# ================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'designation', 'department', 'phone_number', 'is_active')
    list_filter = ('department', 'designation', 'is_active', 'employment_type')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        basic_fields = ['user', 'employee_id']
        employment_fields = ['designation', 'department', 'is_active']
        
        # Add optional fields
        for field in ['phone_number', 'employment_type', 'joining_date', 'leaving_date', 'office_location']:
            if hasattr(Staff, field):
                if field in ['phone_number']:
                    basic_fields.append(field)
                else:
                    employment_fields.append(field)
        
        fieldsets = [
            ('Personal Information', {
                'fields': basic_fields
            }),
            ('Employment Details', {
                'fields': employment_fields
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]
        
        return fieldsets

    def full_name(self, obj):
        return obj.user.get_full_name() if obj.user else obj.employee_id
    full_name.short_description = 'Full Name'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor_type', 'contact_person', 'phone', 'email', 'is_active')
    list_filter = ('vendor_type', 'is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        basic_fields = ['name', 'vendor_type', 'is_active']
        contact_fields = ['contact_person', 'phone', 'email', 'website', 'address']
        
        # Filter fields that actually exist
        contact_fields = [f for f in contact_fields if hasattr(Vendor, f)]
        
        fieldsets = [
            (None, {
                'fields': basic_fields
            }),
            ('Contact Information', {
                'fields': contact_fields
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]
        
        # Add business details if tax_id exists
        if hasattr(Vendor, 'tax_id'):
            fieldsets.insert(-1, ('Business Details', {
                'fields': ('tax_id',),
                'classes': ('collapse',)
            }))
        
        return fieldsets


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
    search_fields = (
        'device_id', 'asset_tag', 'device_name', 'serial_number'
    )
    readonly_fields = (
        'device_id', 'qr_code_image', 'age_in_years',
        'warranty_days_remaining', 'created_at', 'updated_at'
    )
    
    # Add inlines conditionally
    def get_inlines(self, request, obj):
        inlines = [AssignmentInline]
        if MaintenanceInline:
            inlines.append(MaintenanceInline)
        return inlines
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        basic_fields = ['device_id', 'device_name', 'device_type', 'status']
        technical_fields = ['brand', 'model']
        purchase_fields = ['vendor', 'purchase_date']
        
        # Add optional fields
        for field in ['asset_tag', 'serial_number']:
            if hasattr(Device, field):
                basic_fields.append(field)
        
        for field in ['purchase_price', 'warranty_start_date', 'warranty_end_date']:
            if hasattr(Device, field):
                purchase_fields.append(field)
        
        fieldsets = [
            ('Basic Information', {
                'fields': basic_fields
            }),
            ('Technical Details', {
                'fields': technical_fields
            }),
            ('Purchase Information', {
                'fields': purchase_fields
            }),
            ('QR Code', {
                'fields': ('qr_code_image', 'qr_code') if hasattr(Device, 'qr_code') else ('qr_code_image',),
                'classes': ('collapse',)
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
                'classes': ('collapse',)
            }),
        ]
        
        return fieldsets

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

    def qr_code_image(self, obj):
        if obj.device_id:
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr_data = {"deviceId": obj.device_id, "verifyUrl": f"/verify/{obj.device_id}/"}
                qr.add_data(str(qr_data))
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                img_str = base64.b64encode(buffer.getvalue()).decode()
                
                return format_html(
                    '<img src="data:image/png;base64,{}" style="width: 150px; height: 150px;" />',
                    img_str
                )
            except Exception as e:
                return f"Error: {str(e)}"
        return "No Device ID"
    qr_code_image.short_description = 'QR Code'

    def age_in_years(self, obj):
        if obj.purchase_date:
            today = timezone.now().date()
            age = (today - obj.purchase_date).days / 365.25
            return f"{age:.1f} years"
        return '-'
    age_in_years.short_description = 'Age'

    def warranty_days_remaining(self, obj):
        if obj.warranty_end_date:
            today = timezone.now().date()
            days = (obj.warranty_end_date - today).days
            return f"{days} days" if days > 0 else "Expired"
        return 'No warranty'
    warranty_days_remaining.short_description = 'Warranty Remaining'

    def actions(self, obj):
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
        'assigned_to_location', 'start_date', 'is_active', 'assignment_status'
    )
    list_filter = ('is_active', 'is_temporary', 'start_date', 'assigned_to_department')
    search_fields = (
        'device__device_id', 'device__device_name',
        'assigned_to_staff__user__first_name', 'assigned_to_staff__user__last_name'
    )
    readonly_fields = ('created_at', 'updated_at', 'assignment_duration')
    
    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on available fields"""
        assignment_fields = ['device', 'assigned_to_staff', 'assigned_to_department', 'assigned_to_location']
        timeline_fields = ['start_date', 'is_active']
        
        # Add optional fields
        for field in ['created_by', 'assignment_type']:
            if hasattr(Assignment, field):
                assignment_fields.append(field)
        
        for field in ['is_temporary', 'expected_return_date', 'actual_return_date']:
            if hasattr(Assignment, field):
                timeline_fields.append(field)
        
        fieldsets = [
            ('Assignment Details', {
                'fields': assignment_fields
            }),
            ('Timeline', {
                'fields': timeline_fields
            }),
            ('Additional Information', {
                'fields': ('purpose', 'notes') if hasattr(Assignment, 'purpose') else (),
                'classes': ('collapse',)
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]
        
        return fieldsets

    def assignment_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: gray;">📋 Returned</span>')
        elif hasattr(obj, 'is_temporary') and obj.is_temporary and hasattr(obj, 'expected_return_date') and obj.expected_return_date:
            if obj.expected_return_date < timezone.now().date():
                return format_html('<span style="color: red;">⏰ Overdue</span>')
            else:
                return format_html('<span style="color: blue;">⏳ Temporary</span>')
        else:
            return format_html('<span style="color: green;">✅ Active</span>')
    assignment_status.short_description = 'Status'

    def assignment_duration(self, obj):
        if obj.start_date:
            end_date = (obj.actual_return_date if hasattr(obj, 'actual_return_date') and obj.actual_return_date 
                       else timezone.now().date())
            duration = (end_date - obj.start_date).days
            return f"{duration} days"
        return '-'
    assignment_duration.short_description = 'Duration'


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
# CONDITIONAL MODEL REGISTRATION
# ================================

# Register optional models if they exist
for model_name, model_class in OPTIONAL_MODELS.items():
    if model_class:
        if model_name == 'MaintenanceSchedule':
            class MaintenanceScheduleAdmin(admin.ModelAdmin):
                list_display = ('device', 'maintenance_type', 'scheduled_date', 'status')
                list_filter = ('status', 'maintenance_type', 'scheduled_date')
            admin.site.register(model_class, MaintenanceScheduleAdmin)
        
        elif model_name == 'AssignmentHistory':
            class AssignmentHistoryAdmin(admin.ModelAdmin):
                list_display = ('device', 'action', 'timestamp', 'changed_by')
                list_filter = ('action', 'timestamp')
                readonly_fields = ('timestamp',)
                def has_add_permission(self, request):
                    return False
            admin.site.register(model_class, AssignmentHistoryAdmin)
        
        elif model_name in ['ServiceRequest', 'Notification']:
            class GenericAdmin(admin.ModelAdmin):
                list_display = ('__str__', 'created_at') if hasattr(model_class, 'created_at') else ('__str__',)
                readonly_fields = ('created_at',) if hasattr(model_class, 'created_at') else ()
            admin.site.register(model_class, GenericAdmin)


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