"""
QR Code Management Forms for BPS IT Inventory Management System
Forms for QR code generation, scanning, and management operations.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import re
import json

from inventory.models import Device, Location, Department, Staff
from .models import QRCodeScan


# ================================
# FORM UTILITIES AND VALIDATORS
# ================================

class QRDataValidator:
    """Utility class for validating QR code data"""
    
    @staticmethod
    def validate_qr_json_structure(data):
        """Validate that QR data has required structure"""
        required_fields = ['deviceId', 'lastUpdated']
        
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("QR data must be valid JSON.")
        
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"QR data missing required field: {field}")
        
        return data
    
    @staticmethod
    def validate_device_id_format(device_id):
        """Validate device ID format"""
        pattern = r'^[A-Z]{2,4}-[A-Z]{2}-\d{3,6}$'
        if not re.match(pattern, device_id):
            raise ValidationError(f"Invalid device ID format: {device_id}")
        
        return device_id


class QRFormMixin:
    """Mixin for QR-related forms with common functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add common styling
        for field_name, field in self.fields.items():
            if not field.widget.attrs.get('class'):
                if isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                    field.widget.attrs['class'] = 'form-check-input'
                else:
                    field.widget.attrs['class'] = 'form-control'
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Common date validation for forms with date fields
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("End date must be after start date.")
        
        return cleaned_data


# ================================
# QR CODE GENERATION FORMS
# ================================

class QRCodeGenerationForm(forms.Form):
    """Form for generating QR codes for devices"""
    
    QR_SIZES = [
        ('small', 'Small (100x100px)'),
        ('medium', 'Medium (200x200px)'),
        ('large', 'Large (300x300px)'),
        ('xlarge', 'Extra Large (500x500px)')
    ]
    
    QR_FORMATS = [
        ('png', 'PNG Image'),
        ('svg', 'SVG Vector'),
        ('pdf', 'PDF Document'),
        ('eps', 'EPS Vector')
    ]
    
    ERROR_CORRECTION_LEVELS = [
        ('L', 'Low (~7%)'),
        ('M', 'Medium (~15%)'),
        ('Q', 'Quartile (~25%)'),
        ('H', 'High (~30%)')
    ]
    
    # Device selection
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Select devices to generate QR codes for"
    )
    
    # QR Code configuration
    qr_size = forms.ChoiceField(
        choices=QR_SIZES,
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="QR code size"
    )
    
    qr_format = forms.ChoiceField(
        choices=QR_FORMATS,
        initial='png',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Output format"
    )
    
    error_correction = forms.ChoiceField(
        choices=ERROR_CORRECTION_LEVELS,
        initial='M',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Error correction level",
        help_text="Higher levels allow QR codes to be readable even when partially damaged"
    )
    
    # Label options
    include_device_info = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include device information below QR code"
    )
    
    include_asset_tag = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Show asset tag"
    )
    
    include_device_name = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Show device name"
    )
    
    include_organization_logo = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include organization logo"
    )


# ================================
# QR CODE SCANNING FORMS
# ================================

class QRCodeScanForm(forms.Form):
    """Form for scanning QR codes and recording scan data"""
    
    qr_data = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Paste QR code data here or scan using camera...'
        }),
        label="QR Code Data"
    )
    
    scan_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Scan location"
    )
    
    scan_purpose = forms.ChoiceField(
        choices=[
            ('verification', 'Device Verification'),
            ('audit', 'Audit Check'),
            ('maintenance', 'Maintenance Check'),
            ('inspection', 'Inspection'),
            ('other', 'Other')
        ],
        initial='verification',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes...'
        })
    )
    
    def clean_qr_data(self):
        qr_data = self.cleaned_data.get('qr_data')
        if qr_data:
            try:
                # Try to parse as JSON
                data = json.loads(qr_data)
                
                # Validate required fields
                if 'deviceId' not in data:
                    raise ValidationError("QR code data must contain deviceId field.")
                
                # Check if device exists
                if not Device.objects.filter(device_id=data['deviceId']).exists():
                    raise ValidationError(f"Device with ID '{data['deviceId']}' not found.")
                
                return data
                
            except json.JSONDecodeError:
                # If not JSON, assume it's a simple device ID
                device_id = qr_data.strip()
                if not Device.objects.filter(device_id=device_id).exists():
                    raise ValidationError(f"Device with ID '{device_id}' not found.")
                
                return {'deviceId': device_id}
        
        return qr_data


