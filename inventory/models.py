from django.core.validators import RegexValidator
from datetime import date, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import json

# ================================
# 1. ORGANIZATION & LOCATION MODELS
# ================================

class Organization(models.Model):
    """Organization/Company information"""
    name = models.CharField(max_length=200)
    address = models.TextField()
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Building(models.Model):
    """Building information"""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='buildings')
    name = models.CharField(max_length=100)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

class Floor(models.Model):
    """Floor information within buildings"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.building.name} - {self.name}"

class Department(models.Model):
    """Department information"""
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)  # This field was missing!
    head_of_department = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['floor', 'code']

    def __str__(self):
        return f"{self.floor.building.name} - {self.name}"

class Room(models.Model):
    """Room information within departments"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=20)
    room_name = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.department.name} - {self.room_number}"

class Location(models.Model):
    """Specific location combining building, floor, department, and room"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='locations')
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='locations')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='locations')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='locations', null=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['building', 'floor', 'department', 'room']

    def __str__(self):
        location_str = f"{self.building.name} - {self.floor.name} - {self.department.name}"
        if self.room:
            location_str += f" - {self.room.room_number}"
        return location_str

# ================================
# 2. STAFF & USER MANAGEMENT MODELS
# ================================

class Staff(models.Model):
    """Staff information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='staff')
    designation = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    extension = models.CharField(max_length=10, blank=True)
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    is_active = models.BooleanField(default=True)
    joining_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

class StaffAssignmentHistory(models.Model):
    """Track staff department and designation changes"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='assignment_history')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    designation = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.staff.full_name} - {self.designation} at {self.department.name}"

# ================================
# 3. VENDOR & SUPPLIER MODELS
# ================================

class Vendor(models.Model):
    """Vendor/Supplier information"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

# ================================
# 4. DEVICE CATEGORY & TYPE MODELS
# ================================

class DeviceCategory(models.Model):
    """Main device categories"""
    CATEGORY_TYPES = [
        ('DATA_CENTER', 'Data Centre Equipment'),
        ('NETWORK', 'Network Equipment'),
        ('COMPUTING', 'End-User Computing Devices'),
        ('DISPLAY', 'Projectors and Displays'),
        ('PERIPHERAL', 'Peripherals'),
        ('STORAGE', 'Storage Devices'),
        ('AUDIO_VIDEO', 'Audio/Video Equipment'),
        ('MOBILE', 'Mobile Devices'),
        ('SECURITY', 'Security Equipment'),
        ('OTHER', 'Other Equipment'),
    ]

    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Device Categories"

    def __str__(self):
        return self.name

