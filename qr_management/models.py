
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import json

# ================================
# QR CODE & VERIFICATION MODELS
# ================================

class QRCodeScan(models.Model):
    """Track QR code scans and verifications for audit and analytics"""
    
    SCAN_TYPES = [
        ('VERIFICATION', 'Device Verification'),
        ('INVENTORY', 'Inventory Check'),
        ('ASSIGNMENT', 'Assignment Verification'),
        ('MAINTENANCE', 'Maintenance Scan'),
        ('AUDIT', 'Audit Scan'),
        ('BATCH_VERIFICATION', 'Batch Verification'),
        ('MOBILE_SCAN', 'Mobile App Scan'),
        ('LOCATION_UPDATE', 'Location Update'),
        ('ASSIGNMENT_CHECK', 'Assignment Check'),
        ('TRANSFER', 'Device Transfer'),
        ('GENERAL', 'General Scan'),
    ]

    VERIFICATION_STATUS = [
        ('SUCCESS', 'Verification Successful'),
        ('FAILED', 'Verification Failed'),
        ('WARNING', 'Verification with Warnings'),
        ('ERROR', 'Scan Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core scan information
    device = models.ForeignKey(
        'inventory.Device', 
        on_delete=models.CASCADE, 
        related_name='qr_scans'
    )
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPES, default='VERIFICATION')
    scanned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='qr_scans'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Location information at time of scan
    scan_location = models.ForeignKey(
        'inventory.Location', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='qr_scans_performed',
        help_text="Location where the scan was performed"
    )
    
    # Device state captured at scan time
    device_status_at_scan = models.CharField(
        max_length=20, 
        help_text="Device status when scanned"
    )
    device_location_at_scan = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_location_scans',
        help_text="Device's recorded location at scan time"
    )
    assigned_staff_at_scan = models.ForeignKey(
        'inventory.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_scans_as_assignee',
        help_text="Staff assigned to device at scan time"
    )
    
    # Verification results
    verification_success = models.BooleanField(default=True)
    discrepancies_found = models.TextField(
        blank=True,
        help_text="Details of any discrepancies found during verification"
    )
    actions_taken = models.TextField(
        blank=True,
        help_text="Actions taken as a result of the scan"
    )
    
    # Scan metadata
    scan_notes = models.TextField(
        blank=True, 
        help_text="Additional notes from the scan session"
    )
    
    # Geographic and technical information
    gps_coordinates = models.CharField(
        max_length=100, 
        blank=True,
        help_text="GPS coordinates if available (latitude,longitude)"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_info = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Information about the scanning device"
    )
    app_version = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Mobile app version if applicable"
    )
    
    # Performance metrics
    scan_duration_ms = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Time taken to complete scan in milliseconds"
    )
    
    # Batch scan information
    batch_scan_id = models.UUIDField(
        null=True, 
        blank=True,
        help_text="ID linking scans performed in the same batch"
    )
    batch_sequence = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Order within batch scan"
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['scanned_by', 'timestamp']),
            models.Index(fields=['scan_type', 'timestamp']),
            models.Index(fields=['verification_success']),
            models.Index(fields=['batch_scan_id']),
        ]
        
    def __str__(self):
        scanned_by_name = self.scanned_by.username if self.scanned_by else 'Unknown'
        return f"QR Scan: {self.device.device_id} by {scanned_by_name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def has_discrepancies(self):
        """Check if scan found any discrepancies"""
        return bool(self.discrepancies_found.strip())
    
    @property
    def scan_result_display(self):
        """Human-readable scan result"""
        if not self.verification_success:
            return "Failed"
        elif self.has_discrepancies:
            return "Success (with notes)"
        else:
            return "Success"

    @property
    def location_matches(self):
        """Check if scan location matches device's recorded location"""
        if self.scan_location and self.device_location_at_scan:
            return self.scan_location == self.device_location_at_scan
        return None

