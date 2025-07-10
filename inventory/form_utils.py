# inventory/form_utils.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date, timedelta
import re
import json


# ================================
# FORM MIXINS
# ================================

class DateValidationMixin:
    """Mixin for common date validation patterns"""
    
    def validate_date_range(self, start_date, end_date, field_prefix="date"):
        """Validate date range relationships"""
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(f"{field_prefix.title()} range is invalid: start date must be before end date")
            
            # Check for reasonable date ranges (not more than 5 years)
            if (end_date - start_date).days > 1825:
                raise ValidationError(f"{field_prefix.title()} range cannot exceed 5 years")
    
    def validate_date_not_future(self, date_value, field_name="Date"):
        """Validate that a date is not in the future"""
        if date_value and date_value > timezone.now().date():
            raise ValidationError(f"{field_name} cannot be in the future")
    
    def validate_date_not_past(self, date_value, field_name="Date", days_limit=30):
        """Validate that a date is not too far in the past"""
        if date_value:
            cutoff_date = timezone.now().date() - timedelta(days=days_limit)
            if date_value < cutoff_date:
                raise ValidationError(f"{field_name} cannot be more than {days_limit} days in the past")


class UniqueFieldValidationMixin:
    """Mixin for validating field uniqueness"""
    
    def validate_unique_field(self, model_class, field_name, value, exclude_pk=None):
        """Validate that a field value is unique in the model"""
        if value:
            queryset = model_class.objects.filter(**{field_name: value})
            if exclude_pk:
                queryset = queryset.exclude(pk=exclude_pk)
            
            if queryset.exists():
                raise ValidationError(f"A record with this {field_name.replace('_', ' ')} already exists")
    
    def validate_unique_together(self, model_class, field_dict, exclude_pk=None):
        """Validate unique_together constraints"""
        if all(field_dict.values()):
            queryset = model_class.objects.filter(**field_dict)
            if exclude_pk:
                queryset = queryset.exclude(pk=exclude_pk)
            
            if queryset.exists():
                fields = ', '.join(field_dict.keys())
                raise ValidationError(f"A record with this combination of {fields} already exists")


class NumberValidationMixin:
    """Mixin for number validation patterns"""
    
    def validate_positive_number(self, value, field_name="Number"):
        """Validate that a number is positive"""
        if value is not None and value <= 0:
            raise ValidationError(f"{field_name} must be a positive number")
    
    def validate_percentage(self, value, field_name="Percentage"):
        """Validate percentage values (0-100)"""
        if value is not None and not (0 <= value <= 100):
            raise ValidationError(f"{field_name} must be between 0 and 100")
    
    def validate_price(self, value, field_name="Price"):
        """Validate price values"""
        if value is not None:
            if value < 0:
                raise ValidationError(f"{field_name} cannot be negative")
            if value > 9999999.99:
                raise ValidationError(f"{field_name} is too large")


class TextValidationMixin:
    """Mixin for text validation patterns"""
    
    def validate_phone_number(self, value):
        """Validate Bangladesh phone number format"""
        if value:
            # Remove spaces, dashes, and plus signs
            cleaned = re.sub(r'[\s\-\+]', '', value)
            
            # Bangladesh phone patterns
            patterns = [
                r'^880[1-9]\d{8}$',  # +880 format
                r'^0[1-9]\d{8,10}$',  # Domestic format
                r'^[1-9]\d{8,10}$',   # Without leading 0
            ]
            
            if not any(re.match(pattern, cleaned) for pattern in patterns):
                raise ValidationError("Invalid phone number format")
    
    def validate_email_domain(self, email, allowed_domains=None):
        """Validate email domain"""
        if email and allowed_domains:
            domain = email.split('@')[1].lower() if '@' in email else ''
            if domain not in [d.lower() for d in allowed_domains]:
                raise ValidationError(f"Email domain must be one of: {', '.join(allowed_domains)}")
    
    def validate_bangladeshi_tin(self, tin):
        """Validate Bangladesh TIN format"""
        if tin:
            cleaned = re.sub(r'[\s\-]', '', tin)
            if not (cleaned.isdigit() and len(cleaned) in [12, 13]):
                raise ValidationError("TIN must be 12 or 13 digits")


# ================================
# CUSTOM FORM FIELDS
# ================================

class BangladeshPhoneField(forms.CharField):
    """Custom field for Bangladesh phone numbers"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            # Basic validation
            cleaned = re.sub(r'[\s\-\+]', '', value)
            patterns = [
                r'^880[1-9]\d{8}$',
                r'^0[1-9]\d{8,10}$',
                r'^[1-9]\d{8,10}$',
            ]
            
            if not any(re.match(pattern, cleaned) for pattern in patterns):
                raise ValidationError("Enter a valid Bangladesh phone number")
        
        return value


class DeviceIDField(forms.CharField):
    """Custom field for device IDs with automatic formatting"""
    
    def __init__(self, prefix='BPS', *args, **kwargs):
        self.prefix = prefix
        kwargs.setdefault('max_length', 50)
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            value = value.upper().strip()
            
            # Auto-add prefix if not present
            if not value.startswith(f'{self.prefix}-'):
                value = f'{self.prefix}-{value}'
            
            # Validate format
            pattern = r'^[A-Z]{2,5}-[A-Z0-9\-]+$'
            if not re.match(pattern, value):
                raise ValidationError(f"Device ID must follow format: {self.prefix}-XXX-XXX")
        
        return value


class AssetTagField(forms.CharField):
    """Custom field for asset tags"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 30)
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            value = value.upper().strip()
            
            # Validate format (alphanumeric with hyphens)
            pattern = r'^[A-Z0-9\-]+$'
            if not re.match(pattern, value):
                raise ValidationError("Asset tag can only contain letters, numbers, and hyphens")
        
        return value


