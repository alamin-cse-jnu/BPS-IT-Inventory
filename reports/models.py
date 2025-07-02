# reports/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.files.storage import default_storage
import uuid
import json

# ================================
# REPORTING & ANALYTICS MODELS
# ================================

class ReportTemplate(models.Model):
    """Predefined report templates for consistent reporting"""
    
    REPORT_TYPES = [
        ('INVENTORY', 'Inventory Report'),
        ('ASSIGNMENT', 'Assignment Report'),
        ('MAINTENANCE', 'Maintenance Report'),
        ('AUDIT', 'Audit Report'),
        ('WARRANTY', 'Warranty Report'),
        ('UTILIZATION', 'Utilization Report'),
        ('COMPLIANCE', 'Compliance Report'),
        ('FINANCIAL', 'Financial Report'),
        ('ANALYTICS', 'Analytics Report'),
        ('CUSTOM', 'Custom Report'),
    ]

    REPORT_CATEGORIES = [
        ('OPERATIONAL', 'Operational Reports'),
        ('MANAGEMENT', 'Management Reports'),
        ('COMPLIANCE', 'Compliance & Audit Reports'),
        ('ANALYTICS', 'Analytics & Insights'),
        ('FINANCIAL', 'Financial Reports'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Report template name")
    description = models.TextField(blank=True, help_text="Detailed description of the report")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    category = models.CharField(max_length=20, choices=REPORT_CATEGORIES)
    
    # Template configuration
    template_config = models.JSONField(
        default=dict, 
        help_text="Template configuration including filters, columns, and formatting"
    )
    sql_query = models.TextField(
        blank=True, 
        help_text="Custom SQL query for advanced reports"
    )
    
    # Report structure
    columns = models.JSONField(
        default=list, 
        help_text="List of columns to include in the report"
    )
    filters = models.JSONField(
        default=dict, 
        help_text="Default filters for the report"
    )
    sorting = models.JSONField(
        default=dict, 
        help_text="Default sorting configuration"
    )
    
    # Access control
    accessible_by_roles = models.JSONField(
        default=list, 
        help_text="List of user roles that can access this report"
    )
    requires_approval = models.BooleanField(
        default=False, 
        help_text="Whether this report requires approval to generate"
    )
    
    # Template metadata
    is_active = models.BooleanField(default=True)
    is_system_template = models.BooleanField(
        default=False, 
        help_text="System-defined template (cannot be deleted)"
    )
    version = models.CharField(max_length=10, default='1.0')
    
    # Lifecycle tracking
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_report_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"

    def increment_usage(self):
        """Increment usage count and update last used timestamp"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=['usage_count', 'last_used'])

class ReportGeneration(models.Model):
    """Track report generation requests and their status"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    FORMAT_CHOICES = [
        ('PDF', 'PDF Document'),
        ('CSV', 'CSV File'),
        ('EXCEL', 'Excel Spreadsheet'),
        ('JSON', 'JSON Data'),
        ('HTML', 'HTML Report'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('NORMAL', 'Normal Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ReportTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generations'
    )
    generated_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='generated_reports'
    )
    
    # Generation parameters
    report_name = models.CharField(max_length=200, help_text="Custom name for this report instance")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='PDF')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Filters and parameters applied
    filters_applied = models.JSONField(
        default=dict, 
        help_text="Specific filters applied to this report generation"
    )
    parameters = models.JSONField(
        default=dict, 
        help_text="Additional parameters for report generation"
    )
    
    # Date range (common filter)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)
    
    # Generation tracking
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When the generated file expires")
    
    # Progress tracking
    progress_percentage = models.PositiveIntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True)
    
    # Results and output
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    record_count = models.PositiveIntegerField(null=True, blank=True, help_text="Number of records in report")
    error_message = models.TextField(blank=True)
    
    # Performance metrics
    generation_time_seconds = models.FloatField(null=True, blank=True)
    query_time_seconds = models.FloatField(null=True, blank=True)
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Sharing and access
    is_shared = models.BooleanField(default=False)
    shared_with_users = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='shared_reports',
        help_text="Users who have access to this report"
    )
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['generated_by', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['template', 'created_at']),
        ]
        
    def __str__(self):
        template_name = self.template.name if self.template else "Custom Report"
        return f"{template_name} - {self.get_status_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def is_completed(self):
        return self.status == 'COMPLETED'
    
    @property
    def is_in_progress(self):
        return self.status in ['PENDING', 'PROCESSING']
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def file_size_human(self):
        """Return human-readable file size"""
        if not self.file_size:
            return "Unknown"
        
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"