class QuickQRScanForm(forms.Form):
    """Quick QR scan form for AJAX requests"""
    
    qr_data = forms.CharField()
    scan_location_id = forms.IntegerField(required=False)
    
    def clean_qr_data(self):
        qr_data = self.cleaned_data.get('qr_data')
        
        try:
            if qr_data.startswith('{'):
                # JSON format
                data = json.loads(qr_data)
                device_id = data.get('deviceId')
            else:
                # Simple device ID
                device_id = qr_data.strip()
            
            if not Device.objects.filter(device_id=device_id).exists():
                raise ValidationError("Device not found.")
            
            return qr_data
        
        except (json.JSONDecodeError, AttributeError):
            raise ValidationError("Invalid QR code data.")


class MobileQRScanForm(forms.Form):
    """Simplified form for mobile QR scanning"""
    
    device_id = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    scan_timestamp = forms.DateTimeField(
        widget=forms.HiddenInput(),
        initial=timezone.now
    )
    
    location_coordinates = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="GPS coordinates from mobile device"
    )
    
    quick_note = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Quick note (optional)...'
        })
    )


# ================================
# EXPORT AND IMPORT FORMS
# ================================

class QRDataExportForm(forms.Form):
    """Form for exporting QR code data"""
    
    EXPORT_FORMATS = [
        ('csv', 'CSV File'),
        ('excel', 'Excel Spreadsheet'),
        ('json', 'JSON Data'),
        ('xml', 'XML Data')
    ]
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    include_scan_history = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include scan history"
    )
    
    include_device_details = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include device details"
    )
    
    date_range_filter = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Apply date range filter"
    )
    
    filter_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    filter_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


# ================================
# CUSTOM WIDGETS
# ================================

class QRCodePreviewWidget(forms.Widget):
    """Custom widget for previewing QR codes"""
    
    template_name = 'qr_management/widgets/qr_preview.html'
    
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs:
            self.device_id = attrs.get('device_id')


# ================================
# FORM CONSTANTS
# ================================

QR_SIZE_MAPPING = {
    'small': 100,
    'medium': 200,
    'large': 300,
    'xlarge': 500
}

ERROR_CORRECTION_MAPPING = {
    'L': 'qrcode.constants.ERROR_CORRECT_L',
    'M': 'qrcode.constants.ERROR_CORRECT_M',
    'Q': 'qrcode.constants.ERROR_CORRECT_Q',
    'H': 'qrcode.constants.ERROR_CORRECT_H'
}

# Default QR code data structure
DEFAULT_QR_DATA_STRUCTURE = {
    'deviceId': '',
    'assetTag': '',
    'deviceName': '',
    'category': '',
    'assignedTo': None,
    'assignedDepartment': None,
    'location': None,
    'lastUpdated': '',
    'verifyUrl': ''
}


# ================================
# PRINT LABEL FORMS
# ================================

