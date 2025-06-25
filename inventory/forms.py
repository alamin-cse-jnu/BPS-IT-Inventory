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
    MaintenanceSchedule, Building, Floor, User
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
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Latitude 5520'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00:00:00:00:00:00'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.100'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'warranty_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manufacturer, Extended, etc.'}),
            'support_contract': forms.TextInput(attrs={'class': 'form-control'}),
            'amc_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial category and subcategory if editing
        if self.instance.pk and self.instance.device_type:
            self.fields['category'].initial = self.instance.device_type.subcategory.category
            self.fields['subcategory'].queryset = DeviceSubCategory.objects.filter(
                category=self.instance.device_type.subcategory.category,
                is_active=True
            )
            self.fields['subcategory'].initial = self.instance.device_type.subcategory
            
            # Set device type queryset
            self.fields['device_type'].queryset = DeviceType.objects.filter(
                subcategory=self.instance.device_type.subcategory,
                is_active=True
            )
            
            # Convert specifications to text
            if self.instance.specifications:
                specs_text = "\n".join([f"{k}: {v}" for k, v in self.instance.specifications.items()])
                self.fields['specifications_text'].initial = specs_text
        else:
            self.fields['device_type'].queryset = DeviceType.objects.none()
    
    def clean_asset_tag(self):
        """Validate asset tag uniqueness"""
        asset_tag = self.cleaned_data.get('asset_tag')
        if asset_tag:
            existing = Device.objects.filter(asset_tag=asset_tag)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A device with this asset tag already exists.")
        return asset_tag
    
    def clean_serial_number(self):
        """Validate serial number uniqueness"""
        serial_number = self.cleaned_data.get('serial_number')
        if serial_number:
            existing = Device.objects.filter(serial_number=serial_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A device with this serial number already exists.")
        return serial_number
    
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
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter available devices
        self.fields['device'].queryset = Device.objects.filter(status='AVAILABLE')
        
        # Set initial start date to today
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now().date()
    
    def clean(self):
        """Validate assignment data"""
        cleaned_data = super().clean()
        device = cleaned_data.get('device')
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        start_date = cleaned_data.get('start_date')
        
        # Must assign to at least one target
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("Must assign to at least one of: Staff, Department, or Location.")
        
        # Check device availability
        if device and device.status != 'AVAILABLE':
            raise ValidationError(f"Device {device.device_id} is not available for assignment.")
        
        # Temporary assignments need return date
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        # Expected return date should be after start date
        if start_date and expected_return_date and expected_return_date <= start_date:
            raise ValidationError("Expected return date must be after start date.")
        
        return cleaned_data

class AssignmentSearchForm(forms.Form):
    """Form for searching assignments"""
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by Assignment ID, Device, or Staff name...'
        })
    )
    
    status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('overdue', 'Overdue')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assignment_type = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('permanent', 'Permanent'),
            ('temporary', 'Temporary')
        ],
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
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Condition of device upon return"
    )
    
    return_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Any notes about the return"
    )
    
    device_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Update device condition if needed"
    )

# ================================
# STAFF FORMS
# ================================

class StaffForm(forms.ModelForm):
    """Form for adding/editing staff members"""
    
    class Meta:
        model = Staff
        fields = [
            'employee_id', 'first_name', 'last_name', 'designation',
            'department', 'phone', 'email', 'reporting_manager',
            'hire_date', 'is_active'
        ]
        
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'reporting_manager': forms.Select(attrs={'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Exclude self from reporting manager choices
        if self.instance.pk:
            self.fields['reporting_manager'].queryset = Staff.objects.filter(
                is_active=True
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['reporting_manager'].queryset = Staff.objects.filter(is_active=True)
    
    def clean_employee_id(self):
        """Validate employee ID uniqueness"""
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            existing = Staff.objects.filter(employee_id=employee_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("A staff member with this employee ID already exists.")
        return employee_id

# ================================
# DEPARTMENT FORMS
# ================================

class DepartmentForm(forms.ModelForm):
    """Form for department management"""
    
    class Meta:
        model = Department
        fields = ['name', 'code', 'floor', 'head_of_department', 'contact_phone', 'contact_email']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.Select(attrs={'class': 'form-control'}),
            'head_of_department': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'})
        }

# ================================
# LOCATION FORMS
# ================================

class LocationForm(forms.ModelForm):
    """Form for location management"""
    
    class Meta:
        model = Location
        fields = [
            'name', 'location_code', 'room', 'location_type',
            'capacity', 'description', 'is_active'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location_code': forms.TextInput(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'location_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

# ================================
# VENDOR FORMS
# ================================

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
        fields = ['name', 'subcategory', 'description']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subcategory': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }