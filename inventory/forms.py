# inventory/forms.py
# Updated forms with Block hierarchy support

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import re
from django.db.models import Q
from .models import (
    Device, Assignment, Staff, Location, Building, Block, Floor, 
    Department, Room, DeviceType, DeviceCategory, DeviceSubCategory, 
    Vendor, MaintenanceSchedule
)

# ================================
# LOCATION HIERARCHY FORMS WITH BLOCK SUPPORT
# ================================

class BuildingForm(forms.ModelForm):
    """Form for creating and editing buildings"""
    
    class Meta:
        model = Building
        fields = ['name', 'code', 'address', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Building name (e.g., Bangladesh Parliament Secretariat - Main Building)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Building code (e.g., BPS-MAIN-BLDG)',
                'maxlength': 50
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Complete address of the building'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of the building and its purpose'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper()
        if code:
            # Check for duplicate code
            existing = Building.objects.filter(code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Building with code "{code}" already exists.')
        return code

class BlockForm(forms.ModelForm):
    """Form for creating and editing blocks within buildings"""
    
    class Meta:
        model = Block
        fields = ['name', 'code', 'building', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Block name (e.g., Administrative Block, East Wing)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Block code (e.g., ADMIN-BLK, EAST-WING)',
                'maxlength': 50
            }),
            'building': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of the block and its purpose'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['building'].queryset = Building.objects.filter(is_active=True)
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper()
        building = self.cleaned_data.get('building')
        
        if code and building:
            # Check for duplicate code within the same building
            existing = Block.objects.filter(code=code, building=building)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    f'Block with code "{code}" already exists in {building.name}.'
                )
        return code

