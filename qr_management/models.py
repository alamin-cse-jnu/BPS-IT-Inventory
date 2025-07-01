# 9. QR CODE & VERIFICATION MODELS
# ================================
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from inventory.models import Device, Location, Staff
import uuid

class QRCodeScan(models.Model):
    """Track QR code scans and verifications"""
    
    SCAN_TYPES = [
        ('VERIFICATION', 'Verification'),
        ('INVENTORY', 'Inventory Check'),
        ('ASSIGNMENT', 'Assignment'),
        ('MAINTENANCE', 'Maintenance'),
        ('AUDIT', 'Audit'),
        ('BATCH_VERIFICATION', 'Batch Verification'),
        ('MOBILE_SCAN', 'Mobile Scan'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Scan details
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='qr_scans')
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPES, default='VERIFICATION')
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='qr_scans')
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Location information
    scan_location = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='qr_scans',
        help_text="Location where the scan occurred"
    )
    
    # Device state at scan time
    device_status_at_scan = models.CharField(max_length=20, help_text="Device status when scanned")
    device_location_at_scan = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_location_scans',
        help_text="Device's recorded location at scan time"
    )
    assigned_staff_at_scan = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_scans',
        help_text="Staff assigned to device at scan time"
    )
    
    # Verification results
    verification_success = models.BooleanField(default=True)
    discrepancies_found = models.TextField(
        blank=True,
        help_text="Details of any discrepancies found during verification"
    )
    
    # Additional scan data
    scan_notes = models.TextField(blank=True, help_text="Additional notes from the scan")
    gps_coordinates = models.CharField(
        max_length=100, 
        blank=True,
        help_text="GPS coordinates if available (lat,lng)"
    )
    
    # Technical details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    app_version = models.CharField(max_length=50, blank=True, help_text="Mobile app version if applicable")
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['scanned_by', 'timestamp']),
            models.Index(fields=['scan_type', 'timestamp']),
            models.Index(fields=['verification_success']),
        ]
        
    def __str__(self):
        return f"QR Scan: {self.device.device_id} by {self.scanned_by} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def has_discrepancies(self):
        return bool(self.discrepancies_found.strip())
    
    @property
    def scan_result_display(self):
        if not self.verification_success:
            return "Failed"
        elif self.has_discrepancies:
            return "Success (with notes)"
        else:
            return "Success"

class QRCodeTemplate(models.Model):
    """Templates for QR code generation and styling"""
    
    TEMPLATE_TYPES = [
        ('STANDARD', 'Standard'),
        ('WITH_LOGO', 'With Logo'),
        ('LABEL', 'Label Format'),
        ('ASSET_TAG', 'Asset Tag Format'),
        ('CUSTOM', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    description = models.TextField(blank=True)
    
    # QR Code settings
    qr_size = models.PositiveIntegerField(default=10, help_text="QR code box size")
    qr_border = models.PositiveIntegerField(default=4, help_text="QR code border size")
    error_correction = models.CharField(
        max_length=1,
        choices=[('L', 'Low'), ('M', 'Medium'), ('Q', 'Quartile'), ('H', 'High')],
        default='L'
    )
    
    # Styling
    foreground_color = models.CharField(max_length=7, default='#000000', help_text="Hex color code")
    background_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Hex color code")
    
    # Label settings (if applicable)
    include_device_name = models.BooleanField(default=True)
    include_asset_tag = models.BooleanField(default=True)
    include_category = models.BooleanField(default=False)
    include_brand_model = models.BooleanField(default=False)
    
    # Template configuration
    label_width = models.PositiveIntegerField(default=600, help_text="Label width in pixels")
    label_height = models.PositiveIntegerField(default=200, help_text="Label height in pixels")
    font_size_large = models.PositiveIntegerField(default=24)
    font_size_medium = models.PositiveIntegerField(default=18)
    font_size_small = models.PositiveIntegerField(default=14)
    
    # Management
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default template
        if self.is_default:
            QRCodeTemplate.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class QRCodeBatch(models.Model):
    """Track batch QR code generation jobs"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Batch job name")
    template = models.ForeignKey(QRCodeTemplate, on_delete=models.SET_NULL, null=True)
    
    # Job details
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='qr_batches')
    device_count = models.PositiveIntegerField(help_text="Number of devices in batch")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Progress tracking
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.PositiveIntegerField(default=0)
    
    # Results
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    output_file = models.FileField(upload_to='qr_batches/', null=True, blank=True)
    error_log = models.TextField(blank=True)
    
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