class QRCodeTemplate(models.Model):
    """Templates for QR code generation with different styles and formats"""
    
    TEMPLATE_TYPES = [
        ('STANDARD', 'Standard QR Code'),
        ('WITH_LOGO', 'QR Code with Logo'),
        ('LABEL', 'Label Format'),
        ('ASSET_TAG', 'Asset Tag Format'),
        ('MINI', 'Mini QR Code'),
        ('CUSTOM', 'Custom Format'),
    ]

    SIZE_CHOICES = [
        ('SMALL', 'Small (100x100)'),
        ('MEDIUM', 'Medium (200x200)'),
        ('LARGE', 'Large (400x400)'),
        ('XLARGE', 'Extra Large (600x600)'),
        ('CUSTOM', 'Custom Size'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Template name")
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    
    # QR Code generation settings
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='MEDIUM')
    custom_width = models.PositiveIntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(1000)],
        help_text="Custom width in pixels"
    )
    custom_height = models.PositiveIntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(1000)],
        help_text="Custom height in pixels"
    )
    
    # QR Code appearance
    qr_size = models.PositiveIntegerField(default=10, help_text="QR code box size")
    qr_border = models.PositiveIntegerField(default=4, help_text="QR code border size")
    error_correction = models.CharField(
        max_length=1,
        choices=[
            ('L', 'Low (~7%)'),
            ('M', 'Medium (~15%)'),
            ('Q', 'Quartile (~25%)'),
            ('H', 'High (~30%)'),
        ],
        default='L',
        help_text="Error correction level"
    )
    
    # Colors and styling
    foreground_color = models.CharField(
        max_length=7, 
        default='#000000',
        help_text="QR code foreground color (hex)"
    )
    background_color = models.CharField(
        max_length=7, 
        default='#FFFFFF',
        help_text="QR code background color (hex)"
    )
    
    # Logo and branding
    include_logo = models.BooleanField(default=False)
    logo_file = models.ImageField(upload_to='qr_logos/', null=True, blank=True)
    logo_size_percentage = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(5), MaxValueValidator(30)],
        help_text="Logo size as percentage of QR code"
    )
    
    # Label and text settings
    include_device_name = models.BooleanField(default=True)
    include_asset_tag = models.BooleanField(default=True)
    include_category = models.BooleanField(default=False)
    include_brand_model = models.BooleanField(default=False)
    include_text_label = models.BooleanField(default=True)
    
    label_template = models.CharField(
        max_length=200,
        default='{device_id}',
        help_text="Label template using placeholders like {device_id}, {device_name}"
    )
    label_position = models.CharField(
        max_length=10,
        choices=[
            ('TOP', 'Top'),
            ('BOTTOM', 'Bottom'),
            ('LEFT', 'Left'),
            ('RIGHT', 'Right'),
        ],
        default='BOTTOM'
    )
    
    # Template configuration
    label_width = models.PositiveIntegerField(default=600, help_text="Label width in pixels")
    label_height = models.PositiveIntegerField(default=200, help_text="Label height in pixels")
    font_size_large = models.PositiveIntegerField(default=24)
    font_size_medium = models.PositiveIntegerField(default=18)
    font_size_small = models.PositiveIntegerField(default=14)
    
    # Data included in QR code
    qr_data_template = models.JSONField(
        default=dict,
        help_text="Template for data included in QR code"
    )
    include_device_details = models.BooleanField(default=True)
    include_assignment_info = models.BooleanField(default=True)
    include_location_info = models.BooleanField(default=True)
    include_verification_url = models.BooleanField(default=True)
    
    # Template metadata
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_system_template = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_qr_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def save(self, *args, **kwargs):
        # Ensure only one default template
        if self.is_default:
            QRCodeTemplate.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])

