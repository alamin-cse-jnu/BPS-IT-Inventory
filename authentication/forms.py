

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import re


# ================================
# LOGIN AND AUTHENTICATION FORMS
# ================================

class CustomLoginForm(AuthenticationForm):
    """Custom login form with enhanced styling and validation"""
    
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Username or Employee ID',
            'autocomplete': 'username',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Password',
            'autocomplete': 'current-password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Remember me for 30 days"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remove default help text
        for field in self.fields.values():
            field.help_text = None
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip().lower()
        return username
    
    def confirm_login_allowed(self, user):
        """Additional validation for login"""
        super().confirm_login_allowed(user)
        
        # Check if user has staff profile
        if not hasattr(user, 'staff_profile'):
            raise ValidationError(
                "Your account is not properly configured. Please contact administrator.",
                code='no_staff_profile'
            )
        
        # Check if staff profile is active
        if hasattr(user, 'staff_profile') and not user.staff_profile.is_active:
            raise ValidationError(
                "Your account has been deactivated. Please contact administrator.",
                code='inactive_staff'
            )


# ================================
# USER PROFILE MANAGEMENT FORMS
# ================================

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address'
            })
        }
    
    # Additional profile fields
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make all fields required except phone
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        
        # Populate phone number from staff profile if available
        if self.instance and hasattr(self.instance, 'staff_profile'):
            self.fields['phone_number'].initial = self.instance.staff_profile.phone_number
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check for duplicate emails
            existing = User.objects.filter(email=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("This email address is already in use.")
        
        return email
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Basic phone number validation
            phone_pattern = re.compile(r'^[\+]?[1-9][\d]{0,15}$')
            if not phone_pattern.match(phone.replace('-', '').replace(' ', '')):
                raise ValidationError("Please enter a valid phone number.")
        
        return phone
    
    def save(self, commit=True):
        user = super().save(commit)
        
        # Update staff profile phone number if exists
        if commit and hasattr(user, 'staff_profile'):
            phone_number = self.cleaned_data.get('phone_number')
            if phone_number is not None:
                user.staff_profile.phone_number = phone_number
                user.staff_profile.save()
        
        return user


class StaffProfileDetailsForm(forms.Form):
    """Additional form for staff-specific profile details"""
    
    designation = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job Title/Designation'
        })
    )
    
    department = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        })
    )
    
    employee_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        })
    )
    
    joining_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'readonly': True
        })
    )
    
    office_location = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate fields from staff profile
        if hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            self.fields['designation'].initial = staff.designation
            self.fields['department'].initial = str(staff.department) if staff.department else ''
            self.fields['employee_id'].initial = staff.employee_id
            self.fields['joining_date'].initial = staff.joining_date
            self.fields['office_location'].initial = str(staff.office_location) if staff.office_location else ''


# ================================
# PASSWORD MANAGEMENT FORMS
# ================================

class CustomPasswordChangeForm(DjangoPasswordChangeForm):
    """Enhanced password change form"""
    
    old_password = forms.CharField(
        label="Current Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current Password',
            'autocomplete': 'current-password'
        })
    )
    
    new_password1 = forms.CharField(
        label="New Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New Password',
            'autocomplete': 'new-password'
        }),
        help_text="Password must be at least 8 characters long and contain letters and numbers."
    )
    
    new_password2 = forms.CharField(
        label="Confirm New Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm New Password',
            'autocomplete': 'new-password'
        })
    )
    
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        if password:
            # Custom password validation
            if len(password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            
            if password.isdigit():
                raise ValidationError("Password cannot be entirely numeric.")
            
            if not re.search(r'[A-Za-z]', password):
                raise ValidationError("Password must contain at least one letter.")
            
            if not re.search(r'[0-9]', password):
                raise ValidationError("Password must contain at least one number.")
        
        return password


class PasswordResetRequestForm(forms.Form):
    """Form for requesting password reset"""
    
    email_or_username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Email address or username',
            'autocomplete': 'email'
        }),
        label="Email or Username"
    )
    
    def clean_email_or_username(self):
        identifier = self.cleaned_data.get('email_or_username')
        if identifier:
            identifier = identifier.strip().lower()
            
            # Try to find user by email or username
            try:
                if '@' in identifier:
                    user = User.objects.get(email=identifier)
                else:
                    user = User.objects.get(username=identifier)
                
                if not user.is_active:
                    raise ValidationError("This account has been deactivated.")
                
                # Store the user for later use
                self.user = user
                
            except User.DoesNotExist:
                raise ValidationError("No account found with this email or username.")
        
        return identifier