class DeviceSubCategory(models.Model):
    """Sub-categories within main categories"""
    category = models.ForeignKey(DeviceCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['category', 'code']
        verbose_name_plural = "Device Sub-Categories"

    def __str__(self):
        return f"{self.category.name} > {self.name}"

class DeviceType(models.Model):
    """Specific device types within sub-categories"""
    subcategory = models.ForeignKey(DeviceSubCategory, on_delete=models.CASCADE, related_name='device_types')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    typical_specifications = models.JSONField(default=dict, blank=True, help_text="Common specifications for this device type")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['subcategory', 'code']

    def __str__(self):
        return f"{self.subcategory} > {self.name}"

# ================================
# 5. DEVICE MODELS
# ================================

class Device(models.Model):
    """Main device model"""
    
    # FIXED: Renamed to follow Django conventions
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('ASSIGNED', 'Assigned'),
        ('IN_USE', 'In Use'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('REPAIR', 'Under Repair'),
        ('RETIRED', 'Retired'),
        ('DISPOSED', 'Disposed'),
        ('LOST', 'Lost/Missing'),
        ('DAMAGED', 'Damaged'),
    ]

    CONDITION_CHOICES = [
        ('NEW', 'New'),
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('DAMAGED', 'Damaged'),
        ('NOT_WORKING', 'Not Working'),
    ]

    # Basic Identification
    device_id = models.CharField(max_length=20, unique=True, editable=False)  # Auto-generated BPS-YYYY-XXXX
    asset_tag = models.CharField(max_length=50, unique=True)
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Device Classification
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='devices')
    device_name = models.CharField(max_length=200)
    
    # Hardware Information
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    mac_address = models.CharField(
        max_length=17, 
        blank=True, 
        validators=[RegexValidator(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', 'Invalid MAC address format')]
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Technical Specifications (stored as JSON for flexibility)
    specifications = models.JSONField(default=dict, blank=True, help_text="Technical specifications as key-value pairs")
    
    # Status and Condition - FIXED: Using the correct choice field names
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='NEW')
    
    # Procurement Information
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='devices')
    purchase_date = models.DateField()
    purchase_order_number = models.CharField(max_length=50, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Warranty Information
    warranty_start_date = models.DateField()
    warranty_end_date = models.DateField()
    warranty_type = models.CharField(max_length=50, default='Standard')
    support_contract = models.TextField(blank=True)
    amc_details = models.TextField(blank=True, help_text="Annual Maintenance Contract details")
    
    # Location and Assignment
    current_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')
    
    # Lifecycle Management
    deployment_date = models.DateField(null=True, blank=True)
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    retirement_date = models.DateField(null=True, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    is_critical = models.BooleanField(default=False, help_text="Mark as critical infrastructure")
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_devices')
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='updated_devices')

    class Meta:
        ordering = ['device_id']

    def __str__(self):
        return f"{self.device_id} - {self.device_name}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate device_id"""
        if not self.device_id:
            current_year = timezone.now().year
            # Get the last device for the current year
            last_device = Device.objects.filter(
                device_id__startswith=f'BPS-{current_year}'
            ).order_by('-device_id').first()
            
            if last_device:
                # Extract the sequence number from the last device ID
                try:
                    last_sequence = int(last_device.device_id.split('-')[-1])
                    new_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    new_sequence = 1
            else:
                new_sequence = 1
            
            self.device_id = f'BPS-{current_year}-{new_sequence:04d}'
        
        super().save(*args, **kwargs)

    @property
    def warranty_status(self):
        """Get warranty status"""
        if not self.warranty_end_date:
            return 'Unknown'
        
        today = date.today()
        if self.warranty_end_date < today:
            return 'Expired'
        elif self.warranty_end_date <= today + timezone.timedelta(days=30):
            return 'Expiring Soon'
        else:
            return 'Active'

    @property
    def age_in_years(self):
        """Calculate device age in years"""
        if self.purchase_date:
            today = date.today()
            return (today - self.purchase_date).days / 365.25
        return 0


# ================================
# 6. ASSIGNMENT MODELS
# ================================

class Assignment(models.Model):
    """Device assignment tracking"""
    assignment_id = models.CharField(max_length=20, unique=True, editable=False)  # Auto-generated
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='assignments')
    
    # Assignment targets (at least one must be specified)
    assigned_to_staff = models.ForeignKey('Staff', on_delete=models.CASCADE, null=True, blank=True, related_name='assignments')
    assigned_to_department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True, related_name='assignments')
    assigned_to_location = models.ForeignKey('Location', on_delete=models.CASCADE, null=True, blank=True, related_name='assignments')
    
    # Assignment details
    is_temporary = models.BooleanField(default=False, help_text="Is this a temporary assignment?")
    expected_return_date = models.DateField(null=True, blank=True, help_text="Required for temporary assignments")
    actual_return_date = models.DateField(null=True, blank=True)
    
    # Dates
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True)
    
    # Assignment metadata
    purpose = models.CharField(max_length=200, help_text="Purpose of assignment")
    conditions = models.TextField(blank=True, help_text="Special conditions or requirements")
    notes = models.TextField(blank=True)
    return_notes = models.TextField(blank=True, help_text="Notes when device is returned")
    return_condition = models.CharField(max_length=50, blank=True, help_text="Device condition when returned")
    
    # Status tracking
    is_active = models.BooleanField(default=True)
    
    # Tracking
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assignments_made')
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assignments_created')
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assignments_updated')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assignments_requested')

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        target = self.assigned_to_staff or self.assigned_to_department or self.assigned_to_location
        return f"{self.device.device_name} → {target}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate assignment_id"""
        if not self.assignment_id:
            current_year = timezone.now().year
            # Get the last assignment for the current year
            last_assignment = Assignment.objects.filter(
                assignment_id__startswith=f'ASG-{current_year}'
            ).order_by('-assignment_id').first()
            
            if last_assignment:
                # Extract the sequence number from the last assignment ID
                try:
                    last_sequence = int(last_assignment.assignment_id.split('-')[-1])
                    new_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    new_sequence = 1
            else:
                new_sequence = 1
            
            self.assignment_id = f'ASG-{current_year}-{new_sequence:04d}'
        
        super().save(*args, **kwargs)

    def clean(self):
        """Validate assignment data"""
        from django.core.exceptions import ValidationError
        
        # At least one assignment target must be specified
        if not any([self.assigned_to_staff, self.assigned_to_department, self.assigned_to_location]):
            raise ValidationError("Must assign to at least one target (staff, department, or location)")
        
        # Temporary assignments must have expected return date
        if self.is_temporary and not self.expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments")
        
        # Return date validations
        if self.expected_return_date and self.start_date:
            if self.expected_return_date <= self.start_date:
                raise ValidationError("Expected return date must be after start date")
        
        if self.actual_return_date and self.start_date:
            if self.actual_return_date < self.start_date:
                raise ValidationError("Actual return date cannot be before start date")

    @property
    def is_overdue(self):
        """Check if temporary assignment is overdue"""
        if self.is_temporary and self.is_active and self.expected_return_date:
            return self.expected_return_date < date.today()
        return False

    @property
    def assignment_duration(self):
        """Calculate assignment duration"""
        end_date = self.actual_return_date or self.end_date or date.today()
        return (end_date - self.start_date).days

