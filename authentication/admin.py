# authentication/admin.py
# Location: bps_inventory/apps/authentication/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django import forms 
from .models import UserRole, UserRoleAssignment, UserProfile, UserSession
from django.urls import reverse
from django.utils import timezone

# ================================
# CUSTOM FORMS
# ================================

class UserRoleAssignmentForm(forms.ModelForm):
    """Custom form for UserRoleAssignment to make department optional"""
    
    class Meta:
        model = UserRoleAssignment
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make department field explicitly optional
        self.fields['department'].required = False
        self.fields['department'].empty_label = "No Department (System-wide access)"
        
        # Add help text
        self.fields['department'].help_text = (
            "Select department for Department Head and General Staff roles. "
            "Leave empty for IT Administrator and IT Officer (system-wide access)."
        )
        
        # Style the form fields
        self.fields['role'].widget.attrs.update({'class': 'form-control'})
        self.fields['department'].widget.attrs.update({'class': 'form-control'})
        self.fields['user'].widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        department = cleaned_data.get('department')
        
        if role:
            # Check if this role typically requires a department
            department_required_roles = ['DEPARTMENT_HEAD', 'GENERAL_STAFF', 'MANAGER']
            system_wide_roles = ['IT_ADMINISTRATOR', 'IT_OFFICER', 'AUDITOR']
            
            # Warning for department-required roles without department
            if role.name in department_required_roles and not department:
                self.add_error('department', 
                    f'{role.display_name} role typically requires a department assignment. '
                    f'Are you sure you want system-wide access?'
                )
            
            # Info message for system-wide roles with department
            if role.name in system_wide_roles and department:
                # Don't error, just note it's unusual
                pass
        
        return cleaned_data

# ================================
# USER ROLE MANAGEMENT
# ================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'display_name', 'permission_summary', 
        'user_count', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'can_system_admin', 'can_manage_users', 
        'can_view_all_devices', 'created_at'
    )
    search_fields = ('name', 'display_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Device & Assignment Permissions', {
            'fields': (
                'can_view_all_devices', 'can_manage_assignments', 
                'can_approve_requests', 'can_manage_maintenance'
            )
        }),
        ('System Permissions', {
            'fields': (
                'can_system_admin', 'can_manage_users', 
                'can_generate_reports', 'can_manage_vendors'
            )
        }),
        ('Access Control', {
            'fields': (
                'restricted_to_own_department', 'can_view_financial_data',
                'can_scan_qr_codes', 'can_generate_qr_codes'
            )
        }),
        ('Advanced Operations', {
            'fields': ('can_bulk_operations', 'can_export_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def permission_summary(self, obj):
        permissions = []
        if obj.can_system_admin:
            permissions.append("System Admin")
        if obj.can_manage_users:
            permissions.append("User Management")
        if obj.can_view_all_devices:
            permissions.append("All Devices")
        return ", ".join(permissions) if permissions else "Basic Access"
    permission_summary.short_description = 'Key Permissions'
    
    def user_count(self, obj):
        count = obj.user_assignments.count()
        if count > 0:
            url = reverse('admin:authentication_userroleassignment_changelist')
            return format_html(
                '<a href="{}?role__id__exact={}">{}</a>',
                url, obj.pk, count
            )
        return 0
    user_count.short_description = 'Users'

@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    form = UserRoleAssignmentForm  # <-- ADD THIS LINE TO USE CUSTOM FORM
    
    list_display = (
        'user', 'role', 'get_department_scope', 'is_active', 'assigned_by', 'start_date', 'end_date', 'is_currently_active'
    )
    list_filter = (
        'is_active', 'role', 'assigned_at', 'start_date', 'end_date'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'role__display_name'
    )
    readonly_fields = ('assigned_at',)
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('user', 'role', 'department', 'is_active', 'start_date', 'end_date'),
            'description': (
                '<div style="background: #e8f4fd; padding: 12px; border-left: 4px solid #2196F3; margin-bottom: 20px; border-radius: 4px;">'
                '<h4 style="margin: 0 0 8px 0; color: #1976D2;">Department Assignment Guidelines</h4>'
                '<p style="margin: 0;"><strong>IT Administrator & IT Officer:</strong> Leave department empty for system-wide access</p>'
                '<p style="margin: 4px 0 0 0;"><strong>Department Head & General Staff:</strong> Select specific department</p>'
                '</div>'
            )
        }),
        ('Assignment Context', {
            'fields': ('notes', 'assigned_by'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('assigned_at',),
            'classes': ('collapse',)
        })
    )
    
    def get_department_scope(self, obj):
        """Show department name or system-wide access indicator"""
        if obj.department:
            return format_html(
                '<span style="background: #4CAF50; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">'
                '{}</span>',
                obj.department.name
            )
        else:
            # Check if role should have system-wide access
            if obj.role and not obj.role.restricted_to_own_department:
                return format_html(
                    '<span style="background: #2196F3; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">'
                    '🌐 System-wide</span>'
                )
            else:
                return format_html(
                    '<span style="background: #FF9800; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">'
                    '⚠️ No Department</span>'
                )
    get_department_scope.short_description = 'Access Scope'
    
    def get_department(self, obj):
        """Get department from UserRoleAssignment or user's staff profile"""
        if obj.department:
            return obj.department.name
        try:
            from inventory.models import Staff
            if hasattr(obj.user, 'staff_profile') and obj.user.staff_profile.department:
                return obj.user.staff_profile.department.name
        except (ImportError, AttributeError):
            pass
        return "No Department"
    get_department.short_description = 'Department'
    
    def is_currently_active(self, obj):
        return obj.is_currently_active
    is_currently_active.short_description = 'Currently Active'
    is_currently_active.boolean = True

# ================================
# INLINE ADMIN CLASSES
# ================================

class UserRoleAssignmentInline(admin.TabularInline):
    model = UserRoleAssignment
    extra = 0
    readonly_fields = ('assigned_at',)
    fk_name = 'user'

# ================================
# USER PROFILE MANAGEMENT
# ================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'get_department', 'get_phone_number', 'get_is_active', 'get_last_login'
    )
    list_filter = (
        'theme', 'language', 'email_notifications', 'created_at'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email'
    )
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('UI Preferences', {
            'fields': ('theme', 'language', 'timezone', 'default_items_per_page')
        }),
        ('Notification Settings', {
            'fields': (
                'email_notifications', 'sms_notifications', 'in_app_notifications',
                'notification_frequency', 'mobile_push_notifications'
            ),
            'classes': ('collapse',)
        }),
        ('Security Settings', {
            'fields': ('require_2fa', 'session_timeout_minutes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_login_ip', 'last_password_change'),
            'classes': ('collapse',)
        })
    )
    
    def get_department(self, obj):
        """Get department from default_department field or staff profile"""
        if obj.default_department:
            return obj.default_department.name
        elif hasattr(obj.user, 'staff_profile') and obj.user.staff_profile.department:
            return obj.user.staff_profile.department.name
        return "No Department"
    get_department.short_description = 'Department'
    
    def get_phone_number(self, obj):
        """Get phone number from staff profile"""
        if hasattr(obj.user, 'staff_profile'):
            return obj.user.staff_profile.phone_number or "Not provided"
        return "No staff profile"
    get_phone_number.short_description = 'Phone Number'
    
    def get_is_active(self, obj):
        """Get active status from user"""
        return obj.user.is_active
    get_is_active.short_description = 'Is Active'
    get_is_active.boolean = True
    
    def get_last_login(self, obj):
        """Get last login from user"""
        return obj.user.last_login
    get_last_login.short_description = 'Last Login'