class SerialNumberField(forms.CharField):
    """Custom field for serial numbers"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 100)
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            value = value.strip()
            
            # Remove common prefixes/suffixes
            prefixes = ['S/N:', 'SN:', 'Serial:', 'Serial Number:']
            for prefix in prefixes:
                if value.upper().startswith(prefix.upper()):
                    value = value[len(prefix):].strip()
        
        return value


class CoordinatesField(forms.CharField):
    """Custom field for GPS coordinates"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 50)
        kwargs.setdefault('help_text', 'Format: latitude, longitude (e.g., 23.7104, 90.4074)')
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            try:
                coords = [float(x.strip()) for x in value.split(',')]
                if len(coords) != 2:
                    raise ValueError
                
                lat, lng = coords
                if not (-90 <= lat <= 90):
                    raise ValidationError("Latitude must be between -90 and 90")
                if not (-180 <= lng <= 180):
                    raise ValidationError("Longitude must be between -180 and 180")
                
                return f"{lat}, {lng}"
            except (ValueError, TypeError):
                raise ValidationError("Enter coordinates as: latitude, longitude")
        
        return value

class BlockCodeField(forms.CharField):
    """Custom field for block codes with automatic formatting"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        kwargs.setdefault('help_text', 'Short code for block (e.g., EB, WB, NB, SB)')
        
        # Add custom widget attributes
        widget_attrs = kwargs.get('widget', forms.TextInput()).attrs
        widget_attrs.update({
            'style': 'text-transform: uppercase;',
            'pattern': '[A-Z0-9]{1,4}',
            'title': 'Enter 1-4 uppercase letters or numbers'
        })
        
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if value:
            # Auto-format to uppercase
            value = value.upper().strip()
            
            # Validate format
            import re
            if not re.match(r'^[A-Z0-9]{1,4}$', value):
                raise forms.ValidationError(
                    "Block code must be 1-4 uppercase letters or numbers (e.g., EB, WB)"
                )
        
        return value
# ================================
# CUSTOM WIDGETS
# ================================

class DatePickerWidget(forms.DateInput):
    """Enhanced date picker widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'date',
            'class': 'form-control date-picker'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DateTimePickerWidget(forms.DateTimeInput):
    """Enhanced datetime picker widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'datetime-local',
            'class': 'form-control datetime-picker'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class AutocompleteWidget(forms.TextInput):
    """Autocomplete widget for forms"""
    
    def __init__(self, autocomplete_url, min_length=2, *args, **kwargs):
        self.autocomplete_url = autocomplete_url
        self.min_length = min_length
        
        default_attrs = {
            'class': 'form-control autocomplete-input',
            'data-autocomplete-url': autocomplete_url,
            'data-min-length': min_length,
            'autocomplete': 'off'
        }
        
        attrs = kwargs.get('attrs', {})
        attrs.update(default_attrs)
        kwargs['attrs'] = attrs
        
        super().__init__(*args, **kwargs)


class TagInputWidget(forms.TextInput):
    """Widget for tag input with autocomplete"""
    
    def __init__(self, separator=',', *args, **kwargs):
        self.separator = separator
        
        default_attrs = {
            'class': 'form-control tag-input',
            'data-separator': separator,
            'placeholder': f'Enter tags separated by {separator}'
        }
        
        attrs = kwargs.get('attrs', {})
        attrs.update(default_attrs)
        kwargs['attrs'] = attrs
        
        super().__init__(*args, **kwargs)


class ColorPickerWidget(forms.TextInput):
    """Color picker widget"""
    
    def __init__(self, *args, **kwargs):
        default_attrs = {
            'type': 'color',
            'class': 'form-control color-picker'
        }
        
        attrs = kwargs.get('attrs', {})
        attrs.update(default_attrs)
        kwargs['attrs'] = attrs
        
        super().__init__(*args, **kwargs)


class FileUploadWidget(forms.ClearableFileInput):
    """Enhanced file upload widget with preview"""
    
    template_name = 'widgets/file_upload.html'
    
    def __init__(self, accepted_types=None, max_size=None, *args, **kwargs):
        self.accepted_types = accepted_types or []
        self.max_size = max_size
        
        default_attrs = {
            'class': 'form-control file-upload',
            'data-max-size': max_size or (5 * 1024 * 1024),  # 5MB default
        }
        
        if accepted_types:
            default_attrs['accept'] = ','.join(accepted_types)
        
        attrs = kwargs.get('attrs', {})
        attrs.update(default_attrs)
        kwargs['attrs'] = attrs
        
        super().__init__(*args, **kwargs)

class HierarchyDisplayWidget(forms.Widget):
    """Widget to display location hierarchy as breadcrumb"""
    
    template_name = 'widgets/hierarchy_display.html'
    
    def __init__(self, hierarchy_fields=None, separator=" → ", attrs=None):
        self.hierarchy_fields = hierarchy_fields or ['building', 'block', 'floor', 'department', 'room']
        self.separator = separator
        super().__init__(attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        if not value:
            return ""
        
        # Generate hierarchy breadcrumb
        breadcrumb = LocationHierarchyUtils.get_hierarchy_breadcrumb(value)
        
        context = {
            'widget': {
                'name': name,
                'value': value,
                'breadcrumb': breadcrumb,
                'separator': self.separator,
                'attrs': attrs or {}
            }
        }
        
        return self.render_template(context, renderer)
    
    def render_template(self, context, renderer=None):
        # Simple HTML rendering for hierarchy display
        breadcrumb = context['widget']['breadcrumb']
        attrs_str = ' '.join([f'{k}="{v}"' for k, v in context['widget']['attrs'].items()])
        
        return f'<div class="hierarchy-display" {attrs_str}>{breadcrumb}</div>'
# ================================
# FORM VALIDATORS
# ================================

def validate_device_id_format(value):
    """Validate device ID format"""
    pattern = r'^[A-Z]{2,5}-[A-Z0-9\-]+$'
    if not re.match(pattern, value):
        raise ValidationError("Device ID must follow format: PREFIX-XXX-XXX")


def validate_asset_tag_format(value):
    """Validate asset tag format"""
    pattern = r'^[A-Z0-9\-]+$'
    if not re.match(pattern, value):
        raise ValidationError("Asset tag can only contain letters, numbers, and hyphens")


def validate_bangladesh_phone(value):
    """Validate Bangladesh phone number"""
    if value:
        cleaned = re.sub(r'[\s\-\+]', '', value)
        patterns = [
            r'^880[1-9]\d{8}$',
            r'^0[1-9]\d{8,10}$',
            r'^[1-9]\d{8,10}$',
        ]
        
        if not any(re.match(pattern, cleaned) for pattern in patterns):
            raise ValidationError("Enter a valid Bangladesh phone number")


def validate_tin_number(value):
    """Validate Bangladesh TIN number"""
    if value:
        cleaned = re.sub(r'[\s\-]', '', value)
        if not (cleaned.isdigit() and len(cleaned) in [12, 13]):
            raise ValidationError("TIN must be 12 or 13 digits")


def validate_coordinates(value):
    """Validate GPS coordinates"""
    if value:
        try:
            coords = [float(x.strip()) for x in value.split(',')]
            if len(coords) != 2:
                raise ValueError
            
            lat, lng = coords
            if not (-90 <= lat <= 90):
                raise ValidationError("Latitude must be between -90 and 90")
            if not (-180 <= lng <= 180):
                raise ValidationError("Longitude must be between -180 and 180")
        except (ValueError, TypeError):
            raise ValidationError("Enter coordinates as: latitude, longitude")


# ================================
# FORM HELPERS
# ================================

class FormHelper:
    """Helper class for common form operations"""
    
    @staticmethod
    def add_css_classes(form, css_classes):
        """Add CSS classes to all form fields"""
        for field_name, field in form.fields.items():
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                new_classes = f"{existing_classes} {css_classes}".strip()
                field.widget.attrs['class'] = new_classes
    
    @staticmethod
    def add_placeholders(form, placeholders):
        """Add placeholders to form fields"""
        for field_name, placeholder in placeholders.items():
            if field_name in form.fields:
                form.fields[field_name].widget.attrs['placeholder'] = placeholder
    
    @staticmethod
    def make_fields_required(form, field_names):
        """Make specific fields required"""
        for field_name in field_names:
            if field_name in form.fields:
                form.fields[field_name].required = True
    
    @staticmethod
    def make_fields_readonly(form, field_names):
        """Make specific fields readonly"""
        for field_name in field_names:
            if field_name in form.fields:
                form.fields[field_name].widget.attrs['readonly'] = True
    
    @staticmethod
    def filter_choices(form, field_name, filter_func):
        """Filter choices for a choice field"""
        if field_name in form.fields:
            field = form.fields[field_name]
            if hasattr(field, 'choices'):
                field.choices = [choice for choice in field.choices if filter_func(choice)]
    
    @staticmethod
    def set_field_help_text(form, help_texts):
        """Set help text for form fields"""
        for field_name, help_text in help_texts.items():
            if field_name in form.fields:
                form.fields[field_name].help_text = help_text


def create_bootstrap_form(form_class, **kwargs):
    """Create a form with Bootstrap CSS classes"""
    form = form_class(**kwargs)
    
    # Add Bootstrap classes to all fields
    for field_name, field in form.fields.items():
        widget = field.widget
        
        if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.URLInput, 
                              forms.NumberInput, forms.DateInput, forms.TimeInput,
                              forms.DateTimeInput, forms.PasswordInput)):
            widget.attrs.update({'class': 'form-control'})
        elif isinstance(widget, forms.Textarea):
            widget.attrs.update({'class': 'form-control'})
        elif isinstance(widget, forms.Select):
            widget.attrs.update({'class': 'form-control'})
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs.update({'class': 'form-check-input'})
        elif isinstance(widget, forms.FileInput):
            widget.attrs.update({'class': 'form-control'})
    
    return form


# ================================
# DYNAMIC FORM CREATION
# ================================

def create_search_form(model_class, search_fields, filter_fields=None):
    """Dynamically create a search form for a model"""
    
    class DynamicSearchForm(forms.Form):
        search = forms.CharField(
            max_length=200,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': f'Search {", ".join(search_fields)}...'
            })
        )
    
    # Add filter fields if specified
    if filter_fields:
        for field_name, field_config in filter_fields.items():
            field_type = field_config.get('type', 'CharField')
            field_kwargs = field_config.get('kwargs', {})
            field_kwargs.setdefault('required', False)
            
            if field_type == 'ChoiceField':
                field = forms.ChoiceField(**field_kwargs)
            elif field_type == 'ModelChoiceField':
                field = forms.ModelChoiceField(**field_kwargs)
            elif field_type == 'DateField':
                field_kwargs.setdefault('widget', DatePickerWidget())
                field = forms.DateField(**field_kwargs)
            else:
                field = forms.CharField(**field_kwargs)
            
            setattr(DynamicSearchForm, field_name, field)
    
    return DynamicSearchForm


def create_bulk_action_form(actions, model_class=None):
    """Create a form for bulk actions"""
    
    class BulkActionForm(forms.Form):
        action = forms.ChoiceField(
            choices=[('', 'Select Action')] + actions,
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        selected_items = forms.CharField(
            widget=forms.HiddenInput(),
            help_text="Comma-separated list of selected item IDs"
        )
        
        confirm = forms.BooleanField(
            required=False,
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            help_text="Confirm bulk action"
        )
        
        def clean_selected_items(self):
            selected_items = self.cleaned_data.get('selected_items')
            if selected_items:
                try:
                    ids = [int(id.strip()) for id in selected_items.split(',') if id.strip()]
                    
                    # Validate IDs exist if model is provided
                    if model_class:
                        existing_count = model_class.objects.filter(id__in=ids).count()
                        if existing_count != len(ids):
                            raise ValidationError("Some selected items no longer exist")
                    
                    return ids
                except (ValueError, TypeError):
                    raise ValidationError("Invalid item selection")
            
            return []
    
    return BulkActionForm


# ================================
# FORM VALIDATION UTILITIES
# ================================

class ValidationUtils:
    """Utility functions for form validation"""
    
    @staticmethod
    def validate_file_size(file, max_size_mb=5):
        """Validate uploaded file size"""
        if file.size > max_size_mb * 1024 * 1024:
            raise ValidationError(f"File size cannot exceed {max_size_mb}MB")
    
    @staticmethod
    def validate_file_extension(file, allowed_extensions):
        """Validate uploaded file extension"""
        ext = file.name.split('.')[-1].lower()
        if ext not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationError(f"File must be one of: {', '.join(allowed_extensions)}")
    
    @staticmethod
    def validate_image_dimensions(image, max_width=None, max_height=None):
        """Validate image dimensions"""
        from PIL import Image
        
        try:
            img = Image.open(image)
            width, height = img.size
            
            if max_width and width > max_width:
                raise ValidationError(f"Image width cannot exceed {max_width} pixels")
            if max_height and height > max_height:
                raise ValidationError(f"Image height cannot exceed {max_height} pixels")
        except Exception:
            raise ValidationError("Invalid image file")
    
    @staticmethod
    def validate_json_field(value):
        """Validate JSON field data"""
        if value:
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format")
    
    @staticmethod
    def validate_password_strength(password):
        """Validate password strength"""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character")


# ================================
# FORM RENDERING UTILITIES
# ================================

class FormRenderer:
    """Utilities for rendering forms"""
    
    @staticmethod
    def render_field_with_label(field, label_class="", field_class="", wrapper_class=""):
        """Render a form field with custom classes"""
        from django.template.loader import render_to_string
        
        context = {
            'field': field,
            'label_class': label_class,
            'field_class': field_class,
            'wrapper_class': wrapper_class,
        }
        
        return render_to_string('forms/field.html', context)
    
    @staticmethod
    def render_form_errors(form, error_class="alert alert-danger"):
        """Render form errors with custom styling"""
        if form.errors:
            from django.template.loader import render_to_string
            
            context = {
                'form': form,
                'error_class': error_class,
            }
            
            return render_to_string('forms/errors.html', context)
        
        return ""
    
    @staticmethod
    def render_form_as_table(form, table_class="table"):
        """Render form as an HTML table"""
        from django.template.loader import render_to_string
        
        context = {
            'form': form,
            'table_class': table_class,
        }
        
        return render_to_string('forms/table.html', context)


# ================================
# FORM SECURITY UTILITIES
# ================================

class SecurityUtils:
    """Security utilities for forms"""
    
    @staticmethod
    def sanitize_input(value):
        """Sanitize user input to prevent XSS"""
        import html
        if isinstance(value, str):
            return html.escape(value.strip())
        return value
    
    @staticmethod
    def validate_csrf_token(request, form):
        """Additional CSRF validation"""
        from django.middleware.csrf import get_token
        
        if not get_token(request):
            raise ValidationError("Invalid security token")
    
    @staticmethod
    def rate_limit_check(request, action_key, max_attempts=5, window_minutes=15):
        """Check rate limiting for form submissions"""
        from django.core.cache import cache
        
        cache_key = f"rate_limit_{action_key}_{request.META.get('REMOTE_ADDR', 'unknown')}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= max_attempts:
            raise ValidationError(f"Too many attempts. Try again in {window_minutes} minutes.")
        
        cache.set(cache_key, attempts + 1, 60 * window_minutes)


# ================================
# EXPORT/IMPORT FORM UTILITIES
# ================================

class DataExportUtils:
    """Utilities for data export forms"""
    
    @staticmethod
    def create_export_form(model_class, export_formats=None):
        """Create a dynamic export form"""
        
        if export_formats is None:
            export_formats = [
                ('csv', 'CSV'),
                ('excel', 'Excel'),
                ('json', 'JSON'),
                ('pdf', 'PDF')
            ]
        
        class ExportForm(forms.Form):
            format = forms.ChoiceField(
                choices=export_formats,
                initial='csv',
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            
            include_headers = forms.BooleanField(
                initial=True,
                required=False,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            date_from = forms.DateField(
                required=False,
                widget=DatePickerWidget()
            )
            
            date_to = forms.DateField(
                required=False,
                widget=DatePickerWidget()
            )
        
        return ExportForm
    
    @staticmethod
    def create_import_form(model_class, required_fields=None):
        """Create a dynamic import form"""
        
        class ImportForm(forms.Form):
            file = forms.FileField(
                widget=FileUploadWidget(
                    accepted_types=['.csv', '.xlsx', '.json'],
                    max_size=5 * 1024 * 1024  # 5MB
                )
            )
            
            has_headers = forms.BooleanField(
                initial=True,
                required=False,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            update_existing = forms.BooleanField(
                initial=False,
                required=False,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            def clean_file(self):
                file = self.cleaned_data.get('file')
                if file:
                    ValidationUtils.validate_file_size(file, 5)
                    ValidationUtils.validate_file_extension(file, ['csv', 'xlsx', 'json'])
                
                return file
        
        return ImportForm


# ================================
# AJAX FORM UTILITIES
# ================================

class AjaxFormUtils:
    """Utilities for AJAX form handling"""
    
    @staticmethod
    def get_form_errors_json(form):
        """Convert form errors to JSON format"""
        errors = {}
        
        # Field errors
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]
        
        # Non-field errors
        if form.non_field_errors():
            errors['__all__'] = [str(error) for error in form.non_field_errors()]
        
        return errors
    
    @staticmethod
    def create_ajax_response(success=True, data=None, errors=None, message=""):
        """Create standardized AJAX response"""
        return {
            'success': success,
            'data': data or {},
            'errors': errors or {},
            'message': message
        }
    
    @staticmethod
    def handle_ajax_form_submission(request, form_class, success_callback=None):
        """Handle AJAX form submission"""
        if request.method == 'POST':
            form = form_class(request.POST, request.FILES)
            
            if form.is_valid():
                try:
                    result = success_callback(form) if success_callback else None
                    return AjaxFormUtils.create_ajax_response(
                        success=True,
                        data=result,
                        message="Operation completed successfully"
                    )
                except Exception as e:
                    return AjaxFormUtils.create_ajax_response(
                        success=False,
                        errors={'__all__': [str(e)]},
                        message="An error occurred"
                    )
            else:
                return AjaxFormUtils.create_ajax_response(
                    success=False,
                    errors=AjaxFormUtils.get_form_errors_json(form),
                    message="Please correct the errors below"
                )
        else:
            form = form_class()
        
        return {'form': form}


# ================================
# MOBILE FORM UTILITIES
# ================================

class MobileFormUtils:
    """Utilities for mobile-optimized forms"""
    
    @staticmethod
    def create_mobile_form(form_class, **kwargs):
        """Create a mobile-optimized version of a form"""
        form = form_class(**kwargs)
        
        # Add mobile-specific attributes
        for field_name, field in form.fields.items():
            widget = field.widget
            
            # Add mobile input types
            if isinstance(widget, forms.TextInput):
                if 'email' in field_name.lower():
                    widget.attrs['type'] = 'email'
                elif 'phone' in field_name.lower() or 'tel' in field_name.lower():
                    widget.attrs['type'] = 'tel'
                elif 'url' in field_name.lower() or 'website' in field_name.lower():
                    widget.attrs['type'] = 'url'
            
            # Add mobile-friendly classes
            existing_classes = widget.attrs.get('class', '')
            mobile_classes = 'form-control-lg mobile-input'
            widget.attrs['class'] = f"{existing_classes} {mobile_classes}".strip()
            
            # Add touch-friendly attributes
            widget.attrs.update({
                'autocomplete': 'on',
                'autocapitalize': 'words' if 'name' in field_name.lower() else 'off',
                'autocorrect': 'off',
                'spellcheck': 'false'
            })
        
        return form
    
    @staticmethod
    def add_qr_scanner_support(form, qr_fields):
        """Add QR code scanner support to specified fields"""
        for field_name in qr_fields:
            if field_name in form.fields:
                widget = form.fields[field_name].widget
                widget.attrs.update({
                    'data-qr-scanner': 'true',
                    'data-qr-field': field_name
                })


# ================================
# ACCESSIBILITY UTILITIES
# ================================

class AccessibilityUtils:
    """Utilities for improving form accessibility"""
    
    @staticmethod
    def add_aria_labels(form):
        """Add ARIA labels to form fields"""
        for field_name, field in form.fields.items():
            if not field.widget.attrs.get('aria-label'):
                label = field.label or field_name.replace('_', ' ').title()
                field.widget.attrs['aria-label'] = label
                
                if field.required:
                    field.widget.attrs['aria-required'] = 'true'
                
                if field.help_text:
                    field.widget.attrs['aria-describedby'] = f'{field_name}_help'
    
    @staticmethod
    def add_error_announcements(form):
        """Add ARIA live regions for error announcements"""
        for field_name, field in form.fields.items():
            if form.errors.get(field_name):
                field.widget.attrs.update({
                    'aria-invalid': 'true',
                    'aria-describedby': f'{field_name}_error'
                })
    
    @staticmethod
    def add_keyboard_navigation(form):
        """Improve keyboard navigation for forms"""
        for field_name, field in form.fields.items():
            widget = field.widget
            
            # Add tab index for better navigation
            if not widget.attrs.get('tabindex'):
                widget.attrs['tabindex'] = '0'
            
            # Add keyboard shortcuts for common actions
            if isinstance(widget, forms.widgets.Input):
                widget.attrs['data-keyboard-shortcuts'] = 'true'
    
    @staticmethod
    def add_hierarchy_navigation_aids(form):
        """Add navigation aids for hierarchical location forms"""
        hierarchy_fields = ['building', 'block', 'floor', 'department', 'room']
        
        for i, field_name in enumerate(hierarchy_fields):
            if field_name in form.fields:
                field = form.fields[field_name]
                
                # Add role and aria-level for screen readers
                field.widget.attrs.update({
                    'role': 'combobox',
                    'aria-level': str(i + 1),
                    'aria-expanded': 'false',
                    'aria-haspopup': 'listbox'
                })
                
                # Add description for hierarchy level
                hierarchy_descriptions = {
                    'building': 'Level 1: Select building',
                    'block': 'Level 2: Select block within building',
                    'floor': 'Level 3: Select floor within block',
                    'department': 'Level 4: Select department within floor',
                    'room': 'Level 5: Select room within department (optional)'
                }
                
                if field_name in hierarchy_descriptions:
                    existing_help = field.help_text or ""
                    field.help_text = f"{hierarchy_descriptions[field_name]}. {existing_help}".strip()


# ================================
# PERFORMANCE UTILITIES
# ================================

class PerformanceUtils:
    """Utilities for optimizing form performance"""
    
    @staticmethod
    def optimize_queryset_fields(form):
        """Optimize queryset fields to reduce database queries"""
        for field_name, field in form.fields.items():
            if isinstance(field, forms.ModelChoiceField):
                # Add select_related for foreign keys
                if hasattr(field.queryset.model, '_meta'):
                    related_fields = []
                    for f in field.queryset.model._meta.get_fields():
                        if f.is_relation and not f.many_to_many:
                            related_fields.append(f.name)
                    
                    if related_fields:
                        field.queryset = field.queryset.select_related(*related_fields[:3])  # Limit to 3 levels
    
    @staticmethod
    def add_lazy_loading(form, lazy_fields):
        """Add lazy loading support for specified fields"""
        for field_name in lazy_fields:
            if field_name in form.fields:
                widget = form.fields[field_name].widget
                widget.attrs.update({
                    'data-lazy-load': 'true',
                    'data-lazy-url': f'/api/lazy/{field_name}/'
                })
    
    @staticmethod
    def enable_client_side_caching(form, cache_fields):
        """Enable client-side caching for form data"""
        for field_name in cache_fields:
            if field_name in form.fields:
                widget = form.fields[field_name].widget
                widget.attrs.update({
                    'data-cache-enabled': 'true',
                    'data-cache-key': f'form_{form.__class__.__name__.lower()}_{field_name}'
                })

    @staticmethod
    def optimize_location_hierarchy_queries(form):
        """Optimize queries for location hierarchy forms"""
        from .models import Building, Block, Floor, Department, Room
        
        # Optimize building queryset
        if 'building' in form.fields:
            form.fields['building'].queryset = Building.objects.filter(
                is_active=True
            ).prefetch_related('blocks')
        
        # Optimize block queryset
        if 'block' in form.fields:
            form.fields['block'].queryset = Block.objects.filter(
                is_active=True
            ).select_related('building').prefetch_related('floors')
        
        # Optimize floor queryset
        if 'floor' in form.fields:
            form.fields['floor'].queryset = Floor.objects.filter(
                is_active=True
            ).select_related('building', 'block').prefetch_related('departments')
        
        # Optimize department queryset
        if 'department' in form.fields:
            form.fields['department'].queryset = Department.objects.filter(
                is_active=True
            ).select_related('floor__building', 'floor__block').prefetch_related('rooms')
        
        # Optimize room queryset
        if 'room' in form.fields:
            form.fields['room'].queryset = Room.objects.filter(
                is_active=True
            ).select_related('department__floor__building', 'department__floor__block')

# ================================
# LOCATION HIERARCHY UTILITIES
# ================================

class LocationHierarchyUtils:
    """Utilities for handling location hierarchy with blocks"""
    
    @staticmethod
    def setup_cascade_filtering(form, building_field='building', block_field='block', 
                              floor_field='floor', department_field='department', room_field='room'):
        """Setup cascade filtering for location hierarchy forms"""
        from .models import Building, Block, Floor, Department, Room
        
        # Add cascade data attributes
        if building_field in form.fields:
            form.fields[building_field].widget.attrs.update({
                'data-cascade-target': block_field,
                'data-cascade-url': '/api/cascade/blocks/',
                'class': f"{form.fields[building_field].widget.attrs.get('class', '')} cascade-parent".strip()
            })
        
        if block_field in form.fields:
            form.fields[block_field].widget.attrs.update({
                'data-cascade-parent': building_field,
                'data-cascade-target': floor_field,
                'data-cascade-url': '/api/cascade/floors/',
                'class': f"{form.fields[block_field].widget.attrs.get('class', '')} cascade-child".strip()
            })
        
        if floor_field in form.fields:
            form.fields[floor_field].widget.attrs.update({
                'data-cascade-parent': block_field,
                'data-cascade-target': department_field,
                'data-cascade-url': '/api/cascade/departments/',
                'class': f"{form.fields[floor_field].widget.attrs.get('class', '')} cascade-child".strip()
            })
        
        if department_field in form.fields:
            form.fields[department_field].widget.attrs.update({
                'data-cascade-parent': floor_field,
                'data-cascade-target': room_field,
                'data-cascade-url': '/api/cascade/rooms/',
                'class': f"{form.fields[department_field].widget.attrs.get('class', '')} cascade-child".strip()
            })
        
        if room_field in form.fields:
            form.fields[room_field].widget.attrs.update({
                'data-cascade-parent': department_field,
                'class': f"{form.fields[room_field].widget.attrs.get('class', '')} cascade-child".strip()
            })
    
    @staticmethod
    def get_hierarchy_breadcrumb(location):
        """Generate breadcrumb for location hierarchy"""
        if not location:
            return ""
        
        parts = []
        
        if hasattr(location, 'building') and location.building:
            parts.append(location.building.name)
        
        if hasattr(location, 'block') and location.block:
            parts.append(location.block.name)
        
        if hasattr(location, 'floor') and location.floor:
            parts.append(location.floor.name)
        
        if hasattr(location, 'department') and location.department:
            parts.append(location.department.name)
        
        if hasattr(location, 'room') and location.room:
            parts.append(f"Room {location.room.room_number}")
        
        return " → ".join(parts)
    
    @staticmethod
    def validate_hierarchy_consistency(building=None, block=None, floor=None, department=None, room=None):
        """Validate that location hierarchy is consistent"""
        errors = {}
        
        # Validate block belongs to building
        if building and block and block.building != building:
            errors['block'] = 'Selected block does not belong to the selected building.'
        
        # Validate floor belongs to block
        if block and floor and floor.block != block:
            errors['floor'] = 'Selected floor does not belong to the selected block.'
        
        # Validate department belongs to floor
        if floor and department and department.floor != floor:
            errors['department'] = 'Selected department does not belong to the selected floor.'
        
        # Validate room belongs to department
        if department and room and room.department != department:
            errors['room'] = 'Selected room does not belong to the selected department.'
        
        return errors
    
    @staticmethod
    def get_location_code(building=None, block=None, floor=None, department=None, room=None):
        """Generate location code from hierarchy components"""
        parts = []
        
        if building and hasattr(building, 'code'):
            parts.append(building.code)
        
        if block and hasattr(block, 'code'):
            parts.append(block.code)
        
        if floor and hasattr(floor, 'floor_number'):
            parts.append(f"F{floor.floor_number}")
        
        if department and hasattr(department, 'code'):
            parts.append(department.code)
        
        if room and hasattr(room, 'room_number'):
            parts.append(room.room_number)
        
        return "-".join(parts)

# ================================
# BLOCK VALIDATION UTILITIES
# ================================

class BlockValidationUtils:
    """Utilities for block-specific validation"""
    
    @staticmethod
    def validate_block_code(code, building=None, instance=None):
        """Validate block code format and uniqueness"""
        from .models import Block
        from django.core.exceptions import ValidationError
        
        if not code:
            return None
        
        # Format validation
        code = code.upper().strip()
        
        # Check format: Should be 2-4 uppercase letters/numbers
        import re
        if not re.match(r'^[A-Z0-9]{1,4}$', code):
            raise ValidationError("Block code must be 1-4 uppercase letters/numbers (e.g., EB, WB, NB)")
        
        # Uniqueness validation within building
        if building:
            existing = Block.objects.filter(building=building, code=code)
            if instance:
                existing = existing.exclude(pk=instance.pk)
            
            if existing.exists():
                raise ValidationError(f'Block code "{code}" already exists in this building.')
        
        return code
    
    @staticmethod
    def validate_block_name(name, building=None, instance=None):
        """Validate block name and uniqueness"""
        from .models import Block
        from django.core.exceptions import ValidationError
        
        if not name:
            return None
        
        name = name.strip()
        
        # Length validation
        if len(name) < 2:
            raise ValidationError("Block name must be at least 2 characters long.")
        
        # Uniqueness validation within building (case-insensitive)
        if building:
            existing = Block.objects.filter(building=building, name__iexact=name)
            if instance:
                existing = existing.exclude(pk=instance.pk)
            
            if existing.exists():
                raise ValidationError(f'Block name "{name}" already exists in this building.')
        
        return name
    
    @staticmethod
    def suggest_block_code(name, building=None):
        """Suggest block code based on name"""
        from .models import Block
        
        if not name:
            return ""
        
        # Extract initials from block name
        words = name.upper().split()
        if len(words) == 1:
            # Single word: take first 2-3 characters
            suggested = words[0][:3]
        elif len(words) == 2:
            # Two words: take first letter of each
            suggested = words[0][0] + words[1][0]
        else:
            # Multiple words: take first letter of first two words
            suggested = words[0][0] + words[1][0]
        
        # Check if suggested code exists, if so, add number
        if building:
            base_code = suggested
            counter = 1
            while Block.objects.filter(building=building, code=suggested).exists():
                suggested = f"{base_code}{counter}"
                counter += 1
        
        return suggested

# ================================
# INTERNATIONALIZATION UTILITIES
# ================================

class I18nUtils:
    """Utilities for internationalization support"""
    
    @staticmethod
    def translate_form_labels(form, language_code=None):
        """Translate form labels based on language code"""
        from django.utils.translation import gettext as _
        
        for field_name, field in form.fields.items():
            if field.label:
                # Use Django's translation system
                field.label = _(field.label)
            
            if field.help_text:
                field.help_text = _(field.help_text)
    
    @staticmethod
    def add_rtl_support(form):
        """Add right-to-left language support"""
        for field_name, field in form.fields.items():
            widget = field.widget
            widget.attrs.update({
                'dir': 'auto',  # Automatic text direction
                'data-rtl-support': 'true'
            })
    
    @staticmethod
    def format_numbers_by_locale(form, locale='en_US'):
        """Format number fields according to locale"""
        import locale as locale_module
        
        try:
            locale_module.setlocale(locale_module.LC_ALL, locale)
            
            for field_name, field in form.fields.items():
                if isinstance(field, (forms.IntegerField, forms.FloatField, forms.DecimalField)):
                    widget = field.widget
                    widget.attrs.update({
                        'data-locale': locale,
                        'data-number-format': 'true'
                    })
        except locale_module.Error:
            pass  # Fallback to default formatting


# ================================
# TESTING UTILITIES
# ================================

class FormTestUtils:
    """Utilities for testing forms"""
    
    @staticmethod
    def create_test_data(form_class, **overrides):
        """Create valid test data for a form"""
        from django.test import RequestFactory
        from factory import Faker
        
        factory = RequestFactory()
        test_data = {}
        
        # Generate test data for each field
        for field_name, field in form_class().fields.items():
            if isinstance(field, forms.CharField):
                test_data[field_name] = Faker('text', max_nb_chars=field.max_length or 50).generate()
            elif isinstance(field, forms.EmailField):
                test_data[field_name] = Faker('email').generate()
            elif isinstance(field, forms.IntegerField):
                test_data[field_name] = Faker('random_int', min=1, max=1000).generate()
            elif isinstance(field, forms.DateField):
                test_data[field_name] = Faker('date').generate()
            elif isinstance(field, forms.BooleanField):
                test_data[field_name] = Faker('boolean').generate()
            elif isinstance(field, forms.ChoiceField):
                if field.choices:
                    test_data[field_name] = field.choices[0][0]
        
        # Apply overrides
        test_data.update(overrides)
        
        return test_data
    
    @staticmethod
    def validate_form_security(form_class, test_data):
        """Test form for common security vulnerabilities"""
        results = {
            'xss_safe': True,
            'sql_injection_safe': True,
            'csrf_protected': True,
            'issues': []
        }
        
        # Test XSS protection
        xss_payloads = ['<script>alert("xss")</script>', '"><script>alert("xss")</script>']
        for payload in xss_payloads:
            test_case = test_data.copy()
            for field_name in test_case:
                if isinstance(test_case[field_name], str):
                    test_case[field_name] = payload
                    form = form_class(data=test_case)
                    
                    # Check if payload is properly escaped
                    if form.is_valid() and payload in str(form.cleaned_data.get(field_name, '')):
                        results['xss_safe'] = False
                        results['issues'].append(f'XSS vulnerability in field: {field_name}')
        
        return results


# ================================
# DOCUMENTATION UTILITIES
# ================================

class FormDocUtils:
    """Utilities for generating form documentation"""
    
    @staticmethod
    def generate_field_documentation(form_class):
        """Generate documentation for form fields"""
        docs = {
            'form_name': form_class.__name__,
            'description': form_class.__doc__ or '',
            'fields': []
        }
        
        form_instance = form_class()
        
        for field_name, field in form_instance.fields.items():
            field_doc = {
                'name': field_name,
                'type': field.__class__.__name__,
                'required': field.required,
                'label': field.label or field_name.replace('_', ' ').title(),
                'help_text': field.help_text or '',
                'max_length': getattr(field, 'max_length', None),
                'choices': getattr(field, 'choices', None),
                'default': field.initial,
                'widget': field.widget.__class__.__name__
            }
            
            docs['fields'].append(field_doc)
        
        return docs
    
    @staticmethod
    def export_documentation_to_markdown(form_classes):
        """Export form documentation to Markdown format"""
        markdown = "# Form Documentation\n\n"
        
        for form_class in form_classes:
            docs = FormDocUtils.generate_field_documentation(form_class)
            
            markdown += f"## {docs['form_name']}\n\n"
            if docs['description']:
                markdown += f"{docs['description']}\n\n"
            
            markdown += "| Field | Type | Required | Description |\n"
            markdown += "|-------|------|----------|-------------|\n"
            
            for field in docs['fields']:
                required = "Yes" if field['required'] else "No"
                description = field['help_text'] or field['label']
                markdown += f"| {field['name']} | {field['type']} | {required} | {description} |\n"
            
            markdown += "\n"
        
        return markdown


# ================================
# END OF FORM UTILS MODULE
# ================================