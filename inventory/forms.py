# inventory/forms.py - Complete Forms for Inventory Management

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import re
import json

from .models import (
    Device, DeviceCategory, DeviceSubCategory, DeviceType,
    Vendor, Assignment, Staff, Department, Location, Room,
    Building, Floor, User
)
# ================================
# DEVICE FORMS
# ================================

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
    
    specifications_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter specifications in JSON format or one per line:\nCPU: Intel Core i7\nRAM: 16GB\nStorage: 512GB SSD'
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
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OptiPlex 7090'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SN123456789'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00:1B:44:11:3A:B7'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.100'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_order_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PO-2024-001'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'warranty_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Standard, Extended, etc.'}),
            'support_contract': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'amc_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial category and subcategory based on device_type
        if self.instance and self.instance.pk and self.instance.device_type:
            self.fields['category'].initial = self.instance.device_type.subcategory.category
            self.fields['subcategory'].queryset = DeviceSubCategory.objects.filter(
                category=self.instance.device_type.subcategory.category
            )
            self.fields['subcategory'].initial = self.instance.device_type.subcategory
    
    def clean_mac_address(self):
        mac_address = self.cleaned_data.get('mac_address', '').strip()
        if mac_address:
            # Validate MAC address format
            mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
            if not re.match(mac_pattern, mac_address):
                raise ValidationError("Enter a valid MAC address (e.g., 00:1B:44:11:3A:B7)")
        return mac_address
    
    def clean(self):
        cleaned_data = super().clean()
        purchase_date = cleaned_data.get('purchase_date')
        warranty_start_date = cleaned_data.get('warranty_start_date')
        warranty_end_date = cleaned_data.get('warranty_end_date')
        
        # Purchase date should not be in the future
        if purchase_date and purchase_date > date.today():
            raise ValidationError("Purchase date cannot be in the future.")
        
        # Warranty start date should be after or equal to purchase date
        if purchase_date and warranty_start_date:
            if warranty_start_date < purchase_date:
                raise ValidationError("Warranty start date should be after or equal to purchase date.")
        
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
    search = forms.CharField(
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
    
    # FIXED: Using correct choice field names
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="All Locations",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        empty_label="All Vendors",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    warranty_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('active', 'Active Warranty'),
            ('expired', 'Expired Warranty'),
            ('expiring', 'Expiring Soon (30 days)')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assignment_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('assigned', 'Assigned'),
            ('unassigned', 'Unassigned')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # FIXED: Using correct choice field names
    condition = forms.ChoiceField(
        choices=[('', 'All Conditions')] + Device.CONDITION_CHOICES,
        required=False,
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

# ================================
# ASSIGNMENT FORMS
# ================================

class AssignmentForm(forms.ModelForm):
    """Form for creating/editing assignments"""
    
    class Meta:
        model = Assignment
        fields = [
            'device', 'assigned_to_staff', 'assigned_to_department', 
            'assigned_to_location', 'is_temporary', 'expected_return_date',
            'start_date', 'purpose', 'conditions', 'notes'
        ]
        
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_staff': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_department': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_location': forms.Select(attrs={'class': 'form-control'}),
            'is_temporary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expected_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control'}),
            'conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter devices to only show available ones for new assignments
        if not self.instance.pk:
            self.fields['device'].queryset = Device.objects.filter(status='AVAILABLE')
    
    def clean(self):
        cleaned_data = super().clean()
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        start_date = cleaned_data.get('start_date')
        
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        if start_date and start_date < date.today():
            raise ValidationError("Start date cannot be in the past.")
        
        if expected_return_date and start_date and expected_return_date <= start_date:
            raise ValidationError("Expected return date must be after start date.")
        
        return cleaned_data

