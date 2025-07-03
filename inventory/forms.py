
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import re

from .models import (
    Device, Assignment, Staff, Department, Location, Vendor,
    DeviceCategory, DeviceType, DeviceSubCategory, MaintenanceSchedule,
    Building, Room, AuditLog, Floor, Room
)


# ================================
# DEVICE MANAGEMENT FORMS
# ================================

class DeviceForm(forms.ModelForm):
    """Comprehensive form for creating and editing devices - CORRECTED FIELD MAPPING"""
    
    class Meta:
        model = Device
        fields = [
            'device_id', 'asset_tag', 'device_name', 'device_type', 'brand', 'model',
            'serial_number', 'processor', 'memory_ram', 'storage_capacity', 'operating_system',
            'purchase_date', 'purchase_price', 'vendor', 'warranty_start_date',
            'warranty_end_date', 'device_condition', 'status', 'location', 'notes',
            'is_critical'
        ]
        
        widgets = {
            'device_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., BPS-LT-001'
            }),
            'asset_tag': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., AT-2024-001'
            }),
            'device_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., HP EliteBook 840 G8'
            }),
            'device_type': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'processor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Intel Core i7-1165G7'
            }),
            'memory_ram': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 16GB DDR4'
            }),
            'storage_capacity': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 512GB SSD'
            }),
            'operating_system': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Windows 11 Pro'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'warranty_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'warranty_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'device_condition': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes about this device'
            }),
            'is_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
        labels = {
            'device_id': 'Device ID',
            'asset_tag': 'Asset Tag',
            'device_name': 'Device Name',
            'device_type': 'Device Type',
            'brand': 'Brand/Manufacturer',
            'model': 'Model',
            'serial_number': 'Serial Number',
            'processor': 'Processor/CPU',
            'memory_ram': 'Memory (RAM)',
            'storage_capacity': 'Storage',
            'operating_system': 'Operating System',
            'purchase_date': 'Purchase Date',
            'purchase_price': 'Purchase Price',
            'vendor': 'Vendor/Supplier',
            'warranty_start_date': 'Warranty Start Date',
            'warranty_end_date': 'Warranty End Date',
            'device_condition': 'Physical Condition',
            'status': 'Current Status',
            'location': 'Current Location',
            'notes': 'Additional Notes',
            'is_critical': 'Critical Infrastructure Device'
        }
        
        help_texts = {
            'device_id': 'Unique identifier for this device (auto-generated if left blank)',
            'asset_tag': 'Physical asset tag number attached to the device',
            'memory_ram': 'RAM specification (e.g., 16GB DDR4)',
            'storage_capacity': 'Storage specification (e.g., 512GB SSD)',
            'is_critical': 'Mark this device as critical infrastructure'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        self.fields['device_name'].required = True
        self.fields['device_type'].required = True
        
        # Filter active device types only
        if 'device_type' in self.fields:
            self.fields['device_type'].queryset = DeviceType.objects.filter(
                is_active=True
            ).select_related('subcategory__category')
        
        # Filter active vendors only
        if 'vendor' in self.fields:
            self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        
        # Filter active locations only
        if 'location' in self.fields:
            self.fields['location'].queryset = Location.objects.filter(is_active=True)
        
        # Add CSS classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'

    def clean_device_id(self):
        """Validate device ID format and uniqueness"""
        device_id = self.cleaned_data.get('device_id')
        
        if device_id:
            # Check format (BPS-XXXX-XXX pattern)
            import re
            if not re.match(r'^BPS-[A-Z0-9]+-[A-Z0-9]+$', device_id):
                raise ValidationError(
                    "Device ID must follow format: BPS-XXXX-XXX (e.g., BPS-LT-001)"
                )
            
            # Check uniqueness
            if Device.objects.filter(device_id=device_id).exclude(
                pk=self.instance.pk if self.instance else None
            ).exists():
                raise ValidationError("A device with this ID already exists.")
        
        return device_id

    def clean_asset_tag(self):
        """Validate asset tag uniqueness"""
        asset_tag = self.cleaned_data.get('asset_tag')
        
        if asset_tag:
            if Device.objects.filter(asset_tag=asset_tag).exclude(
                pk=self.instance.pk if self.instance else None
            ).exists():
                raise ValidationError("A device with this asset tag already exists.")
        
        return asset_tag

    def clean_serial_number(self):
        """Validate serial number"""
        serial_number = self.cleaned_data.get('serial_number')
        
        if serial_number:
            # Check for duplicates within same brand/model
            brand = self.cleaned_data.get('brand')
            model = self.cleaned_data.get('model')
            
            if brand and model:
                existing = Device.objects.filter(
                    serial_number=serial_number,
                    brand=brand,
                    model=model
                ).exclude(
                    pk=self.instance.pk if self.instance else None
                )
                
                if existing.exists():
                    raise ValidationError(
                        f"A {brand} {model} with this serial number already exists."
                    )
        
        return serial_number

    def clean_purchase_price(self):
        """Validate purchase price"""
        price = self.cleaned_data.get('purchase_price')
        
        if price is not None and price < 0:
            raise ValidationError("Purchase price cannot be negative.")
        
        return price

    def clean_warranty_end_date(self):
        """Validate warranty end date"""
        start_date = self.cleaned_data.get('warranty_start_date')
        end_date = self.cleaned_data.get('warranty_end_date')
        
        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError(
                    "Warranty end date cannot be before warranty start date."
                )
        
        return end_date

    def clean(self):
        """Perform cross-field validation"""
        cleaned_data = super().clean()
        
        # Validate purchase date
        purchase_date = cleaned_data.get('purchase_date')
        if purchase_date:
            from datetime import date
            if purchase_date > date.today():
                raise ValidationError({
                    'purchase_date': "Purchase date cannot be in the future."
                })
        
        # Validate warranty dates
        warranty_start = cleaned_data.get('warranty_start_date')
        warranty_end = cleaned_data.get('warranty_end_date')
        
        if warranty_start and warranty_end:
            if warranty_end <= warranty_start:
                raise ValidationError({
                    'warranty_end_date': "Warranty end date must be after start date."
                })
        
        return cleaned_data

    def save(self, commit=True):
        """Override save to auto-generate device ID if needed"""
        device = super().save(commit=False)
        
        # Auto-generate device ID if not provided
        if not device.device_id:
            device.device_id = self._generate_device_id()
        
        if commit:
            device.save()
            self.save_m2m()
        
        return device

    def _generate_device_id(self):
        """Generate a unique device ID"""
        from django.utils import timezone
        import random
        
        # Get device type prefix
        device_type = self.cleaned_data.get('device_type')
        if device_type and hasattr(device_type, 'code'):
            type_code = device_type.code.upper()
        else:
            type_code = 'DEV'
        
        # Generate ID with year and sequence
        current_year = timezone.now().year
        
        # Find next sequence number
        existing_devices = Device.objects.filter(
            device_id__startswith=f'BPS-{type_code}-{current_year}'
        ).count()
        
        sequence = existing_devices + 1
        
        # Generate device ID
        device_id = f'BPS-{type_code}-{current_year}-{sequence:03d}'
        
        # Ensure uniqueness
        while Device.objects.filter(device_id=device_id).exists():
            sequence += 1
            device_id = f'BPS-{type_code}-{current_year}-{sequence:03d}'
        
        return device_id


# ================================
# ASSIGNMENT MANAGEMENT FORMS
# ================================

class AssignmentForm(forms.ModelForm):
    """Comprehensive form for creating and editing assignments"""
    
    class Meta:
        model = Assignment
        fields = [
            'device', 'assignment_type', 'assigned_to_staff', 'assigned_to_department',
            'assigned_to_location', 'start_date', 'expected_return_date', 'purpose',
            'notes', 'is_temporary'
        ]
        
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_staff': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_department': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_location': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'expected_return_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Purpose of assignment...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes...'
            }),
            'is_temporary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set querysets for related fields
        self.fields['device'].queryset = Device.objects.filter(status='AVAILABLE')
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(is_active=True)
        self.fields['assigned_to_department'].queryset = Department.objects.all()
        self.fields['assigned_to_location'].queryset = Location.objects.filter(is_active=True)
        
        # Set default start date
        self.fields['start_date'].initial = timezone.now().date()
        
        # Make fields optional
        self.fields['assigned_to_staff'].required = False
        self.fields['assigned_to_department'].required = False
        self.fields['assigned_to_location'].required = False
        
        # Add help text
        self.fields['expected_return_date'].help_text = "Required for temporary assignments"
    
    def clean(self):
        cleaned_data = super().clean()
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        start_date = cleaned_data.get('start_date')
        
        # At least one assignment target must be specified
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("At least one assignment target (Staff, Department, or Location) must be specified.")
        
        # Temporary assignments require return date
        if is_temporary and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        # Return date must be after start date
        if start_date and expected_return_date:
            if expected_return_date <= start_date:
                raise ValidationError("Expected return date must be after start date.")
        
        return cleaned_data


