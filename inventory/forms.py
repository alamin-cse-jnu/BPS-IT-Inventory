from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import re

from .models import (
    Device, DeviceCategory, DeviceSubCategory, DeviceType,
    Vendor, Assignment, Staff, Department, Location, Room,
    MaintenanceSchedule, Building, Floor, User
)

class DeviceForm(forms.ModelForm):
    """Form for adding/editing devices"""
    
    # Additional fields for easier data entry
    category = forms.ModelChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        empty_label="Select Category",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_category'})
    )
    
    subcategory = forms.ModelChoiceField(
        queryset=DeviceSubCategory.objects.none(),
        empty_label="Select Subcategory",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_subcategory'})
    )
    
    # JSON field for specifications - convert to textarea for easier editing
    specifications_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter specifications in JSON format or one per line:\n'
                          'CPU: Intel Core i7\n'
                          'RAM: 16GB\n'
                          'Storage: 512GB SSD'
        }),
        required=False,
        help_text="Enter technical specifications. JSON format or one specification per line."
    )
    
    class Meta:
        model = Device
        fields = [
            'asset_tag', 'device_name', 'device_type', 'brand', 'model', 
            'serial_number', 'mac_address', 'ip_address', 'status', 'condition',
            'vendor', 'purchase_date', 'purchase_order_number', 'purchase_price',
            'warranty_start_date', 'warranty_end_date', 'warranty_type',
            'support_contract', 'amc_details', 'notes', 'is_critical'
        ]
        
        widgets = {
            'asset_tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BPS-IT-0001'}),
            'device_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Finance Dept Laptop'}),
            'device_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_device_type'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dell, HP, Lenovo, etc.'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Latitude 7420'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ABC123XYZ789'}),
            'mac_address': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '00:1B:44:11:3A:B7',
                'pattern': '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '192.168.1.100'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'purchase_order_number': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'PO-2025-001'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'min': '0'
            }),
            'warranty_start_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'warranty_end_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'warranty_type': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Standard, Extended, On-site'
            }),
            'support_contract': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3
            }),
            'amc_details': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3
            }),
            'is_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing device, populate category and subcategory
        if self.instance.pk:
            device_type = self.instance.device_type
            if device_type:
                self.fields['category'].initial = device_type.subcategory.category
                self.fields['subcategory'].queryset = DeviceSubCategory.objects.filter(
                    category=device_type.subcategory.category, is_active=True
                )
                self.fields['subcategory'].initial = device_type.subcategory
                self.fields['device_type'].queryset = DeviceType.objects.filter(
                    subcategory=device_type.subcategory, is_active=True
                )
            
            # Convert specifications JSON to text
            if self.instance.specifications:
                specs_text = []
                for key, value in self.instance.specifications.items():
                    specs_text.append(f"{key}: {value}")
                self.fields['specifications_text'].initial = '\n'.join(specs_text)
        
        # Set default warranty start date to purchase date if not set
        if not self.instance.pk:
            self.fields['warranty_start_date'].initial = timezone.now().date()
            self.fields['warranty_end_date'].initial = timezone.now().date() + timedelta(days=365)
    
    def clean_mac_address(self):
        """Validate MAC address format"""
        mac_address = self.cleaned_data.get('mac_address')
        if mac_address:
            # Allow common MAC address formats
            mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
            if not mac_pattern.match(mac_address):
                raise ValidationError("Invalid MAC address format. Use format: 00:1B:44:11:3A:B7")
        return mac_address
    
    def clean_serial_number(self):
        """Ensure serial number is unique"""
        serial_number = self.cleaned_data.get('serial_number')
        if serial_number:
            existing = Device.objects.filter(serial_number=serial_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A device with this serial number already exists.")
        return serial_number
    
    def clean_asset_tag(self):
        """Ensure asset tag is unique"""
        asset_tag = self.cleaned_data.get('asset_tag')
        if asset_tag:
            existing = Device.objects.filter(asset_tag=asset_tag)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A device with this asset tag already exists.")
        return asset_tag
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        purchase_date = cleaned_data.get('purchase_date')
        warranty_start_date = cleaned_data.get('warranty_start_date')
        warranty_end_date = cleaned_data.get('warranty_end_date')
        
        # Warranty start date should not be before purchase date
        if purchase_date and warranty_start_date:
            if warranty_start_date < purchase_date:
                raise ValidationError("Warranty start date cannot be before purchase date.")
        
        # Warranty end date should be after start date
        if warranty_start_date and warranty_end_date:
            if warranty_end_date <= warranty_start_date:
                raise ValidationError("Warranty end date must be after warranty start date.")
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to handle specifications conversion"""
        instance = super().save(commit=False)
        
        # Convert specifications text to JSON
        specs_text = self.cleaned_data.get('specifications_text', '')
        if specs_text:
            specs_dict = {}
            for line in specs_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    specs_dict[key.strip()] = value.strip()
            instance.specifications = specs_dict
        else:
            instance.specifications = {}
        
        if commit:
            instance.save()
        return instance

class DeviceSearchForm(forms.Form):
    """Form for searching and filtering devices"""
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by Device ID, Name, Asset Tag, Brand, Model, or Serial Number...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Device.DEVICE_STATUS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    warranty_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('active', 'Active Warranty'),
            ('expired', 'Expired Warranty'),
            ('expiring_soon', 'Expiring Soon')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class AssignmentForm(forms.ModelForm):
    """Form for creating device assignments"""
    
    class Meta:
        model = Assignment
        fields = [
            'device', 'assignment_type', 'assigned_to_staff', 
            'assigned_to_department', 'assigned_to_location',
            'project_name', 'project_code', 'purpose', 'conditions',
            'is_temporary', 'expected_return_date', 'notes'
        ]
        
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_staff': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_department': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_location': forms.Select(attrs={'class': 'form-control'}),
            'project_name': forms.TextInput(attrs={'class': 'form-control'}),
            'project_code': forms.TextInput(attrs={'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_temporary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expected_return_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }
    
    def __init__(self, *args, **kwargs):
        device = kwargs.pop('device', None)
        super().__init__(*args, **kwargs)
        
        # If device is provided, set it and make it readonly
        if device:
            self.fields['device'].initial = device
            self.fields['device'].widget.attrs['readonly'] = True
            self.fields['device'].queryset = Device.objects.filter(pk=device.pk)
        else:
            # Only show available devices
            self.fields['device'].queryset = Device.objects.filter(
                status__in=['AVAILABLE', 'IN_USE']
            ).exclude(
                assignments__is_active=True
            )
        
        # Filter active staff
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(is_active=True)
    
    def clean(self):
        """Validate assignment logic"""
        cleaned_data = super().clean()
        assignment_type = cleaned_data.get('assignment_type')
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        device = cleaned_data.get('device')
        
        # Ensure at least one assignment target is selected
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("Please select at least one assignment target (staff, department, or location).")
        
        # For personal assignments, staff must be selected
        if assignment_type == 'PERSONAL' and not assigned_to_staff:
            raise ValidationError("Personal assignments must have a staff member selected.")
        
        # For temporary assignments, return date is required
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        # Return date should be in the future
        if expected_return_date and expected_return_date <= timezone.now().date():
            raise ValidationError("Expected return date must be in the future.")
        
        # Check if device is already assigned
        if device and device.assignments.filter(is_active=True).exists():
            raise ValidationError("This device is already assigned. Please return it first.")

class BulkAssignmentForm(forms.Form):
    """Form for bulk device assignments"""
    assignment_type = forms.ChoiceField(
        choices=Assignment.ASSIGNMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select Staff Member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select Location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    purpose = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    is_temporary = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        
        # At least one assignment target must be selected
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("Please select at least one assignment target.")
        
        # Temporary assignments need return date
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        return cleaned_data

class MaintenanceScheduleForm(forms.ModelForm):
    """Form for scheduling maintenance"""
    
    class Meta:
        model = MaintenanceSchedule
        fields = [
            'device', 'maintenance_type', 'title', 'description',
            'scheduled_date', 'scheduled_time', 'estimated_duration',
            'vendor', 'technician_name', 'technician_contact',
            'estimated_cost', 'parts_used'
        ]
        
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'estimated_duration': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'e.g., 2:30:00 for 2 hours 30 minutes'
            }),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'technician_name': forms.TextInput(attrs={'class': 'form-control'}),
            'technician_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_cost': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'min': '0'
            }),
            'parts_used': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active vendors
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['scheduled_date'].initial = timezone.now().date()

class LocationForm(forms.ModelForm):
    """Form for managing locations"""
    
    # Additional fields for easier navigation
    building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
        empty_label="Select Building",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_building'})
    )
    
    floor = forms.ModelChoiceField(
        queryset=Floor.objects.none(),
        empty_label="Select Floor",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_floor'})
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_department'})
    )
    
    class Meta:
        model = Location
        fields = [
            'room', 'name', 'location_code', 'location_type',
            'coordinates', 'capacity', 'description', 'is_active'
        ]
        
        widgets = {
            'room': forms.Select(attrs={'class': 'form-control', 'id': 'id_room'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location_code': forms.TextInput(attrs={'class': 'form-control'}),
            'location_type': forms.Select(attrs={'class': 'form-control'}),
            'coordinates': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing location, populate hierarchical fields
        if self.instance.pk:
            room = self.instance.room
            if room:
                department = room.department
                floor = department.floor
                building = floor.building
                
                self.fields['building'].initial = building
                self.fields['floor'].queryset = Floor.objects.filter(building=building)
                self.fields['floor'].initial = floor
                self.fields['department'].queryset = Department.objects.filter(floor=floor)
                self.fields['department'].initial = department
                self.fields['room'].queryset = Room.objects.filter(department=department)

class StaffForm(forms.ModelForm):
    """Form for managing staff members"""
    
    class Meta:
        model = Staff
        fields = [
            'user', 'employee_id', 'full_name', 'designation',
            'department', 'phone', 'email', 'extension',
            'reporting_manager', 'security_clearance', 'date_joined', 'is_active'
        ]
        
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'extension': forms.TextInput(attrs={'class': 'form-control'}),
            'reporting_manager': forms.Select(attrs={'class': 'form-control'}),
            'security_clearance': forms.Select(attrs={'class': 'form-control'}),
            'date_joined': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show users without staff profiles for new staff
        if not self.instance.pk:
            self.fields['user'].queryset = User.objects.filter(staff_profile__isnull=True)
        
        # Reporting manager should be from the same or higher department
        self.fields['reporting_manager'].queryset = Staff.objects.filter(is_active=True)
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['date_joined'].initial = timezone.now().date()
    
    def clean_employee_id(self):
        """Ensure employee ID is unique"""
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            existing = Staff.objects.filter(employee_id=employee_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A staff member with this employee ID already exists.")
        return employee_id

class VendorForm(forms.ModelForm):
    """Form for managing vendors"""
    
    class Meta:
        model = Vendor
        fields = [
            'name', 'vendor_code', 'vendor_type', 'contact_person',
            'phone', 'email', 'address', 'website', 'tax_id',
            'registration_number', 'performance_rating', 'is_active'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor_code': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor_type': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'performance_rating': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.1',
                'min': '0',
                'max': '5'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_vendor_code(self):
        """Ensure vendor code is unique"""
        vendor_code = self.cleaned_data.get('vendor_code')
        if vendor_code:
            existing = Vendor.objects.filter(vendor_code=vendor_code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A vendor with this code already exists.")
        return vendor_code
    
    def clean_performance_rating(self):
        """Validate performance rating range"""
        rating = self.cleaned_data.get('performance_rating')
        if rating is not None and (rating < 0 or rating > 5):
            raise ValidationError("Performance rating must be between 0 and 5.")
        return rating

class DeviceTransferForm(forms.Form):
    """Form for transferring devices between locations/staff"""
    
    new_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select Staff Member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select Location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    transfer_reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3,
            'placeholder': 'Reason for transfer...'
        })
    )
    
    effective_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_staff = cleaned_data.get('new_staff')
        new_department = cleaned_data.get('new_department')
        new_location = cleaned_data.get('new_location')
        
        # At least one target must be selected
        if not any([new_staff, new_department, new_location]):
            raise ValidationError("Please select at least one transfer target.")
        
        return cleaned_data

class QuickSearchForm(forms.Form):
    """Quick search form for the header"""
    
    SEARCH_TYPES = [
        ('device', 'Device'),
        ('staff', 'Staff'),
        ('assignment', 'Assignment'),
        ('location', 'Location'),
    ]
    
    query = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Quick search...',
            'autocomplete': 'off'
        })
    )
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPES,
        initial='device',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class BulkImportForm(forms.Form):
    """Form for bulk importing data from CSV/Excel"""
    
    IMPORT_TYPES = [
        ('devices', 'Devices'),
        ('staff', 'Staff Members'),
        ('locations', 'Locations'),
        ('vendors', 'Vendors'),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        help_text="Upload CSV or Excel file"
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Update existing records if they match"
    )
    
    def clean_file(self):
        """Validate file type and size"""
        file = self.cleaned_data.get('file')
        if file:
            # Check file extension
            allowed_extensions = ['.csv', '.xlsx', '.xls']
            file_extension = '.' + file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise ValidationError("Only CSV and Excel files are allowed.")
            
            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("File size should not exceed 5MB.")
        
        return file

class DeviceFilterForm(forms.Form):
    """Advanced filtering form for devices"""
    
    category = forms.ModelChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.MultipleChoiceField(
        choices=Device.DEVICE_STATUS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    condition = forms.MultipleChoiceField(
        choices=Device.CONDITION_STATUS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        empty_label="All Vendors",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    purchase_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    purchase_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    warranty_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('active', 'Active Warranty'),
            ('expired', 'Expired Warranty'),
            ('expiring_soon', 'Expiring Soon (30 days)')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    price_min = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )
    
    price_max = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )
    
    is_critical = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        price_min = cleaned_data.get('price_min')
        price_max = cleaned_data.get('price_max')
        purchase_date_from = cleaned_data.get('purchase_date_from')
        purchase_date_to = cleaned_data.get('purchase_date_to')
        
        # Validate price range
        if price_min and price_max and price_min > price_max:
            raise ValidationError("Minimum price cannot be greater than maximum price.")
        
        # Validate date range
        if purchase_date_from and purchase_date_to and purchase_date_from > purchase_date_to:
            raise ValidationError("Start date cannot be after end date.")
        
        return cleaned_data