class AssignmentSearchForm(forms.Form):
    """Form for searching assignments"""
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by device, staff, or department...'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All'), ('active', 'Active'), ('inactive', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assignment_type = forms.ChoiceField(
        choices=[('', 'All'), ('permanent', 'Permanent'), ('temporary', 'Temporary')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

class BulkAssignmentForm(forms.Form):
    """Form for bulk device assignment"""
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.filter(status='AVAILABLE'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select devices to assign"
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
    
    is_temporary = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    purpose = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    conditions = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        
        # Must assign to at least one target
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("Must assign to at least one of: Staff, Department, or Location.")
        
        # Temporary assignments need return date
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        return cleaned_data

class DeviceTransferForm(forms.Form):
    """Form for transferring device assignments"""
    new_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select New Staff Member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select New Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select New Location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    transfer_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Reason for transfer"
    )
    
    conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Any special conditions for the transfer"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_staff = cleaned_data.get('new_staff')
        new_department = cleaned_data.get('new_department')
        new_location = cleaned_data.get('new_location')
        
        # Must assign to at least one new target
        if not any([new_staff, new_department, new_location]):
            raise ValidationError("Must transfer to at least one of: Staff, Department, or Location.")
        
        return cleaned_data

class ReturnForm(forms.Form):
    """Form for returning devices"""
    
    return_date = forms.DateField(
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    return_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    return_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Any notes about the device condition or return process"
    )
    
    def clean_return_date(self):
        return_date = self.cleaned_data.get('return_date')
        if return_date and return_date > date.today():
            raise ValidationError("Return date cannot be in the future.")
        return return_date

# ================================
# STAFF FORMS
# ================================

class StaffForm(forms.ModelForm):
    """Form for staff members"""
    
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Staff
        fields = ['employee_id', 'department', 'designation', 'phone', 'extension', 'supervisor', 'joining_date', 'is_active']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'extension': forms.TextInput(attrs={'class': 'form-control'}),
            'supervisor': forms.Select(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ================================
# DEPARTMENT FORMS
# ================================

class DepartmentForm(forms.ModelForm):
    """Form for departments"""
    
    class Meta:
        model = Department
        fields = ['floor', 'name', 'head_of_department', 'contact_email', 'contact_phone', 'is_active']
        widgets = {
            'floor': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'head_of_department': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ================================
# LOCATION FORMS
# ================================

class LocationForm(forms.ModelForm):
    """Form for locations"""
    
    class Meta:
        model = Location
        fields = ['building', 'floor', 'department', 'room', 'description', 'is_active']
        widgets = {
            'building': forms.Select(attrs={'class': 'form-control'}),
            'floor': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ================================
# VENDOR FORMS
# ================================

class VendorForm(forms.ModelForm):
    """Form for vendors"""
    
    class Meta:
        model = Vendor
        fields = ['name', 'contact_person', 'email', 'phone', 'address', 'website', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ================================
# MAINTENANCE FORMS
# ================================

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

# ================================
# DEVICE TYPE FORMS
# ================================

class DeviceTypeForm(forms.ModelForm):
    """Form for device types"""
    
    class Meta:
        model = DeviceType
        fields = ['subcategory', 'name', 'code', 'description', 'typical_specifications', 'is_active']
        widgets = {
            'subcategory': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'typical_specifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
# ================================
# IMPORT/EXPORT FORMS
# ================================

class CSVImportForm(forms.Form):
    """Form for CSV file upload"""
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        help_text="Upload CSV, Excel (.xlsx) or Excel (.xls) file"
    )
    skip_header = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Skip the first row if it contains headers"
    )
    update_existing = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Update existing records if they match"
    )

class DeviceImportForm(forms.Form):
    """Form for importing devices from CSV/Excel"""
    
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        help_text="Upload CSV or Excel file with device data"
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Update existing devices if asset tag matches"
    )
    
    validate_only = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Only validate data without importing"
    )

class DeviceExportForm(forms.Form):
    """Form for exporting devices"""
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF Report'),
    ]
    
    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    include_specifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include technical specifications"
    )
    
    include_assignments = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include assignment information"
    )
    
    date_range_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text="Filter by purchase date from"
    )
    
    date_range_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text="Filter by purchase date to"
    )

# ================================
# ADVANCED SEARCH FORMS
# ================================

class AdvancedSearchForm(forms.Form):
    """Advanced search form"""
    
    SEARCH_TYPE_CHOICES = [
        ('all', 'All Items'),
        ('devices', 'Devices Only'),
        ('assignments', 'Assignments Only'),
        ('staff', 'Staff Only'),
        ('locations', 'Locations Only'),
        ('maintenance', 'Maintenance Only'),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search devices, assignments, staff, locations...',
            'autocomplete': 'off'
        }),
        help_text="Enter keywords to search across all fields"
    )
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        initial='all',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    category = forms.ModelChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter by date range (from)"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter by date range (to)"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date cannot be after end date.")
        
        return cleaned_data