class AssignmentSearchForm(forms.Form):
    """Form for searching and filtering assignments"""
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by device ID, staff name, or purpose...'
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
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="All Staff",
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignment_type'].choices = [('', 'All Types')] + Assignment.ASSIGNMENT_TYPES


class ReturnForm(forms.Form):
    """Form for returning assigned devices"""
    
    return_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    return_condition = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Condition upon return...'
        })
    )
    
    return_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Return notes and observations...'
        })
    )
    
    device_condition = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_condition'].choices = [('', 'No Change')] + Device.CONDITION_CHOICES
    
    def clean_return_date(self):
        return_date = self.cleaned_data.get('return_date')
        if return_date and return_date > timezone.now().date():
            raise ValidationError("Return date cannot be in the future.")
        return return_date


class DeviceTransferForm(forms.Form):
    """Form for transferring device assignments"""
    
    new_assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select Staff",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select Location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    transfer_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for transfer...'
        })
    )
    
    conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Transfer conditions and notes...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_staff = cleaned_data.get('new_assigned_to_staff')
        new_department = cleaned_data.get('new_assigned_to_department')
        new_location = cleaned_data.get('new_assigned_to_location')
        
        if not any([new_staff, new_department, new_location]):
            raise ValidationError("At least one new assignment target must be specified.")
        
        return cleaned_data