class FloorForm(forms.ModelForm):
    """Form for creating and editing floors"""
    
    class Meta:
        model = Floor
        # CHANGE: Replace 'number' with 'floor_number'
        fields = ['floor_number', 'name', 'building', 'block', 'description', 'is_active']
        widgets = {
            # CHANGE: Replace 'number' with 'floor_number'
            'floor_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor number (e.g., 1, 2, 3)'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor name (e.g., Ground Floor, First Floor)'
            }),
            'building': forms.Select(attrs={'class': 'form-control'}),
            'block': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Floor description'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['building'].queryset = Building.objects.filter(is_active=True)
        self.fields['block'].queryset = Block.objects.filter(is_active=True)
        self.fields['block'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        # CHANGE: Replace 'number' with 'floor_number'
        floor_number = cleaned_data.get('floor_number')
        
        if block and building and block.building != building:
            raise ValidationError("Selected block does not belong to the selected building.")
        
        if building and floor_number is not None:
            # Check for duplicate floor number in building/block combination
            existing = Floor.objects.filter(
                building=building,
                block=block,
                # CHANGE: Replace 'number' with 'floor_number'
                floor_number=floor_number
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                location_str = f"{building.name}"
                if block:
                    location_str += f" - {block.name}"
                raise ValidationError(
                    f'Floor {floor_number} already exists in {location_str}.'
                )
        
        return cleaned_data

class DepartmentForm(forms.ModelForm):
    """Form for creating and editing departments with full hierarchy"""
    
    building = forms.ModelChoiceField(
        queryset=Building.objects.filter(is_active=True),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control cascade-parent',
            'data-cascade-target': 'block',
            'data-cascade-url': '/api/blocks/by-building/'
        })
    )
    
    block = forms.ModelChoiceField(
        queryset=Block.objects.none(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control cascade-child',
            'data-cascade-parent': 'building',
            'data-cascade-target': 'floor',
            'data-cascade-url': '/api/floors/by-block/'
        })
    )
    
    class Meta:
        model = Department
        fields = ['building', 'block', 'floor', 'name', 'code', 'head_of_department', 
                 'contact_email', 'contact_phone', 'is_active']
        widgets = {
            'floor': forms.Select(attrs={
                'class': 'form-control cascade-child',
                'data-cascade-parent': 'block',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Department name (e.g., Information Technology Department)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Department code (e.g., BPS-IT-DEPT)',
                'maxlength': 30
            }),
            'head_of_department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of department head/manager'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'department@parliament.gov.bd'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+880-2-XXXXXXX'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing department, populate hierarchy fields
        if self.instance.pk and self.instance.floor:
            self.fields['building'].initial = self.instance.floor.building
            self.fields['block'].initial = self.instance.floor.block
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.floor.building, 
                is_active=True
            )
            self.fields['floor'].queryset = Floor.objects.filter(
                block=self.instance.floor.block, 
                is_active=True
            )
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor = cleaned_data.get('floor')
        code = cleaned_data.get('code', '').upper()
        
        # Validate hierarchy consistency
        if building and block and block.building != building:
            raise ValidationError('Selected block does not belong to the selected building.')
        
        if block and floor and floor.block != block:
            raise ValidationError('Selected floor does not belong to the selected block.')
        
        # Check for duplicate department code within the same floor
        if floor and code:
            existing = Department.objects.filter(floor=floor, code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Department with code "{code}" already exists on {floor.name}.')
        
        cleaned_data['code'] = code
        return cleaned_data

class RoomForm(forms.ModelForm):
    """Form for creating and editing rooms"""
    
    class Meta:
        model = Room
        fields = ['department', 'room_number', 'room_name', 'capacity', 'is_active']
        widgets = {
            'department': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'room_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room number (e.g., IT-EB301, AD-WB201)'
            }),
            'room_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room name (e.g., IT Director Office, Server Room)'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100,
                'placeholder': 'Maximum occupancy'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active departments
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        room_number = cleaned_data.get('room_number', '').upper()
        
        # Check for duplicate room number within the same department
        if department and room_number:
            existing = Room.objects.filter(department=department, room_number=room_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Room "{room_number}" already exists in {department.name}.')
        
        cleaned_data['room_number'] = room_number
        return cleaned_data

class LocationForm(forms.ModelForm):
    """Enhanced location form with full block hierarchy support"""
    
    class Meta:
        model = Location
        fields = ['building', 'block', 'floor', 'department', 'room', 'description', 'is_active']
        widgets = {
            'building': forms.Select(attrs={
                'class': 'form-control cascade-parent',
                'data-cascade-target': 'block',
                'data-cascade-url': '/api/blocks/by-building/',
                'required': True
            }),
            'block': forms.Select(attrs={
                'class': 'form-control cascade-child',
                'data-cascade-parent': 'building',
                'data-cascade-target': 'floor',
                'data-cascade-url': '/api/floors/by-block/',
                'required': True
            }),
            'floor': forms.Select(attrs={
                'class': 'form-control cascade-child',
                'data-cascade-parent': 'block',
                'data-cascade-target': 'department',
                'data-cascade-url': '/api/departments/by-floor/',
                'required': True
            }),
            'department': forms.Select(attrs={
                'class': 'form-control cascade-child',
                'data-cascade-parent': 'floor',
                'data-cascade-target': 'room',
                'data-cascade-url': '/api/rooms/by-department/',
                'required': True
            }),
            'room': forms.Select(attrs={
                'class': 'form-control cascade-child',
                'data-cascade-parent': 'department'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional description for this location'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up querysets
        self.fields['building'].queryset = Building.objects.filter(is_active=True).order_by('name')
        
        # If editing existing location, populate cascade dropdowns
        if self.instance.pk:
            if self.instance.building:
                self.fields['block'].queryset = Block.objects.filter(
                    building=self.instance.building, is_active=True
                ).order_by('name')
            if self.instance.block:
                self.fields['floor'].queryset = Floor.objects.filter(
                    block=self.instance.block, is_active=True
                ).order_by('floor_number')
            if self.instance.floor:
                self.fields['department'].queryset = Department.objects.filter(
                    floor=self.instance.floor, is_active=True
                ).order_by('name')
            if self.instance.department:
                self.fields['room'].queryset = Room.objects.filter(
                    department=self.instance.department, is_active=True
                ).order_by('room_number')
        else:
            # For new locations, start with empty querysets
            self.fields['block'].queryset = Block.objects.none()
            self.fields['floor'].queryset = Floor.objects.none()
            self.fields['department'].queryset = Department.objects.none()
            self.fields['room'].queryset = Room.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor = cleaned_data.get('floor')
        department = cleaned_data.get('department')
        room = cleaned_data.get('room')
        
        # Validate hierarchy consistency
        if building and block and block.building != building:
            raise ValidationError('Selected block does not belong to the selected building.')
        
        if block and floor and floor.block != block:
            raise ValidationError('Selected floor does not belong to the selected block.')
        
        if floor and department and department.floor != floor:
            raise ValidationError('Selected department does not belong to the selected floor.')
        
        if department and room and room.department != department:
            raise ValidationError('Selected room does not belong to the selected department.')
        
        # Check for duplicate location
        if building and block and floor and department:
            existing = Location.objects.filter(
                building=building,
                block=block,
                floor=floor,
                department=department,
                room=room
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('A location with this exact hierarchy already exists.')
        
        return cleaned_data

# ================================
# UPDATED STAFF FORM WITH DEPARTMENT HIERARCHY
# ================================

class StaffForm(forms.ModelForm):
    """Enhanced staff form with department hierarchy display"""
    
    class Meta:
        model = Staff
        fields = ['user', 'employee_id', 'designation', 'department', 'phone_number', 'joining_date', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Employee ID'
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Job designation'
            }),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+880-1XXXXXXXXX'
            }),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show users without staff profiles and active departments
        self.fields['user'].queryset = User.objects.filter(staff__isnull=True)
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        
        # If editing, include current user
        if self.instance.pk and self.instance.user:
            self.fields['user'].queryset = User.objects.filter(
                Q(staff__isnull=True) | Q(pk=self.instance.user.pk)
            )

# ================================
# UPDATED ASSIGNMENT FORM WITH LOCATION HIERARCHY
# ================================

class AssignmentForm(forms.ModelForm):
    """Enhanced assignment form with location hierarchy support"""
    
    class Meta:
        model = Assignment
        fields = [
            'device', 
            'assigned_to_staff', 
            'assigned_to_department', 
            'assigned_to_location', 
            'assignment_type',
            'purpose', 
            'expected_return_date', 
            'notes'
        ]
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_staff': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_assigned_to_staff'
            }),
            'assigned_to_department': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_assigned_to_department'
            }),
            'assigned_to_location': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_assigned_to_location'
            }),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Purpose of assignment'
            }),
            'expected_return_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter querysets for better performance and relevant data
        self.fields['device'].queryset = Device.objects.filter(
            status='AVAILABLE'
        ).select_related('device_type', 'current_location')
        
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(
            is_active=True
        ).select_related('user', 'department')
        
        self.fields['assigned_to_location'].queryset = Location.objects.filter(
            is_active=True
        ).select_related('building', 'block', 'floor', 'department', 'room')
        
        # Make assignment target fields optional since only one is required
        self.fields['assigned_to_staff'].required = False
        self.fields['assigned_to_department'].required = False
        self.fields['assigned_to_location'].required = False
        
        # Set help texts
        self.fields['assigned_to_staff'].help_text = "Assign to a specific staff member"
        self.fields['assigned_to_department'].help_text = "Assign to department pool"
        self.fields['assigned_to_location'].help_text = "Assign to a specific location"
        
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least one assignment target is specified
        staff = cleaned_data.get('assigned_to_staff')
        department = cleaned_data.get('assigned_to_department')
        location = cleaned_data.get('assigned_to_location')
        
        if not any([staff, department, location]):
            raise ValidationError(
                "At least one assignment target must be specified "
                "(Staff, Department, or Location)."
            )
        
        # Validate expected return date
        expected_return = cleaned_data.get('expected_return_date')
        if expected_return and expected_return <= timezone.now().date():
            raise ValidationError(
                "Expected return date must be in the future."
            )
        
        return cleaned_data

# ================================
# DEVICE FORM (Updated to include current_location hierarchy)
# ================================

class DeviceForm(forms.ModelForm):
    """Enhanced device form with current location hierarchy"""
    
    class Meta:
        model = Device
        fields = [
            'device_id', 'device_name', 'device_type', 'brand', 'model',
            'serial_number', 'asset_tag', 'purchase_date', 'purchase_price',
            'location', 'status', 'device_condition', 'warranty_end_date',
            'processor', 'memory_ram', 'storage_capacity', 'operating_system',
            'is_critical', 'notes'
        ]
        widgets = {
            'device_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-generated if left blank'
            }),
            'device_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descriptive device name'
            }),
            'device_type': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Device brand/manufacturer'
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Model number/name'
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Serial number'
            }),
            'asset_tag': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Asset tag number'
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
            'location': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'device_condition': forms.Select(attrs={'class': 'form-control'}),
            'warranty_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_critical': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
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
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active locations with proper hierarchy
        self.fields['location'].queryset = Location.objects.filter(
            is_active=True
        ).select_related('building', 'block', 'floor', 'department', 'room')
        
        # Make device_id optional for auto-generation
        self.fields['device_id'].required = False

# ================================
# Vendor FORMS
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
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vendor name'
            }),
            'vendor_type': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Primary contact person'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'vendor@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1-234-567-8900'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Business address'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://vendor-website.com'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tax ID / Business registration number'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make name required
        self.fields['name'].required = True
        self.fields['vendor_type'].required = True
        
        # Add help text
        self.fields['name'].help_text = "Official vendor/supplier name"
        self.fields['vendor_type'].help_text = "Select the type of vendor"
        self.fields['contact_person'].help_text = "Primary contact person"
        self.fields['email'].help_text = "Primary email for communications"
        self.fields['phone'].help_text = "Include country code for international numbers"
        self.fields['website'].help_text = "Company website URL"
        self.fields['tax_id'].help_text = "Business registration or tax identification number"
        self.fields['is_active'].help_text = "Uncheck to deactivate this vendor"
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Check for duplicate vendor names
            existing = Vendor.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"A vendor with the name '{name}' already exists.")
        
        return name
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Basic email validation (Django's EmailField handles most cases)
            # Check for duplicate emails
            existing = Vendor.objects.filter(email__iexact=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"A vendor with the email '{email}' already exists.")
        
        return email
    
    def clean_website(self):
        website = self.cleaned_data.get('website')
        if website:
            # Ensure website starts with http:// or https://
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
        
        return website
    
    def clean(self):
        cleaned_data = super().clean()
        vendor_type = cleaned_data.get('vendor_type')
        email = cleaned_data.get('email')
        phone = cleaned_data.get('phone')
        
        # For certain vendor types, require contact information
        if vendor_type in ['SERVICE_PROVIDER', 'MAINTENANCE_CONTRACTOR', 'CONSULTANT']:
            if not email and not phone:
                raise ValidationError(
                    f"For {vendor_type.replace('_', ' ').title()} vendors, "
                    "either email or phone number is required."
                )
        
        return cleaned_data

# ================================
# CSVImport FORMS
# ================================

class CSVImportForm(forms.Form):
    """Form for importing data from CSV/Excel files"""
    
    IMPORT_TYPES = [
        ('devices', 'Devices'),
        ('staff', 'Staff'),
        ('locations', 'Locations'),
        ('assignments', 'Assignments'),
        ('vendors', 'Vendors'),
        ('buildings', 'Buildings'),
        ('departments', 'Departments'),
    ]
    
    # Import configuration
    import_type = forms.ChoiceField(
        choices=IMPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Data type to import"
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        }),
        label="Import file",
        help_text="Supported formats: CSV, Excel (.xlsx, .xls). Maximum size: 10MB"
    )
    
    # Import options
    skip_header = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="File has header row",
        help_text="Check if the first row contains column headers"
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Update existing records",
        help_text="Update existing records if duplicates are found"
    )
    
    validate_only = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Validate only (don't import)",
        help_text="Only validate the data without actually importing"
    )
    
    # Advanced options
    batch_size = forms.IntegerField(
        min_value=1,
        max_value=1000,
        initial=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '1000'
        }),
        label="Batch size",
        help_text="Number of records to process at once"
    )
    
    encoding = forms.ChoiceField(
        choices=[
            ('utf-8', 'UTF-8'),
            ('utf-16', 'UTF-16'),
            ('iso-8859-1', 'ISO-8859-1'),
            ('windows-1252', 'Windows-1252'),
        ],
        initial='utf-8',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="File encoding",
        help_text="Character encoding of the file"
    )
    
    delimiter = forms.ChoiceField(
        choices=[
            (',', 'Comma (,)'),
            (';', 'Semicolon (;)'),
            ('\t', 'Tab'),
            ('|', 'Pipe (|)'),
        ],
        initial=',',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="CSV delimiter",
        help_text="Character used to separate fields (for CSV files only)"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text for import types
        self.fields['import_type'].help_text = "Select the type of data you want to import"
    
    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        if file:
            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size cannot exceed 10MB.')
            
            # Validate file extension
            valid_extensions = ['.csv', '.xlsx', '.xls']
            file_ext = '.' + file.name.split('.')[-1].lower()
            
            if file_ext not in valid_extensions:
                raise ValidationError(
                    f'Invalid file format. Supported formats: {", ".join(valid_extensions)}'
                )
            
            # Basic file content validation
            if file.size == 0:
                raise ValidationError('The uploaded file is empty.')
        
        return file
    
    def clean_batch_size(self):
        batch_size = self.cleaned_data.get('batch_size')
        if batch_size and batch_size < 1:
            raise ValidationError('Batch size must be at least 1.')
        if batch_size and batch_size > 1000:
            raise ValidationError('Batch size cannot exceed 1000.')
        
        return batch_size
    
    def clean(self):
        cleaned_data = super().clean()
        import_type = cleaned_data.get('import_type')
        csv_file = cleaned_data.get('csv_file')
        
        # Additional validation can be added here based on import_type
        if import_type and csv_file:
            file_ext = '.' + csv_file.name.split('.')[-1].lower()
            
            # For certain import types, recommend specific formats
            if import_type in ['devices', 'staff'] and file_ext == '.csv':
                # CSV is good for these types
                pass
            elif import_type in ['locations', 'assignments'] and file_ext in ['.xlsx', '.xls']:
                # Excel is preferred for complex data
                pass
        
        return cleaned_data
# ================================
# ADDITIONAL UTILITY FORMS
# ================================

class DeviceSearchForm(forms.Form):
    """Advanced device search form"""
    
    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search devices...'
        })
    )
    
    device_type = forms.ModelChoiceField(
        queryset=DeviceType.objects.filter(is_active=True),
        required=False,
        empty_label="All Types",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Device.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="All Locations",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class AssignmentSearchForm(forms.Form):
    """Assignment search and filter form"""
    
    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search assignments...'
        })
    )
    
    assignment_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Assignment.ASSIGNMENT_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="All Staff",
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
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

