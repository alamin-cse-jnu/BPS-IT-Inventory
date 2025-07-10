

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
    """Enhanced device form for admin interface"""
    
    class Meta:
        model = Device
        fields = '__all__'
        widgets = {
            'specifications': forms.Textarea(attrs={'rows': 8, 'cols': 80}),
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Auto-generate device_id if not provided
        if not cleaned_data.get('device_id'):
            device_type = cleaned_data.get('device_type')
            if device_type:
                # Generate ID based on device type
                count = Device.objects.filter(device_type=device_type).count() + 1
                cleaned_data['device_id'] = f"BPS-{device_type.code}-{count:03d}"
        
        return cleaned_data


class DeviceInlineForm(forms.ModelForm):
    """Inline form for devices in location admin"""
    
    class Meta:
        model = Device
        fields = ['device_id', 'device_name', 'device_type', 'status', 'condition']
        widgets = {
            'device_id': forms.TextInput(attrs={'size': 15}),
            'device_name': forms.TextInput(attrs={'size': 30}),
        }

class BlockAdminForm(forms.ModelForm):
    """Enhanced block form for admin interface"""
    
    class Meta:
        model = Block
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g., EB, WB, NB, SB',
                'style': 'text-transform: uppercase;'
            }),
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g., East Block, West Block'
            }),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            
            # Check for duplicate code within the same building
            building = self.cleaned_data.get('building')
            if building:
                existing_block = Block.objects.filter(
                    building=building,
                    code=code
                )
                
                if self.instance.pk:
                    existing_block = existing_block.exclude(pk=self.instance.pk)
                
                if existing_block.exists():
                    raise ValidationError(f'Block with code "{code}" already exists in this building.')
        
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            
            # Check for duplicate name within the same building
            building = self.cleaned_data.get('building')
            if building:
                existing_block = Block.objects.filter(
                    building=building,
                    name__iexact=name
                )
                
                if self.instance.pk:
                    existing_block = existing_block.exclude(pk=self.instance.pk)
                
                if existing_block.exists():
                    raise ValidationError(f'Block with name "{name}" already exists in this building.')
        
        return name

class FloorAdminForm(forms.ModelForm):
    """Enhanced floor form for admin interface"""
    
    class Meta:
        model = Floor
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'floor_number': forms.NumberInput(attrs={
                'min': 0,
                'max': 50,
                'placeholder': 'e.g., 1, 2, 3'
            }),
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g., First Floor, Ground Floor'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter blocks based on selected building
        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['block'].queryset = Block.objects.filter(
                    building_id=building_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                self.fields['block'].queryset = Block.objects.none()
        elif self.instance.pk and self.instance.building:
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.building,
                is_active=True
            ).order_by('name')
        else:
            self.fields['block'].queryset = Block.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor_number = cleaned_data.get('floor_number')
        
        # Validate that block belongs to the selected building
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
                raise ValidationError(f'Floor {floor_number} already exists in {block.name}.')
        
        return cleaned_data
# ================================
# ASSIGNMENT ADMIN FORMS
# ================================

class AssignmentAdminForm(forms.ModelForm):
    """Enhanced assignment form for admin interface"""
    
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


# ================================
# STAFF ADMIN FORMS
# ================================

class StaffAdminForm(forms.ModelForm):
    """Enhanced staff form for admin interface"""
    
    # User fields for inline editing
    username = forms.CharField(max_length=150)
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
        
        # Populate user fields if editing existing staff
        if self.instance.pk and hasattr(self.instance, 'user'):
            user = self.instance.user
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['is_active_user'].initial = user.is_active
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            existing = User.objects.filter(username=username)
            if self.instance.pk and hasattr(self.instance, 'user'):
                existing = existing.exclude(pk=self.instance.user.pk)
            
            if existing.exists():
                raise ValidationError(f"Username '{username}' already exists.")
        
        return username
    
    def save(self, commit=True):
        staff = super().save(commit=False)
        
        # Create or update associated user
        if hasattr(staff, 'user'):
            user = staff.user
        else:
            user = User()
            
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_active = self.cleaned_data['is_active_user']
        
        if commit:
            user.save()
            staff.user = user
            staff.save()
        
        return staff


# ================================
# LOCATION ADMIN FORMS
# ================================

