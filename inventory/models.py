from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

# ================================
# 1. CORE ORGANIZATIONAL MODELS
# ================================

class Building(models.Model):
    """Building information for asset location tracking"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

class Floor(models.Model):
    """Floor information within buildings"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    name = models.CharField(max_length=50)
    floor_number = models.IntegerField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['building', 'floor_number']
        ordering = ['building', 'floor_number']

    def __str__(self):
        return f"{self.building.name} - {self.name}"

class Department(models.Model):
    """Department information"""
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30)
    head_of_department = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['floor', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.floor.building.name} - {self.name}"

class Room(models.Model):
    """Room information within departments"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=30)
    room_name = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['department', 'room_number']
        ordering = ['department', 'room_number']

    def __str__(self):
        return f"{self.department.name} - {self.room_number}"

class Location(models.Model):
    """Specific location combining building, floor, department, and room"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='locations')
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='locations')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='locations')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='locations', null=True, blank=True)
    description = models.CharField(max_length=400, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['building', 'floor', 'department', 'room']
        ordering = ['building', 'floor', 'department', 'room']

    def __str__(self):
        location_str = f"{self.building.name} - {self.floor.name} - {self.department.name}"
        if self.room:
            location_str += f" - {self.room.room_number}"
        return location_str

# ================================
# 2. STAFF & VENDOR MODELS
# ================================

class Staff(models.Model):
    """Staff member information linked to Django User"""
    EMPLOYMENT_TYPES = [
        ('PERMANENT', 'Permanent'),
        ('CONTRACT', 'Contract'),
        ('TEMPORARY', 'Temporary'),
        ('CONSULTANT', 'Consultant'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members')
    designation = models.CharField(max_length=100)
    employment_type = models.CharField(max_length=30, choices=EMPLOYMENT_TYPES, default='PERMANENT')
    phone_number = models.CharField(max_length=20, blank=True)
    office_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members')
    is_active = models.BooleanField(default=True)
    joining_date = models.DateField(null=True, blank=True)
    leaving_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        verbose_name_plural = 'Staff'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

    @property
    def full_name(self):
        return self.user.get_full_name()

class Vendor(models.Model):
    """Vendor/Supplier information"""
    VENDOR_TYPES = [
        ('HARDWARE_SUPPLIER', 'Hardware Supplier'),
        ('SOFTWARE_VENDOR', 'Software Vendor'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('MAINTENANCE_CONTRACTOR', 'Maintenance Contractor'),
        ('CONSULTANT', 'Consultant'),
    ]

    name = models.CharField(max_length=200)
    vendor_type = models.CharField(max_length=40, choices=VENDOR_TYPES)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

# ================================
# 3. DEVICE CATEGORIZATION MODELS
# ================================

class DeviceCategory(models.Model):
    """High-level device categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Device Categories'

    def __str__(self):
        return self.name

class DeviceSubCategory(models.Model):
    """Device subcategories under main categories"""
    category = models.ForeignKey(DeviceCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['category', 'name']
        ordering = ['category', 'name']
        verbose_name_plural = 'Device Subcategories'

    def __str__(self):
        return f"{self.category.name} - {self.name}"

class DeviceType(models.Model):
    """Specific device types under subcategories"""
    subcategory = models.ForeignKey(DeviceSubCategory, on_delete=models.CASCADE, related_name='device_types')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    specifications_template = models.JSONField(default=dict, blank=True, help_text="Template for device specifications")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['subcategory', 'name']
        ordering = ['subcategory', 'name']

    def __str__(self):
        return f"{self.subcategory.category.name} - {self.subcategory.name} - {self.name}"

# ================================
# 4. CORE DEVICE MODEL
# ================================

class Device(models.Model):
    """Core device/asset model"""
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('ASSIGNED', 'Assigned'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('RETIRED', 'Retired'),
        ('LOST', 'Lost'),
        ('DAMAGED', 'Damaged'),
        ('DISPOSED', 'Disposed'),
    ]

    # Primary identification
    device_id = models.CharField(max_length=50, unique=True, primary_key=True)
    device_name = models.CharField(max_length=200)
    asset_tag = models.CharField(max_length=100, unique=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    
    # Classification
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='devices')
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=200, blank=True)
    
    # Status and location
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='AVAILABLE')
    #current_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')
    
    # Financial information
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')
    
    # Warranty information
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    warranty_provider = models.CharField(max_length=300, blank=True)
    
    # Technical specifications
    #specifications = models.JSONField(default=dict, blank=True, help_text="Device technical specifications")
    
    # Technical specifications - individual fields 
    processor = models.CharField(
        max_length=200, 
        blank=True, 
        help_text="e.g., Intel Core i7-1165G7"
    )
    memory_ram = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="e.g., 16GB DDR4",
        db_column='ram'  
    )
    storage_capacity = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="e.g., 512GB SSD",
        db_column='storage'  
    )
    operating_system = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="e.g., Windows 11 Pro"
    )
    
    # Device condition for forms
    CONDITION_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('DAMAGED', 'Damaged'),
        ('DEFECTIVE', 'Defective'),
    ]
    
    device_condition = models.CharField(
        max_length=30, 
        choices=CONDITION_CHOICES, 
        default='GOOD',
        db_column='condition'  
    )
    
    # Location field for forms
    location = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_devices'
    )
    
    # Critical device flag
    is_critical = models.BooleanField(
        default=False, 
        help_text="Mark as critical infrastructure device"
    )
    
    # Lifecycle information
    expected_life_years = models.PositiveIntegerField(null=True, blank=True, help_text="Expected useful life in years")
    disposal_date = models.DateField(null=True, blank=True)
    disposal_method = models.CharField(max_length=100, blank=True)
    
    # QR Code
    qr_code = models.TextField(blank=True, help_text="QR code data")
    
    # Notes and comments
    notes = models.TextField(blank=True)
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='devices_created')
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='devices_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['device_id']
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['asset_tag']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['device_type']),
        ]

    def __str__(self):
        return f"{self.device_id} - {self.device_name}"

    @property
    def is_under_warranty(self):
        if self.warranty_end_date:
            return timezone.now().date() <= self.warranty_end_date
        return False

    @property
    def warranty_days_remaining(self):
        if self.is_under_warranty:
            return (self.warranty_end_date - timezone.now().date()).days
        return 0

    @property
    def age_in_years(self):
        if self.purchase_date:
            return (timezone.now().date() - self.purchase_date).days / 365.25
        return None

# ================================
# 5. ASSIGNMENT MODELS
# ================================

class Assignment(models.Model):
    """Device assignment tracking"""
    ASSIGNMENT_TYPES = [
        ('PERMANENT', 'Permanent Assignment'),
        ('TEMPORARY', 'Temporary Assignment'),
        ('PROJECT', 'Project Assignment'),
        ('POOL', 'Pool Assignment'),
    ]

    assignment_id = models.AutoField(primary_key=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='assignments')
    
    # Assignment targets (at least one must be specified)
    assigned_to_staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_assignments')
    assigned_to_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_assignments')
    assigned_to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_assignments')
    
    # Assignment details
    assignment_type = models.CharField(max_length=30, choices=ASSIGNMENT_TYPES, default='PERMANENT')
    start_date = models.DateField(default=timezone.now)
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)
    
    # Assignment metadata
    purpose = models.CharField(max_length=800, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Temporary assignment specific
    is_temporary = models.BooleanField(default=False)
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assignments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device', 'is_active']),
            models.Index(fields=['assigned_to_staff', 'is_active']),
            models.Index(fields=['start_date']),
            models.Index(fields=['expected_return_date']),
        ]

    def __str__(self):
        target = str(self.assigned_to_staff) if self.assigned_to_staff else (
            str(self.assigned_to_department) if self.assigned_to_department else 
            str(self.assigned_to_location)
        )
        return f"{self.device.device_id} → {target}"

    @property
    def is_overdue(self):
        if self.is_temporary and self.expected_return_date and self.is_active:
            return timezone.now().date() > self.expected_return_date
        return False

    @property
    def days_until_due(self):
        if self.expected_return_date and self.is_active:
            return (self.expected_return_date - timezone.now().date()).days
        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        if not any([self.assigned_to_staff, self.assigned_to_department, self.assigned_to_location]):
            raise ValidationError("At least one assignment target must be specified.")

# ================================
# 6. MAINTENANCE MODELS
# ================================

class MaintenanceSchedule(models.Model):
    """Scheduled maintenance for devices"""
    MAINTENANCE_TYPES = [
        ('PREVENTIVE', 'Preventive Maintenance'),
        ('CORRECTIVE', 'Corrective Maintenance'),
        ('EMERGENCY', 'Emergency Repair'),
        ('UPGRADE', 'Hardware/Software Upgrade'),
        ('INSPECTION', 'Routine Inspection'),
    ]

    FREQUENCY_CHOICES = [
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('SEMI_ANNUAL', 'Semi-Annual'),
        ('ANNUAL', 'Annual'),
        ('AS_NEEDED', 'As Needed'),
    ]

    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='maintenance_schedules')
    maintenance_type = models.CharField(max_length=40, choices=MAINTENANCE_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    description = models.TextField()
    next_due_date = models.DateField()
    last_completed_date = models.DateField(null=True, blank=True)
    assigned_technician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_assignments')
    estimated_duration = models.DurationField(null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_schedules')
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SCHEDULED')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_due_date']

    def __str__(self):
        return f"{self.device.device_name} - {self.get_maintenance_type_display()} ({self.next_due_date})"

    @property
    def is_overdue(self):
        return timezone.now().date() > self.next_due_date and self.status == 'SCHEDULED'

    @property
    def days_until_due(self):
        return (self.next_due_date - timezone.now().date()).days

class MaintenanceRecord(models.Model):
    """Record of completed maintenance activities"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_schedule = models.ForeignKey(MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='records')
    maintenance_type = models.CharField(max_length=30, choices=MaintenanceSchedule.MAINTENANCE_TYPES)
    description = models.TextField()
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    technician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_records')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_records')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SCHEDULED')
    work_performed = models.TextField(blank=True)
    parts_used = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='maintenance_records_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"{self.device.device_name} - {self.get_maintenance_type_display()} on {self.scheduled_date}"

    @property
    def duration(self):
        """Calculate maintenance duration"""
        if self.completed_date and self.scheduled_date:
            return (self.completed_date - self.scheduled_date).days
        return None

# ================================
# 7. AUDIT & TRACKING MODELS
# ================================

class AuditLog(models.Model):
    """System audit log for tracking all activities"""
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('ASSIGN', 'Assign'),
        ('TRANSFER', 'Transfer'),
        ('RETURN', 'Return'),
        ('MAINTENANCE', 'Maintenance'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('BULK_UPDATE', 'Bulk Update'),
        ('IMPORT', 'Import'),
        ('EXPORT', 'Export'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} at {self.timestamp}"

class DeviceMovement(models.Model):
    """Track device location movements"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='movement_logs')
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_from')
    to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_to')
    moved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_movements')
    movement_date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-movement_date']

    def __str__(self):
        return f"{self.device.device_name}: {self.from_location} → {self.to_location}"

class DeviceHistory(models.Model):
    """Track device status and assignment changes"""
    ACTION_TYPES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('ASSIGNMENT', 'Assignment'),
        ('RETURN', 'Return'),
        ('TRANSFER', 'Transfer'),
        ('MAINTENANCE', 'Maintenance'),
        ('LOCATION_CHANGE', 'Location Change'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='history_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    old_value = models.CharField(max_length=200, blank=True)
    new_value = models.CharField(max_length=200, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='device_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.device.device_name} - {self.action} at {self.changed_at}"

# ================================
# 8. SYSTEM CONFIGURATION MODELS
# ================================

class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    CONFIG_TYPES = [
        ('GENERAL', 'General Settings'),
        ('QR_CODE', 'QR Code Settings'),
        ('MAINTENANCE', 'Maintenance Settings'),
        ('NOTIFICATION', 'Notification Settings'),
        ('SECURITY', 'Security Settings'),
        ('INTEGRATION', 'Integration Settings'),
    ]

    category = models.CharField(max_length=20, choices=CONFIG_TYPES)
    key = models.CharField(max_length=100)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['category', 'key']

    def __str__(self):
        return f"{self.category}.{self.key} = {self.value[:50]}"

# ================================
# 9. NOTIFICATION MODELS
# ================================

class NotificationRule(models.Model):
    """Define notification rules for various events"""
    EVENT_TYPES = [
        ('ASSIGNMENT_DUE', 'Assignment Due Date'),
        ('WARRANTY_EXPIRING', 'Warranty Expiring'),
        ('MAINTENANCE_DUE', 'Maintenance Due'),
        ('DEVICE_MISSING', 'Device Missing'),
        ('UNAUTHORIZED_ACCESS', 'Unauthorized Access'),
        ('SYSTEM_ERROR', 'System Error'),
        ('BULK_OPERATION', 'Bulk Operation Completed'),
    ]

    name = models.CharField(max_length=200)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    description = models.TextField()
    trigger_conditions = models.JSONField(default=dict, help_text="Conditions that trigger this notification")
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_in_app = models.BooleanField(default=True)
    notify_device_owner = models.BooleanField(default=True)
    notify_department_head = models.BooleanField(default=False)
    notify_it_admin = models.BooleanField(default=True)
    additional_recipients = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.get_event_type_display()}"

class Notification(models.Model):
    """Individual notification instances"""
    NOTIFICATION_TYPES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('SUCCESS', 'Success'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('READ', 'Read'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(NotificationRule, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='INFO')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects (optional)
    related_device = models.ForeignKey(Device, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    related_assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    # Delivery tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Delivery methods used
    sent_via_email = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)
    sent_via_app = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['related_device']),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"

    @property
    def is_read(self):
        return self.status == 'READ' or self.read_at is not None

# ================================
# 10. AssignmentHistory MODELS
# ================================

class AssignmentHistory(models.Model):
    """Track changes to device assignments"""
    CHANGE_TYPES = [
        ('CREATED', 'Assignment Created'),
        ('MODIFIED', 'Assignment Modified'),
        ('RETURNED', 'Device Returned'),
        ('TRANSFERRED', 'Assignment Transferred'),
        ('CANCELLED', 'Assignment Cancelled'),
        ('EXPIRED', 'Assignment Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        Assignment, 
        on_delete=models.CASCADE, 
        related_name='assignment_history'
    )
    changed_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='assignment_changes'
    )
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    
    # Store before and after values
    old_values = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Previous assignment values"
    )
    new_values = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="New assignment values"
    )
    
    # Change details
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['assignment', '-timestamp']),
            models.Index(fields=['changed_by', '-timestamp']),
            models.Index(fields=['change_type', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.assignment.assignment_id} - {self.get_change_type_display()} by {self.changed_by.username}"

    @property
    def change_summary(self):
        """Return a human-readable summary of changes"""
        if self.change_type == 'CREATED':
            return f"Assignment created for {self.assignment.device.device_name}"
        elif self.change_type == 'MODIFIED':
            changes = []
            for field, new_value in self.new_values.items():
                old_value = self.old_values.get(field, 'None')
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} → {new_value}")
            return "; ".join(changes) if changes else "No specific changes recorded"
        elif self.change_type == 'RETURNED':
            return f"Device {self.assignment.device.device_name} returned"
        elif self.change_type == 'TRANSFERRED':
            return f"Assignment transferred"
        return f"{self.get_change_type_display()}"

# ================================
# 11. ServiceRequest MODELS
# ================================

class ServiceRequest(models.Model):
    """Service requests for devices - repairs, maintenance, etc."""
    SERVICE_TYPES = [
        ('REPAIR', 'Repair Request'),
        ('MAINTENANCE', 'Preventive Maintenance'),
        ('UPGRADE', 'Hardware/Software Upgrade'),
        ('REPLACEMENT', 'Component Replacement'),
        ('CLEANING', 'Device Cleaning'),
        ('INSPECTION', 'Safety Inspection'),
        ('CALIBRATION', 'Device Calibration'),
        ('OTHER', 'Other Service'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
    ]

    # Primary identification
    request_id = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Auto-generated service request ID"
    )
    
    # Related objects
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='service_requests'
    )
    requested_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='requested_services'
    )
    assigned_to = models.ForeignKey(
        Staff, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_service_requests'
    )
    
    # Service details
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Detailed description of the service required")
    
    # Request metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Scheduling
    requested_date = models.DateField(
        help_text="Preferred date for service"
    )
    scheduled_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Cost and approval
    estimated_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    actual_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_service_requests'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Additional details
    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        help_text="External service provider if applicable"
    )
    work_notes = models.TextField(
        blank=True, 
        help_text="Notes from technician performing the work"
    )
    completion_notes = models.TextField(
        blank=True, 
        help_text="Final notes upon completion"
    )
    
    # Attachments and references
    attachments = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of attachment file references"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_service_requests'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device', '-created_at']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['requested_date']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.request_id} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.request_id:
            # Auto-generate request ID
            from django.utils import timezone
            current_year = timezone.now().year
            count = ServiceRequest.objects.filter(
                created_at__year=current_year
            ).count() + 1
            self.request_id = f"SR-{current_year}-{count:04d}"
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if service request is overdue"""
        if self.status not in ['COMPLETED', 'CANCELLED', 'REJECTED']:
            if self.scheduled_date and self.scheduled_date < timezone.now().date():
                return True
        return False

    @property
    def days_pending(self):
        """Calculate days since request was created"""
        return (timezone.now().date() - self.created_at.date()).days

    def get_status_color(self):
        """Return Bootstrap color class for status"""
        status_colors = {
            'PENDING': 'warning',
            'APPROVED': 'info',
            'IN_PROGRESS': 'primary',
            'ON_HOLD': 'secondary',
            'COMPLETED': 'success',
            'CANCELLED': 'dark',
            'REJECTED': 'danger',
        }
        return status_colors.get(self.status, 'secondary')

    def get_priority_color(self):
        """Return Bootstrap color class for priority"""
        priority_colors = {
            'LOW': 'success',
            'MEDIUM': 'info',
            'HIGH': 'warning',
            'URGENT': 'danger',
            'CRITICAL': 'dark',
        }
        return priority_colors.get(self.priority, 'secondary')