class ReportSchedule(models.Model):
    """Schedule for automatic report generation"""
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('CUSTOM', 'Custom Schedule'),
    ]

    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
        (7, 'Sunday'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Schedule name")
    template = models.ForeignKey(
        ReportTemplate, 
        on_delete=models.CASCADE, 
        related_name='schedules'
    )
    
    # Schedule configuration
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES)
    time_of_day = models.TimeField(help_text="Time to generate the report")
    day_of_week = models.PositiveIntegerField(
        choices=DAY_CHOICES, 
        null=True, 
        blank=True,
        help_text="Day of week for weekly reports"
    )
    day_of_month = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Day of month for monthly reports (1-31)"
    )
    
    # Custom schedule (cron-like)
    custom_schedule = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Custom cron expression for complex schedules"
    )
    
    # Report parameters
    default_format = models.CharField(max_length=10, choices=ReportGeneration.FORMAT_CHOICES, default='PDF')
    filters = models.JSONField(default=dict, help_text="Default filters for scheduled reports")
    
    # Recipients
    email_recipients = models.JSONField(
        default=list, 
        help_text="Email addresses to send the report to"
    )
    notify_users = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='scheduled_reports',
        help_text="Users to notify when report is generated"
    )
    
    # Schedule control
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(help_text="When to start generating reports")
    end_date = models.DateField(null=True, blank=True, help_text="When to stop generating reports")
    
    # Execution tracking
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    
    # Lifecycle
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_schedules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"

class ReportAccess(models.Model):
    """Track who accessed which reports"""
    
    ACCESS_TYPES = [
        ('VIEW', 'Viewed Online'),
        ('DOWNLOAD', 'Downloaded'),
        ('SHARE', 'Shared'),
        ('PRINT', 'Printed'),
        ('EMAIL', 'Emailed'),
    ]

    report_generation = models.ForeignKey(
        ReportGeneration, 
        on_delete=models.CASCADE, 
        related_name='access_logs'
    )
    accessed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_accesses')
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPES)
    accessed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-accessed_at']

    def __str__(self):
        return f"{self.accessed_by.username} {self.access_type} {self.report_generation}"

# ================================
# DASHBOARD & ANALYTICS MODELS
# ================================

