from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
import json
import re

from .models import (
    Device, Assignment, Staff, Department, Location, Vendor,
    DeviceCategory, DeviceType, DeviceSubCategory, MaintenanceSchedule,
    Building, Block, Floor, Room
)


# ================================
# API VALIDATION FORMS
# ================================

class APIDeviceForm(forms.ModelForm):
    """Enhanced device form for API endpoints with Block hierarchy support"""
    
    # Additional fields for location hierarchy lookup
    building_code = forms.CharField(
        max_length=50,
        required=False,
        help_text="Building code for location lookup"
    )
    
    block_code = forms.CharField(
        max_length=50,
        required=False,
        help_text="Block code for location lookup"
    )
    
    floor_number = forms.IntegerField(
        required=False,
        help_text="Floor number for location lookup"
    )
    
    department_code = forms.CharField(
        max_length=50,
        required=False,
        help_text="Department code for location lookup"
    )
    
    room_number = forms.CharField(
        max_length=30,
        required=False,
        help_text="Room number for location lookup"
    )
    
    class Meta:
        model = Device
        fields = [
            'device_id', 'device_name', 'device_type', 'brand', 'model',
            'serial_number', 'asset_tag',
            'processor', 'memory_ram', 'storage_capacity', 'operating_system',
            'purchase_date', 'purchase_price', 'vendor', 'warranty_start_date', 
            'warranty_end_date', 'status',
            'device_condition', 'location', 'notes', 'is_critical'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make all fields optional for PATCH requests
        for field in self.fields:
            self.fields[field].required = False
        
        # Filter querysets for API efficiency
        self.fields['device_type'].queryset = DeviceType.objects.filter(is_active=True)
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        self.fields['location'].queryset = Location.objects.filter(is_active=True).select_related(
            'building', 'block', 'floor', 'department', 'room'
        )
    
    def clean_device_id(self):
        """API-specific device ID validation"""
        device_id = self.cleaned_data.get('device_id')
        if device_id:
            existing = Device.objects.filter(device_id=device_id)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("Device ID already exists")
        
        return device_id
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Handle location lookup through hierarchy codes
        building_code = cleaned_data.get('building_code')
        block_code = cleaned_data.get('block_code')
        floor_number = cleaned_data.get('floor_number')
        department_code = cleaned_data.get('department_code')
        room_number = cleaned_data.get('room_number')
        location = cleaned_data.get('location')
        
        # If hierarchy codes provided, lookup location
        if any([building_code, block_code, floor_number, department_code, room_number]) and not location:
            try:
                location_query = Location.objects.filter(is_active=True)
                
                if building_code:
                    location_query = location_query.filter(building__code=building_code)
                if block_code:
                    location_query = location_query.filter(block__code=block_code)
                if floor_number is not None:
                    location_query = location_query.filter(floor__floor_number=floor_number)
                if department_code:
                    location_query = location_query.filter(department__code=department_code)
                if room_number:
                    location_query = location_query.filter(room__room_number=room_number)
                
                location = location_query.first()
                if location:
                    cleaned_data['location'] = location
                else:
                    raise ValidationError("Location not found with provided hierarchy codes.")
            except Exception:
                raise ValidationError("Invalid location hierarchy codes.")
        
        # Auto-generate device_id if not provided
        if not cleaned_data.get('device_id'):
            device_type = cleaned_data.get('device_type')
            location = cleaned_data.get('location')
            
            if device_type:
                building_code = location.building.code if location and location.building else 'BPS'
                block_code = location.block.code if location and location.block else 'MAIN'
                count = Device.objects.filter(device_type=device_type).count() + 1
                cleaned_data['device_id'] = f"{building_code}-{block_code}-{device_type.code}-{count:03d}"
        
        # Validate dates
        purchase_date = cleaned_data.get('purchase_date')
        warranty_start = cleaned_data.get('warranty_start_date')
        warranty_end = cleaned_data.get('warranty_end_date')
        
        if warranty_start and warranty_end and warranty_start >= warranty_end:
            raise ValidationError('Warranty end date must be after warranty start date.')
        
        if purchase_date and warranty_start and warranty_start < purchase_date:
            raise ValidationError('Warranty start date cannot be before purchase date.')
        
        return cleaned_data


class APIAssignmentForm(forms.ModelForm):
    """Enhanced assignment form for API endpoints with Block hierarchy support"""
    
    # Additional fields for device lookup
    device_id = forms.CharField(
        max_length=100,
        required=False,
        help_text="Device ID for lookup (alternative to device field)"
    )
    
    # Additional fields for staff lookup
    staff_employee_id = forms.CharField(
        max_length=50,
        required=False,
        help_text="Staff employee ID for lookup"
    )
    
    # Location hierarchy fields
    location_hierarchy = forms.CharField(
        max_length=500,
        required=False,
        help_text="JSON string with location hierarchy: {building_code, block_code, floor_number, department_code, room_number}"
    )
    
    class Meta:
        model = Assignment
        fields = [
            'device', 'assignment_type', 'assigned_to_staff',
            'assigned_to_department', 'assigned_to_location', 'start_date', 
            'expected_return_date', 'purpose', 'notes'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default start date
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now().date()
        
        # Filter querysets
        self.fields['device'].queryset = Device.objects.filter(status='AVAILABLE')
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(is_active=True)
        self.fields['assigned_to_department'].queryset = Department.objects.filter(is_active=True)
        self.fields['assigned_to_location'].queryset = Location.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Handle device lookup by device_id
        device_id = cleaned_data.get('device_id')
        device = cleaned_data.get('device')
        
        if device_id and not device:
            try:
                device = Device.objects.get(device_id=device_id, status='AVAILABLE')
                cleaned_data['device'] = device
            except Device.DoesNotExist:
                raise ValidationError(f"Available device with ID '{device_id}' not found.")
        
        # Handle staff lookup by employee_id
        staff_employee_id = cleaned_data.get('staff_employee_id')
        staff = cleaned_data.get('assigned_to_staff')
        
        if staff_employee_id and not staff:
            try:
                staff = Staff.objects.get(employee_id=staff_employee_id, is_active=True)
                cleaned_data['assigned_to_staff'] = staff
            except Staff.DoesNotExist:
                raise ValidationError(f"Active staff with employee ID '{staff_employee_id}' not found.")
        
        # Handle location hierarchy lookup
        location_hierarchy = cleaned_data.get('location_hierarchy')
        location = cleaned_data.get('assigned_to_location')
        
        if location_hierarchy and not location:
            try:
                hierarchy_data = json.loads(location_hierarchy)
                location_query = Location.objects.filter(is_active=True)
                
                if hierarchy_data.get('building_code'):
                    location_query = location_query.filter(building__code=hierarchy_data['building_code'])
                if hierarchy_data.get('block_code'):
                    location_query = location_query.filter(block__code=hierarchy_data['block_code'])
                if hierarchy_data.get('floor_number') is not None:
                    location_query = location_query.filter(floor__floor_number=hierarchy_data['floor_number'])
                if hierarchy_data.get('department_code'):
                    location_query = location_query.filter(department__code=hierarchy_data['department_code'])
                if hierarchy_data.get('room_number'):
                    location_query = location_query.filter(room__room_number=hierarchy_data['room_number'])
                
                location = location_query.first()
                if location:
                    cleaned_data['assigned_to_location'] = location
                else:
                    raise ValidationError("Location not found with provided hierarchy.")
            except (json.JSONDecodeError, ValueError):
                raise ValidationError("Invalid location hierarchy JSON format.")
        
        # Ensure at least one assignment target
        staff = cleaned_data.get('assigned_to_staff')
        department = cleaned_data.get('assigned_to_department')
        location = cleaned_data.get('assigned_to_location')
        
        if not any([staff, department, location]):
            raise ValidationError("Assignment must have at least one target (staff, department, or location).")
        
        # Validate dates
        start_date = cleaned_data.get('start_date', timezone.now().date())
        expected_return_date = cleaned_data.get('expected_return_date')
        
        if expected_return_date and expected_return_date <= start_date:
            raise ValidationError('Expected return date must be after start date.')
        
        return cleaned_data


# ================================
# USER MANAGEMENT FORMS
# ================================

class APIUserRegistrationForm(forms.Form):
    """Form for user registration via API with enhanced validation"""
    
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
    
    designation = forms.CharField(
        max_length=100,
        required=False,
        help_text="Job designation"
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
                return Department.objects.get(id=department_id, is_active=True)
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
# HIERARCHY LOOKUP FORMS
# ================================

class APIHierarchyLookupForm(forms.Form):
    """Form for hierarchy navigation and lookup via API"""
    
    lookup_type = forms.ChoiceField(
        choices=[
            ('buildings', 'List Buildings'),
            ('blocks_by_building', 'Blocks by Building'),
            ('floors_by_block', 'Floors by Block'),
            ('departments_by_floor', 'Departments by Floor'),
            ('rooms_by_department', 'Rooms by Department'),
            ('locations_by_hierarchy', 'Locations by Hierarchy')
        ],
        help_text="Type of hierarchy lookup"
    )
    
    building_id = forms.IntegerField(
        required=False,
        help_text="Building ID for filtering"
    )
    
    block_id = forms.IntegerField(
        required=False,
        help_text="Block ID for filtering"
    )
    
    floor_id = forms.IntegerField(
        required=False,
        help_text="Floor ID for filtering"
    )
    
    department_id = forms.IntegerField(
        required=False,
        help_text="Department ID for filtering"
    )
    
    include_inactive = forms.BooleanField(
        required=False,
        help_text="Include inactive records"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        lookup_type = cleaned_data.get('lookup_type')
        
        # Validate required parameters based on lookup type
        if lookup_type == 'blocks_by_building' and not cleaned_data.get('building_id'):
            raise ValidationError('Building ID is required for blocks lookup.')
        
        if lookup_type == 'floors_by_block' and not cleaned_data.get('block_id'):
            raise ValidationError('Block ID is required for floors lookup.')
        
        if lookup_type == 'departments_by_floor' and not cleaned_data.get('floor_id'):
            raise ValidationError('Floor ID is required for departments lookup.')
        
        if lookup_type == 'rooms_by_department' and not cleaned_data.get('department_id'):
            raise ValidationError('Department ID is required for rooms lookup.')
        
        return cleaned_data


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
                'errors': None,
                'timestamp': timezone.now().isoformat()
            }
        else:
            return {
                'success': False,
                'data': None,
                'errors': self.errors,
                'timestamp': timezone.now().isoformat()
            }


class PaginationForm(forms.Form):
    """Enhanced form for API pagination parameters"""
    
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
        help_text="Number of items per page (max 100)"
    )
    
    ordering = forms.CharField(
        max_length=100,
        required=False,
        help_text="Field to order by (prefix with - for descending)"
    )
    
    search = forms.CharField(
        max_length=200,
        required=False,
        help_text="Global search query"
    )
    
    def clean_ordering(self):
        ordering = self.cleaned_data.get('ordering')
        if ordering:
            # Validate ordering field name
            allowed_fields = [
                'created_at', 'updated_at', 'device_id', 'device_name', 
                'status', 'condition', 'employee_id', 'designation',
                'building__name', 'block__name', 'department__name'
            ]
            
            field = ordering.lstrip('-')
            if field not in allowed_fields:
                raise ValidationError(f"Invalid ordering field: {field}")
        
        return ordering


# ================================
# MOBILE APP FORMS
# ================================

class MobileDeviceSearchForm(forms.Form):
    """Enhanced form for mobile device search with Block hierarchy"""
    
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
    
    building_id = forms.IntegerField(
        required=False,
        help_text="Filter by building ID"
    )
    
    block_id = forms.IntegerField(
        required=False,
        help_text="Filter by block ID"
    )
    
    department_id = forms.IntegerField(
        required=False,
        help_text="Filter by department ID"
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
        location_id = cleaned_data.get('location_id')
        building_id = cleaned_data.get('building_id')
        block_id = cleaned_data.get('block_id')
        department_id = cleaned_data.get('department_id')
        
        if not any([query, qr_code, location_id, building_id, block_id, department_id]):
            raise ValidationError("At least one search parameter is required")
        
        return cleaned_data


class MobileAssignmentForm(forms.Form):
    """Simplified assignment form for mobile app with Block hierarchy"""
    
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
    
    assigned_to_location_id = forms.IntegerField(
        required=False,
        help_text="Location ID"
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
        location_id = cleaned_data.get('assigned_to_location_id')
        
        if not any([staff_id, department_id, location_id]):
            raise ValidationError("Must assign to either staff, department, or location")
        
        # Validate staff exists
        if staff_id:
            try:
                Staff.objects.get(id=staff_id, is_active=True)
            except Staff.DoesNotExist:
                raise ValidationError("Invalid staff ID")
        
        # Validate department exists
        if department_id:
            try:
                Department.objects.get(id=department_id, is_active=True)
            except Department.DoesNotExist:
                raise ValidationError("Invalid department ID")
        
        # Validate location exists
        if location_id:
            try:
                Location.objects.get(id=location_id, is_active=True)
            except Location.DoesNotExist:
                raise ValidationError("Invalid location ID")
        
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
            assignment = Assignment.objects.get(id=assignment_id, status='ASSIGNED')
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
    """Enhanced form for bulk updates via API with Block hierarchy support"""
    
    device_ids = forms.CharField(
        help_text="Comma-separated list of device IDs"
    )
    
    operation = forms.ChoiceField(
        choices=[
            ('update_status', 'Update Status'),
            ('update_location', 'Update Location'),
            ('update_condition', 'Update Condition'),
            ('bulk_assign', 'Bulk Assignment'),
            ('generate_qr', 'Generate QR Codes'),
            ('update_vendor', 'Update Vendor')
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
    
    location_hierarchy = forms.CharField(
        max_length=500,
        required=False,
        help_text="JSON string with location hierarchy for lookup"
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
    
    assigned_to_location_id = forms.IntegerField(
        required=False,
        help_text="Location ID for bulk assignment"
    )
    
    assignment_type = forms.ChoiceField(
        choices=Assignment.ASSIGNMENT_TYPES,
        required=False,
        help_text="Assignment type for bulk assignment"
    )
    
    # Vendor update
    new_vendor_id = forms.IntegerField(
        required=False,
        help_text="New vendor ID for devices"
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
        elif operation == 'update_location':
            if not cleaned_data.get('new_location_id') and not cleaned_data.get('location_hierarchy'):
                raise ValidationError("New location ID or hierarchy is required for location update operation")
        elif operation == 'update_condition' and not cleaned_data.get('new_condition'):
            raise ValidationError("New condition is required for condition update operation")
        elif operation == 'update_vendor' and not cleaned_data.get('new_vendor_id'):
            raise ValidationError("New vendor ID is required for vendor update operation")
        elif operation == 'bulk_assign':
            if not any([
                cleaned_data.get('assigned_to_staff_id'), 
                cleaned_data.get('assigned_to_department_id'),
                cleaned_data.get('assigned_to_location_id')
            ]):
                raise ValidationError("Staff, department, or location ID is required for bulk assignment operation")
        
        # Handle location hierarchy lookup for bulk update
        location_hierarchy = cleaned_data.get('location_hierarchy')
        if location_hierarchy:
            try:
                hierarchy_data = json.loads(location_hierarchy)
                location_query = Location.objects.filter(is_active=True)
                
                if hierarchy_data.get('building_code'):
                    location_query = location_query.filter(building__code=hierarchy_data['building_code'])
                if hierarchy_data.get('block_code'):
                    location_query = location_query.filter(block__code=hierarchy_data['block_code'])
                if hierarchy_data.get('floor_number') is not None:
                    location_query = location_query.filter(floor__floor_number=hierarchy_data['floor_number'])
                if hierarchy_data.get('department_code'):
                    location_query = location_query.filter(department__code=hierarchy_data['department_code'])
                if hierarchy_data.get('room_number'):
                    location_query = location_query.filter(room__room_number=hierarchy_data['room_number'])
                
                location = location_query.first()
                if location:
                    cleaned_data['new_location_id'] = location.id
                else:
                    raise ValidationError("Location not found with provided hierarchy.")
            except (json.JSONDecodeError, ValueError):
                raise ValidationError("Invalid location hierarchy JSON format.")
        
        return cleaned_data


# ================================
# REPORTING FORMS
# ================================

class APIReportRequestForm(forms.Form):
    """Enhanced form for requesting reports via API"""
    
    report_type = forms.ChoiceField(
        choices=[
            ('device_summary', 'Device Summary'),
            ('assignment_report', 'Assignment Report'),
            ('maintenance_summary', 'Maintenance Summary'),
            ('utilization_report', 'Utilization Report'),
            ('location_hierarchy_report', 'Location Hierarchy Report'),
            ('block_utilization', 'Block Utilization Report')
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
    
    # Hierarchy filters
    building_id = forms.IntegerField(
        required=False,
        help_text="Filter by building ID"
    )
    
    block_id = forms.IntegerField(
        required=False,
        help_text="Filter by block ID"
    )
    
    department_id = forms.IntegerField(
        required=False,
        help_text="Filter by department ID"
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
# IMPORT/EXPORT FORMS
# ================================

class APIDataImportForm(forms.Form):
    """Form for data import via API"""
    
    import_type = forms.ChoiceField(
        choices=[
            ('devices', 'Devices'),
            ('locations', 'Locations'),
            ('staff', 'Staff'),
            ('assignments', 'Assignments'),
            ('buildings', 'Buildings'),
            ('blocks', 'Blocks'),
            ('departments', 'Departments')
        ],
        help_text="Type of data to import"
    )
    
    file_format = forms.ChoiceField(
        choices=[
            ('csv', 'CSV'),
            ('xlsx', 'Excel'),
            ('json', 'JSON')
        ],
        help_text="Format of import file"
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Update existing records if found"
    )
    
    validate_only = forms.BooleanField(
        required=False,
        help_text="Only validate data without importing"
    )
    
    mapping = forms.CharField(
        max_length=2000,
        required=False,
        help_text="JSON string with field mapping configuration"
    )
    
    batch_size = forms.IntegerField(
        min_value=1,
        max_value=1000,
        initial=100,
        help_text="Number of records to process in each batch"
    )
    
    def clean_mapping(self):
        mapping = self.cleaned_data.get('mapping')
        if mapping:
            try:
                return json.loads(mapping)
            except json.JSONDecodeError:
                raise ValidationError('Invalid mapping JSON format.')
        return {}


class APIDataExportForm(forms.Form):
    """Form for data export via API"""
    
    export_type = forms.ChoiceField(
        choices=[
            ('devices', 'Devices'),
            ('locations', 'Locations'),
            ('staff', 'Staff'),
            ('assignments', 'Assignments'),
            ('maintenance', 'Maintenance Records'),
            ('audit_logs', 'Audit Logs')
        ],
        help_text="Type of data to export"
    )
    
    format = forms.ChoiceField(
        choices=[
            ('csv', 'CSV'),
            ('xlsx', 'Excel'),
            ('json', 'JSON'),
            ('xml', 'XML')
        ],
        initial='xlsx',
        help_text="Export format"
    )
    
    filters = forms.CharField(
        max_length=1000,
        required=False,
        help_text="JSON string with export filters"
    )
    
    fields = forms.CharField(
        max_length=500,
        required=False,
        help_text="Comma-separated list of fields to include"
    )
    
    include_relations = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Include related model data"
    )
    
    date_from = forms.DateField(
        required=False,
        help_text="Export records from this date"
    )
    
    date_to = forms.DateField(
        required=False,
        help_text="Export records until this date"
    )
    
    compress_output = forms.BooleanField(
        required=False,
        help_text="Compress output file (ZIP)"
    )
    
    def clean_filters(self):
        filters = self.cleaned_data.get('filters')
        if filters:
            try:
                return json.loads(filters)
            except json.JSONDecodeError:
                raise ValidationError('Invalid filters JSON format.')
        return {}
    
    def clean_fields(self):
        fields = self.cleaned_data.get('fields')
        if fields:
            return [field.strip() for field in fields.split(',') if field.strip()]
        return []


# ================================
# AUDIT AND MONITORING FORMS
# ================================

class APIAuditForm(forms.Form):
    """Form for audit operations via API"""
    
    audit_type = forms.ChoiceField(
        choices=[
            ('device_audit', 'Device Audit'),
            ('location_audit', 'Location Audit'),
            ('assignment_audit', 'Assignment Audit'),
            ('maintenance_audit', 'Maintenance Audit'),
            ('hierarchy_audit', 'Hierarchy Audit')
        ],
        help_text="Type of audit to perform"
    )
    
    scope = forms.ChoiceField(
        choices=[
            ('all', 'All Records'),
            ('building', 'Specific Building'),
            ('block', 'Specific Block'),
            ('department', 'Specific Department'),
            ('date_range', 'Date Range')
        ],
        help_text="Audit scope"
    )
    
    # Scope filters
    building_id = forms.IntegerField(
        required=False,
        help_text="Building ID for building scope"
    )
    
    block_id = forms.IntegerField(
        required=False,
        help_text="Block ID for block scope"
    )
    
    department_id = forms.IntegerField(
        required=False,
        help_text="Department ID for department scope"
    )
    
    date_from = forms.DateField(
        required=False,
        help_text="Start date for date range scope"
    )
    
    date_to = forms.DateField(
        required=False,
        help_text="End date for date range scope"
    )
    
    include_inactive = forms.BooleanField(
        required=False,
        help_text="Include inactive records in audit"
    )
    
    output_format = forms.ChoiceField(
        choices=[
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('xlsx', 'Excel'),
            ('pdf', 'PDF Report')
        ],
        initial='json',
        help_text="Output format for audit results"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        scope = cleaned_data.get('scope')
        
        # Validate scope-specific requirements
        if scope == 'building' and not cleaned_data.get('building_id'):
            raise ValidationError('Building ID is required for building scope.')
        
        if scope == 'block' and not cleaned_data.get('block_id'):
            raise ValidationError('Block ID is required for block scope.')
        
        if scope == 'department' and not cleaned_data.get('department_id'):
            raise ValidationError('Department ID is required for department scope.')
        
        if scope == 'date_range':
            date_from = cleaned_data.get('date_from')
            date_to = cleaned_data.get('date_to')
            
            if not date_from or not date_to:
                raise ValidationError('Both start and end dates are required for date range scope.')
            
            if date_from >= date_to:
                raise ValidationError('End date must be after start date.')
        
        return cleaned_data


# ================================
# SYSTEM CONFIGURATION FORMS
# ================================

class APISystemConfigForm(forms.Form):
    """Form for system configuration via API"""
    
    config_section = forms.ChoiceField(
        choices=[
            ('general', 'General Settings'),
            ('inventory', 'Inventory Settings'),
            ('assignments', 'Assignment Settings'),
            ('maintenance', 'Maintenance Settings'),
            ('notifications', 'Notification Settings'),
            ('api', 'API Settings'),
            ('hierarchy', 'Hierarchy Settings')
        ],
        help_text="Configuration section to update"
    )
    
    settings = forms.CharField(
        max_length=5000,
        help_text="JSON string with configuration settings"
    )
    
    def clean_settings(self):
        settings = self.cleaned_data.get('settings')
        try:
            return json.loads(settings)
        except json.JSONDecodeError:
            raise ValidationError("Invalid settings JSON format.")
        return {}
    
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


# ================================
# MOBILE APP SYNC FORMS
# ================================

class MobileSyncForm(forms.Form):
    """Enhanced form for mobile app data synchronization"""
    
    last_sync = forms.DateTimeField(
        required=False,
        help_text="Last sync timestamp (ISO format)"
    )
    
    sync_types = forms.MultipleChoiceField(
        choices=[
            ('devices', 'Devices'),
            ('assignments', 'Assignments'),
            ('staff', 'Staff'),
            ('locations', 'Locations'),
            ('buildings', 'Buildings'),
            ('blocks', 'Blocks'),
            ('departments', 'Departments')
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
    
    device_info = forms.CharField(
        max_length=500,
        required=False,
        help_text="Device information JSON"
    )
    
    location_filter = forms.CharField(
        max_length=200,
        required=False,
        help_text="JSON string to filter data by location hierarchy"
    )
    
    def clean_last_sync(self):
        last_sync = self.cleaned_data.get('last_sync')
        if not last_sync:
            # Default to 30 days ago
            last_sync = timezone.now() - timezone.timedelta(days=30)
        
        return last_sync
    
    def clean_device_info(self):
        device_info = self.cleaned_data.get('device_info')
        if device_info:
            try:
                return json.loads(device_info)
            except json.JSONDecodeError:
                raise ValidationError("Invalid device info JSON format.")
        return {}
    
    def clean_location_filter(self):
        location_filter = self.cleaned_data.get('location_filter')
        if location_filter:
            try:
                return json.loads(location_filter)
            except json.JSONDecodeError:
                raise ValidationError("Invalid location filter JSON format.")
        return {}