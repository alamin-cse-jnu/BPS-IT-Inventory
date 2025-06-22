from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid

# ================================
# 1. ORGANIZATION & LOCATION MODELS
# ================================

class Organization(models.Model):
    """Root organization model"""
    name = models.CharField(max_length=200, default="Bangladesh Parliament Secretariat")
    code = models.CharField(max_length=10, unique=True, default="BPS")
    address = models.TextField()
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Building(models.Model):
    """Building/Campus model"""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='buildings')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    address = models.TextField()
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['organization', 'code']

    def __str__(self):
        return f"{self.organization.code}-{self.code} {self.name}"

class Floor(models.Model):
    """Floor model within buildings"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    name = models.CharField(max_length=50)
    floor_number = models.CharField(max_length=10)  # Could be "G", "1", "2", "B1", etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['building', 'floor_number']

    def __str__(self):
        return f"{self.building} - Floor {self.floor_number}"

class Department(models.Model):
    """Department/Office model"""
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    head_of_department = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['floor', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

class Room(models.Model):
    """Room model within departments"""
    ROOM_TYPES = [
        ('OFFICE', 'Office Room'),
        ('MEETING', 'Meeting Room'),
        ('DATA_CENTER', 'Data Center'),
        ('SERVER_ROOM', 'Server Room'),
        ('NETWORK_CLOSET', 'Network Closet'),
        ('STORAGE', 'Storage Room'),
        ('MAINTENANCE', 'Maintenance Room'),
        ('OTHER', 'Other'),
    ]

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100)
    room_number = models.CharField(max_length=20)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='OFFICE')
    capacity = models.PositiveIntegerField(null=True, blank=True)
    environmental_conditions = models.TextField(blank=True, help_text="Temperature, humidity specifications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['department', 'room_number']

    def __str__(self):
        return f"{self.department.code}-{self.room_number} {self.name}"

class Location(models.Model):
    """Specific location within rooms (desk, rack position, etc.)"""
    LOCATION_TYPES = [
        ('DESK', 'Desk Position'),
        ('RACK', 'Server Rack'),
        ('RACK_UNIT', 'Rack Unit (U)'),
        ('WALL_MOUNT', 'Wall Mount'),
        ('FLOOR_STAND', 'Floor Stand'),
        ('CEILING_MOUNT', 'Ceiling Mount'),
        ('MOBILE', 'Mobile/Portable'),
        ('STORAGE_SHELF', 'Storage Shelf'),
        ('OTHER', 'Other'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100)
    location_code = models.CharField(max_length=20)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='DESK')
    coordinates = models.CharField(max_length=50, blank=True, help_text="Grid position or coordinates")
    capacity = models.PositiveIntegerField(default=1, help_text="Number of devices this location can hold")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['room', 'location_code']

    def __str__(self):
        return f"{self.room} - {self.location_code} ({self.name})"

    @property
    def full_location_path(self):
        """Returns full hierarchical location path"""
        return f"{self.room.department.floor.building.organization.code} > {self.room.department.floor.building.name} > Floor {self.room.department.floor.floor_number} > {self.room.department.name} > {self.room.name} > {self.name}"

# ================================
# 2. STAFF & USER MANAGEMENT MODELS
# ================================

class Staff(models.Model):
    """Staff information model"""
    SECURITY_CLEARANCE_LEVELS = [
        ('PUBLIC', 'Public'),
        ('RESTRICTED', 'Restricted'),
        ('CONFIDENTIAL', 'Confidential'),
        ('SECRET', 'Secret'),
        ('TOP_SECRET', 'Top Secret'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=200)
    designation = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='staff_members')
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    extension = models.CharField(max_length=10, blank=True)
    reporting_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    security_clearance = models.CharField(max_length=20, choices=SECURITY_CLEARANCE_LEVELS, default='PUBLIC')
    date_joined = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Staff"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name} ({self.designation})"

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
    VENDOR_TYPES = [
        ('MANUFACTURER', 'Manufacturer'),
        ('DISTRIBUTOR', 'Distributor'),
        ('RESELLER', 'Reseller'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('MAINTENANCE', 'Maintenance Provider'),
    ]

    name = models.CharField(max_length=200)
    vendor_code = models.CharField(max_length=20, unique=True)
    vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPES)
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    website = models.URLField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    performance_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, help_text="Rating out of 5.00")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor_code} - {self.name}"

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
    DEVICE_STATUS = [
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

    CONDITION_STATUS = [
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
    
    # Status and Condition
    status = models.CharField(max_length=20, choices=DEVICE_STATUS, default='AVAILABLE')
    condition = models.CharField(max_length=20, choices=CONDITION_STATUS, default='NEW')
    
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
    
    # Lifecycle Management
    deployment_date = models.DateField(null=True, blank=True)
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    retirement_date = models.DateField(null=True, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    is_critical = models.BooleanField(default=False, help_text="Critical infrastructure device")
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_devices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='updated_devices')
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.device_id:
            # Generate device ID: BPS-YYYY-XXXX
            year = timezone.now().year
            last_device = Device.objects.filter(device_id__startswith=f'BPS-{year}').order_by('device_id').last()
            if last_device:
                last_number = int(last_device.device_id.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            self.device_id = f'BPS-{year}-{new_number:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.device_id} - {self.device_name}"

    @property
    def is_warranty_active(self):
        """Check if warranty is still active"""
        return timezone.now().date() <= self.warranty_end_date

    @property
    def warranty_expires_soon(self):
        """Check if warranty expires within 30 days"""
        days_remaining = (self.warranty_end_date - timezone.now().date()).days
        return 0 <= days_remaining <= 30

# ================================
# 6. ASSIGNMENT MODELS
# ================================

class Assignment(models.Model):
    """Device assignment model - flexible assignment system"""
    ASSIGNMENT_TYPES = [
        ('PERSONAL', 'Personal Assignment'),
        ('DEPARTMENTAL', 'Departmental Assignment'),
        ('LOCATION', 'Location Assignment'),
        ('PROJECT', 'Project Assignment'),
        ('TEMPORARY', 'Temporary Assignment'),
        ('POOL', 'Device Pool'),
        ('MAINTENANCE', 'Maintenance Assignment'),
    ]

    # Assignment Identification
    assignment_id = models.CharField(max_length=20, unique=True, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='assignments')
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES)
    
    # Assignment Targets (flexible - one or more can be set)
    assigned_to_staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True, related_name='assigned_devices')
    assigned_to_department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name='assigned_devices')
    assigned_to_location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True, related_name='assigned_devices')
    
    # Project Assignment (for future project management integration)
    project_name = models.CharField(max_length=200, blank=True)
    project_code = models.CharField(max_length=50, blank=True)
    
    # Assignment Dates
    start_date = models.DateField(default=timezone.now)
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)
    
    # Assignment Status
    is_active = models.BooleanField(default=True)
    is_temporary = models.BooleanField(default=False)
    
    # Assignment Details
    purpose = models.TextField(blank=True, help_text="Purpose of assignment")
    conditions = models.TextField(blank=True, help_text="Special conditions or requirements")
    notes = models.TextField(blank=True)
    
    # Approval Workflow
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='requested_assignments')
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_assignments')
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='updated_assignments')
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.assignment_id:
            # Generate assignment ID: ASN-YYYY-XXXX
            year = timezone.now().year
            last_assignment = Assignment.objects.filter(assignment_id__startswith=f'ASN-{year}').order_by('assignment_id').last()
            if last_assignment:
                last_number = int(last_assignment.assignment_id.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            self.assignment_id = f'ASN-{year}-{new_number:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        target = self.assigned_to_staff or self.assigned_to_department or self.assigned_to_location or "Unassigned"
        return f"{self.assignment_id} - {self.device.device_name} → {target}"

    @property
    def is_overdue(self):
        """Check if temporary assignment is overdue"""
        if self.is_temporary and self.expected_return_date and not self.actual_return_date:
            return timezone.now().date() > self.expected_return_date
        return False

class AssignmentHistory(models.Model):
    """Complete history of all device assignments"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='assignment_history')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='history_records')
    
    # What changed
    action = models.CharField(max_length=50)  # 'ASSIGNED', 'TRANSFERRED', 'RETURNED', 'LOCATION_CHANGED'
    
    # Previous values (for tracking changes)
    previous_staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    previous_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    previous_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # New values
    new_staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    new_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    new_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # Change details
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Audit
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.device_id} - {self.action} on {self.changed_at.date()}"

