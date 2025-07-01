from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Organization, Building, Floor, Department, Room, Location,
    Staff, StaffAssignmentHistory, Vendor, DeviceCategory, 
    DeviceSubCategory, DeviceType, Device, Assignment, 
    AssignmentHistory, MaintenanceSchedule, AuditLog, 
    DeviceMovement, SystemConfiguration, NotificationRule,
    Notification, APIAccessLog, DataImportLog
)

# ================================
# ORGANIZATION & LOCATION ADMIN
# ================================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'contact_phone', 'contact_email', 'created_at']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization', 'contact_person', 'contact_phone']
    list_filter = ['organization']
    search_fields = ['name', 'code', 'contact_person']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ['building', 'name', 'floor_number']
    list_filter = ['building__organization', 'building']
    search_fields = ['name', 'floor_number', 'building__name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'floor', 'head_of_department', 'contact_phone']
    list_filter = ['floor__building__organization', 'floor__building', 'floor']
    search_fields = ['name', 'code', 'head_of_department']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_number', 'department', 'room_type', 'capacity']
    list_filter = ['room_type', 'department__floor__building']
    search_fields = ['name', 'room_number', 'department__name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'location_code', 'room', 'location_type', 'capacity', 'is_active']
    list_filter = ['location_type', 'is_active', 'room__department']
    search_fields = ['name', 'location_code', 'room__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'room__department__floor__building__organization'
        )

# ================================
# STAFF & USER MANAGEMENT ADMIN
# ================================

class StaffAssignmentHistoryInline(admin.TabularInline):
    model = StaffAssignmentHistory
    extra = 0
    readonly_fields = ['created_at']
    can_delete = False

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = [
        'employee_id', 'full_name', 'designation', 'department', 
        'phone', 'email', 'is_active'
    ]
    list_filter = [
        'department', 'designation', 'security_clearance', 
        'is_active', 'date_joined'
    ]
    search_fields = ['employee_id', 'full_name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [StaffAssignmentHistoryInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'full_name', 'designation')
        }),
        ('Department & Reporting', {
            'fields': ('department', 'reporting_manager')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'extension')
        }),
        ('Security & Status', {
            'fields': ('security_clearance', 'date_joined', 'is_active')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(StaffAssignmentHistory)
class StaffAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ['staff', 'department', 'designation', 'start_date', 'end_date']
    list_filter = ['department', 'start_date', 'end_date']
    search_fields = ['staff__full_name', 'staff__employee_id', 'designation']
    readonly_fields = ['created_at']

# ================================
# VENDOR MANAGEMENT ADMIN
# ================================

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = [
        'vendor_code', 'name', 'vendor_type', 'contact_person', 
        'phone', 'performance_rating', 'is_active'
    ]
    list_filter = ['vendor_type', 'is_active', 'performance_rating']
    search_fields = ['name', 'vendor_code', 'contact_person', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'vendor_code', 'vendor_type')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'phone', 'email', 'address', 'website')
        }),
        ('Legal Information', {
            'fields': ('tax_id', 'registration_number')
        }),
        ('Performance & Status', {
            'fields': ('performance_rating', 'is_active')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# DEVICE CATEGORY ADMIN
# ================================

class DeviceSubCategoryInline(admin.TabularInline):
    model = DeviceSubCategory
    extra = 1

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'icon', 'is_active']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name', 'category_type']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DeviceSubCategoryInline]

class DeviceTypeInline(admin.TabularInline):
    model = DeviceType
    extra = 1

@admin.register(DeviceSubCategory)
class DeviceSubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'code', 'category__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DeviceTypeInline]

@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'subcategory', 'is_active']
    list_filter = ['subcategory__category', 'subcategory', 'is_active']
    search_fields = ['name', 'code', 'subcategory__name']
    readonly_fields = ['created_at', 'updated_at']

# ================================
# DEVICE MANAGEMENT ADMIN
# ================================

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ['assignment_id', 'created_at']
    fields = [
        'assignment_type', 'assigned_to_staff', 'assigned_to_department', 
        'assigned_to_location', 'is_active', 'is_temporary'
    ]

class MaintenanceScheduleInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0
    readonly_fields = ['created_at']
    fields = ['maintenance_type', 'title', 'scheduled_date', 'status']

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        'device_id', 'device_name', 'device_type', 'brand', 'model', 
        'status', 'condition', 'current_assignment', 'warranty_status'
    ]
    list_filter = [
        'device_type__subcategory__category', 'device_type__subcategory', 
        'device_type', 'status', 'condition', 'brand', 'vendor', 'is_critical'
    ]
    search_fields = [
        'device_id', 'device_name', 'asset_tag', 'serial_number', 
        'brand', 'model', 'mac_address', 'ip_address'
    ]
    readonly_fields = [
        'device_id', 'qr_code', 'created_at', 'updated_at'
    ]
    inlines = [AssignmentInline, MaintenanceScheduleInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'device_id', 'asset_tag', 'qr_code', 'device_name', 
                'device_type', 'brand', 'model', 'serial_number'
            )
        }),
        ('Network Information', {
            'fields': ('mac_address', 'ip_address'),
            'classes': ('collapse',)
        }),
        ('Technical Specifications', {
            'fields': ('specifications',),
            'classes': ('collapse',)
        }),
        ('Status & Condition', {
            'fields': ('status', 'condition', 'is_critical')
        }),
        ('Procurement Information', {
            'fields': (
                'vendor', 'purchase_date', 'purchase_order_number', 
                'purchase_price'
            ),
            'classes': ('collapse',)
        }),
        ('Warranty Information', {
            'fields': (
                'warranty_start_date', 'warranty_end_date', 'warranty_type',
                'support_contract', 'amc_details'
            ),
            'classes': ('collapse',)
        }),
        ('Lifecycle Management', {
            'fields': (
                'deployment_date', 'last_maintenance_date', 
                'next_maintenance_date', 'retirement_date', 'disposal_date'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def current_assignment(self, obj):
        active_assignment = obj.assignments.filter(is_active=True).first()
        if active_assignment:
            target = (active_assignment.assigned_to_staff or 
                     active_assignment.assigned_to_department or 
                     active_assignment.assigned_to_location)
            return str(target)
        return "Unassigned"
    current_assignment.short_description = "Current Assignment"
    
    def warranty_status(self, obj):
        if obj.is_warranty_active:
            if obj.warranty_expires_soon:
                return format_html(
                    '<span style="color: orange;">⚠️ Expires Soon</span>'
                )
            return format_html('<span style="color: green;">✅ Active</span>')
        return format_html('<span style="color: red;">❌ Expired</span>')
    warranty_status.short_description = "Warranty Status"

# ================================
# ASSIGNMENT MANAGEMENT ADMIN
# ================================

class AssignmentHistoryInline(admin.TabularInline):
    model = AssignmentHistory
    extra = 0
    readonly_fields = ['changed_by', 'changed_at']
    can_delete = False

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'assignment_id', 'device', 'assignment_type', 'assignment_target',
        'start_date', 'is_active', 'is_temporary', 'is_overdue_status'
    ]
    list_filter = [
        'assignment_type', 'is_active', 'is_temporary', 'start_date',
        'assigned_to_department'
    ]
    search_fields = [
        'assignment_id', 'device__device_id', 'device__device_name',
        'assigned_to_staff__full_name', 'assigned_to_department__name'
    ]
    readonly_fields = [
        'assignment_id', 'created_at', 'updated_at'
    ]
    inlines = [AssignmentHistoryInline]
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'assignment_id', 'device', 'assignment_type', 'purpose'
            )
        }),
        ('Assignment Targets', {
            'fields': (
                'assigned_to_staff', 'assigned_to_department', 
                'assigned_to_location', 'project_name', 'project_code'
            )
        }),
        ('Dates & Status', {
            'fields': (
                'start_date', 'expected_return_date', 'actual_return_date',
                'is_active', 'is_temporary'
            )
        }),
        ('Assignment Details', {
            'fields': ('conditions', 'notes'),
            'classes': ('collapse',)
        }),
        ('Approval Workflow', {
            'fields': (
                'requested_by', 'approved_by', 'approval_date'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def assignment_target(self, obj):
        target = (obj.assigned_to_staff or 
                 obj.assigned_to_department or 
                 obj.assigned_to_location or 
                 "Unassigned")
        return str(target)
    assignment_target.short_description = "Assigned To"
    
    def is_overdue_status(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">⚠️ Overdue</span>')
        return "✅ On Time"
    is_overdue_status.short_description = "Overdue Status"

@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'action', 'previous_target', 'new_target', 
        'changed_by', 'changed_at'
    ]
    list_filter = ['action', 'changed_at']
    search_fields = [
        'device__device_id', 'device__device_name', 'reason'
    ]
    readonly_fields = ['changed_at']
    
    def previous_target(self, obj):
        target = obj.previous_staff or obj.previous_department or obj.previous_location
        return str(target) if target else "None"
    previous_target.short_description = "From"
    
    def new_target(self, obj):
        target = obj.new_staff or obj.new_department or obj.new_location
        return str(target) if target else "None"
    new_target.short_description = "To"

# ================================
# MAINTENANCE ADMIN
# ================================

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'maintenance_type', 'title', 'scheduled_date', 
        'status', 'vendor', 'actual_cost'
    ]
    list_filter = [
        'maintenance_type', 'status', 'scheduled_date', 'vendor'
    ]
    search_fields = [
        'device__device_id', 'device__device_name', 'title', 
        'performed_by', 'technician_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Maintenance Information', {
            'fields': (
                'device', 'maintenance_type', 'title', 'description'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_date', 'scheduled_time', 'estimated_duration',
                'actual_start_date', 'actual_end_date', 'status'
            )
        }),
        ('Service Provider', {
            'fields': (
                'performed_by', 'vendor', 'technician_name', 
                'technician_contact'
            )
        }),
        ('Cost & Parts', {
            'fields': (
                'estimated_cost', 'actual_cost', 'parts_used'
            ),
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': (
                'work_performed', 'issues_found', 'recommendations',
                'next_maintenance_date'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# AUDIT & TRACKING ADMIN
# ================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'action', 'model_name', 'object_repr', 'ip_address'
    ]
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__username', 'object_repr', 'ip_address']
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(DeviceMovement)
class DeviceMovementAdmin(admin.ModelAdmin):
    list_display = [
        'device', 'from_location', 'to_location', 'moved_by', 
        'reason', 'qr_scanned', 'timestamp'
    ]
    list_filter = ['qr_scanned', 'timestamp']
    search_fields = [
        'device__device_id', 'device__device_name', 'reason'
    ]
    readonly_fields = ['timestamp']

# ================================
# SYSTEM CONFIGURATION ADMIN
# ================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ['category', 'key', 'value_preview', 'is_active', 'updated_at']
    list_filter = ['category', 'is_active']
    search_fields = ['key', 'value', 'description']
    readonly_fields = ['updated_at']
    
    def value_preview(self, obj):
        return obj.value[:50] + "..." if len(obj.value) > 50 else obj.value
    value_preview.short_description = "Value"

# ================================
# NOTIFICATION ADMIN
# ================================

@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'event_type', 'notify_email', 'notify_sms', 
        'notify_in_app', 'is_active'
    ]
    list_filter = ['event_type', 'is_active', 'notify_email', 'notify_sms']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'recipient', 'status', 'sent_at', 'read_at', 
        'delivery_attempts'
    ]
    list_filter = ['status', 'sent_at', 'rule__event_type']
    search_fields = ['subject', 'recipient__username', 'message']
    readonly_fields = ['created_at']

# ================================
# INTEGRATION & API ADMIN
# ================================

@admin.register(APIAccessLog)
class APIAccessLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'method', 'endpoint', 'status_code', 
        'response_time', 'ip_address'
    ]
    list_filter = ['method', 'status_code', 'timestamp']
    search_fields = ['user__username', 'endpoint', 'ip_address']
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(DataImportLog)
class DataImportLogAdmin(admin.ModelAdmin):
    list_display = [
        'import_type', 'file_name', 'total_records', 
        'successful_imports', 'failed_imports', 'started_at'
    ]
    list_filter = ['import_type', 'started_at']
    search_fields = ['file_name', 'imported_by__username']
    readonly_fields = ['started_at', 'completed_at']