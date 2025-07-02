# reports/forms.py
"""
Report Generation Forms for BPS IT Inventory Management System
Forms for generating various types of reports and analytics.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import json
from inventory.models import Department, Location, DeviceCategory, DeviceType, Vendor, Staff


# ================================
# STANDARD REPORT FORMS
# ================================

class InventoryReportForm(forms.Form):
    """Form for generating inventory reports"""
    
    GROUPING_OPTIONS = [
        ('category', 'By Category'),
        ('location', 'By Location'),
        ('department', 'By Department'),
        ('status', 'By Status'),
        ('condition', 'By Condition'),
        ('vendor', 'By Vendor')
    ]
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF Document'),
        ('excel', 'Excel Spreadsheet'),
        ('csv', 'CSV File'),
        ('json', 'JSON Data')
    ]
    
    # Report Configuration
    report_title = forms.CharField(
        max_length=200,
        initial='Inventory Report',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter report title...'
        })
    )
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='pdf',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    group_by = forms.ChoiceField(
        choices=GROUPING_OPTIONS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Group results by"
    )
    
    # Filters
    categories = forms.ModelMultipleChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Device categories"
    )
    
    locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Locations"
    )
    
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Departments"
    )
    
    vendors = forms.ModelMultipleChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Vendors"
    )
    
    # Status filters
    include_available = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Available devices"
    )
    
    include_assigned = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Assigned devices"
    )
    
    include_maintenance = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Devices under maintenance"
    )
    
    include_disposed = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Disposed devices"
    )
    
    # Value ranges
    min_purchase_price = forms.DecimalField(
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Minimum price'
        })
    )
    
    max_purchase_price = forms.DecimalField(
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Maximum price'
        })
    )
    
    # Date ranges
    purchase_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Purchased from"
    )
    
    purchase_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Purchased to"
    )
    
    # Additional options
    include_specifications = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include technical specifications"
    )
    
    include_warranty_info = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include warranty information"
    )
    
    include_financial_summary = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include financial summary"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get('min_purchase_price')
        max_price = cleaned_data.get('max_purchase_price')
        date_from = cleaned_data.get('purchase_date_from')
        date_to = cleaned_data.get('purchase_date_to')
        
        # Validate price range
        if min_price and max_price and min_price >= max_price:
            raise ValidationError("Maximum price must be greater than minimum price.")
        
        # Validate date range
        if date_from and date_to and date_from > date_to:
            raise ValidationError("End date must be after start date.")
        
        return cleaned_data


class AssignmentReportForm(forms.Form):
    """Form for generating assignment reports"""
    
    REPORT_TYPES = [
        ('current', 'Current Assignments'),
        ('historical', 'Assignment History'),
        ('overdue', 'Overdue Assignments'),
        ('utilization', 'Device Utilization')
    ]
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF Document'),
        ('excel', 'Excel Spreadsheet'),
        ('csv', 'CSV File')
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
    
    # Date range
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
    
    # Filters
    staff_members = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Staff members"
    )
    
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Departments"
    )
    
    assignment_types = forms.MultipleChoiceField(
        choices=[
            ('PERMANENT', 'Permanent'),
            ('TEMPORARY', 'Temporary')
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Assignment types"
    )
    
    # Report options
    include_returned = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include returned assignments"
    )
    
    include_device_details = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include device details"
    )
    
    include_charts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include charts and graphs"
    )


class MaintenanceReportForm(forms.Form):
    """Form for generating maintenance reports"""
    
    REPORT_TYPES = [
        ('scheduled', 'Scheduled Maintenance'),
        ('completed', 'Completed Maintenance'),
        ('overdue', 'Overdue Maintenance'),
        ('costs', 'Maintenance Costs Analysis')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    export_format = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF Document'),
            ('excel', 'Excel Spreadsheet'),
            ('csv', 'CSV File')
        ],
        initial='pdf',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Date range
    date_from = forms.DateField(
        initial=timezone.now().date() - timedelta(days=90),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        initial=timezone.now().date() + timedelta(days=30),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # Filters
    vendors = forms.ModelMultipleChoiceField(
        queryset=Vendor.objects.filter(
            vendor_type__in=['SERVICE_PROVIDER', 'MAINTENANCE_CONTRACTOR'],
            is_active=True
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Service providers"
    )
    
    device_categories = forms.ModelMultipleChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Device categories"
    )
    
    priority_levels = forms.MultipleChoiceField(
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical')
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Priority levels"
    )
    
    # Cost analysis options
    min_cost = forms.DecimalField(
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Minimum cost'
        })
    )
    
    max_cost = forms.DecimalField(
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Maximum cost'
        })
    )
    
    # Report options
    include_cost_analysis = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include cost analysis"
    )
    
    include_renewal_recommendations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include renewal recommendations"
    )


class WarrantyReportForm(forms.Form):
    """Form for generating warranty reports"""
    
    REPORT_TYPES = [
        ('expiring', 'Expiring Warranties'),
        ('expired', 'Expired Warranties'),
        ('active', 'Active Warranties'),
        ('summary', 'Warranty Summary')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    export_format = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF Document'),
            ('excel', 'Excel Spreadsheet'),
            ('csv', 'CSV File')
        ],
        initial='pdf',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Alert thresholds
    alert_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Days before expiry'
        }),
        label="Alert threshold (days)",
        help_text="Show warranties expiring within this many days"
    )
    
    # Filters
    vendors = forms.ModelMultipleChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Vendors"
    )
    
    device_categories = forms.ModelMultipleChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Device categories"
    )
    
    # Value filters
    min_device_value = forms.DecimalField(
        required=False,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Minimum device value'
        })
    )
    
    # Report options
    include_cost_analysis = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include cost analysis"
    )
    
    include_renewal_recommendations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include renewal recommendations"
    )


# ================================
# ANALYTICS REPORT FORMS
# ================================

class UtilizationReportForm(forms.Form):
    """Form for generating device utilization reports"""
    
    ANALYSIS_PERIODS = [
        ('7', 'Last 7 days'),
        ('30', 'Last 30 days'),
        ('90', 'Last 90 days'),
        ('365', 'Last year'),
        ('custom', 'Custom period')
    ]
    
    UTILIZATION_METRICS = [
        ('assignment_duration', 'Assignment Duration'),
        ('idle_time', 'Idle Time'),
        ('department_usage', 'Department Usage'),
        ('cost_per_usage', 'Cost per Usage')
    ]
    
    analysis_period = forms.ChoiceField(
        choices=ANALYSIS_PERIODS,
        initial='30',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Custom date range (shown when analysis_period is 'custom')
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
    
    metrics = forms.MultipleChoiceField(
        choices=UTILIZATION_METRICS,
        initial=['assignment_duration', 'idle_time'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Include metrics"
    )
    
    # Filters
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Departments"
    )
    
    device_categories = forms.ModelMultipleChoiceField(
        queryset=DeviceCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Device categories"
    )
    
    # Analysis options
    include_benchmarks = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include industry benchmarks"
    )
    
    include_recommendations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include optimization recommendations"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        analysis_period = cleaned_data.get('analysis_period')
        custom_date_from = cleaned_data.get('custom_date_from')
        custom_date_to = cleaned_data.get('custom_date_to')
        
        if analysis_period == 'custom':
            if not custom_date_from or not custom_date_to:
                raise ValidationError("Custom date range requires both start and end dates.")
            
            if custom_date_from >= custom_date_to:
                raise ValidationError("End date must be after start date.")
        
        return cleaned_data


class FinancialReportForm(forms.Form):
    """Form for generating financial reports"""
    
    REPORT_TYPES = [
        ('asset_value', 'Asset Valuation'),
        ('depreciation', 'Depreciation Analysis'),
        ('cost_analysis', 'Cost Analysis'),
        ('budget_planning', 'Budget Planning'),
        ('roi_analysis', 'ROI Analysis')
    ]
    
    DEPRECIATION_METHODS = [
        ('straight_line', 'Straight Line'),
        ('declining_balance', 'Declining Balance'),
        ('units_of_production', 'Units of Production')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Financial period
    financial_year_start = forms.DateField(
        initial=date(timezone.now().year, 1, 1),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Financial year start"
    )
    
    financial_year_end = forms.DateField(
        initial=date(timezone.now().year, 12, 31),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Financial year end"
    )
    
    # Depreciation settings
    depreciation_method = forms.ChoiceField(
        choices=DEPRECIATION_METHODS,
        initial='straight_line',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    default_useful_life = forms.IntegerField(
        initial=5,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Years'
        }),
        label="Default useful life (years)"
    )
    
    salvage_value_percentage = forms.DecimalField(
        initial=10.0,
        min_value=0,
        max_value=100,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Percentage'
        }),
        label="Default salvage value (%)"
    )
    
    # Filters
    cost_centers = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Cost centers (departments)"
    )
    
    # Report options
    include_comparisons = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include year-over-year comparisons"
    )
    
    include_projections = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include future projections"
    )
    
    currency_format = forms.ChoiceField(
        choices=[
            ('BDT', 'Bangladeshi Taka (৳)'),
            ('USD', 'US Dollar ($)'),
            ('EUR', 'Euro (€)')
        ],
        initial='BDT',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class AuditReportForm(forms.Form):
    """Form for generating audit trail reports"""
    
    AUDIT_ACTIONS = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('ASSIGN', 'Assign'),
        ('RETURN', 'Return'),
        ('MAINTENANCE', 'Maintenance'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout')
    ]
    
    # Date range
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
    
    # Filters
    users = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Users"
    )
    
    actions = forms.MultipleChoiceField(
        choices=AUDIT_ACTIONS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Actions"
    )
    
    model_types = forms.MultipleChoiceField(
        choices=[
            ('Device', 'Devices'),
            ('Assignment', 'Assignments'),
            ('Staff', 'Staff'),
            ('Department', 'Departments'),
            ('Location', 'Locations')
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Object types"
    )
    
    # Search
    search_term = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search in audit logs...'
        })
    )
    
    # Report options
    include_ip_addresses = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include IP addresses"
    )
    
    include_change_details = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include detailed change information"
    )
    
    group_by_user = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Group results by user"
    )


# ================================
# CUSTOM REPORT FORMS
# ================================

class CustomReportForm(forms.Form):
    """Form for creating custom reports with flexible parameters"""
    
    DATA_SOURCES = [
        ('devices', 'Devices'),
        ('assignments', 'Assignments'),
        ('staff', 'Staff'),
        ('departments', 'Departments'),
        ('locations', 'Locations'),
        ('maintenance', 'Maintenance Records'),
        ('audit_logs', 'Audit Logs')
    ]
    
    AGGREGATION_FUNCTIONS = [
        ('count', 'Count'),
        ('sum', 'Sum'),
        ('avg', 'Average'),
        ('min', 'Minimum'),
        ('max', 'Maximum')
    ]
    
    # Report configuration
    report_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter custom report name...'
        })
    )
    
    data_source = forms.ChoiceField(
        choices=DATA_SOURCES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Field selection
    selected_fields = forms.MultipleChoiceField(
        choices=[],  # Populated dynamically based on data source
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Fields to include"
    )
    
    # Aggregations
    aggregation_field = forms.ChoiceField(
        choices=[],  # Populated dynamically
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Field to aggregate"
    )
    
    aggregation_function = forms.ChoiceField(
        choices=AGGREGATION_FUNCTIONS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Grouping
    group_by_field = forms.ChoiceField(
        choices=[],  # Populated dynamically
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Group by"
    )
    
    # Filtering
    filter_conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Advanced filter conditions (JSON format)...'
        }),
        help_text="Advanced users can specify filter conditions in JSON format"
    )
    
    # Sorting
    sort_by = forms.ChoiceField(
        choices=[],  # Populated dynamically
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort_order = forms.ChoiceField(
        choices=[
            ('asc', 'Ascending'),
            ('desc', 'Descending')
        ],
        initial='asc',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Limits
    limit_results = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Maximum number of results'
        })
    )
    
    # Save options
    save_template = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Save as template for future use"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # TODO: Populate field choices dynamically based on selected data source
        # This would be implemented with JavaScript on the frontend
        
    def clean_filter_conditions(self):
        filter_conditions = self.cleaned_data.get('filter_conditions')
        if filter_conditions:
            try:
                json.loads(filter_conditions)
            except json.JSONDecodeError:
                raise ValidationError("Filter conditions must be valid JSON.")
        
        return filter_conditions


# ================================
# REPORT SCHEDULING FORMS
# ================================

class ReportScheduleForm(forms.Form):
    """Form for scheduling automated report generation"""
    
    SCHEDULE_FREQUENCIES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ]
    
    DELIVERY_METHODS = [
        ('email', 'Email'),
        ('download', 'Download Link'),
        ('ftp', 'FTP Upload'),
        ('api', 'API Webhook')
    ]
    
    # Schedule configuration
    schedule_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter schedule name...'
        })
    )
    
    frequency = forms.ChoiceField(
        choices=SCHEDULE_FREQUENCIES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Leave blank for indefinite scheduling"
    )
    
    # Time configuration
    execution_time = forms.TimeField(
        initial='09:00',
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
    )
    
    # Day of week (for weekly schedules)
    day_of_week = forms.ChoiceField(
        choices=[
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
            (6, 'Sunday')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Day of month (for monthly schedules)
    day_of_month = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Day of month (1-31)'
        })
    )
    
    # Delivery configuration
    delivery_method = forms.ChoiceField(
        choices=DELIVERY_METHODS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    email_recipients = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter email addresses, one per line...'
        }),
        help_text="Required if delivery method is email"
    )
    
    # Report parameters (stored as JSON)
    report_parameters = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Report parameters from the main report form"
    )
    
    # Options
    is_active = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Active"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        day_of_week = cleaned_data.get('day_of_week')
        day_of_month = cleaned_data.get('day_of_month')
        delivery_method = cleaned_data.get('delivery_method')
        email_recipients = cleaned_data.get('email_recipients')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Validate frequency-specific requirements
        if frequency == 'weekly' and day_of_week is None:
            raise ValidationError("Day of week is required for weekly schedules.")
        
        if frequency == 'monthly' and day_of_month is None:
            raise ValidationError("Day of month is required for monthly schedules.")
        
        # Validate delivery method requirements
        if delivery_method == 'email' and not email_recipients:
            raise ValidationError("Email recipients are required when delivery method is email.")
        
        # Validate date range
        if start_date and end_date and start_date >= end_date:
            raise ValidationError("End date must be after start date.")
        
        return cleaned_data
    
    def clean_email_recipients(self):
        recipients = self.cleaned_data.get('email_recipients')
        if recipients:
            emails = [email.strip() for email in recipients.split('\n') if email.strip()]
            
            # Validate each email
            from django.core.validators import validate_email
            for email in emails:
                try:
                    validate_email(email)
                except ValidationError:
                    raise ValidationError(f"Invalid email address: {email}")
            
            return '\n'.join(emails)
        
        return recipients


# ================================
# REPORT EXPORT FORMS
# ================================

class ReportExportForm(forms.Form):
    """Form for configuring report export options"""
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF Document'),
        ('excel', 'Excel Spreadsheet (.xlsx)'),
        ('csv', 'CSV File'),
        ('json', 'JSON Data'),
        ('xml', 'XML Data')
    ]
    
    PAPER_SIZES = [
        ('A4', 'A4'),
        ('A3', 'A3'),
        ('Letter', 'Letter'),
        ('Legal', 'Legal')
    ]
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # PDF-specific options
    paper_size = forms.ChoiceField(
        choices=PAPER_SIZES,
        initial='A4',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    orientation = forms.ChoiceField(
        choices=[
            ('portrait', 'Portrait'),
            ('landscape', 'Landscape')
        ],
        initial='portrait',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Excel-specific options
    include_charts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include charts in Excel export"
    )
    
    separate_worksheets = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Use separate worksheets for different sections"
    )
    
    # CSV-specific options
    csv_delimiter = forms.ChoiceField(
        choices=[
            (',', 'Comma (,)'),
            (';', 'Semicolon (;)'),
            ('\t', 'Tab'),
            ('|', 'Pipe (|)')
        ],
        initial=',',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    include_headers = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include column headers"
    )
    
    # General options
    file_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Custom filename (optional)'
        })
    )
    
    compress_output = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Compress output file (ZIP)"
    )
    
    password_protect = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Password protect file"
    )
    
    password = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password_protect = cleaned_data.get('password_protect')
        password = cleaned_data.get('password')
        
        if password_protect and not password:
            raise ValidationError("Password is required when password protection is enabled.")
        
        return cleaned_data


# ================================
# PERFORMANCE REPORT FORMS
# ================================

class PerformanceReportForm(forms.Form):
    """Form for generating system performance reports"""
    
    PERFORMANCE_METRICS = [
        ('response_time', 'Response Time'),
        ('uptime', 'System Uptime'),
        ('user_activity', 'User Activity'),
        ('data_accuracy', 'Data Accuracy'),
        ('storage_usage', 'Storage Usage'),
        ('backup_status', 'Backup Status')
    ]
    
    TIME_PERIODS = [
        ('24h', 'Last 24 Hours'),
        ('7d', 'Last 7 Days'),
        ('30d', 'Last 30 Days'),
        ('90d', 'Last 90 Days'),
        ('custom', 'Custom Period')
    ]
    
    # Report configuration
    metrics = forms.MultipleChoiceField(
        choices=PERFORMANCE_METRICS,
        initial=['response_time', 'uptime', 'user_activity'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Performance metrics to include"
    )
    
    time_period = forms.ChoiceField(
        choices=TIME_PERIODS,
        initial='7d',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Custom date range
    custom_start_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    custom_end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    # Report options
    include_trends = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include trend analysis"
    )
    
    include_alerts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include performance alerts"
    )
    
    include_recommendations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include optimization recommendations"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        time_period = cleaned_data.get('time_period')
        custom_start_date = cleaned_data.get('custom_start_date')
        custom_end_date = cleaned_data.get('custom_end_date')
        
        if time_period == 'custom':
            if not custom_start_date or not custom_end_date:
                raise ValidationError("Custom time period requires both start and end dates.")
            
            if custom_start_date >= custom_end_date:
                raise ValidationError("End date must be after start date.")
        
        return cleaned_data


class ComplianceReportForm(forms.Form):
    """Form for generating compliance and regulatory reports"""
    
    COMPLIANCE_AREAS = [
        ('data_protection', 'Data Protection'),
        ('asset_management', 'Asset Management'),
        ('security', 'Security Compliance'),
        ('audit_trail', 'Audit Trail'),
        ('access_control', 'Access Control'),
        ('backup_recovery', 'Backup & Recovery')
    ]
    
    REGULATORY_FRAMEWORKS = [
        ('iso27001', 'ISO 27001'),
        ('gdpr', 'GDPR'),
        ('gov_bd', 'Bangladesh Government Standards'),
        ('internal', 'Internal Policies'),
        ('custom', 'Custom Framework')
    ]
    
    # Compliance areas to check
    compliance_areas = forms.MultipleChoiceField(
        choices=COMPLIANCE_AREAS,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Compliance areas to assess"
    )
    
    # Regulatory framework
    framework = forms.ChoiceField(
        choices=REGULATORY_FRAMEWORKS,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Regulatory framework"
    )
    
    # Assessment period
    assessment_start = forms.DateField(
        initial=timezone.now().date() - timedelta(days=90),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    assessment_end = forms.DateField(
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # Report options
    include_violations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include compliance violations"
    )
    
    include_risk_assessment = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include risk assessment"
    )
    
    include_remediation_plan = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include remediation plan"
    )
    
    # Custom framework details
    custom_framework_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter custom framework name...'
        })
    )
    
    custom_requirements = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Enter custom compliance requirements...'
        })
    )


# ================================
# FORM UTILITIES
# ================================

class DateRangeValidator:
    """Utility class for validating date ranges in forms"""
    
    @staticmethod
    def validate_range(date_from, date_to, max_days=None):
        """Validate that date range is logical and within limits"""
        if date_from and date_to:
            if date_from > date_to:
                raise ValidationError("End date must be after start date.")
            
            if max_days:
                delta = (date_to - date_from).days
                if delta > max_days:
                    raise ValidationError(f"Date range cannot exceed {max_days} days.")
        
        return True


class ReportFormMixin:
    """Mixin for common report form functionality"""
    
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
        
        # Common date range validation
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to:
            DateRangeValidator.validate_range(date_from, date_to, max_days=730)
        
        return cleaned_data


# ================================
# REPORT TEMPLATE FORMS
# ================================

class ReportTemplateForm(forms.Form):
    """Form for creating and managing report templates"""
    
    TEMPLATE_TYPES = [
        ('inventory', 'Inventory Report'),
        ('assignment', 'Assignment Report'),
        ('maintenance', 'Maintenance Report'),
        ('warranty', 'Warranty Report'),
        ('financial', 'Financial Report'),
        ('custom', 'Custom Report')
    ]
    
    # Template basic information
    template_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter template name...'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Template description...'
        })
    )
    
    template_type = forms.ChoiceField(
        choices=TEMPLATE_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Template settings (stored as JSON)
    template_config = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Template configuration data"
    )
    
    # Sharing options
    is_public = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Make template public (available to all users)"
    )
    
    is_default = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Set as default template for this report type"
    )
    
    # Tags for organization
    tags = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags separated by commas...'
        }),
        help_text="Tags to help organize and find templates"
    )
    
    def clean_template_config(self):
        template_config = self.cleaned_data.get('template_config')
        if template_config:
            try:
                json.loads(template_config)
            except json.JSONDecodeError:
                raise ValidationError("Template configuration must be valid JSON.")
        
        return template_config
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if tags:
            # Clean and validate tags
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            if len(tag_list) > 10:
                raise ValidationError("Maximum 10 tags allowed.")
            
            return ', '.join(tag_list)
        
        return tags


# ================================
# BULK REPORT FORMS
# ================================

class BulkReportForm(forms.Form):
    """Form for generating multiple reports in bulk"""
    
    BULK_OPERATIONS = [
        ('multiple_formats', 'Same Report, Multiple Formats'),
        ('multiple_periods', 'Same Report, Multiple Time Periods'),
        ('multiple_departments', 'Same Report, Multiple Departments'),
        ('report_suite', 'Complete Report Suite')
    ]
    
    operation_type = forms.ChoiceField(
        choices=BULK_OPERATIONS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Base report configuration
    base_report_type = forms.ChoiceField(
        choices=[
            ('inventory', 'Inventory Report'),
            ('assignment', 'Assignment Report'),
            ('maintenance', 'Maintenance Report'),
            ('warranty', 'Warranty Report'),
            ('financial', 'Financial Report')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Multiple formats
    export_formats = forms.MultipleChoiceField(
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV')
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Export formats"
    )
    
    # Multiple departments
    target_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Target departments"
    )
    
    # Time periods for bulk generation
    time_periods = forms.MultipleChoiceField(
        choices=[
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly')
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Time periods"
    )
    
    # Delivery options
    compress_all = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Compress all reports into single archive"
    )
    
    email_when_complete = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Email notification when bulk generation is complete"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        export_formats = cleaned_data.get('export_formats')
        target_departments = cleaned_data.get('target_departments')
        time_periods = cleaned_data.get('time_periods')
        
        # Validate based on operation type
        if operation_type == 'multiple_formats' and not export_formats:
            raise ValidationError("Export formats are required for multiple format operation.")
        
        if operation_type == 'multiple_departments' and not target_departments:
            raise ValidationError("Target departments are required for multiple department operation.")
        
        if operation_type == 'multiple_periods' and not time_periods:
            raise ValidationError("Time periods are required for multiple period operation.")
        
        return cleaned_data


# ================================
# SUMMARY FORMS
# ================================

class ExecutiveSummaryForm(forms.Form):
    """Form for generating executive summary reports"""
    
    SUMMARY_SECTIONS = [
        ('asset_overview', 'Asset Overview'),
        ('financial_summary', 'Financial Summary'),
        ('utilization_metrics', 'Utilization Metrics'),
        ('maintenance_status', 'Maintenance Status'),
        ('compliance_status', 'Compliance Status'),
        ('performance_kpis', 'Performance KPIs')
    ]
    
    # Report period
    report_period = forms.ChoiceField(
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual'),
            ('custom', 'Custom Period')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Custom period
    period_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    period_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # Sections to include
    sections = forms.MultipleChoiceField(
        choices=SUMMARY_SECTIONS,
        initial=[s[0] for s in SUMMARY_SECTIONS],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Sections to include"
    )
    
    # Executive preferences
    executive_level = forms.ChoiceField(
        choices=[
            ('ceo', 'CEO/Director Level'),
            ('department_head', 'Department Head'),
            ('manager', 'Manager Level'),
            ('custom', 'Custom Level')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Target executive level"
    )
    
    include_charts = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include executive charts"
    )
    
    include_trends = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include trend analysis"
    )
    
    include_recommendations = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include strategic recommendations"
    )


# ================================
# FORM CONSTANTS
# ================================

# Common choices that can be reused across forms
PRIORITY_CHOICES = [
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('CRITICAL', 'Critical')
]

STATUS_CHOICES = [
    ('ACTIVE', 'Active'),
    ('INACTIVE', 'Inactive'),
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('CANCELLED', 'Cancelled')
]

CURRENCY_CHOICES = [
    ('BDT', 'Bangladeshi Taka (৳)'),
    ('USD', 'US Dollar ($)'),
    ('EUR', 'Euro (€)'),
    ('GBP', 'British Pound (£)')
]

# Date format choices
DATE_FORMAT_CHOICES = [
    ('DD/MM/YYYY', 'DD/MM/YYYY'),
    ('MM/DD/YYYY', 'MM/DD/YYYY'),
    ('YYYY-MM-DD', 'YYYY-MM-DD'),
    ('DD-MMM-YYYY', 'DD-MMM-YYYY')
]