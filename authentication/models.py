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

# ================================
# SecurityQuestion Models
# ================================
    
class SecurityQuestion(models.Model):
    """Security questions for password recovery and additional authentication"""
    
    PREDEFINED_QUESTIONS = [
        ('mother_maiden', 'What is your mother\'s maiden name?'),
        ('first_pet', 'What was the name of your first pet?'),
        ('birth_city', 'What city were you born in?'),
        ('first_school', 'What was the name of your first school?'),
        ('favorite_teacher', 'What was the name of your favorite teacher?'),
        ('childhood_friend', 'What was the name of your childhood best friend?'),
        ('first_car', 'What was the make of your first car?'),
        ('street_grew_up', 'What street did you grow up on?'),
        ('custom', 'Custom Question'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='security_questions'
    )
    question_type = models.CharField(
        max_length=20, 
        choices=PREDEFINED_QUESTIONS
    )
    custom_question = models.CharField(
        max_length=200, 
        blank=True, 
        help_text="Used when question_type is 'custom'"
    )
    answer_hash = models.CharField(
        max_length=128, 
        help_text="Hashed security answer"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['user', '-created_at']
        unique_together = ['user', 'question_type']

    def __str__(self):
        return f"{self.user.username} - {self.get_question_display()}"

    def get_question_display(self):
        """Return the actual question text"""
        if self.question_type == 'custom':
            return self.custom_question
        return dict(self.PREDEFINED_QUESTIONS).get(self.question_type, self.question_type)

    def verify_answer(self, answer):
        """Verify the provided answer against stored hash"""
        import hashlib
        answer_hash = hashlib.sha256(answer.lower().strip().encode()).hexdigest()
        if answer_hash == self.answer_hash:
            self.last_used = timezone.now()
            self.usage_count += 1
            self.save(update_fields=['last_used', 'usage_count'])
            return True
        return False

    @staticmethod
    def hash_answer(answer):
        """Hash an answer for storage"""
        import hashlib
        return hashlib.sha256(answer.lower().strip().encode()).hexdigest()

# ================================
# UserPreference Models
# ================================

class UserPreference(models.Model):
    """User preferences and settings"""
    
    THEME_CHOICES = [
        ('light', 'Light Theme'),
        ('dark', 'Dark Theme'),
        ('auto', 'Auto (System)'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('bn', 'Bengali'),
    ]
    
    PREFERENCE_TYPES = [
        ('THEME', 'Theme Preference'),
        ('LANGUAGE', 'Language Setting'),
        ('NOTIFICATION', 'Notification Settings'),
        ('DASHBOARD', 'Dashboard Layout'),
        ('DISPLAY', 'Display Options'),
        ('SECURITY', 'Security Settings'),
        ('REPORTING', 'Report Preferences'),
        ('SYSTEM', 'System Settings'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='user_preferences'
    )
    preference_type = models.CharField(max_length=20, choices=PREFERENCE_TYPES)
    preference_key = models.CharField(max_length=50)
    preference_value = models.TextField()
    
    # Theme and display
    theme = models.CharField(
        max_length=10, 
        choices=THEME_CHOICES, 
        default='light'
    )
    language = models.CharField(
        max_length=5, 
        choices=LANGUAGE_CHOICES, 
        default='en'
    )
    
    # Notification settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    desktop_notifications = models.BooleanField(default=True)
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly Digest'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
            ('never', 'Never'),
        ],
        default='immediate'
    )
    
    # Dashboard preferences
    dashboard_layout = models.JSONField(
        default=dict, 
        help_text="Dashboard widget layout and preferences"
    )
    default_page_size = models.PositiveIntegerField(default=25)
    
    # Security preferences
    session_timeout = models.PositiveIntegerField(
        default=60, 
        help_text="Session timeout in minutes"
    )
    require_password_change = models.BooleanField(default=False)
    
    # Additional settings
    additional_settings = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Additional user-specific settings"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user', 'preference_type']
        unique_together = ['user', 'preference_type', 'preference_key']

    def __str__(self):
        return f"{self.user.username} - {self.get_preference_type_display()}"

    @classmethod
    def get_user_preference(cls, user, preference_type, preference_key, default=None):
        """Get a specific preference value for a user"""
        try:
            pref = cls.objects.get(
                user=user, 
                preference_type=preference_type,
                preference_key=preference_key
            )
            return pref.preference_value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_user_preference(cls, user, preference_type, preference_key, value):
        """Set a preference value for a user"""
        pref, created = cls.objects.get_or_create(
            user=user,
            preference_type=preference_type,
            preference_key=preference_key,
            defaults={'preference_value': str(value)}
        )
        if not created:
            pref.preference_value = str(value)
            pref.save()
        return pref

# ================================
# UserActivity Models
# ================================

class UserActivity(models.Model):
    """Track user activities for audit and analytics"""
    
    ACTIVITY_TYPES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('VIEW', 'View Record'),
        ('CREATE', 'Create Record'),
        ('UPDATE', 'Update Record'),
        ('DELETE', 'Delete Record'),
        ('EXPORT', 'Export Data'),
        ('IMPORT', 'Import Data'),
        ('PRINT', 'Print Document'),
        ('DOWNLOAD', 'Download File'),
        ('SEARCH', 'Search Operation'),
        ('REPORT', 'Generate Report'),
        ('ASSIGNMENT', 'Device Assignment'),
        ('QR_SCAN', 'QR Code Scan'),
        ('ADMIN', 'Admin Action'),
        ('API', 'API Access'),
        ('ERROR', 'Error/Exception'),
        ('SECURITY', 'Security Event'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='user_activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(help_text="Detailed description of the activity")
    
    # Context information
    object_type = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Type of object affected (e.g., 'Device', 'Assignment')"
    )
    object_id = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="ID of the affected object"
    )
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    
    # Success/failure tracking
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Additional data
    additional_data = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Additional activity-specific data"
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    duration_ms = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Activity duration in milliseconds"
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type', '-timestamp']),
            models.Index(fields=['is_successful', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} at {self.timestamp}"

    @property
    def success_icon(self):
        """Return appropriate icon for success status"""
        return "✅" if self.is_successful else "❌"

    @property
    def activity_summary(self):
        """Return a brief summary of the activity"""
        summary = f"{self.get_activity_type_display()}"
        if self.object_type and self.object_id:
            summary += f" on {self.object_type} ({self.object_id})"
        return summary

    @classmethod
    def log_activity(cls, user, activity_type, description, **kwargs):
        """Convenience method to log an activity"""
        return cls.objects.create(
            user=user,
            activity_type=activity_type,
            description=description,
            **kwargs
        )

# ================================
# ApiKey Models
# ================================

class ApiKey(models.Model):
    """API keys for external integrations and mobile apps"""
    
    KEY_TYPES = [
        ('MOBILE', 'Mobile Application'),
        ('INTEGRATION', 'System Integration'),
        ('WEBHOOK', 'Webhook Access'),
        ('REPORTING', 'Reporting API'),
        ('READ_ONLY', 'Read-Only Access'),
        ('FULL_ACCESS', 'Full Access'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='api_keys'
    )
    name = models.CharField(
        max_length=100, 
        help_text="Descriptive name for this API key"
    )
    key = models.CharField(
        max_length=128, 
        unique=True, 
        help_text="The actual API key"
    )
    key_type = models.CharField(
        max_length=20, 
        choices=KEY_TYPES, 
        default='READ_ONLY'
    )
    
    # Permissions and scopes
    permissions = models.JSONField(
        default=list, 
        help_text="List of specific permissions for this key"
    )
    allowed_ips = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of allowed IP addresses (empty = any IP)"
    )
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Rate limiting
    rate_limit_per_hour = models.PositiveIntegerField(
        default=1000, 
        help_text="Maximum API calls per hour"
    )
    current_hour_usage = models.PositiveIntegerField(default=0)
    rate_limit_reset = models.DateTimeField(null=True, blank=True)
    
    # Status and lifecycle
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Optional expiration date"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_api_keys'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['key']),
            models.Index(fields=['is_active', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_api_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_api_key():
        """Generate a secure API key"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))

    @property
    def key_preview(self):
        """Return a preview of the API key for display"""
        if self.key:
            return f"{self.key[:8]}...{self.key[-4:]}"
        return "Not generated"

    @property
    def is_expired(self):
        """Check if the API key has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def is_rate_limited(self):
        """Check if the API key has exceeded rate limits"""
        if not self.rate_limit_reset:
            return False
        
        # Reset counter if hour has passed
        if timezone.now() > self.rate_limit_reset:
            self.current_hour_usage = 0
            self.rate_limit_reset = timezone.now() + timedelta(hours=1)
            self.save(update_fields=['current_hour_usage', 'rate_limit_reset'])
            return False
        
        return self.current_hour_usage >= self.rate_limit_per_hour

    def record_usage(self, ip_address=None):
        """Record API key usage"""
        self.usage_count += 1
        self.current_hour_usage += 1
        self.last_used = timezone.now()
        if ip_address:
            self.last_used_ip = ip_address
        
        # Set rate limit reset if not set
        if not self.rate_limit_reset:
            self.rate_limit_reset = timezone.now() + timedelta(hours=1)
        
        self.save(update_fields=[
            'usage_count', 'current_hour_usage', 'last_used', 
            'last_used_ip', 'rate_limit_reset'
        ])

    def can_access_ip(self, ip_address):
        """Check if the given IP address is allowed"""
        if not self.allowed_ips:  # Empty list means any IP is allowed
            return True
        return ip_address in self.allowed_ips

    def has_permission(self, permission):
        """Check if the API key has a specific permission"""
        return permission in self.permissions

    def get_usage_stats(self):
        """Return usage statistics for this API key"""
        return {
            'total_usage': self.usage_count,
            'current_hour_usage': self.current_hour_usage,
            'rate_limit': self.rate_limit_per_hour,
            'rate_limit_remaining': max(0, self.rate_limit_per_hour - self.current_hour_usage),
            'last_used': self.last_used,
            'is_expired': self.is_expired,
            'is_rate_limited': self.is_rate_limited,
        }