# ================================
# SEARCH AND FILTER FORMS (Updated with Block Support)
# ================================

class AdvancedSearchForm(forms.Form):
    """Enhanced search form with block hierarchy"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search devices, assignments, staff...'
        })
    )
    
    building = forms.ModelChoiceField(
        queryset=Building.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control cascade-parent',
            'data-cascade-target': 'block'
        })
    )
    
    block = forms.ModelChoiceField(
        queryset=Block.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control cascade-child',
            'data-cascade-parent': 'building'
        })
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    device_type = forms.ModelChoiceField(
        queryset=DeviceType.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Device.STATUS_CHOICES,
        required=False,
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

# ================================
# MAINTENANCE AND SERVICE FORMS
# ================================

class MaintenanceScheduleForm(forms.ModelForm):
    """Form for scheduling device maintenance"""
    
    class Meta:
        model = MaintenanceSchedule
        fields = [
            'device', 'maintenance_type', 'next_due_date', 'assigned_technician',
            'estimated_duration', 'description', 'frequency', 'vendor', 
            'cost_estimate', 'status'
        ]
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'next_due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'assigned_technician': forms.Select(attrs={'class': 'form-control'}),
            'estimated_duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2 hours, 1 day'
            }),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Maintenance description'
            }),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'cost_estimate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active devices
        self.fields['device'].queryset = Device.objects.filter(
            status__in=['AVAILABLE', 'ASSIGNED']
        ).select_related('device_type', 'location')
        
        # Filter active technicians
        self.fields['assigned_technician'].queryset = Staff.objects.filter(
            is_active=True,
            role__in=['TECHNICIAN', 'MAINTENANCE', 'IT_SUPPORT']
        )
        
        # Filter maintenance vendors
        self.fields['vendor'].queryset = Vendor.objects.filter(
            vendor_type__in=['SERVICE_PROVIDER', 'MAINTENANCE_CONTRACTOR'],
            is_active=True
        )

# ================================
# QUICK ACTION FORMS
# ================================

class ReturnForm(forms.Form):
    """Simple form for returning devices"""
    
    return_date = forms.DateField(
        initial=timezone.now().date,
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
            'placeholder': 'Condition upon return'
        })
    )
    
    return_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Return notes'
        })
    )
    
    device_condition = forms.ChoiceField(
        choices=Device.CONDITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class TransferForm(forms.Form):
    """Simple form for transferring assignments"""
    
    new_assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select staff member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    transfer_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for transfer'
        })
    )
    
    conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Transfer conditions'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        staff = cleaned_data.get('new_assigned_to_staff')
        department = cleaned_data.get('new_assigned_to_department')
        location = cleaned_data.get('new_assigned_to_location')
        
        if not any([staff, department, location]):
            raise ValidationError(
                "At least one new assignment target must be specified."
            )
        
        return cleaned_data

# ================================
# SIMPLE CATEGORY FORMS
# ================================

class DeviceTypeForm(forms.ModelForm):
    """Simple form for device types"""
    
    class Meta:
        model = DeviceType
        fields = [
            'name', 'subcategory','description', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subcategory': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active subcategories
        self.fields['subcategory'].queryset = DeviceSubCategory.objects.filter(
            is_active=True,
            category__is_active=True
        ).select_related('category')
        
        # Add help text
        self.fields['subcategory'].help_text = "Select the subcategory for this device type"

# ================================
# BULK ACTION FORMS
# ================================

class BulkDeviceActionForm(forms.Form):
    """Form for bulk device actions"""
    
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

class BulkAssignmentForm(forms.Form):
    """Form for bulk assignment creation"""
    
    # Device selection
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.filter(status='AVAILABLE'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Select devices to assign"
    )
    
    # Assignment targets (at least one required)
    assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select staff member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="Select department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    assigned_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Assignment details
    is_temporary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Temporary assignment"
    )
    
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Expected return date"
    )
    
    purpose = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Purpose of assignment...'
        })
    )
    
    conditions = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Assignment conditions...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter devices to only available ones
        self.fields['devices'].queryset = Device.objects.filter(
            status='AVAILABLE'
        ).select_related('device_type', 'location')
        
        # Filter active staff and departments
        self.fields['assigned_to_staff'].queryset = Staff.objects.filter(is_active=True)
        self.fields['assigned_to_department'].queryset = Department.objects.filter(is_active=True)
        self.fields['assigned_to_location'].queryset = Location.objects.filter(
            is_active=True
        ).select_related('building', 'block', 'floor', 'department')
    
    def clean(self):
        cleaned_data = super().clean()
        devices = cleaned_data.get('devices')
        staff = cleaned_data.get('assigned_to_staff')
        department = cleaned_data.get('assigned_to_department')
        location = cleaned_data.get('assigned_to_location')
        is_temporary = cleaned_data.get('is_temporary')
        expected_return_date = cleaned_data.get('expected_return_date')
        
        # Validate at least one assignment target
        if not any([staff, department, location]):
            raise ValidationError(
                "At least one assignment target (staff, department, or location) must be specified."
            )
        
        # Validate devices are selected
        if not devices:
            raise ValidationError("At least one device must be selected for assignment.")
        
        # Validate expected return date for temporary assignments
        if is_temporary and not expected_return_date:
            raise ValidationError(
                "Expected return date is required for temporary assignments."
            )
        
        if expected_return_date and expected_return_date <= timezone.now().date():
            raise ValidationError(
                "Expected return date must be in the future."
            )
        
        return cleaned_data

# ================================
# Transfer FORMS
# ================================

class DeviceTransferForm(forms.Form):
    """Form for transferring device assignments"""
    
    # Source assignment (if transferring from existing assignment)
    source_assignment = forms.ModelChoiceField(
        queryset=Assignment.objects.filter(is_active=True),
        required=False,
        empty_label="Select current assignment",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Or select device directly
    device = forms.ModelChoiceField(
        queryset=Device.objects.filter(status__in=['ASSIGNED', 'AVAILABLE']),
        required=False,
        empty_label="Select device",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Transfer targets (at least one required)
    new_assigned_to_staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select staff member",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="Select department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_assigned_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Select location",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Transfer details
    transfer_type = forms.ChoiceField(
        choices=[
            ('permanent', 'Permanent Transfer'),
            ('temporary', 'Temporary Transfer'),
        ],
        initial='permanent',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Expected return date (for temporary transfers)"
    )
    
    transfer_reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for transfer...'
        })
    )
    
    conditions = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Transfer conditions...'
        })
    )
    
    # Approval workflow
    requires_approval = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Requires approval"
    )
    
    approved_by = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="Select approver",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active assignments
        self.fields['source_assignment'].queryset = Assignment.objects.filter(
            is_active=True
        ).select_related('device', 'assigned_to_staff', 'assigned_to_department')
        
        # Filter devices
        self.fields['device'].queryset = Device.objects.filter(
            status__in=['ASSIGNED', 'AVAILABLE']
        ).select_related('device_type')
        
        # Filter locations with hierarchy
        self.fields['new_assigned_to_location'].queryset = Location.objects.filter(
            is_active=True
        ).select_related('building', 'block', 'floor', 'department')
    
    def clean(self):
        cleaned_data = super().clean()
        source_assignment = cleaned_data.get('source_assignment')
        device = cleaned_data.get('device')
        staff = cleaned_data.get('new_assigned_to_staff')
        department = cleaned_data.get('new_assigned_to_department')
        location = cleaned_data.get('new_assigned_to_location')
        transfer_type = cleaned_data.get('transfer_type')
        expected_return_date = cleaned_data.get('expected_return_date')
        
        # Validate source (either assignment or device)
        if not any([source_assignment, device]):
            raise ValidationError(
                "Either a source assignment or device must be specified."
            )
        
        # Validate transfer target
        if not any([staff, department, location]):
            raise ValidationError(
                "At least one transfer target (staff, department, or location) must be specified."
            )
        
        # Validate return date for temporary transfers
        if transfer_type == 'temporary' and not expected_return_date:
            raise ValidationError(
                "Expected return date is required for temporary transfers."
            )
        
        if expected_return_date and expected_return_date <= timezone.now().date():
            raise ValidationError(
                "Expected return date must be in the future."
            )
        
        return cleaned_data

# Alias the correctly named forms
MaintenanceForm = MaintenanceScheduleForm