# ================================
# 7. MAINTENANCE & LIFECYCLE MODELS
# ================================

class MaintenanceSchedule(models.Model):
    """Maintenance scheduling and tracking"""
    MAINTENANCE_TYPES = [
        ('PREVENTIVE', 'Preventive Maintenance'),
        ('CORRECTIVE', 'Corrective Maintenance'),
        ('PREDICTIVE', 'Predictive Maintenance'),
        ('EMERGENCY', 'Emergency Maintenance'),
        ('UPGRADE', 'Upgrade Maintenance'),
    ]

    MAINTENANCE_STATUS = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='maintenance_schedules')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    estimated_duration = models.DurationField(null=True, blank=True)
    
    actual_start_date = models.DateTimeField(null=True, blank=True)
    actual_end_date = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS, default='SCHEDULED')
    
    # Service provider information
    performed_by = models.CharField(max_length=200, blank=True)  # Internal staff or external vendor
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    technician_name = models.CharField(max_length=100, blank=True)
    technician_contact = models.CharField(max_length=50, blank=True)
    
    # Cost and parts
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    parts_used = models.TextField(blank=True)
    
    # Results and notes
    work_performed = models.TextField(blank=True)
    issues_found = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_maintenance')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='updated_maintenance')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.device.device_id} - {self.title} ({self.scheduled_date})"

