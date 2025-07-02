
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
import json

from .models import (
    Device, Assignment, Staff, Department, Location, Vendor,
    DeviceCategory, DeviceType, DeviceSubCategory, MaintenanceSchedule
)


# ================================
# API VALIDATION FORMS
# ================================

class APIDeviceForm(forms.ModelForm):
    """Lightweight device form for API endpoints"""
    
    class Meta:
        model = Device
        fields = [
            'device_id', 'device_name', 'device_type', 'brand', 'model',
            'serial_number', 'status', 'condition', 'location', 'is_critical'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make all fields optional for PATCH requests
        for field in self.fields:
            self.fields[field].required = False
    
    def validate_device_id(self, value):
        """API-specific device ID validation"""
        if value:
            existing = Device.objects.filter(device_id=value)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("Device ID already exists")
        
        return value


class APIAssignmentForm(forms.ModelForm):
    """Lightweight assignment form for API endpoints"""
    
    class Meta:
        model = Assignment
        fields = [
            'device', 'assignment_type', 'assigned_to_staff',
            'assigned_to_department', 'start_date', 'expected_return_date',
            'purpose', 'notes'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default start date
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now().date()
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least one assignment target
        staff = cleaned_data.get('assigned_to_staff')
        department = cleaned_data.get('assigned_to_department')
        
        if not staff and not department:
            raise ValidationError("Must assign to either staff or department")
        
        return cleaned_data


# ================================
# MOBILE APP FORMS
# ================================

class MobileDeviceSearchForm(forms.Form):
    """Form for mobile device search"""
    
    query = forms.CharField(
        max_length=200,
        required=False,
        help_text="Search by device ID, name, or serial number"
    )
    
    qr_code = forms.CharField(
        max_length=100,
        required=False,
        help_text="Device QR code for direct lookup"
    )
    
    location_id = forms.IntegerField(
        required=False,
        help_text="Filter by location ID"
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All')] + Device.STATUS_CHOICES,
        required=False,
        help_text="Filter by device status"
    )
    
    limit = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=20,
        required=False,
        help_text="Maximum number of results"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        query = cleaned_data.get('query')
        qr_code = cleaned_data.get('qr_code')
        
        if not query and not qr_code and not cleaned_data.get('location_id'):
            raise ValidationError("At least one search parameter is required")
        
        return cleaned_data


class MobileAssignmentForm(forms.Form):
    """Simplified assignment form for mobile app"""
    
    device_id = forms.CharField(
        max_length=50,
        help_text="Device ID to assign"
    )
    
    assigned_to_staff_id = forms.IntegerField(
        required=False,
        help_text="Staff member ID"
    )
    
    assigned_to_department_id = forms.IntegerField(
        required=False,
        help_text="Department ID"
    )
    
    assignment_type = forms.ChoiceField(
        choices=Assignment.ASSIGNMENT_TYPES,
        help_text="Type of assignment"
    )
    
    expected_return_date = forms.DateField(
        required=False,
        help_text="Expected return date (YYYY-MM-DD)"
    )
    
    purpose = forms.CharField(
        max_length=500,
        required=False,
        help_text="Purpose of assignment"
    )
    
    notes = forms.CharField(
        max_length=1000,
        required=False,
        help_text="Additional notes"
    )
    
    def clean_device_id(self):
        device_id = self.cleaned_data.get('device_id')
        try:
            device = Device.objects.get(device_id=device_id)
            if device.status != 'AVAILABLE':
                raise ValidationError(f"Device {device_id} is not available for assignment")
            return device
        except Device.DoesNotExist:
            raise ValidationError(f"Device {device_id} not found")
    
    def clean(self):
        cleaned_data = super().clean()
        staff_id = cleaned_data.get('assigned_to_staff_id')
        department_id = cleaned_data.get('assigned_to_department_id')
        
        if not staff_id and not department_id:
            raise ValidationError("Must assign to either staff or department")
        
        # Validate staff exists
        if staff_id:
            try:
                Staff.objects.get(id=staff_id, is_active=True)
            except Staff.DoesNotExist:
                raise ValidationError("Invalid staff ID")
        
        # Validate department exists
        if department_id:
            try:
                Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                raise ValidationError("Invalid department ID")
        
        return cleaned_data


class MobileReturnForm(forms.Form):
    """Form for returning devices via mobile app"""
    
    assignment_id = forms.IntegerField(
        help_text="Assignment ID to return"
    )
    
    return_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        help_text="Device condition upon return"
    )
    
    return_notes = forms.CharField(
        max_length=1000,
        required=False,
        help_text="Return notes and observations"
    )
    
    gps_location = forms.CharField(
        max_length=100,
        required=False,
        help_text="GPS coordinates of return location"
    )
    
    def clean_assignment_id(self):
        assignment_id = self.cleaned_data.get('assignment_id')
        try:
            assignment = Assignment.objects.get(id=assignment_id, is_active=True)
            return assignment
        except Assignment.DoesNotExist:
            raise ValidationError("Invalid or inactive assignment ID")


# ================================
# QR CODE FORMS
# ================================

class QRCodeScanForm(forms.Form):
    """Form for QR code scanning via mobile app"""
    
    qr_data = forms.CharField(
        max_length=500,
        help_text="QR code data"
    )
    
    scan_location = forms.CharField(
        max_length=100,
        required=False,
        help_text="GPS coordinates where scan occurred"
    )
    
    scan_timestamp = forms.DateTimeField(
        required=False,
        help_text="Timestamp of scan (ISO format)"
    )
    
    def clean_qr_data(self):
        qr_data = self.cleaned_data.get('qr_data')
        
        # Try to parse as JSON for structured QR codes
        try:
            data = json.loads(qr_data)
            if 'device_id' in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Treat as simple device ID
        try:
            device = Device.objects.get(device_id=qr_data)
            return {'device_id': qr_data, 'device': device}
        except Device.DoesNotExist:
            raise ValidationError("Invalid QR code - device not found")
    
    def clean_scan_timestamp(self):
        timestamp = self.cleaned_data.get('scan_timestamp')
        if not timestamp:
            timestamp = timezone.now()
        
        return timestamp


class QRCodeGenerationForm(forms.Form):
    """Form for generating QR codes via API"""
    
    device_ids = forms.CharField(
        help_text="Comma-separated list of device IDs"
    )
    
    qr_format = forms.ChoiceField(
        choices=[
            ('simple', 'Simple Device ID'),
            ('json', 'JSON with metadata'),
            ('url', 'URL to device page')
        ],
        initial='simple',
        help_text="QR code format"
    )
    
    include_logo = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Include organization logo in QR code"
    )
    
    size = forms.ChoiceField(
        choices=[
            ('small', '128x128'),
            ('medium', '256x256'),
            ('large', '512x512')
        ],
        initial='medium',
        help_text="QR code size"
    )
    
    def clean_device_ids(self):
        device_ids = self.cleaned_data.get('device_ids')
        if device_ids:
            ids = [id.strip() for id in device_ids.split(',') if id.strip()]
            
            # Validate all device IDs exist
            existing_devices = Device.objects.filter(device_id__in=ids)
            existing_ids = list(existing_devices.values_list('device_id', flat=True))
            
            invalid_ids = set(ids) - set(existing_ids)
            if invalid_ids:
                raise ValidationError(f"Invalid device IDs: {', '.join(invalid_ids)}")
            
            return ids
        
        return []