# ================================
# STAFF MANAGEMENT FORMS
# ================================

class StaffForm(forms.ModelForm):
    """Comprehensive form for creating and editing staff members"""
    
    # User fields
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Staff
        fields = [
            'employee_id', 'department', 'designation', 'employment_type',
            'phone_number', 'office_location', 'joining_date', 'leaving_date',
            'is_active'
        ]
        
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'office_location': forms.Select(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'leaving_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set querysets
        self.fields['department'].queryset = Department.objects.all()
        self.fields['office_location'].queryset = Location.objects.filter(is_active=True)
        
        # If editing existing staff, populate user fields
        if self.instance.pk and hasattr(self.instance, 'user'):
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['username'].initial = user.username
            self.fields['username'].widget.attrs['readonly'] = True
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            existing = Staff.objects.filter(employee_id=employee_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"Employee ID '{employee_id}' already exists.")
        
        return employee_id
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            existing = User.objects.filter(username=username)
            if self.instance.pk and hasattr(self.instance, 'user'):
                existing = existing.exclude(pk=self.instance.user.pk)
            
            if existing.exists():
                raise ValidationError(f"Username '{username}' already exists.")
        
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        joining_date = cleaned_data.get('joining_date')
        leaving_date = cleaned_data.get('leaving_date')
        
        if joining_date and leaving_date:
            if leaving_date <= joining_date:
                raise ValidationError("Leaving date must be after joining date.")
        
        return cleaned_data


# ================================
# LOCATION & DEPARTMENT FORMS
# ================================

class LocationForm(forms.ModelForm):
    """Form for creating and editing locations - FIXED FIELD MAPPING"""
    
    class Meta:
        model = Location
        fields = ['building', 'floor', 'department', 'room', 'description', 'is_active']
        
        widgets = {
            'building': forms.Select(attrs={'class': 'form-control'}),
            'floor': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional description of this location'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        self.fields['building'].required = True
        self.fields['floor'].required = True
        self.fields['department'].required = True
        self.fields['room'].required = False
        
        # Filter active records only
        self.fields['building'].queryset = Building.objects.filter(is_active=True)
        self.fields['floor'].queryset = Floor.objects.filter(is_active=True)
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['room'].queryset = Room.objects.filter(is_active=True)

    def clean(self):
        """Basic validation"""
        cleaned_data = super().clean()
        
        building = cleaned_data.get('building')
        floor = cleaned_data.get('floor')
        department = cleaned_data.get('department')
        room = cleaned_data.get('room')
        
        # Check for duplicate locations
        if building and floor and department:
            existing_location = Location.objects.filter(
                building=building,
                floor=floor,
                department=department,
                room=room
            )
            
            if self.instance.pk:
                existing_location = existing_location.exclude(pk=self.instance.pk)
            
            if existing_location.exists():
                raise ValidationError('A location with this combination already exists.')
        
        return cleaned_data  


class DepartmentForm(forms.ModelForm):
    """Form for creating and editing departments - FIXED FIELD MAPPING"""
    
    class Meta:
        model = Department
        fields = [
            'floor', 'name', 'code', 'head_of_department', 
            'contact_email', 'contact_phone', 'is_active'
        ]
        
        widgets = {
            'floor': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'head_of_department': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
        labels = {
            'floor': 'Floor',
            'name': 'Department Name',
            'code': 'Department Code',
            'head_of_department': 'Head of Department',
            'contact_email': 'Contact Email',
            'contact_phone': 'Contact Phone',
            'is_active': 'Active Department'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        self.fields['floor'].required = True
        self.fields['name'].required = True
        self.fields['code'].required = True
        
        # Filter active floors only
        self.fields['floor'].queryset = Floor.objects.filter(is_active=True)

    def clean_code(self):
        """Validate department code uniqueness within floor"""
        code = self.cleaned_data.get('code', '').upper()
        floor = self.cleaned_data.get('floor')
        
        if code and floor:
            existing = Department.objects.filter(floor=floor, code=code)
            
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("This department code already exists on the selected floor.")
        
        return code

    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        
        # Validate email format if provided
        email = cleaned_data.get('contact_email')
        if email:
            try:
                from django.core.validators import validate_email
                validate_email(email)
            except ValidationError:
                raise ValidationError({'contact_email': 'Please enter a valid email address.'})
        
        return cleaned_data


# ================================
# VENDOR MANAGEMENT FORMS
# ================================

class VendorForm(forms.ModelForm):
    """Form for creating and editing vendors"""
    
    class Meta:
        model = Vendor
        fields = [
            'name', 'vendor_type', 'contact_person', 'email', 'phone',
            'address', 'website', 'tax_id', 'is_active'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor_type': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


# ================================
# DEVICE TYPE & CATEGORY FORMS
# ================================

class DeviceCategoryForm(forms.ModelForm):
   """Form for device categories - FIXED FIELD MAPPING"""
   
   class Meta:
       model = DeviceCategory
       fields = ['name', 'description', 'is_active']
       
       widgets = {
           'name': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Enter category name (e.g., Computing Devices)'
           }),
           'description': forms.Textarea(attrs={
               'class': 'form-control', 
               'rows': 3,
               'placeholder': 'Describe this device category'
           }),
           'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
       }
       
       labels = {
           'name': 'Category Name',
           'description': 'Description',
           'is_active': 'Active Category'
       }
       
       help_texts = {
           'name': 'Enter a unique name for this device category',
           'description': 'Provide a detailed description of this category',
           'is_active': 'Uncheck to disable this category'
       }

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       
       # Set required fields
       self.fields['name'].required = True
       self.fields['description'].required = False

   def clean_name(self):
       """Validate category name uniqueness"""
       name = self.cleaned_data.get('name', '').strip()
       
       if name:
           existing = DeviceCategory.objects.filter(name__iexact=name)
           
           if self.instance.pk:
               existing = existing.exclude(pk=self.instance.pk)
           
           if existing.exists():
               raise ValidationError("A device category with this name already exists.")
       
       return name

   def clean(self):
       """Additional validation"""
       cleaned_data = super().clean()
       
       name = cleaned_data.get('name')
       if name and len(name.strip()) < 2:
           raise ValidationError({'name': 'Category name must be at least 2 characters long.'})
       
       return cleaned_data


class DeviceSubCategoryForm(forms.ModelForm):
    """Form for device subcategories - FIXED FIELD MAPPING"""
    
    class Meta:
        model = DeviceSubCategory
        fields = ['category', 'name', 'description', 'is_active']
        
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter subcategory name (e.g., Laptops)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Describe this device subcategory'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
        labels = {
            'category': 'Device Category',
            'name': 'Subcategory Name',
            'description': 'Description',
            'is_active': 'Active Subcategory'
        }
        
        help_texts = {
            'category': 'Select the parent device category',
            'name': 'Enter a unique name for this subcategory within the selected category',
            'description': 'Provide a detailed description of this subcategory',
            'is_active': 'Uncheck to disable this subcategory'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        self.fields['category'].required = True
        self.fields['name'].required = True
        self.fields['description'].required = False
        
        # Filter active categories only
        self.fields['category'].queryset = DeviceCategory.objects.filter(is_active=True)

    def clean_name(self):
        """Validate subcategory name uniqueness within category"""
        name = self.cleaned_data.get('name', '').strip()
        category = self.cleaned_data.get('category')
        
        if name and category:
            existing = DeviceSubCategory.objects.filter(
                category=category,
                name__iexact=name
            )
            
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"A subcategory with name '{name}' already exists in this category.")
        
        return name

    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        
        name = cleaned_data.get('name')
        if name and len(name.strip()) < 2:
            raise ValidationError({'name': 'Subcategory name must be at least 2 characters long.'})
        
        return cleaned_data


class DeviceTypeForm(forms.ModelForm):
   """Form for device types - FIXED FIELD MAPPING"""

   class Meta:
       model = DeviceType
       fields = ['subcategory', 'name', 'description', 'specifications_template', 'is_active']

       widgets = {
           'subcategory': forms.Select(attrs={'class': 'form-control'}),
           'name': forms.TextInput(attrs={'class': 'form-control'}),
           'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
           'specifications_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
           'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
       }

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       # Add placeholders for better UX
       self.fields['name'].widget.attrs['placeholder'] = 'Enter device type name'
       self.fields['description'].widget.attrs['placeholder'] = 'Provide a description'
       self.fields['specifications_template'].widget.attrs['placeholder'] = 'JSON format: {"key": "value"}'

       # Custom label override
       self.fields['is_active'].label = "Is this device type currently active?"
       
       # Filter active subcategories only
       self.fields['subcategory'].queryset = DeviceSubCategory.objects.filter(is_active=True)


# ================================
# MAINTENANCE MANAGEMENT FORMS
# ================================

class MaintenanceScheduleForm(forms.ModelForm):
   """Form for maintenance scheduling - FIXED FIELD MAPPING"""
   
   class Meta:
       model = MaintenanceSchedule
       fields = [
           'device', 'maintenance_type', 'description', 'vendor', 'status'
       ]
       
       widgets = {
           'device': forms.Select(attrs={'class': 'form-control'}),
           'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
           'description': forms.Textarea(attrs={
               'class': 'form-control',
               'rows': 3,
               'placeholder': 'Describe the maintenance work required'
           }),
           'vendor': forms.Select(attrs={'class': 'form-control'}),
           'status': forms.Select(attrs={'class': 'form-control'})
       }

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       
       # Filter active devices and vendors
       self.fields['device'].queryset = Device.objects.filter(status__in=['AVAILABLE', 'ASSIGNED', 'MAINTENANCE'])
       self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
       
       # Set required fields
       self.fields['device'].required = True
       self.fields['maintenance_type'].required = True
       self.fields['description'].required = True


# ================================
# BULK OPERATION FORMS
# ================================

class BulkDeviceActionForm(forms.Form):
    """Form for bulk device operations"""
    
    ACTION_CHOICES = [
        ('update_status', 'Update Status'),
        ('update_location', 'Update Location'),
        ('update_condition', 'Update Condition'),
        ('assign_vendor', 'Assign Vendor'),
        ('export_selected', 'Export Selected'),
        ('delete_selected', 'Delete Selected')
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Optional fields for specific actions
    new_status = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_condition = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_status'].choices = [('', 'Select Status')] + Device.STATUS_CHOICES
        self.fields['new_condition'].choices = [('', 'Select Condition')] + Device.CONDITION_CHOICES


class BulkAssignmentForm(forms.Form):
    """Form for bulk assignment creation"""
    
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.filter(status='AVAILABLE'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    assignment_type = forms.ChoiceField(
        choices=Assignment.ASSIGNMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select Staff",
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
    
    start_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    purpose = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Purpose of assignments...'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Assignment notes...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        assigned_to_staff = cleaned_data.get('assigned_to_staff')
        assigned_to_department = cleaned_data.get('assigned_to_department')
        assigned_to_location = cleaned_data.get('assigned_to_location')
        assignment_type = cleaned_data.get('assignment_type')
        expected_return_date = cleaned_data.get('expected_return_date')
        start_date = cleaned_data.get('start_date')
        
        # At least one assignment target must be specified
        if not any([assigned_to_staff, assigned_to_department, assigned_to_location]):
            raise ValidationError("At least one assignment target must be specified.")
        
        # Temporary assignments require return date
        if assignment_type == 'TEMPORARY' and not expected_return_date:
            raise ValidationError("Expected return date is required for temporary assignments.")
        
        # Validate date relationships
        if start_date and expected_return_date:
            if expected_return_date <= start_date:
                raise ValidationError("Expected return date must be after start date.")
        
        return cleaned_data


# ================================
# IMPORT/EXPORT FORMS
# ================================

class CSVImportForm(forms.Form):
    """Form for importing data from CSV files"""
    
    IMPORT_TYPES = [
        ('devices', 'Devices'),
        ('staff', 'Staff Members'),
        ('locations', 'Locations'),
        ('vendors', 'Vendors'),
        ('assignments', 'Assignments')
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text="Upload a CSV file with the appropriate columns."
    )
    
    has_header = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Check if the first row contains column headers."
    )
    
    update_existing = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Update existing records if they already exist."
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            if not csv_file.name.endswith('.csv'):
                raise ValidationError("File must be a CSV file.")
            
            if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size cannot exceed 5MB.")
        
        return csv_file


# ================================
# SEARCH AND FILTER FORMS
# ================================

class AdvancedSearchForm(forms.Form):
    """Advanced search form for complex queries"""
    
    SEARCH_TYPES = [
        ('devices', 'Devices'),
        ('assignments', 'Assignments'),
        ('staff', 'Staff'),
        ('maintenance', 'Maintenance Records')
    ]
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search_query = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter search terms...'
        })
    )
    
    date_field = forms.ChoiceField(
        choices=[
            ('', 'Select Date Field'),
            ('created_at', 'Created Date'),
            ('updated_at', 'Updated Date'),
            ('purchase_date', 'Purchase Date'),
            ('warranty_end_date', 'Warranty End Date')
        ],
        required=False,
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
    
    sort_by = forms.ChoiceField(
        choices=[
            ('', 'Default Sorting'),
            ('name', 'Name'),
            ('created_at', 'Created Date'),
            ('updated_at', 'Updated Date'),
            ('status', 'Status')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort_order = forms.ChoiceField(
        choices=[
            ('asc', 'Ascending'),
            ('desc', 'Descending')
        ],
        initial='desc',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# ================================
# REPORT GENERATION FORMS
# ================================

class ReportGenerationForm(forms.Form):
    """Form for generating custom reports"""
    
    REPORT_TYPES = [
        ('inventory_summary', 'Inventory Summary'),
        ('assignment_report', 'Assignment Report'),
        ('maintenance_schedule', 'Maintenance Schedule'),
        ('warranty_expiry', 'Warranty Expiry Report'),
        ('utilization_report', 'Device Utilization'),
        ('audit_trail', 'Audit Trail'),
        ('financial_summary', 'Financial Summary')
    ]
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel (XLSX)'),
        ('csv', 'CSV'),
        ('json', 'JSON')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='pdf',
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
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    include_inactive = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include inactive/disabled records in the report."
    )
    
    department_filter = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    location_filter = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )


# ================================
# SYSTEM CONFIGURATION FORMS
# ================================

class SystemConfigForm(forms.Form):
    """Form for system configuration settings"""
    
    auto_assign_device_ids = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Automatically generate device IDs for new devices."
    )
    
    device_id_prefix = forms.CharField(
        max_length=10,
        initial='BPS',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Prefix for auto-generated device IDs."
    )
    
    warranty_alert_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of days before warranty expiry to show alerts."
    )
    
    assignment_notification_enabled = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Send email notifications for new assignments."
    )
    
    maintenance_reminder_days = forms.IntegerField(
        initial=7,
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Days before maintenance to send reminders."
    )
    
    max_assignment_duration = forms.IntegerField(
        initial=365,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Maximum allowed assignment duration in days."
    )


# ================================
# AUTHENTICATION FORMS
# ================================

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'})
        }