# ================================
# 8. AUDIT & TRACKING MODELS
# ================================

class AuditLog(models.Model):
    """System-wide audit logging"""
    ACTION_TYPES = [
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
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    
    # Details of the change
    changes = models.JSONField(default=dict, blank=True)  # Store field changes
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} {self.model_name} at {self.timestamp}"

class DeviceMovementLog(models.Model):
    """Track all device movements and location changes"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='movement_logs')
    
    # Movement details
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_from')
    to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_to')
    
    # Staff involved
    moved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_movements')
    authorized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='authorized_movements')
    
    # Movement reason and details
    reason = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    
    # QR code scan verification
    qr_scanned = models.BooleanField(default=False)
    scan_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Audit
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.device_id} moved from {self.from_location} to {self.to_location} on {self.timestamp.date()}"



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
    """Track bulk data imports"""
    IMPORT_TYPES = [
        ('DEVICES', 'Device Import'),
        ('STAFF', 'Staff Import'),
        ('LOCATIONS', 'Location Import'),
        ('ASSIGNMENTS', 'Assignment Import'),
    ]

    import_type = models.CharField(max_length=20, choices=IMPORT_TYPES)
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)
    
    # Import results
    total_records = models.PositiveIntegerField(default=0)
    successful_imports = models.PositiveIntegerField(default=0)
    failed_imports = models.PositiveIntegerField(default=0)
    
    # Error tracking
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.import_type} - {self.file_name} ({self.successful_imports}/{self.total_records})"

# Set verbose names and metadata for better admin interface
Device._meta.verbose_name = "Device"
Device._meta.verbose_name_plural = "Devices"

Assignment._meta.verbose_name = "Assignment"
Assignment._meta.verbose_name_plural = "Assignments"

Staff._meta.verbose_name = "Staff Member"
Staff._meta.verbose_name_plural = "Staff Members"