# ================================
# MAINTENANCE FORMS
# ================================

class APIMaintenanceRequestForm(forms.Form):
    """Form for requesting maintenance via API"""
    
    device_id = forms.CharField(
        max_length=50,
        help_text="Device ID requiring maintenance"
    )
    
    maintenance_type = forms.ChoiceField(
        choices=MaintenanceSchedule.MAINTENANCE_TYPES,
        help_text="Type of maintenance required"
    )
    
    priority = forms.ChoiceField(
        choices=MaintenanceSchedule.PRIORITY_CHOICES,
        initial='MEDIUM',
        help_text="Priority level"
    )
    
    description = forms.CharField(
        max_length=1000,
        help_text="Description of maintenance required"
    )
    
    preferred_date = forms.DateField(
        required=False,
        help_text="Preferred maintenance date (YYYY-MM-DD)"
    )
    
    reporter_email = forms.EmailField(
        required=False,
        help_text="Email of person reporting the issue"
    )
    
    def clean_device_id(self):
        device_id = self.cleaned_data.get('device_id')
        try:
            return Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            raise ValidationError("Device not found")
    
    def clean_preferred_date(self):
        preferred_date = self.cleaned_data.get('preferred_date')
        if preferred_date and preferred_date < timezone.now().date():
            raise ValidationError("Preferred date cannot be in the past")
        
        return preferred_date