# ================================
# USER SESSION TRACKING
# ================================

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session_key_display', 'ip_address', 'user_agent_short',
        'login_time', 'last_activity', 'is_active'
    )
    list_filter = (
        'is_active', 'login_time', 'last_activity', 'session_type'
    )
    search_fields = (
        'user__username', 'ip_address', 'session_key'
    )
    readonly_fields = (
        'session_key', 'login_time', 'last_activity', 'logout_time'
    )
    date_hierarchy = 'login_time'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'session_type', 'is_active')
        }),
        ('Login Details', {
            'fields': ('ip_address', 'user_agent', 'login_time')
        }),
        ('Activity Tracking', {
            'fields': ('last_activity', 'logout_time'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('is_suspicious', 'failed_login_attempts'),
            'classes': ('collapse',)
        })
    )
    
    def session_key_display(self, obj):
        return f"{obj.session_key[:16]}..." if obj.session_key else ""
    session_key_display.short_description = 'Session Key'
    
    def user_agent_short(self, obj):
        return obj.user_agent[:50] + "..." if len(obj.user_agent) > 50 else obj.user_agent
    user_agent_short.short_description = 'User Agent'
    
    def has_add_permission(self, request):
        return False

# ================================
# EXTENDED USER ADMIN
# ================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class ExtendedUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, UserRoleAssignmentInline)
    list_display = BaseUserAdmin.list_display + ('get_department', 'get_roles')
    
    def get_department(self, obj):
        if hasattr(obj, 'user_profile') and obj.user_profile.default_department:
            return obj.user_profile.default_department.name
        elif hasattr(obj, 'staff_profile') and obj.staff_profile.department:
            return obj.staff_profile.department.name
        return 'No Department'
    get_department.short_description = 'Department'
    
    def get_roles(self, obj):
        roles = UserRoleAssignment.objects.filter(user=obj, is_active=True)
        return ', '.join([assignment.role.display_name for assignment in roles])
    get_roles.short_description = 'Active Roles'

# Unregister the default User admin and register our extended one
admin.site.unregister(User)
admin.site.register(User, ExtendedUserAdmin)

# ================================
# ADMIN ACTIONS
# ================================

def activate_users(modeladmin, request, queryset):
    """Activate selected users"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request, 
        f'{updated} user(s) activated.'
    )
activate_users.short_description = "Activate selected users"

def deactivate_users(modeladmin, request, queryset):
    """Deactivate selected users"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f'{updated} user(s) deactivated.'
    )
deactivate_users.short_description = "Deactivate selected users"

def force_logout_sessions(modeladmin, request, queryset):
    """Force logout selected sessions"""
    updated = queryset.update(is_active=False, logout_time=timezone.now())
    modeladmin.message_user(
        request,
        f'{updated} session(s) logged out.'
    )
force_logout_sessions.short_description = "Force logout selected sessions"

# Add actions to admin classes
UserRoleAssignmentAdmin.actions = [activate_users, deactivate_users]
UserSessionAdmin.actions = [force_logout_sessions]