class PrintLabelForm(forms.Form):
    """Form for generating printable QR code labels"""
    
    LABEL_SIZES = [
        ('small', '2" x 1" (51mm x 25mm)'),
        ('medium', '2.6" x 1" (66mm x 25mm)'),
        ('large', '4" x 2" (102mm x 51mm)'),
        ('custom', 'Custom Size')
    ]
    
    LABEL_LAYOUTS = [
        ('single', 'Single QR per label'),
        ('double', 'Two QRs per label'),
        ('grid_2x2', '2x2 Grid'),
        ('grid_3x3', '3x3 Grid')
    ]
    
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Select devices for labels"
    )
    
    label_size = forms.ChoiceField(
        choices=LABEL_SIZES,
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    layout = forms.ChoiceField(
        choices=LABEL_LAYOUTS,
        initial='single',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    custom_width = forms.DecimalField(
        required=False,
        decimal_places=1,
        max_digits=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Width in mm'
        })
    )
    
    custom_height = forms.DecimalField(
        required=False,
        decimal_places=1,
        max_digits=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Height in mm'
        })
    )
    
    include_text = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include device information text"
    )
    
    text_size = forms.ChoiceField(
        choices=[
            ('small', 'Small'),
            ('medium', 'Medium'),
            ('large', 'Large')
        ],
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    copies_per_device = forms.IntegerField(
        initial=1,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Number of copies'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        label_size = cleaned_data.get('label_size')
        custom_width = cleaned_data.get('custom_width')
        custom_height = cleaned_data.get('custom_height')
        
        if label_size == 'custom':
            if not custom_width or not custom_height:
                raise ValidationError("Custom width and height are required for custom label size.")
            
            if custom_width <= 0 or custom_height <= 0:
                raise ValidationError("Custom dimensions must be positive values.")
        
        return cleaned_data


# ================================
# QR CODE AUDIT FORMS
# ================================

class QRAuditForm(forms.Form):
    """Form for QR code audit and compliance checking"""
    
    AUDIT_TYPES = [
        ('full_audit', 'Full System Audit'),
        ('sample_audit', 'Sample-based Audit'),
        ('location_audit', 'Location-specific Audit'),
        ('department_audit', 'Department-specific Audit')
    ]
    
    COMPLIANCE_STANDARDS = [
        ('iso_27001', 'ISO 27001'),
        ('sox', 'Sarbanes-Oxley'),
        ('internal', 'Internal Policies'),
        ('custom', 'Custom Standard')
    ]
    
    audit_type = forms.ChoiceField(
        choices=AUDIT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    compliance_standard = forms.ChoiceField(
        choices=COMPLIANCE_STANDARDS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    audit_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    auditor_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Auditor name'
        })
    )
    
    # Audit scope
    sample_percentage = forms.IntegerField(
        initial=10,
        min_value=1,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Percentage of devices to audit'
        }),
        help_text="Only for sample-based audits"
    )
    
    specific_locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Specific locations (if applicable)"
    )
    
    specific_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Specific departments (if applicable)"
    )
    
    # Audit checks
    verify_qr_readability = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Verify QR code readability"
    )
    
    verify_data_accuracy = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Verify data accuracy"
    )
    
    verify_physical_presence = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Verify physical device presence"
    )
    
    verify_location_accuracy = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Verify location accuracy"
    )
    
    verify_assignment_status = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Verify assignment status"
    )
    
    # Report options
    generate_report = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Generate audit report"
    )
    
    include_photos = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include photos in report"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        audit_type = cleaned_data.get('audit_type')
        sample_percentage = cleaned_data.get('sample_percentage')
        specific_locations = cleaned_data.get('specific_locations')
        specific_departments = cleaned_data.get('specific_departments')
        
        if audit_type == 'sample_audit' and not sample_percentage:
            raise ValidationError("Sample percentage is required for sample-based audits.")
        
        if audit_type == 'location_audit' and not specific_locations:
            raise ValidationError("Specific locations must be selected for location audits.")
        
        if audit_type == 'department_audit' and not specific_departments:
            raise ValidationError("Specific departments must be selected for department audits.")
        
        return cleaned_data


# ================================
# QR CODE INTEGRATION FORMS
# ================================

class MobileAppIntegrationForm(forms.Form):
    """Form for configuring mobile app QR integration"""
    
    enable_mobile_scanning = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enable mobile QR scanning"
    )
    
    require_gps_location = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Require GPS location for scans"
    )
    
    allow_offline_scanning = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Allow offline scanning (sync later)"
    )
    
    api_key = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        }),
        help_text="API key for mobile app authentication"
    )
    
    rate_limit_per_hour = forms.IntegerField(
        initial=1000,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'API calls per hour'
        })
    )
    
    allowed_scan_types = forms.MultipleChoiceField(
        choices=[
            ('verification', 'Device Verification'),
            ('audit', 'Audit Scanning'),
            ('maintenance', 'Maintenance Checks'),
            ('inventory', 'Inventory Counts')
        ],
        initial=['verification', 'audit'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Allowed scan types in mobile app"
    )


# ================================
# ADVANCED QR FEATURES FORMS
# ================================

class QRCodeEncryptionForm(forms.Form):
    """Form for configuring QR code encryption settings"""
    
    ENCRYPTION_LEVELS = [
        ('none', 'No Encryption'),
        ('basic', 'Basic Encryption'),
        ('advanced', 'Advanced Encryption'),
        ('enterprise', 'Enterprise Grade')
    ]
    
    encryption_level = forms.ChoiceField(
        choices=ENCRYPTION_LEVELS,
        initial='basic',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    encrypt_device_ids = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Encrypt device IDs"
    )
    
    encrypt_assignment_data = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Encrypt assignment information"
    )
    
    encrypt_location_data = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Encrypt location information"
    )
    
    key_rotation_days = forms.IntegerField(
        initial=90,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Days between key rotation'
        })
    )
    
    backup_encryption_keys = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Backup encryption keys"
    )


class QRCodeCustomizationForm(forms.Form):
    """Form for customizing QR code appearance and branding"""
    
    # Logo settings
    include_logo = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include organization logo in QR code"
    )
    
    logo_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Upload logo image (PNG, JPG, SVG)"
    )
    
    logo_size_percentage = forms.IntegerField(
        initial=20,
        min_value=5,
        max_value=40,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Logo size as % of QR code'
        })
    )
    
    # Color customization
    foreground_color = forms.CharField(
        initial='#000000',
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'color'
        }),
        label="QR code color"
    )
    
    background_color = forms.CharField(
        initial='#FFFFFF',
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'color'
        }),
        label="Background color"
    )
    
    # Border and margin
    include_border = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include border around QR code"
    )
    
    border_width = forms.IntegerField(
        initial=4,
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Border width in pixels'
        })
    )
    
    margin_size = forms.IntegerField(
        initial=4,
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Margin size in modules'
        })
    )
    
    def clean_logo_file(self):
        logo_file = self.cleaned_data.get('logo_file')
        if logo_file:
            if not logo_file.content_type.startswith('image/'):
                raise ValidationError("Logo must be an image file.")
            
            if logo_file.size > 2 * 1024 * 1024:  # 2MB limit
                raise ValidationError("Logo file size cannot exceed 2MB.")
        
        return logo_file


# ================================
# QR CODE VERIFICATION FORMS
# ================================

class DeviceVerificationForm(forms.Form):
    """Form for device verification through QR scanning"""
    
    VERIFICATION_TYPES = [
        ('physical_check', 'Physical Device Check'),
        ('location_verify', 'Location Verification'),
        ('assignment_verify', 'Assignment Verification'),
        ('condition_check', 'Condition Assessment'),
        ('maintenance_check', 'Maintenance Check')
    ]
    
    CONDITION_OPTIONS = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged')
    ]
    
    device_id = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    verification_type = forms.ChoiceField(
        choices=VERIFICATION_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    device_present = forms.ChoiceField(
        choices=[
            ('yes', 'Device is present'),
            ('no', 'Device is missing'),
            ('relocated', 'Device has been moved')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Device status"
    )
    
    current_condition = forms.ChoiceField(
        choices=CONDITION_OPTIONS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Current condition"
    )
    
    location_confirmed = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Location matches records"
    )
    
    actual_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Actual location (if different)"
    )
    
    assignment_confirmed = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Assignment details are correct"
    )
    
    verification_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Verification notes and observations...'
        })
    )
    
    issues_found = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Describe any issues found...'
        })
    )
    
    photos_taken = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Photos taken for documentation"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        device_present = cleaned_data.get('device_present')
        location_confirmed = cleaned_data.get('location_confirmed')
        actual_location = cleaned_data.get('actual_location')
        
        if device_present == 'no':
            # If device is missing, certain fields should be cleared
            cleaned_data['current_condition'] = None
            cleaned_data['location_confirmed'] = False
        
        if not location_confirmed and not actual_location:
            raise ValidationError("Actual location must be specified when location doesn't match records.")
        
        return cleaned_data


class QRCodeValidationForm(forms.Form):
    """Form for validating QR code integrity and data"""
    
    qr_image = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label="QR Code Image",
        help_text="Upload an image containing the QR code to validate"
    )
    
    expected_device_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Expected device ID (optional)'
        }),
        help_text="If provided, will check if QR code matches this device"
    )
    
    validate_device_exists = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Validate that device exists in system"
    )
    
    check_assignment_status = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Check current assignment status"
    )
    
    def clean_qr_image(self):
        qr_image = self.cleaned_data.get('qr_image')
        if qr_image:
            # Validate file type
            if not qr_image.content_type.startswith('image/'):
                raise ValidationError("File must be an image.")
            
            # Validate file size (max 5MB)
            if qr_image.size > 5 * 1024 * 1024:
                raise ValidationError("Image file too large (max 5MB).")
        
        return qr_image


# ================================
# QR CODE MANAGEMENT FORMS
# ================================

class QRCodeBatchOperationForm(forms.Form):
    """Form for batch operations on QR codes"""
    
    BATCH_OPERATIONS = [
        ('regenerate', 'Regenerate QR Codes'),
        ('update_data', 'Update QR Code Data'),
        ('validate_all', 'Validate All QR Codes'),
        ('export_data', 'Export QR Code Data'),
        ('print_labels', 'Generate Print Labels')
    ]
    
    device_ids = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Comma-separated list of device IDs"
    )
    
    operation = forms.ChoiceField(
        choices=BATCH_OPERATIONS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Options for specific operations
    force_regenerate = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Force regenerate even if QR codes exist"
    )
    
    update_device_info = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Update device information in QR data"
    )
    
    include_assignment_data = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include current assignment data"
    )
    
    label_template = forms.ChoiceField(
        choices=[
            ('standard', 'Standard Label'),
            ('compact', 'Compact Label'),
            ('detailed', 'Detailed Label'),
            ('custom', 'Custom Template')
        ],
        initial='standard',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean_device_ids(self):
        device_ids = self.cleaned_data.get('device_ids')
        if device_ids:
            try:
                ids = [id.strip() for id in device_ids.split(',') if id.strip()]
                # Validate that all device IDs exist
                existing_devices = Device.objects.filter(device_id__in=ids)
                existing_ids = set(existing_devices.values_list('device_id', flat=True))
                
                invalid_ids = set(ids) - existing_ids
                if invalid_ids:
                    raise ValidationError(f"Invalid device IDs: {', '.join(invalid_ids)}")
                
                return ids
            except Exception as e:
                raise ValidationError(f"Error processing device IDs: {str(e)}")
        
        return []


class QRCodeConfigurationForm(forms.Form):
    """Form for configuring QR code system settings"""
    
    # QR Code generation settings
    default_qr_size = forms.ChoiceField(
        choices=[
            ('small', 'Small (100x100px)'),
            ('medium', 'Medium (200x200px)'),
            ('large', 'Large (300x300px)'),
            ('xlarge', 'Extra Large (500x500px)')
        ],
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    default_error_correction = forms.ChoiceField(
        choices=[
            ('L', 'Low (~7%)'),
            ('M', 'Medium (~15%)'),
            ('Q', 'Quartile (~25%)'),
            ('H', 'High (~30%)')
        ],
        initial='M',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    auto_generate_on_device_creation = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Automatically generate QR codes for new devices"
    )
    
    include_verification_url = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include verification URL in QR data"
    )
    
    # Data inclusion settings
    include_device_specifications = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include device specifications in QR data"
    )
    
    include_warranty_info = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include warranty information"
    )
    
    include_purchase_info = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include purchase information"
    )
    
    # Security settings
    encrypt_qr_data = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Encrypt sensitive data in QR codes"
    )
    
    require_authentication_for_verification = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Require authentication for QR verification"
    )
    
    # Scanning settings
    log_all_scans = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Log all QR code scans"
    )
    
    scan_rate_limit = forms.IntegerField(
        initial=100,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Scans per hour'
        }),
        help_text="Maximum scans per user per hour"
    )


# ================================
# QR CODE ANALYTICS FORMS
# ================================

class QRScanAnalyticsForm(forms.Form):
    """Form for generating QR scan analytics"""
    
    REPORT_TYPES = [
        ('scan_frequency', 'Scan Frequency Report'),
        ('device_popularity', 'Most Scanned Devices'),
        ('user_activity', 'User Scan Activity'),
        ('location_usage', 'Location-based Scanning'),
        ('time_analysis', 'Time-based Analysis')
    ]
    
    CHART_TYPES = [
        ('bar', 'Bar Chart'),
        ('line', 'Line Chart'),
        ('pie', 'Pie Chart'),
        ('heatmap', 'Heat Map')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        initial=timezone.now().date() - timedelta(days=30),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    chart_type = forms.ChoiceField(
        choices=CHART_TYPES,
        initial='bar',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Filters
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Filter by departments"
    )
    
    locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Filter by locations"
    )
    
    users = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Filter by users"
    )
    
    # Analysis options
    group_by_hour = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Group by hour of day"
    )
    
    group_by_day = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Group by day"
    )
    
    include_failed_scans = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include failed scan attempts"
    )


# ================================
# QR CODE HISTORY FILTER FORM
# ================================

class QRScanHistoryFilterForm(forms.Form):
    """Form for filtering QR scan history"""
    
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
    
    scanned_by = forms.ModelChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        empty_label="All users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    device_filter = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by device ID or name...'
        })
    )
    
    scan_purpose = forms.ChoiceField(
        choices=[('', 'All purposes')] + [
            ('verification', 'Device Verification'),
            ('audit', 'Audit Check'),
            ('maintenance', 'Maintenance Check'),
            ('inspection', 'Inspection'),
            ('other', 'Other')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="All locations",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# ================================
# END OF QR MANAGEMENT FORMS
# ================================