class MaintenanceStatusUpdateForm(forms.Form):
    """Form for updating maintenance status via API"""
    
    maintenance_id = forms.IntegerField(
        help_text="Maintenance schedule ID"
    )
    
    status = forms.ChoiceField(
        choices=MaintenanceSchedule.STATUS_CHOICES,
        help_text="New maintenance status"
    )
    
    completion_notes = forms.CharField(
        max_length=1000,
        required=False,
        help_text="Completion notes (required for completed status)"
    )
    
    actual_cost = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        help_text="Actual maintenance cost"
    )
    
    completed_by = forms.CharField(
        max_length=200,
        required=False,
        help_text="Name of person who completed maintenance"
    )
    
    def clean_maintenance_id(self):
        maintenance_id = self.cleaned_data.get('maintenance_id')
        try:
            return MaintenanceSchedule.objects.get(id=maintenance_id)
        except MaintenanceSchedule.DoesNotExist:
            raise ValidationError("Maintenance record not found")
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        completion_notes = cleaned_data.get('completion_notes')
        
        if status == 'COMPLETED' and not completion_notes:
            raise ValidationError("Completion notes are required when marking as completed")
        
        return cleaned_data


# ================================
# BULK OPERATION FORMS
# ================================

class APIBulkUpdateForm(forms.Form):
    """Form for bulk updates via API"""
    
    device_ids = forms.CharField(
        help_text="Comma-separated list of device IDs"
    )
    
    operation = forms.ChoiceField(
        choices=[
            ('update_status', 'Update Status'),
            ('update_location', 'Update Location'),
            ('update_condition', 'Update Condition'),
            ('bulk_assign', 'Bulk Assignment')
        ],
        help_text="Bulk operation to perform"
    )
    
    # Status update
    new_status = forms.ChoiceField(
        choices=Device.STATUS_CHOICES,
        required=False,
        help_text="New status for devices"
    )
    
    # Location update
    new_location_id = forms.IntegerField(
        required=False,
        help_text="New location ID for devices"
    )
    
    # Condition update
    new_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        required=False,
        help_text="New condition for devices"
    )
    
    # Bulk assignment
    assigned_to_staff_id = forms.IntegerField(
        required=False,
        help_text="Staff ID for bulk assignment"
    )
    
    assigned_to_department_id = forms.IntegerField(
        required=False,
        help_text="Department ID for bulk assignment"
    )
    
    update_reason = forms.CharField(
        max_length=500,
        required=False,
        help_text="Reason for bulk update"
    )
    
    def clean_device_ids(self):
        device_ids = self.cleaned_data.get('device_ids')
        if device_ids:
            ids = [id.strip() for id in device_ids.split(',') if id.strip()]
            
            # Validate all device IDs exist
            existing_devices = Device.objects.filter(device_id__in=ids)
            existing_ids = list(existing_devices.values_list('device_id', flat=True))
            
            invalid_ids = set(ids) - set(existing_ids)
            if invalid_ids:
                raise ValidationError(f"Invalid device IDs: {', '.join(invalid_ids)}")
            
            return existing_devices
        
        return Device.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        operation = cleaned_data.get('operation')
        
        # Validate required fields based on operation
        if operation == 'update_status' and not cleaned_data.get('new_status'):
            raise ValidationError("New status is required for status update operation")
        elif operation == 'update_location' and not cleaned_data.get('new_location_id'):
            raise ValidationError("New location ID is required for location update operation")
        elif operation == 'update_condition' and not cleaned_data.get('new_condition'):
            raise ValidationError("New condition is required for condition update operation")
        elif operation == 'bulk_assign':
            if not cleaned_data.get('assigned_to_staff_id') and not cleaned_data.get('assigned_to_department_id'):
                raise ValidationError("Either staff ID or department ID is required for bulk assignment")
        
        return cleaned_data


# ================================
# REPORTING FORMS
# ================================

class APIReportRequestForm(forms.Form):
    """Form for requesting reports via API"""
    
    report_type = forms.ChoiceField(
        choices=[
            ('device_summary', 'Device Summary'),
            ('assignment_report', 'Assignment Report'),
            ('maintenance_summary', 'Maintenance Summary'),
            ('utilization_report', 'Utilization Report')
        ],
        help_text="Type of report to generate"
    )
    
    format = forms.ChoiceField(
        choices=[
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('pdf', 'PDF'),
            ('excel', 'Excel')
        ],
        initial='json',
        help_text="Report output format"
    )
    
    date_from = forms.DateField(
        required=False,
        help_text="Start date for report (YYYY-MM-DD)"
    )
    
    date_to = forms.DateField(
        required=False,
        help_text="End date for report (YYYY-MM-DD)"
    )
    
    filters = forms.CharField(
        max_length=1000,
        required=False,
        help_text="JSON string with additional filters"
    )
    
    email_to = forms.EmailField(
        required=False,
        help_text="Email address to send report to"
    )
    
    def clean_filters(self):
        filters = self.cleaned_data.get('filters')
        if filters:
            try:
                return json.loads(filters)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for filters")
        
        return {}
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date must be before end date")
        
        return cleaned_data