# ================================
# DEVICE TYPE MANAGEMENT FORMS
# ================================

class DeviceCategoryForm(forms.ModelForm):
    """Form for device categories"""
    
    class Meta:
        model = DeviceCategory
        fields = ['name', 'category_type', 'description', 'icon', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fa-laptop'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class DeviceSubCategoryForm(forms.ModelForm):
    """Form for device subcategories"""
    
    class Meta:
        model = DeviceSubCategory
        fields = ['category', 'name', 'code', 'description', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        category = self.cleaned_data.get('category')
        
        if code and category:
            # Check for duplicate codes within the same category
            existing = DeviceSubCategory.objects.filter(
                category=category,
                code=code
            )
            
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"Code '{code}' already exists in this category.")
        
        return code

# ================================
# BACKUP & RECOVERY FORMS
# ================================

class DatabaseBackupForm(forms.Form):
    """Form for database backup options"""
    
    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Database Backup'),
        ('data_only', 'Data Only (No Schema)'),
        ('schema_only', 'Schema Only (No Data)'),
    ]
    
    backup_type = forms.ChoiceField(
        choices=BACKUP_TYPE_CHOICES,
        initial='full',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select the type of backup to create"
    )
    
    include_media = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include uploaded media files (QR codes, documents, etc.)"
    )
    
    include_logs = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include system logs and audit trails"
    )
    
    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description for this backup...'
        }),
        help_text="Add a description to identify this backup"
    )

class DatabaseRestoreForm(forms.Form):
    """Form for database restore options"""
    
    backup_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.zip,.sql,.json'
        }),
        help_text="Upload backup file (.zip, .sql, or .json)"
    )
    
    restore_data = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Restore data (WARNING: This will overwrite existing data)"
    )
    
    restore_media = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Restore media files"
    )
    
    create_backup_before_restore = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Create a backup of current data before restoring"
    )
    
    confirm_restore = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="I understand that this operation will overwrite existing data"
    )

# ================================
# BULK OPERATION FORMS
# ================================

class BulkDeviceActionForm(forms.Form):
    """Form for bulk device actions"""
    
    ACTION_CHOICES = [
        ('update_status', 'Update Status'),
        ('update_condition', 'Update Condition'),
        ('update_location', 'Update Location'),
        ('assign_devices', 'Assign Devices'),
        ('generate_qr', 'Generate QR Codes'),
        ('export_selected', 'Export Selected'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select action to perform on selected devices"
    )
    
    # FIXED: Using correct choice field names
    new_status = forms.ChoiceField(
        choices=Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # FIXED: Using correct choice field names
    new_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Fields for location update
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Fields for assignment
    assign_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assign_to_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assignment_purpose = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        # Validate required fields based on action
        if action == 'update_status' and not cleaned_data.get('new_status'):
            raise ValidationError("New status is required for status update action.")
        
        if action == 'update_condition' and not cleaned_data.get('new_condition'):
            raise ValidationError("New condition is required for condition update action.")
        
        if action == 'update_location' and not cleaned_data.get('new_location'):
            raise ValidationError("New location is required for location update action.")
        
        if action == 'assign_devices':
            if not cleaned_data.get('assign_to_staff') and not cleaned_data.get('assign_to_department'):
                raise ValidationError("Must assign to either staff or department.")
        
        return cleaned_data

# ================================
# NOTIFICATION FORMS
# ================================

class NotificationPreferencesForm(forms.Form):
    """Form for user notification preferences"""
    
    email_notifications = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Receive email notifications"
    )
    
    overdue_assignments = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Notify about overdue assignments"
    )
    
    warranty_alerts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Notify about expiring warranties"
    )
    
    maintenance_reminders = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Notify about upcoming maintenance"
    )
    
    assignment_updates = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Notify about assignment changes"
    )
    
    notification_frequency = forms.ChoiceField(
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Summary'),
        ],
        initial='daily',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How often to receive notifications"
    )