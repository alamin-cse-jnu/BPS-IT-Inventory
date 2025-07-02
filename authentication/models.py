# authentication/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

# ================================
# USER ROLE & PERMISSION MODELS
# ================================

class UserRole(models.Model):
    """Extended user roles beyond Django's default groups"""
    ROLE_TYPES = [
        ('IT_ADMINISTRATOR', 'IT Administrator'),
        ('IT_OFFICER', 'IT Officer'),
        ('DEPARTMENT_HEAD', 'Department Head'),
        ('MANAGER', 'Manager'),
        ('GENERAL_STAFF', 'General Staff'),
        ('AUDITOR', 'Auditor'),
        ('VENDOR', 'Vendor/External'),
        ('READONLY', 'Read Only User'),
    ]

    name = models.CharField(max_length=50, choices=ROLE_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Permissions configuration
    permissions = models.JSONField(default=dict, help_text="Detailed permissions configuration")
    
    # Access control flags
    can_view_all_devices = models.BooleanField(default=False, help_text="Can view devices across all departments")
    can_manage_assignments = models.BooleanField(default=False, help_text="Can create/modify assignments")
    can_approve_requests = models.BooleanField(default=False, help_text="Can approve assignment requests")
    can_generate_reports = models.BooleanField(default=True, help_text="Can generate and view reports")
    can_manage_users = models.BooleanField(default=False, help_text="Can manage user accounts")
    can_system_admin = models.BooleanField(default=False, help_text="Can access system administration")
    can_manage_maintenance = models.BooleanField(default=False, help_text="Can manage maintenance schedules")
    can_manage_vendors = models.BooleanField(default=False, help_text="Can manage vendor information")
    can_bulk_operations = models.BooleanField(default=False, help_text="Can perform bulk operations")
    can_export_data = models.BooleanField(default=False, help_text="Can export system data")
    
    # Departmental restrictions
    restricted_to_own_department = models.BooleanField(default=True, help_text="Restrict access to own department only")
    can_view_financial_data = models.BooleanField(default=False, help_text="Can view purchase prices and costs")
    
    # QR and mobile access
    can_scan_qr_codes = models.BooleanField(default=True, help_text="Can scan QR codes for verification")
    can_generate_qr_codes = models.BooleanField(default=False, help_text="Can generate QR codes")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

    @property
    def permission_summary(self):
        """Return a summary of key permissions"""
        permissions = []
        if self.can_view_all_devices:
            permissions.append("All Devices")
        if self.can_manage_assignments:
            permissions.append("Assignments")
        if self.can_system_admin:
            permissions.append("System Admin")
        if self.can_manage_users:
            permissions.append("User Management")
        return ", ".join(permissions) if permissions else "Basic Access"

class UserRoleAssignment(models.Model):
    """Assign roles to users with additional context and temporal control"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(UserRole, on_delete=models.CASCADE, related_name='user_assignments')
    
    # Assignment scope - department restriction
    department = models.ForeignKey(
        'inventory.Department', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        help_text="Department scope for this role assignment"
    )
    
    # Temporal assignment control
    start_date = models.DateField(default=timezone.now, help_text="When this role assignment becomes active")
    end_date = models.DateField(null=True, blank=True, help_text="When this role assignment expires")
    
    # Assignment metadata
    is_active = models.BooleanField(default=True)
    is_primary_role = models.BooleanField(default=False, help_text="Primary role for the user")
    
    # Assignment tracking
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Additional notes about this role assignment")

    class Meta:
        unique_together = ['user', 'role', 'department']
        ordering = ['-is_primary_role', 'start_date']

    def __str__(self):
        scope = f" in {self.department.name}" if self.department else ""
        primary = " (Primary)" if self.is_primary_role else ""
        return f"{self.user.username} - {self.role.display_name}{scope}{primary}"

    @property
    def is_currently_active(self):
        """Check if role assignment is currently active"""
        now = timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")

# ================================
# USER SESSION & SECURITY MODELS
# ================================

class UserSession(models.Model):
    """Track user sessions for security monitoring"""
    SESSION_TYPES = [
        ('WEB', 'Web Browser'),
        ('MOBILE', 'Mobile App'),
        ('API', 'API Access'),
        ('ADMIN', 'Admin Interface'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_sessions')
    session_key = models.CharField(max_length=40, unique=True)
    session_type = models.CharField(max_length=10, choices=SESSION_TYPES, default='WEB')
    
    # Session tracking
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Security information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_info = models.JSONField(default=dict, blank=True, help_text="Device and browser information")
    
    # Location information (if available)
    location_data = models.JSONField(default=dict, blank=True, help_text="Geographic location data")
    
    # Security flags
    is_suspicious = models.BooleanField(default=False, help_text="Flagged for suspicious activity")
    failed_login_attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['last_activity']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.session_type} ({self.login_time.strftime('%Y-%m-%d %H:%M')})"

    @property
    def session_duration(self):
        """Calculate session duration"""
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time

    @property
    def is_expired(self):
        """Check if session is expired (inactive for more than 24 hours)"""
        if not self.is_active:
            return True
        inactive_time = timezone.now() - self.last_activity
        return inactive_time.total_seconds() > 86400  # 24 hours

class LoginAttempt(models.Model):
    """Track login attempts for security monitoring"""
    ATTEMPT_TYPES = [
        ('SUCCESS', 'Successful Login'),
        ('FAILED_PASSWORD', 'Failed - Wrong Password'),
        ('FAILED_USERNAME', 'Failed - Wrong Username'),
        ('FAILED_LOCKED', 'Failed - Account Locked'),
        ('FAILED_DISABLED', 'Failed - Account Disabled'),
        ('FAILED_SUSPICIOUS', 'Failed - Suspicious Activity'),
    ]

    username = models.CharField(max_length=150)
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Associated user (if login was successful or user exists)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='login_attempts')
    
    # Geographic and device information
    location_data = models.JSONField(default=dict, blank=True)
    device_fingerprint = models.CharField(max_length=64, blank=True)
    
    # Security flags
    is_suspicious = models.BooleanField(default=False)
    blocked_by_security = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['attempt_type']),
        ]

    def __str__(self):
        return f"{self.username} - {self.get_attempt_type_display()} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

# ================================
# USER PREFERENCES & PROFILE MODELS
# ================================

class UserProfile(models.Model):
    """Extended user profile information"""
    THEME_CHOICES = [
        ('LIGHT', 'Light Theme'),
        ('DARK', 'Dark Theme'),
        ('AUTO', 'Auto (System)'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('bn', 'Bengali'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    
    # UI Preferences
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='LIGHT')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, default='Asia/Dhaka')
    
    # Dashboard preferences
    dashboard_layout = models.JSONField(default=dict, blank=True, help_text="Dashboard widget layout preferences")
    default_items_per_page = models.PositiveIntegerField(
        default=25, 
        validators=[MinValueValidator(10), MaxValueValidator(100)],
        help_text="Default number of items to show per page"
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")
    sms_notifications = models.BooleanField(default=False, help_text="Receive SMS notifications")
    in_app_notifications = models.BooleanField(default=True, help_text="Show in-app notifications")
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('HOURLY', 'Hourly Digest'),
            ('DAILY', 'Daily Digest'),
            ('WEEKLY', 'Weekly Digest'),
        ],
        default='IMMEDIATE'
    )
    
    # Department and access context
    default_department = models.ForeignKey(
        'inventory.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Default department context for the user"
    )
    
    # Mobile app preferences
    mobile_push_notifications = models.BooleanField(default=True)
    mobile_device_tokens = models.JSONField(default=list, blank=True, help_text="Mobile device FCM tokens")
    
    # Security preferences
    require_2fa = models.BooleanField(default=False, help_text="Require two-factor authentication")
    session_timeout_minutes = models.PositiveIntegerField(
        default=480,  # 8 hours
        validators=[MinValueValidator(30), MaxValueValidator(1440)],
        help_text="Session timeout in minutes"
    )
    
    # Profile metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_password_change = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"Profile: {self.user.username}"

    def get_active_roles(self):
        """Get currently active roles for the user"""
        return UserRoleAssignment.objects.filter(
            user=self.user,
            is_active=True,
            start_date__lte=timezone.now().date()
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now().date())
        )

    def has_permission(self, permission_name):
        """Check if user has a specific permission through their roles"""
        active_roles = self.get_active_roles()
        for assignment in active_roles:
            if hasattr(assignment.role, permission_name):
                if getattr(assignment.role, permission_name, False):
                    return True
        return False

# ================================
# TWO-FACTOR AUTHENTICATION MODELS
# ================================

class TwoFactorAuth(models.Model):
    """Two-factor authentication settings for users"""
    METHOD_CHOICES = [
        ('TOTP', 'Time-based OTP (Authenticator App)'),
        ('SMS', 'SMS Code'),
        ('EMAIL', 'Email Code'),
        ('BACKUP', 'Backup Codes'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_auth')
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    
    # TOTP specific
    secret_key = models.CharField(max_length=32, blank=True, help_text="TOTP secret key")
    
    # SMS/Email specific
    phone_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    
    # Backup codes
    backup_codes = models.JSONField(default=list, blank=True, help_text="List of backup codes")
    
    # Settings
    is_enabled = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'method']

    def __str__(self):
        return f"{self.user.username} - {self.get_method_display()}"

class PasswordHistory(models.Model):
    """Track password history to prevent reuse"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"

# ================================
# API ACCESS & TOKENS
# ================================

class APIToken(models.Model):
    """API access tokens for users and applications"""
    TOKEN_TYPES = [
        ('USER', 'User Token'),
        ('APPLICATION', 'Application Token'),
        ('INTEGRATION', 'Integration Token'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    name = models.CharField(max_length=100, help_text="Descriptive name for this token")
    token_type = models.CharField(max_length=15, choices=TOKEN_TYPES, default='USER')
    
    # Token data
    token_key = models.CharField(max_length=64, unique=True)
    token_hash = models.CharField(max_length=128)
    
    # Permissions and restrictions
    allowed_ips = models.JSONField(default=list, blank=True, help_text="Allowed IP addresses")
    permissions = models.JSONField(default=dict, blank=True, help_text="API permissions")
    rate_limit = models.PositiveIntegerField(default=1000, help_text="Requests per hour")
    
    # Lifecycle
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False