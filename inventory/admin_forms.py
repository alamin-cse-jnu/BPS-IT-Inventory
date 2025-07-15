

from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models

from .models import (
    Device, Assignment, Staff, Department, Location, Vendor,
    DeviceCategory, DeviceType, DeviceSubCategory, MaintenanceSchedule,
    Building, Room, AuditLog, Block, Floor
)


# ================================
# DEVICE ADMIN FORMS
# ================================

class DeviceAdminForm(forms.ModelForm):
    """Enhanced device form for admin interface with Block hierarchy support"""
    
    class Meta:
        model = Device
        fields = '__all__'
        widgets = {
            'processor': forms.TextInput(attrs={'class': 'vTextField'}),
            'memory_ram': forms.TextInput(attrs={'class': 'vTextField'}),
            'storage_capacity': forms.TextInput(attrs={'class': 'vTextField'}),
            'operating_system': forms.TextInput(attrs={'class': 'vTextField'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_start_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({'class': 'vTextField'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'vLargeTextField'})
        
        # Enhanced location filtering with Block hierarchy
        if hasattr(self, 'instance') and self.instance.pk and self.instance.location:
            location = self.instance.location
            self.fields['location'].help_text = f"Current location hierarchy: {location.get_full_hierarchy()}"
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Auto-generate device_id if not provided
        if not cleaned_data.get('device_id'):
            device_type = cleaned_data.get('device_type')
            if device_type:
                # Generate ID based on device type and building
                location = cleaned_data.get('location')
                building_code = location.building.code if location and location.building else 'BPS'
                block_code = location.block.code if location and location.block else 'MAIN'
                count = Device.objects.filter(device_type=device_type).count() + 1
                cleaned_data['device_id'] = f"{building_code}-{block_code}-{device_type.code}-{count:03d}"
        
        # Validate warranty dates
        warranty_start = cleaned_data.get('warranty_start_date')
        warranty_end = cleaned_data.get('warranty_end_date')
        purchase_date = cleaned_data.get('purchase_date')
        
        if warranty_start and warranty_end and warranty_start >= warranty_end:
            raise ValidationError('Warranty end date must be after warranty start date.')
        
        if purchase_date and warranty_start and warranty_start < purchase_date:
            raise ValidationError('Warranty start date cannot be before purchase date.')
        
        return cleaned_data


class DeviceInlineForm(forms.ModelForm):
    """Inline form for devices in location admin with enhanced display"""
    
    class Meta:
        model = Device
        fields = ['device_id', 'device_name', 'device_type', 'status', 'condition']
        widgets = {
            'device_id': forms.TextInput(attrs={'size': 20}),
            'device_name': forms.TextInput(attrs={'size': 35}),
        }


# ================================
# BLOCK ADMIN FORMS (NEW)
# ================================

class BlockAdminForm(forms.ModelForm):
    """Enhanced block form for admin interface"""
    
    class Meta:
        model = Block
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter buildings to active only
        self.fields['building'].queryset = Building.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        name = cleaned_data.get('name')
        code = cleaned_data.get('code')
        
        # Check for duplicate block name within the same building
        if building and name:
            existing_block = Block.objects.filter(
                building=building,
                name=name
            )
            
            if self.instance.pk:
                existing_block = existing_block.exclude(pk=self.instance.pk)
            
            if existing_block.exists():
                raise ValidationError(f'Block "{name}" already exists in {building.name}.')
        
        # Check for duplicate block code within the same building
        if building and code:
            existing_code = Block.objects.filter(
                building=building,
                code=code
            )
            
            if self.instance.pk:
                existing_code = existing_code.exclude(pk=self.instance.pk)
            
            if existing_code.exists():
                raise ValidationError(f'Block code "{code}" already exists in {building.name}.')
        
        return cleaned_data


# ================================
# FLOOR ADMIN FORMS (UPDATED)
# ================================

class FloorAdminForm(forms.ModelForm):
    """Enhanced floor form for admin interface with Block support"""
    
    class Meta:
        model = Floor
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter buildings and blocks to active only
        self.fields['building'].queryset = Building.objects.filter(is_active=True)
        self.fields['block'].queryset = Block.objects.filter(is_active=True)
        
        # Cascade filtering for building -> block
        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['block'].queryset = Block.objects.filter(
                    building_id=building_id,
                    is_active=True
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.building:
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.building,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor_number = cleaned_data.get('floor_number')
        
        # Validate block belongs to building
        if building and block and block.building != building:
            raise ValidationError('Selected block does not belong to the selected building.')
        
        # Check for duplicate floor number within the same building and block
        if building and block and floor_number is not None:
            existing_floor = Floor.objects.filter(
                building=building,
                block=block,
                floor_number=floor_number
            )
            
            if self.instance.pk:
                existing_floor = existing_floor.exclude(pk=self.instance.pk)
            
            if existing_floor.exists():
                raise ValidationError(f'Floor {floor_number} already exists in {building.name} - {block.name}.')
        
        return cleaned_data


# ================================
# ASSIGNMENT ADMIN FORMS (UPDATED)
# ================================

class AssignmentAdminForm(forms.ModelForm):
    """Enhanced assignment form for admin interface with Block hierarchy"""
    
    class Meta:
        model = Assignment
        fields = '__all__'
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_return_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_return_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'return_notes': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter available devices
        self.fields['device'].queryset = Device.objects.filter(
            models.Q(status='AVAILABLE') | 
            models.Q(id=self.instance.device_id if self.instance.pk else None)
        )
        
        # Filter active staff
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(is_active=True)
        
        # Filter active locations with hierarchy display
        locations = Location.objects.filter(is_active=True).select_related(
            'building', 'block', 'floor', 'department', 'room'
        )
        self.fields['assigned_to_location'].queryset = locations
    
    def clean(self):
        cleaned_data = super().clean()
        device = cleaned_data.get('device')
        staff = cleaned_data.get('assigned_to_staff')
        department = cleaned_data.get('assigned_to_department')
        location = cleaned_data.get('assigned_to_location')
        
        # Ensure at least one assignment target
        if not any([staff, department, location]):
            raise ValidationError('Device must be assigned to staff, department, or location.')
        
        # Validate device availability for new assignments
        if device and not self.instance.pk and device.status != 'AVAILABLE':
            raise ValidationError(f'Device {device.device_id} is not available for assignment.')
        
        return cleaned_data


# ================================
# STAFF ADMIN FORMS (UPDATED)
# ================================

class StaffAdminForm(forms.ModelForm):
    """Enhanced staff form for admin interface"""
    
    # Additional user fields for convenience
    username = forms.CharField(max_length=150, help_text="Required. 150 characters or fewer.")
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()
    is_active_user = forms.BooleanField(
        required=False,
        label="User Account Active",
        help_text="Designates whether this user should be treated as active."
    )
    
    class Meta:
        model = Staff
        fields = '__all__'
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'}),
            'leaving_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter departments to active only with hierarchy display
        departments = Department.objects.filter(is_active=True).select_related(
            'floor__building', 'floor__block'
        )
        self.fields['department'].queryset = departments
        
        # Only show users without staff profiles
        self.fields['user'].queryset = User.objects.filter(staff_profile__isnull=True)
        
        # Populate user fields if editing existing staff
        if self.instance.pk and hasattr(self.instance, 'user'):
            user = self.instance.user
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['is_active_user'].initial = user.is_active
            self.fields['user'].queryset = User.objects.filter(
                models.Q(staff_profile__isnull=True) | models.Q(pk=user.pk)
            ).distinct()
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            existing = User.objects.filter(username=username)
            if self.instance.pk and hasattr(self.instance, 'user'):
                existing = existing.exclude(pk=self.instance.user.pk)
            
            if existing.exists():
                raise ValidationError(f"Username '{username}' already exists.")
        
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            existing = User.objects.filter(email=email)
            if self.instance.pk and hasattr(self.instance, 'user'):
                existing = existing.exclude(pk=self.instance.user.pk)
            
            if existing.exists():
                raise ValidationError(f"Email '{email}' is already in use.")
        
        return email


# ================================
# LOCATION ADMIN FORMS (UPDATED)
# ================================

class LocationAdminForm(forms.ModelForm):
    """Enhanced location form for admin interface with Block hierarchy"""
    
    class Meta:
        model = Location
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cascade filtering for building -> block -> floor -> department -> room
        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['block'].queryset = Block.objects.filter(
                    building_id=building_id,
                    is_active=True
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.building:
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.building,
                is_active=True
            )
        
        if 'block' in self.data:
            try:
                block_id = int(self.data.get('block'))
                self.fields['floor'].queryset = Floor.objects.filter(
                    block_id=block_id,
                    is_active=True
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.block:
            self.fields['floor'].queryset = Floor.objects.filter(
                block=self.instance.block,
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor = cleaned_data.get('floor')
        department = cleaned_data.get('department')
        room = cleaned_data.get('room')
        
        # Validate hierarchy relationships
        if building and block and block.building != building:
            raise ValidationError('Selected block does not belong to the selected building.')
        
        if block and floor and floor.block != block:
            raise ValidationError('Selected floor does not belong to the selected block.')
        
        if floor and department and department.floor != floor:
            raise ValidationError('Selected department does not belong to the selected floor.')
        
        if department and room and room.department != department:
            raise ValidationError('Selected room does not belong to the selected department.')
        
        # Check for duplicate locations
        if building and block and floor and department:
            existing_location = Location.objects.filter(
                building=building,
                block=block,
                floor=floor,
                department=department,
                room=room
            )
            
            if self.instance.pk:
                existing_location = existing_location.exclude(pk=self.instance.pk)
            
            if existing_location.exists():
                raise ValidationError('A location with this combination already exists.')
        
        return cleaned_data


# ================================
# MAINTENANCE ADMIN FORMS (UPDATED)
# ================================

class MaintenanceScheduleAdminForm(forms.ModelForm):
    """Enhanced maintenance schedule form for admin interface"""
    
    class Meta:
        model = MaintenanceSchedule
        fields = '__all__'
        widgets = {
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
            'last_completed_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'estimated_duration': forms.TextInput(attrs={'placeholder': 'e.g., 2:00:00 (HH:MM:SS)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter vendors by maintenance types
        self.fields['vendor'].queryset = Vendor.objects.filter(
            vendor_type__in=['SERVICE_PROVIDER', 'MAINTENANCE_CONTRACTOR'],
            is_active=True
        )
        
        # Filter devices to show hierarchy location
        devices = Device.objects.select_related('location__building', 'location__block')
        self.fields['device'].queryset = devices
    
    def clean(self):
        cleaned_data = super().clean()
        next_due_date = cleaned_data.get('next_due_date')
        last_completed_date = cleaned_data.get('last_completed_date')
        status = cleaned_data.get('status')
        
        if last_completed_date and next_due_date and last_completed_date > next_due_date:
            raise ValidationError('Last completed date cannot be after next due date.')
        
        return cleaned_data


# ================================
# BULK OPERATION FORMS (UPDATED)
# ================================

class BulkDeviceUpdateForm(forms.Form):
    """Form for bulk device updates in admin with enhanced options"""
    
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('update_status', 'Update Status'),
        ('update_location', 'Update Location'),
        ('update_condition', 'Update Condition'),
        ('assign_vendor', 'Assign Vendor'),
        ('bulk_assignment', 'Bulk Assignment'),
        ('generate_qr', 'Generate QR Codes'),
        ('export_data', 'Export Data'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Status update
    new_status = forms.ChoiceField(
        choices=[('', 'Select Status')] + Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Location update with hierarchy
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True).select_related(
            'building', 'block', 'floor', 'department'
        ),
        required=False,
        empty_label="Select Location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Condition update
    new_condition = forms.ChoiceField(
        choices=[('', 'Select Condition')] + Device.CONDITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Vendor assignment
    new_vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        empty_label="Select Vendor",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Bulk assignment options
    assign_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select Staff",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assign_to_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    update_reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Reason for bulk update...',
            'class': 'form-control'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        # Validate required fields based on action
        if action == 'update_status' and not cleaned_data.get('new_status'):
            raise ValidationError('New status is required for status update.')
        
        if action == 'update_location' and not cleaned_data.get('new_location'):
            raise ValidationError('New location is required for location update.')
        
        if action == 'update_condition' and not cleaned_data.get('new_condition'):
            raise ValidationError('New condition is required for condition update.')
        
        if action == 'assign_vendor' and not cleaned_data.get('new_vendor'):
            raise ValidationError('Vendor is required for vendor assignment.')
        
        if action == 'bulk_assignment':
            if not any([cleaned_data.get('assign_to_staff'), cleaned_data.get('assign_to_department')]):
                raise ValidationError('Staff or department is required for bulk assignment.')
        
        return cleaned_data


# ================================
# IMPORT/EXPORT ADMIN FORMS (UPDATED)
# ================================

class DataImportForm(forms.Form):
    """Form for importing data in admin interface with enhanced validation"""
    
    IMPORT_MODELS = [
        ('devices', 'Devices'),
        ('locations', 'Locations'),
        ('staff', 'Staff'),
        ('buildings', 'Buildings'),
        ('blocks', 'Blocks'),
        ('floors', 'Floors'),
        ('departments', 'Departments'),
        ('assignments', 'Assignments'),
    ]
    
    model_type = forms.ChoiceField(
        choices=IMPORT_MODELS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    import_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        help_text="Supported formats: CSV, Excel (.xlsx, .xls)"
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Update existing records if found"
    )
    
    validate_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Only validate data without importing"
    )
    
    def clean_import_file(self):
        file = self.cleaned_data.get('import_file')
        if file:
            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 10MB.')
            
            # Validate file extension
            valid_extensions = ['.csv', '.xlsx', '.xls']
            if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError('Please upload a valid CSV or Excel file.')
        
        return file


class DataExportForm(forms.Form):
    """Form for exporting data from admin interface"""
    
    EXPORT_MODELS = [
        ('devices', 'Devices'),
        ('locations', 'Locations'),
        ('staff', 'Staff'),
        ('assignments', 'Assignments'),
        ('maintenance', 'Maintenance Records'),
        ('audit_logs', 'Audit Logs'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF Report'),
    ]
    
    model_type = forms.ChoiceField(
        choices=EXPORT_MODELS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='xlsx',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter records from this date"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter records until this date"
    )
    
    include_inactive = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include inactive/deleted records"
    )


# ================================
# SYSTEM SETTINGS FORMS
# ================================

class SystemSettingsForm(forms.Form):
    """Form for system-wide settings in admin"""
    
    # General Settings
    organization_name = forms.CharField(
        max_length=200,
        initial="Bangladesh Parliament Secretariat",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    system_name = forms.CharField(
        max_length=200,
        initial="BPS IT Inventory Management System",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Device ID Settings
    auto_generate_device_ids = forms.BooleanField(
        initial=True,
        required=False,
        label="Auto-generate Device IDs",
        help_text="Automatically generate device IDs for new devices"
    )
    
    device_id_prefix = forms.CharField(
        max_length=10,
        initial="BPS",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Prefix for auto-generated device IDs"
    )
    
    # Notification Settings
    email_notifications_enabled = forms.BooleanField(
        initial=True,
        required=False,
        label="Enable Email Notifications",
        help_text="Send email notifications for assignments, maintenance, etc."
    )
    
    warranty_alert_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Days before warranty expiry to show alerts"
    )
    
    maintenance_reminder_days = forms.IntegerField(
        initial=7,
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Days before maintenance to send reminders"
    )
    
    # Assignment Settings
    max_assignment_duration = forms.IntegerField(
        initial=365,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Maximum allowed assignment duration in days"
    )
    
    require_assignment_approval = forms.BooleanField(
        initial=False,
        required=False,
        label="Require Assignment Approval",
        help_text="Require approval for new device assignments"
    )
    
    # Backup Settings
    auto_backup_enabled = forms.BooleanField(
        initial=True,
        required=False,
        label="Enable Automatic Backups",
        help_text="Automatically backup system data"
    )
    
    backup_frequency = forms.ChoiceField(
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        initial='weekly',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    backup_retention_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of days to retain backup files"
    )


# ================================
# AUDIT LOG FORMS
# ================================

class AuditLogFilterForm(forms.Form):
    """Form for filtering audit logs in admin"""
    
    ACTION_CHOICES = [
        ('', 'All Actions'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('ASSIGN', 'Assign'),
        ('RETURN', 'Return'),
        ('TRANSFER', 'Transfer'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
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
    
    search_query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search in descriptions...'
        })
    )


# ================================
# DEVICE CATEGORY ADMIN FORMS
# ================================

class DeviceCategoryAdminForm(forms.ModelForm):
    """Enhanced device category form for admin"""
    
    class Meta:
        model = DeviceCategory
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'icon': forms.TextInput(attrs={
                'placeholder': 'e.g., fas fa-laptop, fas fa-server'
            }),
        }
    
    def clean_icon(self):
        icon = self.cleaned_data.get('icon')
        if icon:
            # Basic validation for FontAwesome icon format
            if not icon.startswith(('fa ', 'fas ', 'far ', 'fab ')):
                raise ValidationError("Icon should be a valid FontAwesome class (e.g., fas fa-laptop)")
        
        return icon


class DeviceTypeAdminForm(forms.ModelForm):
    """Enhanced device type form for admin"""
    
    class Meta:
        model = DeviceType
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Group subcategories by category for better UX
        self.fields['subcategory'].queryset = DeviceSubCategory.objects.select_related('category').filter(is_active=True)


# ================================
# VENDOR ADMIN FORMS
# ================================

class VendorAdminForm(forms.ModelForm):
    """Enhanced vendor form for admin interface"""
    
    class Meta:
        model = Vendor
        fields = '__all__'
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'website': forms.URLInput(attrs={
                'placeholder': 'https://example.com'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'contact@vendor.com'
            }),
        }
    
    def clean_website(self):
        website = self.cleaned_data.get('website')
        if website and not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        
        return website
    
    def clean_tax_id(self):
        tax_id = self.cleaned_data.get('tax_id')
        if tax_id:
            # Basic validation for Bangladesh TIN format
            tax_id = tax_id.replace('-', '').replace(' ', '')
            if not tax_id.isdigit() or len(tax_id) not in [12, 13]:
                raise ValidationError("Invalid TIN format. Should be 12 or 13 digits.")
        
        return tax_id


# ================================
# ADVANCED FILTER FORMS
# ================================

class DeviceAdvancedFilterForm(forms.Form):
    """Advanced filtering form for devices in admin"""
    
    # Basic filters
    status = forms.MultipleChoiceField(
        choices=Device.STATUS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    condition = forms.MultipleChoiceField(
        choices=Device.CONDITION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    device_type = forms.ModelMultipleChoiceField(
        queryset=DeviceType.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    location = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    vendor = forms.ModelMultipleChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    # Date filters
    purchase_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    purchase_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    warranty_expiry_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    warranty_expiry_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # Price filters
    price_from = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    
    price_to = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    
    # Special filters
    is_critical = forms.BooleanField(
        required=False,
        label="Critical Devices Only"
    )
    
    warranty_expired = forms.BooleanField(
        required=False,
        label="Warranty Expired"
    )
    
    warranty_expiring_soon = forms.BooleanField(
        required=False,
        label="Warranty Expiring Soon (30 days)"
    )
    
    unassigned_only = forms.BooleanField(
        required=False,
        label="Unassigned Devices Only"
    )


# ================================
# REPORT CONFIGURATION FORMS
# ================================

class ReportConfigForm(forms.Form):
    """Form for configuring admin reports"""
    
    REPORT_TYPES = [
        ('device_summary', 'Device Summary Report'),
        ('assignment_summary', 'Assignment Summary Report'),
        ('maintenance_report', 'Maintenance Report'),
        ('warranty_report', 'Warranty Status Report'),
        ('utilization_report', 'Device Utilization Report'),
        ('financial_report', 'Financial Summary Report'),
        ('audit_report', 'Audit Trail Report'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_range = forms.ChoiceField(
        choices=[
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_3_months', 'Last 3 Months'),
            ('last_year', 'Last Year'),
            ('custom', 'Custom Range'),
        ],
        initial='last_30_days',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    custom_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    custom_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    include_inactive = forms.BooleanField(
        initial=False,
        required=False,
        label="Include Inactive Records",
        help_text="Include inactive devices, staff, etc. in the report"
    )
    
    group_by = forms.ChoiceField(
        choices=[
            ('', 'No Grouping'),
            ('department', 'Department'),
            ('location', 'Location'),
            ('device_type', 'Device Type'),
            ('vendor', 'Vendor'),
            ('status', 'Status'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    export_format = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
        ],
        initial='pdf',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# ================================
# FORM WIDGETS AND UTILITIES
# ================================

class AutocompleteWidget(forms.TextInput):
    """Custom widget for autocomplete functionality"""
    
    def __init__(self, source_url, *args, **kwargs):
        self.source_url = source_url
        super().__init__(*args, **kwargs)
    
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        
        attrs.update({
            'data-autocomplete-url': self.source_url,
            'class': 'form-control autocomplete-input'
        })
        
        return super().render(name, value, attrs, renderer)


class ColorPickerWidget(forms.TextInput):
    """Color picker widget for admin forms"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'type': 'color', 'class': 'form-control color-picker'})


# ================================
# END OF ADMIN FORMS MODULE
# ================================