class AssignmentHistory(models.Model):
    """Track assignment changes and history"""
    assignment = models.ForeignKey('Assignment', on_delete=models.CASCADE, related_name='history_records')
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='assignment_history')
    action = models.CharField(max_length=50)  # ASSIGNED, TRANSFERRED, RETURNED, etc.
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.device.device_name} - {self.action} at {self.changed_at}"

# ================================
# 7. MAINTENANCE & LIFECYCLE MODELS
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

    MAINTENANCE_STATUS = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]

    FREQUENCY_CHOICES = [
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('SEMI_ANNUAL', 'Semi-Annual'),
        ('ANNUAL', 'Annual'),
        ('AS_NEEDED', 'As Needed'),
    ]

    # Existing fields (keep these)
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='maintenance_schedules')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    description = models.TextField()
    next_due_date = models.DateField()
    last_completed_date = models.DateField(null=True, blank=True)
    assigned_technician = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_assignments')
    estimated_duration = models.DurationField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Add the missing fields that your forms expect
    title = models.CharField(max_length=200, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS, default='SCHEDULED')
    vendor = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_schedules')
    technician_name = models.CharField(max_length=100, blank=True)
    technician_contact = models.CharField(max_length=50, blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    parts_used = models.TextField(blank=True)
    work_performed = models.TextField(blank=True)
    completion_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['next_due_date']

    def __str__(self):
        return f"{self.device.device_name} - {self.get_maintenance_type_display()}"

    @property
    def is_overdue(self):
        """Check if maintenance is overdue"""
        if self.scheduled_date:
            return self.scheduled_date < date.today()
        return self.next_due_date < date.today()

    @property
    def days_until_due(self):
        """Calculate days until next maintenance"""
        if self.scheduled_date:
            return (self.scheduled_date - date.today()).days
        return (self.next_due_date - date.today()).days
    
class MaintenanceRecord(models.Model):
    """Record of completed maintenance activities"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]

    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_schedule = models.ForeignKey(MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='records')
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceSchedule.MAINTENANCE_TYPES)
    description = models.TextField()
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    technician = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
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
# 8. AUDIT & TRACKING MODELS
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

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
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



# 11. SYSTEM CONFIGURATION MODELS
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
# 12. NOTIFICATION & ALERT MODELS
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
    
    # Trigger conditions
    trigger_conditions = models.JSONField(default=dict, help_text="Conditions that trigger this notification")
    
    # Notification settings
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_in_app = models.BooleanField(default=True)
    
    # Recipients
    notify_device_owner = models.BooleanField(default=True)
    notify_department_head = models.BooleanField(default=False)
    notify_it_admin = models.BooleanField(default=True)
    additional_recipients = models.JSONField(default=list, help_text="List of additional email addresses")
    
    # Message template
    email_subject_template = models.CharField(max_length=200)
    email_body_template = models.TextField()
    sms_template = models.CharField(max_length=160, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.event_type} - {self.name}"

class Notification(models.Model):
    """Individual notification instances"""
    NOTIFICATION_STATUS = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('READ', 'Read'),
    ]

    rule = models.ForeignKey(NotificationRule, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    # Related objects
    device = models.ForeignKey(Device, on_delete=models.CASCADE, null=True, blank=True)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True)
    maintenance = models.ForeignKey(MaintenanceSchedule, on_delete=models.CASCADE, null=True, blank=True)
    
    # Message content
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Delivery tracking
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} → {self.recipient.username} ({self.status})"

# 14. INTEGRATION & API MODELS
# ================================

class APIAccessLog(models.Model):
    """Log API access for monitoring and security"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Request details
    method = models.CharField(max_length=10)  # GET, POST, PUT, DELETE
    endpoint = models.CharField(max_length=200)
    request_data = models.JSONField(default=dict, blank=True)
    
    # Response details
    status_code = models.PositiveIntegerField()
    response_time = models.FloatField(help_text="Response time in seconds")
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code} ({self.user or 'Anonymous'})"

class DataImportLog(models.Model):
    """Log data import operations"""
    IMPORT_TYPES = [
        ('DEVICES', 'Device Import'),
        ('STAFF', 'Staff Import'),
        ('LOCATIONS', 'Location Import'),
        ('ASSIGNMENTS', 'Assignment Import'),
    ]

    import_type = models.CharField(max_length=20, choices=IMPORT_TYPES)
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)
    total_records = models.PositiveIntegerField(default=0)
    successful_imports = models.PositiveIntegerField(default=0)
    failed_imports = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.import_type} - {self.file_name} ({self.successful_imports}/{self.total_records})"

    @property
    def success_rate(self):
        """Calculate import success rate"""
        if self.total_records > 0:
            return (self.successful_imports / self.total_records) * 100
        return 0

    @property
    def duration(self):
        """Calculate import duration"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None