class LocationAdminForm(forms.ModelForm):
    """Enhanced location form for admin interface"""
    
    class Meta:
        model = Location
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cascade filtering for block -> floor -> department -> room
        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['block'].queryset = Block.objects.filter(
                    building_id=building_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                self.fields['block'].queryset = Block.objects.none()
        elif self.instance.pk and self.instance.building:
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.building,
                is_active=True
            ).order_by('name')
        
        if 'block' in self.data:
            try:
                block_id = int(self.data.get('block'))
                self.fields['floor'].queryset = Floor.objects.filter(
                    block_id=block_id,
                    is_active=True
                ).order_by('floor_number')
            except (ValueError, TypeError):
                self.fields['floor'].queryset = Floor.objects.none()
        elif self.instance.pk and self.instance.block:
            self.fields['floor'].queryset = Floor.objects.filter(
                block=self.instance.block,
                is_active=True
            ).order_by('floor_number')
        
        if 'floor' in self.data:
            try:
                floor_id = int(self.data.get('floor'))
                self.fields['department'].queryset = Department.objects.filter(
                    floor_id=floor_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                self.fields['department'].queryset = Department.objects.none()
        elif self.instance.pk and self.instance.floor:
            self.fields['department'].queryset = Department.objects.filter(
                floor=self.instance.floor,
                is_active=True
            ).order_by('name')
        
        if 'department' in self.data:
            try:
                department_id = int(self.data.get('department'))
                self.fields['room'].queryset = Room.objects.filter(
                    department_id=department_id,
                    is_active=True
                ).order_by('room_number')
            except (ValueError, TypeError):
                self.fields['room'].queryset = Room.objects.none()
        elif self.instance.pk and self.instance.department:
            self.fields['room'].queryset = Room.objects.filter(
                department=self.instance.department,
                is_active=True
            ).order_by('room_number')

    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor = cleaned_data.get('floor')
        department = cleaned_data.get('department')
        room = cleaned_data.get('room')
        
        # Validate hierarchical relationships
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
# MAINTENANCE ADMIN FORMS
# ================================

class MaintenanceScheduleAdminForm(forms.ModelForm):
    """Enhanced maintenance schedule form for admin interface"""
    
    class Meta:
        model = MaintenanceSchedule
        fields = '__all__'
        widgets = {
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'completed_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'completion_notes': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter vendors by maintenance types
        self.fields['vendor'].queryset = Vendor.objects.filter(
            vendor_type__in=['SERVICE_PROVIDER', 'MAINTENANCE_CONTRACTOR'],
            is_active=True
        )


# ================================
# BULK OPERATION FORMS
# ================================

class BulkDeviceUpdateForm(forms.Form):
    """Form for bulk device updates in admin"""
    
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('update_status', 'Update Status'),
        ('update_location', 'Update Location'),
        ('update_condition', 'Update Condition'),
        ('assign_vendor', 'Assign Vendor'),
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
    
    # Location update
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
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
    
    update_reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Reason for bulk update...'
        })
    )


# ================================
# IMPORT/EXPORT ADMIN FORMS
# ================================

class DataImportForm(forms.Form):
    """Form for importing data in admin interface"""
    
    IMPORT_MODELS = [
        ('devices', 'Devices'),
        ('staff', 'Staff Members'),
        ('locations', 'Locations'),
        ('vendors', 'Vendors'),
        ('assignments', 'Assignments'),
        ('device_types', 'Device Types'),
    ]
    
    model_type = forms.ChoiceField(
        choices=IMPORT_MODELS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    import_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.json'
        }),
        help_text="Supported formats: CSV, Excel (XLSX), JSON"
    )
    
    has_header = forms.BooleanField(
        initial=True,
        required=False,
        label="File has header row",
        help_text="Check if the first row contains column headers"
    )
    
    update_existing = forms.BooleanField(
        initial=False,
        required=False,
        label="Update existing records",
        help_text="Update records if they already exist (based on unique identifiers)"
    )
    
    validate_only = forms.BooleanField(
        initial=False,
        required=False,
        label="Validate only (don't import)",
        help_text="Only validate the data without importing"
    )
    
    def clean_import_file(self):
        import_file = self.cleaned_data.get('import_file')
        if import_file:
            # Check file extension
            allowed_extensions = ['.csv', '.xlsx', '.json']
            file_ext = import_file.name.lower().split('.')[-1]
            if f'.{file_ext}' not in allowed_extensions:
                raise ValidationError("File must be CSV, Excel (XLSX), or JSON format.")
            
            # Check file size (5MB limit)
            if import_file.size > 5 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 5MB.")
        
        return import_file


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