class PasswordChangeForm(forms.Form):
    """Custom password change form"""
    
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Enter your current password."
    )
    
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Enter your new password."
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Confirm your new password."
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise ValidationError("Current password is incorrect.")
        return current_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match.")
        
        return cleaned_data


# ================================
# FORM MIXINS AND UTILITIES
# ================================

class DateRangeFormMixin:
    """Mixin for forms that need date range validation"""
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                raise ValidationError("Start date must be before end date.")
            
            # Limit date range to 2 years
            if (date_to - date_from).days > 730:
                raise ValidationError("Date range cannot exceed 2 years.")
        
        return cleaned_data


class RequiredFieldsMixin:
    """Mixin to mark specific fields as required"""
    
    required_fields = []
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True


# ================================
# DYNAMIC FORM UTILITIES
# ================================

def get_device_form_for_category(category_id):
    """Generate a dynamic device form based on category"""
    
    class DynamicDeviceForm(DeviceForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            # Filter device types based on category
            if category_id:
                self.fields['device_type'].queryset = DeviceType.objects.filter(
                    subcategory__category_id=category_id,
                    is_active=True
                )
    
    return DynamicDeviceForm


def get_assignment_form_for_user(user):
    """Generate an assignment form with user-specific permissions"""
    
    class UserSpecificAssignmentForm(AssignmentForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            # Limit device choices based on user permissions
            if not user.is_superuser:
                # Regular users can only assign available devices
                self.fields['device'].queryset = Device.objects.filter(
                    status='AVAILABLE'
                )
                
                # Limit staff choices to same department if applicable
                if hasattr(user, 'staff_profile') and user.staff_profile.department:
                    self.fields['assigned_to_staff'].queryset = Staff.objects.filter(
                        department=user.staff_profile.department,
                        is_active=True
                    )
    
    return UserSpecificAssignmentForm


# ================================
# AJAX AND DYNAMIC FORMS
# ================================

class QuickDeviceSearchForm(forms.Form):
    """Quick search form for AJAX device lookups"""
    
    query = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search devices...',
            'autocomplete': 'off'
        })
    )
    
    limit = forms.IntegerField(
        initial=10,
        min_value=1,
        max_value=50,
        widget=forms.HiddenInput()
    )