class QRCodeBatch(models.Model):
    """Track batch QR code generation jobs"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    GENERATION_TYPES = [
        ('SINGLE', 'Single Device'),
        ('BATCH', 'Batch Generation'),
        ('DEPARTMENT', 'Department Batch'),
        ('CATEGORY', 'Category Batch'),
        ('CUSTOM_LIST', 'Custom Device List'),
    ]

    OUTPUT_FORMATS = [
        ('PNG', 'PNG Images'),
        ('PDF', 'PDF Document'),
        ('ZIP', 'ZIP Archive'),
        ('LABEL_SHEET', 'Label Sheet'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Batch job name")
    generation_type = models.CharField(max_length=15, choices=GENERATION_TYPES, default='BATCH')
    template = models.ForeignKey(QRCodeTemplate, on_delete=models.SET_NULL, null=True, related_name='batches')
    
    # Generation parameters
    device_filter = models.JSONField(
        default=dict,
        help_text="Filters applied to select devices for QR generation"
    )
    device_list = models.JSONField(
        default=list,
        help_text="Specific list of device IDs for custom generation"
    )
    
    # Job details
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_batches')
    device_count = models.PositiveIntegerField(default=0, help_text="Number of devices in batch")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    output_format = models.CharField(max_length=15, choices=OUTPUT_FORMATS, default='ZIP')
    
    # Progress tracking
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.PositiveIntegerField(default=0)
    current_device = models.CharField(max_length=50, blank=True)
    
    # Results
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    output_file = models.FileField(upload_to='qr_batches/', null=True, blank=True)
    error_log = models.TextField(blank=True)
    failed_devices = models.JSONField(
        default=list,
        help_text="List of device IDs that failed to generate"
    )
    
    # Performance metrics
    generation_time_seconds = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"QR Batch: {self.name} ({self.get_status_display()})"
    
    @property
    def success_rate(self):
        if self.device_count > 0:
            return (self.generated_count / self.device_count) * 100
        return 0
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_completed(self):
        return self.status == 'COMPLETED'

class QRCodePrintJob(models.Model):
    """Track QR code printing requests and jobs"""
    
    PRINT_FORMATS = [
        ('AVERY_5160', 'Avery 5160 (Address Labels)'),
        ('AVERY_5167', 'Avery 5167 (Return Labels)'),
        ('AVERY_8160', 'Avery 8160 (Mini Labels)'),
        ('CUSTOM_SHEET', 'Custom Label Sheet'),
        ('INDIVIDUAL', 'Individual Labels'),
    ]

    PAPER_SIZES = [
        ('A4', 'A4 (210 x 297 mm)'),
        ('LETTER', 'Letter (8.5 x 11 in)'),
        ('A3', 'A3 (297 x 420 mm)'),
        ('LEGAL', 'Legal (8.5 x 14 in)'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready to Print'),
        ('PRINTED', 'Printed'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qr_batch = models.ForeignKey(
        QRCodeBatch, 
        on_delete=models.CASCADE, 
        related_name='print_jobs'
    )
    
    # Print settings
    print_format = models.CharField(max_length=20, choices=PRINT_FORMATS)
    paper_size = models.CharField(max_length=10, choices=PAPER_SIZES, default='A4')
    copies_per_device = models.PositiveIntegerField(default=1)
    
    # Layout settings
    labels_per_row = models.PositiveIntegerField(default=3)
    labels_per_column = models.PositiveIntegerField(default=10)
    margin_top = models.FloatField(default=0.5, help_text="Top margin in inches")
    margin_left = models.FloatField(default=0.5, help_text="Left margin in inches")
    label_width = models.FloatField(default=2.5, help_text="Label width in inches")
    label_height = models.FloatField(default=1.0, help_text="Label height in inches")
    
    # Print job tracking
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Output
    print_file = models.FileField(upload_to='qr_print_jobs/', null=True, blank=True)
    total_labels = models.PositiveIntegerField(default=0)
    total_pages = models.PositiveIntegerField(default=0)
    
    # Tracking
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_print_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    
    # Printer information
    printer_name = models.CharField(max_length=200, blank=True)
    print_queue_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Print Job: {self.print_format} - {self.get_status_display()}"

# ================================
# QR ANALYTICS & REPORTING MODELS
# ================================

class QRAnalytics(models.Model):
    """Store aggregated QR code analytics and metrics"""
    
    METRIC_TYPES = [
        ('DAILY_SCANS', 'Daily Scan Count'),
        ('DEVICE_SCAN_FREQUENCY', 'Device Scan Frequency'),
        ('USER_SCAN_ACTIVITY', 'User Scan Activity'),
        ('LOCATION_SCAN_ACTIVITY', 'Location Scan Activity'),
        ('VERIFICATION_SUCCESS_RATE', 'Verification Success Rate'),
        ('SCAN_TYPE_DISTRIBUTION', 'Scan Type Distribution'),
        ('DISCREPANCY_RATE', 'Discrepancy Rate'),
        ('BATCH_SCAN_EFFICIENCY', 'Batch Scan Efficiency'),
    ]

    AGGREGATION_PERIODS = [
        ('HOUR', 'Hourly'),
        ('DAY', 'Daily'),
        ('WEEK', 'Weekly'),
        ('MONTH', 'Monthly'),
        ('QUARTER', 'Quarterly'),
        ('YEAR', 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    aggregation_period = models.CharField(max_length=10, choices=AGGREGATION_PERIODS)
    
    # Time period for this metric
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Metric data
    metric_value = models.DecimalField(max_digits=15, decimal_places=4)
    additional_data = models.JSONField(
        default=dict,
        help_text="Additional metric data and breakdowns"
    )
    
    # Dimensions for filtering
    department = models.ForeignKey(
        'inventory.Department',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qr_analytics'
    )
    location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qr_analytics'
    )
    device_category = models.ForeignKey(
        'inventory.DeviceCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qr_analytics'
    )
    
    # Calculation metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    calculation_time_ms = models.PositiveIntegerField(null=True, blank=True)
    data_points_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-period_start']
        unique_together = [
            'metric_type', 'aggregation_period', 'period_start', 
            'department', 'location', 'device_category'
        ]
        indexes = [
            models.Index(fields=['metric_type', 'aggregation_period']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['department', 'period_start']),
        ]

    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.period_start.strftime('%Y-%m-%d')}"

class QRCampaign(models.Model):
    """Track QR code verification campaigns and initiatives"""
    
    CAMPAIGN_TYPES = [
        ('AUDIT', 'Audit Campaign'),
        ('VERIFICATION', 'Verification Campaign'),
        ('INVENTORY_CHECK', 'Inventory Check'),
        ('LOCATION_UPDATE', 'Location Update Campaign'),
        ('TRAINING', 'Training Campaign'),
        ('COMPLIANCE', 'Compliance Check'),
    ]

    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PLANNED')
    
    # Campaign scope
    target_devices = models.JSONField(
        default=list,
        help_text="List of device IDs or filter criteria for target devices"
    )
    target_locations = models.ManyToManyField(
        'inventory.Location',
        blank=True,
        related_name='qr_campaigns'
    )
    target_departments = models.ManyToManyField(
        'inventory.Department',
        blank=True,
        related_name='qr_campaigns'
    )
    
    # Campaign timeline
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Campaign team
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_qr_campaigns')
    assigned_to = models.ManyToManyField(
        User,
        related_name='assigned_qr_campaigns',
        help_text="Users assigned to execute this campaign"
    )
    
    # Campaign goals and metrics
    target_scan_percentage = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Target percentage of devices to scan"
    )
    expected_completion_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Progress tracking
    total_target_devices = models.PositiveIntegerField(default=0)
    devices_scanned = models.PositiveIntegerField(default=0)
    successful_scans = models.PositiveIntegerField(default=0)
    discrepancies_found = models.PositiveIntegerField(default=0)
    
    # Campaign configuration
    scan_requirements = models.JSONField(
        default=dict,
        help_text="Specific requirements for scans in this campaign"
    )
    notification_settings = models.JSONField(
        default=dict,
        help_text="Notification settings for campaign progress"
    )

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"

    @property
    def progress_percentage(self):
        if self.total_target_devices > 0:
            return (self.devices_scanned / self.total_target_devices) * 100
        return 0

    @property
    def success_rate(self):
        if self.devices_scanned > 0:
            return (self.successful_scans / self.devices_scanned) * 100
        return 0

    @property
    def is_active(self):
        now = timezone.now()
        return (self.status == 'ACTIVE' and 
                self.start_date <= now <= self.end_date)

    @property
    def days_remaining(self):
        if self.end_date:
            remaining = self.end_date - timezone.now()
            return max(0, remaining.days)
        return 0

class QRVerificationRule(models.Model):
    """Define rules for QR code verification and validation"""
    
    RULE_TYPES = [
        ('LOCATION_CHECK', 'Location Verification'),
        ('ASSIGNMENT_CHECK', 'Assignment Verification'),
        ('STATUS_CHECK', 'Status Verification'),
        ('TIME_RESTRICTION', 'Time-based Restriction'),
        ('USER_AUTHORIZATION', 'User Authorization'),
        ('DEPARTMENT_RESTRICTION', 'Department Restriction'),
        ('CUSTOM_VALIDATION', 'Custom Validation'),
    ]

    SEVERITY_LEVELS = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    rule_type = models.CharField(max_length=25, choices=RULE_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='WARNING')
    
    # Rule configuration
    rule_config = models.JSONField(
        default=dict,
        help_text="Configuration parameters for the rule"
    )
    validation_query = models.TextField(
        blank=True,
        help_text="SQL query or validation logic"
    )
    
    # Rule applicability
    applies_to_device_types = models.ManyToManyField(
        'inventory.DeviceType',
        blank=True,
        related_name='qr_verification_rules'
    )
    applies_to_departments = models.ManyToManyField(
        'inventory.Department',
        blank=True,
        related_name='qr_verification_rules'
    )
    applies_to_scan_types = models.JSONField(
        default=list,
        help_text="List of scan types this rule applies to"
    )
    
    # Rule behavior
    is_active = models.BooleanField(default=True)
    is_blocking = models.BooleanField(
        default=False,
        help_text="Whether this rule blocks the scan if violated"
    )
    auto_remediation = models.BooleanField(
        default=False,
        help_text="Whether to attempt automatic remediation"
    )
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_qr_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['severity', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"

class QRVerificationResult(models.Model):
    """Store results of verification rule evaluation"""
    
    scan = models.ForeignKey(
        QRCodeScan,
        on_delete=models.CASCADE,
        related_name='verification_results'
    )
    rule = models.ForeignKey(
        QRVerificationRule,
        on_delete=models.CASCADE,
        related_name='verification_results'
    )
    
    # Result data
    passed = models.BooleanField()
    message = models.TextField(blank=True)
    details = models.JSONField(
        default=dict,
        help_text="Detailed result data"
    )
    
    # Remediation
    remediation_attempted = models.BooleanField(default=False)
    remediation_successful = models.BooleanField(default=False)
    remediation_details = models.TextField(blank=True)
    
    # Timing
    evaluated_at = models.DateTimeField(auto_now_add=True)
    evaluation_time_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ['scan', 'rule']
        ordering = ['-evaluated_at']

    def __str__(self):
        result = "PASS" if self.passed else "FAIL"
        return f"{self.rule.name}: {result} for {self.scan.device.device_id}"

# ================================
# QR CODE CONFIGURATION MODELS
# ================================

class QRSystemConfiguration(models.Model):
    """System-wide QR code configuration settings"""
    
    CONFIG_CATEGORIES = [
        ('GENERATION', 'QR Generation Settings'),
        ('SCANNING', 'QR Scanning Settings'),
        ('VERIFICATION', 'Verification Settings'),
        ('ANALYTICS', 'Analytics Settings'),
        ('MOBILE', 'Mobile App Settings'),
        ('INTEGRATION', 'Integration Settings'),
        ('TEMPLATES', 'Template Settings'),
        ('BATCH', 'Batch Processing Settings'),
    ]

    category = models.CharField(max_length=20, choices=CONFIG_CATEGORIES)
    key = models.CharField(max_length=100)
    value = models.TextField()
    description = models.TextField(blank=True)
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('STRING', 'String'),
            ('INTEGER', 'Integer'),
            ('FLOAT', 'Float'),
            ('BOOLEAN', 'Boolean'),
            ('JSON', 'JSON Object'),
            ('LIST', 'List'),
        ],
        default='STRING'
    )
    
    # Configuration metadata
    is_active = models.BooleanField(default=True)
    is_system_setting = models.BooleanField(default=True)
    requires_restart = models.BooleanField(default=False)
    
    # Change tracking
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    previous_value = models.TextField(blank=True)

    class Meta:
        unique_together = ['category', 'key']
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category}.{self.key} = {self.value[:50]}"

    def get_typed_value(self):
        """Return the value converted to the appropriate data type"""
        if self.data_type == 'INTEGER':
            return int(self.value)
        elif self.data_type == 'FLOAT':
            return float(self.value)
        elif self.data_type == 'BOOLEAN':
            return self.value.lower() in ['true', '1', 'yes', 'on']
        elif self.data_type == 'JSON':
            return json.loads(self.value)
        elif self.data_type == 'LIST':
            return json.loads(self.value) if self.value.startswith('[') else self.value.split(',')
        else:
            return self.value

# ================================
# QR MOBILE APP MODELS
# ================================

class QRMobileSession(models.Model):
    """Track mobile app sessions for QR scanning"""
    
    SESSION_TYPES = [
        ('SCAN_SESSION', 'Scanning Session'),
        ('VERIFICATION_SESSION', 'Verification Session'),
        ('BATCH_SESSION', 'Batch Scanning Session'),
        ('AUDIT_SESSION', 'Audit Session'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_mobile_sessions')
    session_type = models.CharField(max_length=25, choices=SESSION_TYPES, default='SCAN_SESSION')
    
    # Session tracking
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Location and device info
    location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_mobile_sessions'
    )
    device_info = models.JSONField(default=dict, help_text="Mobile device information")
    app_version = models.CharField(max_length=50, blank=True)
    
    # Session statistics
    scans_performed = models.PositiveIntegerField(default=0)
    successful_scans = models.PositiveIntegerField(default=0)
    failed_scans = models.PositiveIntegerField(default=0)
    
    # GPS tracking
    start_gps = models.CharField(max_length=100, blank=True, help_text="Starting GPS coordinates")
    end_gps = models.CharField(max_length=100, blank=True, help_text="Ending GPS coordinates")

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Mobile Session: {self.user.username} - {self.get_session_type_display()}"

    @property
    def duration(self):
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        if self.scans_performed > 0:
            return (self.successful_scans / self.scans_performed) * 100
        return 0

class QRBulkVerification(models.Model):
    """Track bulk verification operations"""
    
    VERIFICATION_TYPES = [
        ('LOCATION_AUDIT', 'Location Audit'),
        ('DEPARTMENT_AUDIT', 'Department Audit'),
        ('INVENTORY_CHECK', 'Inventory Check'),
        ('COMPLIANCE_CHECK', 'Compliance Check'),
        ('SCHEDULED_AUDIT', 'Scheduled Audit'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('PAUSED', 'Paused'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Scope and targeting
    target_devices = models.JSONField(default=list, help_text="Device IDs to verify")
    target_locations = models.ManyToManyField(
        'inventory.Location',
        blank=True,
        related_name='bulk_verifications'
    )
    target_departments = models.ManyToManyField(
        'inventory.Department',
        blank=True,
        related_name='bulk_verifications'
    )
    
    # Verification settings
    verification_rules = models.ManyToManyField(
        QRVerificationRule,
        blank=True,
        related_name='bulk_verifications'
    )
    auto_remediate = models.BooleanField(default=False)
    require_photos = models.BooleanField(default=False)
    require_gps = models.BooleanField(default=False)
    
    # Progress tracking
    total_devices = models.PositiveIntegerField(default=0)
    verified_devices = models.PositiveIntegerField(default=0)
    failed_devices = models.PositiveIntegerField(default=0)
    devices_with_discrepancies = models.PositiveIntegerField(default=0)
    
    # Timeline
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_bulk_verifications')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    results_summary = models.JSONField(default=dict, help_text="Summary of verification results")
    export_file = models.FileField(upload_to='bulk_verifications/', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bulk Verification: {self.name} ({self.get_status_display()})"

    @property
    def progress_percentage(self):
        if self.total_devices > 0:
            return (self.verified_devices / self.total_devices) * 100
        return 0

    @property
    def success_rate(self):
        verified_total = self.verified_devices + self.failed_devices
        if verified_total > 0:
            return (self.verified_devices / verified_total) * 100
        return 0

# ================================
# QR NOTIFICATION MODELS
# ================================

class QRNotification(models.Model):
    """QR-specific notifications and alerts"""
    
    NOTIFICATION_TYPES = [
        ('SCAN_ALERT', 'Scan Alert'),
        ('DISCREPANCY_ALERT', 'Discrepancy Alert'),
        ('BATCH_COMPLETE', 'Batch Complete'),
        ('VERIFICATION_FAILED', 'Verification Failed'),
        ('CAMPAIGN_UPDATE', 'Campaign Update'),
        ('SYSTEM_ALERT', 'System Alert'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    
    # Recipients
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_notifications')
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    related_scan = models.ForeignKey(
        QRCodeScan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_campaign = models.ForeignKey(
        QRCampaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_batch = models.ForeignKey(
        QRCodeBatch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Delivery tracking
    sent_via_email = models.BooleanField(default=False)
    sent_via_push = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', 'priority']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])

# ================================
# QR INTEGRATION MODELS
# ================================

class QRIntegrationLog(models.Model):
    """Log QR-related integration activities"""
    
    INTEGRATION_TYPES = [
        ('API_CALL', 'API Call'),
        ('WEBHOOK', 'Webhook'),
        ('DATA_SYNC', 'Data Synchronization'),
        ('EXPORT', 'Data Export'),
        ('IMPORT', 'Data Import'),
        ('MOBILE_SYNC', 'Mobile App Sync'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
        ('TIMEOUT', 'Timeout'),
        ('ERROR', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration_type = models.CharField(max_length=15, choices=INTEGRATION_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    # Integration details
    endpoint = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    # Performance metrics
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    
    # Metadata
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['integration_type', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_integration_type_display()}: {self.get_status_display()}"
    
# ================================
# QRScanLocation MODELS 
# ================================

class QRScanLocation(models.Model):
    """Enhanced location tracking for QR code scans with GPS and contextual data"""
    
    LOCATION_ACCURACY_LEVELS = [
        ('HIGH', 'High (GPS < 5m)'),
        ('MEDIUM', 'Medium (GPS 5-15m)'),
        ('LOW', 'Low (GPS > 15m)'),
        ('NETWORK', 'Network-based'),
        ('MANUAL', 'Manually Entered'),
        ('UNKNOWN', 'Unknown'),
    ]
    
    LOCATION_SOURCES = [
        ('GPS', 'GPS Coordinates'),
        ('WIFI', 'WiFi-based Location'),
        ('CELLULAR', 'Cellular Tower'),
        ('BLUETOOTH', 'Bluetooth Beacon'),
        ('MANUAL', 'Manual Entry'),
        ('SYSTEM', 'System Location'),
    ]

    # Related scan
    scan = models.OneToOneField(
        'QRCodeScan',
        on_delete=models.CASCADE,
        related_name='scan_location',
        primary_key=True
    )
    
    # Location coordinates
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8, 
        null=True, 
        blank=True,
        help_text="GPS latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8, 
        null=True, 
        blank=True,
        help_text="GPS longitude coordinate"
    )
    altitude = models.FloatField(
        null=True, 
        blank=True,
        help_text="Altitude in meters"
    )
    
    # Location accuracy and metadata
    accuracy_meters = models.FloatField(
        null=True, 
        blank=True,
        help_text="Location accuracy radius in meters"
    )
    accuracy_level = models.CharField(
        max_length=10, 
        choices=LOCATION_ACCURACY_LEVELS,
        default='UNKNOWN'
    )
    location_source = models.CharField(
        max_length=15, 
        choices=LOCATION_SOURCES,
        default='GPS'
    )
    
    # Administrative location mapping
    detected_location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_scan_locations',
        help_text="System-detected location based on coordinates"
    )
    verified_location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_qr_scan_locations',
        help_text="User-verified actual location"
    )
    
    # Address information
    street_address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Building/floor/room details
    building_name = models.CharField(max_length=100, blank=True)
    floor_number = models.CharField(max_length=10, blank=True)
    room_number = models.CharField(max_length=20, blank=True)
    
    # Network context
    wifi_ssid = models.CharField(
        max_length=32, 
        blank=True,
        help_text="WiFi network SSID if available"
    )
    wifi_bssid = models.CharField(
        max_length=17, 
        blank=True,
        help_text="WiFi access point MAC address"
    )
    cellular_tower_id = models.CharField(max_length=50, blank=True)
    
    # Environmental context
    weather_conditions = models.CharField(max_length=50, blank=True)
    temperature_celsius = models.FloatField(null=True, blank=True)
    
    # Device context during scan
    device_orientation = models.CharField(
        max_length=20, 
        choices=[
            ('PORTRAIT', 'Portrait'),
            ('LANDSCAPE', 'Landscape'),
            ('UNKNOWN', 'Unknown'),
        ],
        default='UNKNOWN'
    )
    battery_level = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Device battery percentage"
    )
    signal_strength = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Cellular signal strength in dBm"
    )
    
    # Verification and validation
    location_verified = models.BooleanField(
        default=False,
        help_text="Whether the location has been manually verified"
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_scan_locations'
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Distance calculations
    distance_to_assigned_location = models.FloatField(
        null=True, 
        blank=True,
        help_text="Distance in meters to device's assigned location"
    )
    is_location_anomaly = models.BooleanField(
        default=False,
        help_text="Flag for location that seems incorrect"
    )
    anomaly_reason = models.TextField(blank=True)
    
    # Additional metadata
    scan_duration_seconds = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Time taken to complete the scan"
    )
    movement_detected = models.BooleanField(
        default=False,
        help_text="Whether device was moving during scan"
    )
    
    # Raw location data
    raw_location_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw location data from device sensors"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['scan']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['detected_location']),
            models.Index(fields=['location_verified']),
            models.Index(fields=['is_location_anomaly']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        location_str = "Unknown Location"
        if self.latitude and self.longitude:
            location_str = f"({self.latitude}, {self.longitude})"
        elif self.detected_location:
            location_str = str(self.detected_location)
        elif self.street_address:
            location_str = self.street_address
        
        return f"Scan Location: {location_str}"

    @property
    def coordinates(self):
        """Return coordinates as a tuple if available"""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None

    @property
    def has_gps_coordinates(self):
        """Check if GPS coordinates are available"""
        return self.latitude is not None and self.longitude is not None

    @property
    def location_display(self):
        """Return a human-readable location description"""
        parts = []
        
        if self.room_number:
            parts.append(f"Room {self.room_number}")
        if self.floor_number:
            parts.append(f"Floor {self.floor_number}")
        if self.building_name:
            parts.append(self.building_name)
        elif self.street_address:
            parts.append(self.street_address)
        
        if parts:
            return ", ".join(parts)
        elif self.detected_location:
            return str(self.detected_location)
        elif self.has_gps_coordinates:
            return f"GPS: {self.latitude}, {self.longitude}"
        
        return "Location not specified"

    def calculate_distance_to_location(self, target_location):
        """Calculate distance to a target location if GPS coordinates available"""
        if not self.has_gps_coordinates:
            return None
        
        # This would typically use a geospatial library like geopy
        # For now, return a placeholder
        # from geopy.distance import geodesic
        # return geodesic((self.latitude, self.longitude), target_coordinates).meters
        return None

    def detect_location_from_coordinates(self):
        """Attempt to detect system location based on GPS coordinates"""
        if not self.has_gps_coordinates:
            return None
        
        # This would query the Location model to find the closest match
        # based on GPS coordinates or predefined location boundaries
        from inventory.models import Location
        
        # Placeholder logic - would need actual geospatial queries
        # For a complete implementation, you'd use PostGIS or similar
        
        return None

    def validate_location(self):
        """Validate the scan location against expected parameters"""
        validation_issues = []
        
        # Check if coordinates are reasonable
        if self.has_gps_coordinates:
            if not (-90 <= float(self.latitude) <= 90):
                validation_issues.append("Invalid latitude value")
            if not (-180 <= float(self.longitude) <= 180):
                validation_issues.append("Invalid longitude value")
        
        # Check distance to assigned location if available
        if (self.scan.device and 
            self.scan.device.current_location and 
            self.distance_to_assigned_location and 
            self.distance_to_assigned_location > 1000):  # More than 1km away
            validation_issues.append("Location is far from assigned location")
            self.is_location_anomaly = True
            self.anomaly_reason = "Distance exceeds expected range"
        
        # Check for movement during scan
        if self.movement_detected and self.scan.scan_type == 'VERIFICATION':
            validation_issues.append("Device was moving during verification scan")
        
        return validation_issues

    def geocode_address(self):
        """Convert GPS coordinates to street address"""
        if not self.has_gps_coordinates:
            return False
        
        # This would use a geocoding service like Google Maps API
        # Placeholder implementation
        try:
            # geocoded = geocoding_service.reverse(self.latitude, self.longitude)
            # self.street_address = geocoded.address
            # self.city = geocoded.city
            # self.country = geocoded.country
            # self.postal_code = geocoded.postal_code
            # return True
            pass
        except Exception:
            pass
        
        return False

    def save(self, *args, **kwargs):
        """Override save to perform validation and geocoding"""
        # Validate location data
        validation_issues = self.validate_location()
        
        # Attempt to detect system location
        if not self.detected_location and self.has_gps_coordinates:
            self.detected_location = self.detect_location_from_coordinates()
        
        # Calculate distance to assigned location
        if (self.scan.device and 
            self.scan.device.current_location and 
            self.has_gps_coordinates):
            # This would calculate actual distance
            # self.distance_to_assigned_location = self.calculate_distance_to_location(
            #     self.scan.device.current_location
            # )
            pass
        
        super().save(*args, **kwargs)

    @classmethod
    def get_location_analytics(cls, date_range=None):
        """Get analytics about scan locations"""
        queryset = cls.objects.all()
        
        if date_range:
            start_date, end_date = date_range
            queryset = queryset.filter(
                created_at__date__range=[start_date, end_date]
            )
        
        analytics = {
            'total_scans_with_location': queryset.count(),
            'gps_enabled_scans': queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).count(),
            'verified_locations': queryset.filter(
                location_verified=True
            ).count(),
            'location_anomalies': queryset.filter(
                is_location_anomaly=True
            ).count(),
            'accuracy_distribution': queryset.values('accuracy_level').annotate(
                count=models.Count('accuracy_level')
            ),
            'source_distribution': queryset.values('location_source').annotate(
                count=models.Count('location_source')
            ),
        }
        
        return analytics

    @classmethod
    def find_nearby_scans(cls, latitude, longitude, radius_meters=100):
        """Find scans within a specified radius"""
        # This would use geospatial queries in a production system
        # For now, return a placeholder queryset
        return cls.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )