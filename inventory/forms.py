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
        fields = ['building', 'name', 'code', 'description', 'is_active']
        widgets = {
            'building': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Block name (e.g., East Block, West Block)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Block code (e.g., EB, WB, NB, SB)',
                'maxlength': 20
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of this block and its departments'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active buildings
        self.fields['building'].queryset = Building.objects.filter(is_active=True).order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        code = cleaned_data.get('code', '').upper()
        
        if building and code:
            # Check for duplicate code within the same building
            existing = Block.objects.filter(building=building, code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Block with code "{code}" already exists in {building.name}.')
        
        cleaned_data['code'] = code
        return cleaned_data

class FloorForm(forms.ModelForm):
    """Form for creating and editing floors with building and block hierarchy"""
    
    class Meta:
        model = Floor
        fields = ['building', 'block', 'name', 'floor_number', 'description', 'is_active']
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
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor name (e.g., Ground Floor, First Floor)'
            }),
            'floor_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 50,
                'placeholder': 'Floor number (0 for ground floor)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of this floor and its departments'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active buildings and blocks
        self.fields['building'].queryset = Building.objects.filter(is_active=True).order_by('name')
        
        # If editing, filter blocks by building
        if self.instance.pk and self.instance.building:
            self.fields['block'].queryset = Block.objects.filter(
                building=self.instance.building, 
                is_active=True
            ).order_by('name')
        else:
            self.fields['block'].queryset = Block.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        building = cleaned_data.get('building')
        block = cleaned_data.get('block')
        floor_number = cleaned_data.get('floor_number')
        
        # Validate block belongs to building
        if building and block and block.building != building:
            raise ValidationError('Selected block does not belong to the selected building.')
        
        # Check for duplicate floor number within the same block
        if building and block and floor_number is not None:
            existing = Floor.objects.filter(building=building, block=block, floor_number=floor_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(f'Floor {floor_number} already exists in {block.name}.')
        
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
        fields = ['device', 'staff', 'location', 'purpose', 'expected_return_date', 'notes']
        widgets = {
            'device': forms.Select(attrs={'class': 'form-control'}),
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.Select(attrs={'class': 'form-control'}),
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
        # Only show available devices, active staff, and active locations
        self.fields['device'].queryset = Device.objects.filter(status='AVAILABLE')
        self.fields['staff'].queryset = Staff.objects.filter(is_active=True).select_related('user', 'department')
        self.fields['location'].queryset = Location.objects.filter(is_active=True).select_related(
            'building', 'block', 'floor', 'department', 'room'
        )

# ================================
# DEVICE FORM (Updated to include current_location hierarchy)
# ================================

class DeviceForm(forms.ModelForm):
    """Enhanced device form with location hierarchy"""
    
    class Meta:
        model = Device
        fields = [
            'device_type', 'brand', 'model', 'serial_number', 'asset_tag',
            'purchase_date', 'purchase_price', 'vendor', 'warranty_end_date',
            'current_location', 'status', 'notes'
        ]
        widgets = {
            'device_type': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'asset_tag': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'warranty_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'current_location': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show locations with hierarchy information
        self.fields['current_location'].queryset = Location.objects.filter(is_active=True).select_related(
            'building', 'block', 'floor', 'department', 'room'
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