# ================================
# USER MANAGEMENT FORMS
# ================================

class APIUserRegistrationForm(forms.Form):
    """Form for user registration via API"""
    
    username = forms.CharField(
        max_length=150,
        help_text="Unique username"
    )
    
    email = forms.EmailField(
        help_text="Email address"
    )
    
    first_name = forms.CharField(
        max_length=30,
        help_text="First name"
    )
    
    last_name = forms.CharField(
        max_length=30,
        help_text="Last name"
    )
    
    password = forms.CharField(
        min_length=8,
        help_text="Password (minimum 8 characters)"
    )
    
    employee_id = forms.CharField(
        max_length=20,
        help_text="Employee ID"
    )
    
    department_id = forms.IntegerField(
        required=False,
        help_text="Department ID"
    )
    
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        help_text="Phone number"
    )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists")
        
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already registered")
        
        return email
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Staff.objects.filter(employee_id=employee_id).exists():
            raise ValidationError("Employee ID already exists")
        
        return employee_id
    
    def clean_department_id(self):
        department_id = self.cleaned_data.get('department_id')
        if department_id:
            try:
                return Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                raise ValidationError("Invalid department ID")
        
        return None


# ================================
# AUTHENTICATION FORMS
# ================================

class APILoginForm(forms.Form):
    """Form for API authentication"""
    
    username = forms.CharField(
        max_length=150,
        help_text="Username or email"
    )
    
    password = forms.CharField(
        help_text="Password"
    )
    
    remember_me = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Keep session active for extended period"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            from django.contrib.auth import authenticate
            
            # Try username first, then email
            user = authenticate(username=username, password=password)
            if not user:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if not user:
                raise ValidationError("Invalid credentials")
            elif not user.is_active:
                raise ValidationError("Account is disabled")
            
            cleaned_data['user'] = user
        
        return cleaned_data


class APIPasswordResetForm(forms.Form):
    """Form for password reset via API"""
    
    email = forms.EmailField(
        help_text="Email address associated with account"
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            return User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise ValidationError("No active account found with this email")


# ================================
# VALIDATION UTILITIES
# ================================

class APIResponseForm(forms.Form):
    """Base form for standardized API responses"""
    
    def get_response_data(self):
        """Return standardized response data"""
        if self.is_valid():
            return {
                'success': True,
                'data': self.cleaned_data,
                'errors': None
            }
        else:
            return {
                'success': False,
                'data': None,
                'errors': self.errors
            }


class PaginationForm(forms.Form):
    """Form for API pagination parameters"""
    
    page = forms.IntegerField(
        min_value=1,
        initial=1,
        required=False,
        help_text="Page number"
    )
    
    page_size = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=20,
        required=False,
        help_text="Number of items per page"
    )
    
    ordering = forms.CharField(
        max_length=100,
        required=False,
        help_text="Field to order by (prefix with - for descending)"
    )


# ================================
# MOBILE APP SYNC FORMS
# ================================

class MobileSyncForm(forms.Form):
    """Form for mobile app data synchronization"""
    
    last_sync = forms.DateTimeField(
        required=False,
        help_text="Last sync timestamp (ISO format)"
    )
    
    sync_types = forms.MultipleChoiceField(
        choices=[
            ('devices', 'Devices'),
            ('assignments', 'Assignments'),
            ('staff', 'Staff'),
            ('locations', 'Locations')
        ],
        required=False,
        help_text="Types of data to sync"
    )
    
    device_version = forms.CharField(
        max_length=50,
        required=False,
        help_text="Mobile app version"
    )
    
    platform = forms.ChoiceField(
        choices=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web')
        ],
        required=False,
        help_text="Client platform"
    )
    
    def clean_last_sync(self):
        last_sync = self.cleaned_data.get('last_sync')
        if not last_sync:
            # Default to 30 days ago
            last_sync = timezone.now() - timezone.timedelta(days=30)
        
        return last_sync


# ================================
# END OF API FORMS MODULE
# ================================