# ================================
# USER PREFERENCES FORMS
# ================================

class UserPreferencesForm(forms.Form):
    """Form for managing user preferences and settings"""
    
    THEME_CHOICES = [
        ('light', 'Light Theme'),
        ('dark', 'Dark Theme'),
        ('auto', 'Auto (System Preference)')
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('bn', 'Bengali'),
    ]
    
    TIMEZONE_CHOICES = [
        ('Asia/Dhaka', 'Dhaka (GMT+6)'),
        ('UTC', 'UTC'),
    ]
    
    theme = forms.ChoiceField(
        choices=THEME_CHOICES,
        initial='light',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        initial='en',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        initial='Asia/Dhaka',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notifications_enabled = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enable email notifications"
    )
    
    assignment_notifications = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Assignment notifications"
    )
    
    maintenance_notifications = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Maintenance reminders"
    )
    
    warranty_notifications = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Warranty expiry alerts"
    )
    
    dashboard_refresh_interval = forms.IntegerField(
        initial=30,
        min_value=10,
        max_value=300,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '10'
        }),
        help_text="Dashboard auto-refresh interval in seconds"
    )


# ================================
# SESSION MANAGEMENT FORMS
# ================================

class SessionManagementForm(forms.Form):
    """Form for managing user sessions"""
    
    session_timeout = forms.IntegerField(
        initial=30,
        min_value=5,
        max_value=480,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Session timeout (minutes)",
        help_text="Session will expire after this period of inactivity"
    )
    
    max_concurrent_sessions = forms.IntegerField(
        initial=3,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Maximum concurrent sessions",
        help_text="Maximum number of active sessions allowed"
    )
    
    force_logout_other_sessions = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Logout other sessions when changing password"
    )


# ================================
# SECURITY SETTINGS FORMS
# ================================

class SecuritySettingsForm(forms.Form):
    """Form for security-related settings"""
    
    two_factor_enabled = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enable Two-Factor Authentication",
        help_text="Requires additional verification when logging in"
    )
    
    login_alerts_enabled = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Email alerts for new logins",
        help_text="Receive email when your account is accessed from a new device"
    )
    
    password_expiry_days = forms.IntegerField(
        initial=90,
        min_value=30,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Password expiry (days)",
        help_text="You will be prompted to change password after this period"
    )
    
    failed_login_lockout = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Lock account after failed login attempts"
    )
    
    max_failed_attempts = forms.IntegerField(
        initial=5,
        min_value=3,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Maximum failed login attempts"
    )


# ================================
# ACCOUNT DEACTIVATION FORM
# ================================

class AccountDeactivationForm(forms.Form):
    """Form for account deactivation request"""
    
    DEACTIVATION_REASONS = [
        ('leaving', 'Leaving Organization'),
        ('temporary', 'Temporary Leave'),
        ('role_change', 'Role Change'),
        ('security', 'Security Concerns'),
        ('other', 'Other')
    ]
    
    reason = forms.ChoiceField(
        choices=DEACTIVATION_REASONS,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Reason for deactivation"
    )
    
    effective_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Effective date"
    )
    
    return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Expected return date (for temporary leave)"
    )
    
    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional information...'
        }),
        label="Additional notes"
    )
    
    confirm_deactivation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I understand that this will deactivate my account"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get('reason')
        return_date = cleaned_data.get('return_date')
        effective_date = cleaned_data.get('effective_date')
        
        # Validate return date for temporary leave
        if reason == 'temporary' and not return_date:
            raise ValidationError("Return date is required for temporary leave.")
        
        # Validate date relationships
        if effective_date and return_date:
            if return_date <= effective_date:
                raise ValidationError("Return date must be after effective date.")
        
        return cleaned_data


# ================================
# ACTIVITY LOG FORMS
# ================================

class ActivityLogFilterForm(forms.Form):
    """Form for filtering user activity logs"""
    
    ACTION_CHOICES = [
        ('', 'All Actions'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import')
    ]
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search in activity descriptions...'
        })
    )
    
    ip_address = forms.CharField(
        max_length=45,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by IP address...'
        })
    )