class Dashboard(models.Model):
    """Custom dashboards for different user roles"""
    
    DASHBOARD_TYPES = [
        ('SYSTEM', 'System Dashboard'),
        ('DEPARTMENT', 'Department Dashboard'),
        ('USER', 'Personal Dashboard'),
        ('EXECUTIVE', 'Executive Dashboard'),
        ('OPERATIONAL', 'Operational Dashboard'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    dashboard_type = models.CharField(max_length=15, choices=DASHBOARD_TYPES)
    
    # Layout configuration
    layout_config = models.JSONField(
        default=dict, 
        help_text="Dashboard layout configuration including widgets and positioning"
    )
    
    # Access control
    is_public = models.BooleanField(default=False, help_text="Available to all users")
    accessible_by_roles = models.JSONField(default=list, help_text="Roles that can access this dashboard")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_dashboards')
    shared_with_users = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='shared_dashboards'
    )
    
    # Dashboard metadata
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default dashboard for the role")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['dashboard_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_dashboard_type_display()})"

class DashboardWidget(models.Model):
    """Individual widgets that can be placed on dashboards"""
    
    WIDGET_TYPES = [
        ('CHART', 'Chart Widget'),
        ('TABLE', 'Data Table'),
        ('METRIC', 'Key Metric'),
        ('GAUGE', 'Gauge/Progress'),
        ('LIST', 'Item List'),
        ('MAP', 'Location Map'),
        ('CALENDAR', 'Calendar View'),
        ('ALERT', 'Alert/Notification'),
        ('CUSTOM', 'Custom Widget'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    widget_type = models.CharField(max_length=15, choices=WIDGET_TYPES)
    
    # Widget configuration
    config = models.JSONField(
        default=dict, 
        help_text="Widget-specific configuration including data sources and display options"
    )
    data_source = models.CharField(max_length=200, help_text="Data source identifier")
    refresh_interval = models.PositiveIntegerField(
        default=300, 
        help_text="Auto-refresh interval in seconds"
    )
    
    # Widget metadata
    is_active = models.BooleanField(default=True)
    is_system_widget = models.BooleanField(default=False, help_text="System-defined widget")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_widgets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['widget_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_widget_type_display()})"

class AnalyticsMetric(models.Model):
    """Store calculated metrics for analytics and reporting"""
    
    METRIC_TYPES = [
        ('COUNT', 'Count Metric'),
        ('SUM', 'Sum Metric'),
        ('AVERAGE', 'Average Metric'),
        ('PERCENTAGE', 'Percentage Metric'),
        ('RATIO', 'Ratio Metric'),
        ('TREND', 'Trend Metric'),
    ]

    CALCULATION_PERIODS = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('REAL_TIME', 'Real Time'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=15, choices=METRIC_TYPES)
    
    # Metric definition
    calculation_query = models.TextField(help_text="SQL query or calculation logic")
    calculation_period = models.CharField(max_length=15, choices=CALCULATION_PERIODS)
    
    # Metric value and metadata
    current_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    previous_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    target_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Calculation tracking
    last_calculated = models.DateTimeField(null=True, blank=True)
    calculation_time_seconds = models.FloatField(null=True, blank=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_metric_type_display()})"

    @property
    def change_percentage(self):
        """Calculate percentage change from previous value"""
        if self.current_value and self.previous_value and self.previous_value != 0:
            return ((self.current_value - self.previous_value) / self.previous_value) * 100
        return None

    @property
    def target_achievement_percentage(self):
        """Calculate achievement percentage against target"""
        if self.current_value and self.target_value and self.target_value != 0:
            return (self.current_value / self.target_value) * 100
        return None

class DataExport(models.Model):
    """Track data export operations for audit and monitoring"""
    
    EXPORT_TYPES = [
        ('MANUAL', 'Manual Export'),
        ('SCHEDULED', 'Scheduled Export'),
        ('API', 'API Export'),
        ('BULK', 'Bulk Export'),
    ]

    EXPORT_FORMATS = [
        ('CSV', 'CSV File'),
        ('EXCEL', 'Excel Spreadsheet'),
        ('JSON', 'JSON Data'),
        ('XML', 'XML Data'),
        ('PDF', 'PDF Report'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    export_type = models.CharField(max_length=15, choices=EXPORT_TYPES)
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    
    # Export details
    data_source = models.CharField(max_length=200, help_text="Source of exported data")
    filters_applied = models.JSONField(default=dict, help_text="Filters applied during export")
    columns_included = models.JSONField(default=list, help_text="Columns included in export")
    
    # Results
    record_count = models.PositiveIntegerField(null=True, blank=True)
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)
    file_path = models.FileField(upload_to='exports/', null=True, blank=True)
    
    # Tracking
    exported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='data_exports')
    exported_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    
    # Security and compliance
    contains_sensitive_data = models.BooleanField(default=False)
    retention_days = models.PositiveIntegerField(default=30, help_text="Days to retain the export file")
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-exported_at']

    def __str__(self):
        return f"{self.data_source} export by {self.exported_by.username} ({self.exported_at.strftime('%Y-%m-%d')})"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False