class DeviceStatusUpdateForm(forms.Form):
    """Form for quick device status updates"""
    
    device_ids = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Comma-separated list of device IDs"
    )
    
    new_status = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    update_reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason for status change...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_status'].choices = Device.STATUS_CHOICES
    
    def clean_device_ids(self):
        device_ids = self.cleaned_data.get('device_ids')
        if device_ids:
            try:
                ids = [int(id.strip()) for id in device_ids.split(',') if id.strip()]
                # Validate that all IDs exist
                existing_count = Device.objects.filter(id__in=ids).count()
                if existing_count != len(ids):
                    raise ValidationError("Some device IDs are invalid.")
                return ids
            except (ValueError, TypeError):
                raise ValidationError("Invalid device ID format.")
        return []


# ================================
# WORKFLOW AND APPROVAL FORMS
# ================================

class DeviceApprovalWorkflowForm(forms.Form):
    """Form for device approval workflows"""
    
    APPROVAL_ACTIONS = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('request_changes', 'Request Changes'),
        ('escalate', 'Escalate to Higher Authority')
    ]
    
    action = forms.ChoiceField(
        choices=APPROVAL_ACTIONS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    comments = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Add your comments...'
        }),
        help_text="Provide reasoning for your decision"
    )
    
    next_approver = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Required when escalating"
    )
    
    priority_level = forms.ChoiceField(
        choices=[
            ('normal', 'Normal'),
            ('high', 'High'),
            ('urgent', 'Urgent')
        ],
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        next_approver = cleaned_data.get('next_approver')
        
        if action == 'escalate' and not next_approver:
            raise ValidationError("Next approver is required when escalating.")
        
        return cleaned_data


# ================================
# NOTIFICATION FORMS
# ================================

class NotificationPreferencesForm(forms.Form):
    """Form for managing user notification preferences"""
    
    # Email notifications
    email_new_assignments = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="New device assignments"
    )
    
    email_assignment_reminders = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Assignment return reminders"
    )
    
    email_maintenance_alerts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Maintenance schedule alerts"
    )
    
    email_warranty_expiry = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Warranty expiry notifications"
    )
    
    # System notifications
    system_status_changes = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Device status changes"
    )
    
    system_new_devices = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="New device additions"
    )
    
    # Alert thresholds
    assignment_reminder_days = forms.IntegerField(
        initial=7,
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Days before due date'
        }),
        label="Assignment reminder threshold (days)"
    )
    
    warranty_alert_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Days before expiry'
        }),
        label="Warranty alert threshold (days)"
    )