# ================================
# DEVICE ACCESS REQUEST FORMS
# ================================

class DeviceAccessRequestForm(forms.Form):
    """Form for requesting access to devices"""
    
    REQUEST_TYPES = [
        ('assignment', 'Device Assignment'),
        ('temporary', 'Temporary Access'),
        ('maintenance', 'Maintenance Access'),
        ('inspection', 'Inspection Access')
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ]
    
    request_type = forms.ChoiceField(
        choices=REQUEST_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    device_category = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Laptop, Desktop, Tablet'
        }),
        label="Device type needed"
    )
    
    justification = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Explain why you need access to this device...'
        }),
        label="Business justification"
    )
    
    priority = forms.ChoiceField(
        choices=PRIORITY_LEVELS,
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    requested_start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Start date"
    )
    
    requested_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="End date (for temporary access)"
    )
    
    supervisor_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'supervisor@example.com'
        }),
        label="Supervisor email for approval"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        requested_start_date = cleaned_data.get('requested_start_date')
        requested_end_date = cleaned_data.get('requested_end_date')
        
        # Validate dates
        if requested_start_date and requested_start_date < timezone.now().date():
            raise ValidationError("Start date cannot be in the past.")
        
        # End date required for temporary access
        if request_type in ['temporary', 'maintenance', 'inspection'] and not requested_end_date:
            raise ValidationError("End date is required for temporary access requests.")
        
        # Validate date relationship
        if requested_start_date and requested_end_date:
            if requested_end_date <= requested_start_date:
                raise ValidationError("End date must be after start date.")
        
        return cleaned_data


# ================================
# PERMISSION REQUEST FORMS
# ================================

class PermissionRequestForm(forms.Form):
    """Form for requesting additional permissions"""
    
    PERMISSION_TYPES = [
        ('device_create', 'Create Devices'),
        ('device_edit', 'Edit Devices'),
        ('device_delete', 'Delete Devices'),
        ('assignment_create', 'Create Assignments'),
        ('assignment_edit', 'Edit Assignments'),
        ('staff_management', 'Staff Management'),
        ('report_access', 'Advanced Reports'),
        ('system_admin', 'System Administration')
    ]
    
    requested_permissions = forms.MultipleChoiceField(
        choices=PERMISSION_TYPES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Requested permissions"
    )
    
    business_justification = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Explain why you need these permissions...'
        }),
        label="Business justification"
    )
    
    supervisor_approval = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'supervisor@example.com'
        }),
        label="Supervisor email for approval"
    )
    
    temporary_access = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="This is a temporary access request"
    )
    
    access_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Access end date (for temporary requests)"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        temporary_access = cleaned_data.get('temporary_access')
        access_end_date = cleaned_data.get('access_end_date')
        
        if temporary_access and not access_end_date:
            raise ValidationError("End date is required for temporary access requests.")
        
        if access_end_date and access_end_date <= timezone.now().date():
            raise ValidationError("Access end date must be in the future.")
        
        return cleaned_data


# ================================
# FORM UTILITIES AND MIXINS
# ================================

class BaseAuthForm(forms.Form):
    """Base form with common authentication styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Apply consistent styling to all fields
        for field_name, field in self.fields.items():
            if not field.widget.attrs.get('class'):
                if isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs['class'] = 'form-check-input'
                else:
                    field.widget.attrs['class'] = 'form-control'


class TimestampMixin:
    """Mixin for forms that track creation/modification timestamps"""
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if not instance.pk:
            instance.created_at = timezone.now()
        instance.updated_at = timezone.now()
        
        if commit:
            instance.save()
        
        return instance


# ================================
# AJAX RESPONSE FORMS
# ================================

class QuickLoginForm(forms.Form):
    """Simplified login form for AJAX requests"""
    
    username = forms.CharField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            from django.contrib.auth import authenticate
            
            user = authenticate(username=username, password=password)
            if user is None:
                raise ValidationError("Invalid username or password.")
            
            if not user.is_active:
                raise ValidationError("Account is deactivated.")
            
            self.user = user
        
        return self.cleaned_data


class SessionExtensionForm(forms.Form):
    """Form for extending user session"""
    
    extend_minutes = forms.IntegerField(
        initial=30,
        min_value=5,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    reason = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason for extension (optional)'
        })
    )