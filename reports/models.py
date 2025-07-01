# 10. REPORTING & ANALYTICS MODELS
# ================================
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid

class ReportTemplate(models.Model):
    """Predefined report templates"""
    
    REPORT_TYPES = [
        ('INVENTORY', 'Inventory Report'),
        ('ASSIGNMENT', 'Assignment Report'),
        ('MAINTENANCE', 'Maintenance Report'),
        ('AUDIT', 'Audit Report'),
        ('WARRANTY', 'Warranty Report'),
        ('UTILIZATION', 'Utilization Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    template_config = models.JSONField(default=dict, help_text="Template configuration and filters")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_report_templates')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"

class ReportGeneration(models.Model):
    """Track report generation requests and status"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    FORMAT_CHOICES = [
        ('PDF', 'PDF'),
        ('CSV', 'CSV'),
        ('EXCEL', 'Excel'),
        ('JSON', 'JSON'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_reports')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='PDF')
    
    # Generation parameters
    filters_applied = models.JSONField(default=dict, help_text="Filters applied to the report")
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)
    
    # Generation tracking
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.PositiveIntegerField(default=0)
    
    # Results
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    record_count = models.PositiveIntegerField(null=True, blank=True, help_text="Number of records in report")
    error_message = models.TextField(blank=True)
    
    # Metadata
    generation_time_seconds = models.FloatField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        template_name = self.template.name if self.template else "Custom Report"
        return f"{template_name} - {self.get_status_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def is_completed(self):
        return self.status == 'COMPLETED'
    
    @property
    def is_failed(self):
        return self.status == 'FAILED'
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

class ReportSchedule(models.Model):
    """Scheduled automatic report generation"""
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Schedule configuration
    scheduled_time = models.TimeField(help_text="Time of day to run the report")
    day_of_week = models.PositiveIntegerField(null=True, blank=True, help_text="Day of week (0=Monday, 6=Sunday) for weekly reports")
    day_of_month = models.PositiveIntegerField(null=True, blank=True, help_text="Day of month for monthly reports")
    
    # Recipients
    email_recipients = models.JSONField(default=list, help_text="List of email addresses to send reports")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"