# ================================
# FORM CONSTANTS AND UTILITIES
# ================================

COMMON_WIDGET_ATTRS = {
    'text': {'class': 'form-control'},
    'email': {'class': 'form-control'},
    'number': {'class': 'form-control'},
    'select': {'class': 'form-control'},
    'textarea': {'class': 'form-control', 'rows': 3},
    'checkbox': {'class': 'form-check-input'},
    'date': {'class': 'form-control', 'type': 'date'},
    'datetime': {'class': 'form-control', 'type': 'datetime-local'},
    'password': {'class': 'form-control'},
    'file': {'class': 'form-control'},
}


class FormValidationMixin:
    """Mixin for common form validation patterns"""
    
    def validate_unique_field(self, field_name, field_value, exclude_pk=None):
        """Validate that a field value is unique"""
        if field_value:
            queryset = self.Meta.model.objects.filter(**{field_name: field_value})
            if exclude_pk:
                queryset = queryset.exclude(pk=exclude_pk)
            
            if queryset.exists():
                raise ValidationError(f"A record with this {field_name} already exists.")
    
    def validate_date_not_future(self, date_value, field_name="date"):
        """Validate that a date is not in the future"""
        if date_value and date_value > timezone.now().date():
            raise ValidationError(f"{field_name.title()} cannot be in the future.")
    
    def validate_positive_number(self, number_value, field_name="number"):
        """Validate that a number is positive"""
        if number_value is not None and number_value <= 0:
            raise ValidationError(f"{field_name.title()} must be a positive number.")


# ================================
# FORM FACTORY FUNCTIONS
# ================================

def create_dynamic_device_form(category_filter=None, location_filter=None):
    """Create a dynamic device form with specific filters"""
    
    class DynamicDeviceForm(DeviceForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            if category_filter:
                self.fields['device_type'].queryset = DeviceType.objects.filter(
                    subcategory__category=category_filter,
                    is_active=True
                )
            
            if location_filter:
                self.fields['location'].queryset = Location.objects.filter(
                    id__in=location_filter,
                    is_active=True
                )
    
    return DynamicDeviceForm


def create_filtered_assignment_form(user_permissions=None):
    """Create an assignment form filtered by user permissions"""
    
    class FilteredAssignmentForm(AssignmentForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            if user_permissions:
                # Apply permission-based filtering
                if 'view_all_devices' not in user_permissions:
                    # Limit to devices in user's department/location
                    pass
                
                if 'assign_to_any_staff' not in user_permissions:
                    # Limit staff choices
                    pass
    
    return FilteredAssignmentForm


# ================================
# END OF FORMS MODULE
# ================================