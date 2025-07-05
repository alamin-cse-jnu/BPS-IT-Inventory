# authentication/admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.shortcuts import redirect
from django import forms
from .models import (
    UserRole, UserProfile, UserSession, LoginAttempt, 
    PasswordHistory, UserPreference, UserActivity, 
    TwoFactorAuth, ApiKey, SecurityQuestion
)

# ================================
# CUSTOM FILTERS
# ================================

class ActiveUserFilter(admin.SimpleListFilter):
    title = 'Account Status'
    parameter_name = 'account_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('locked', 'Locked'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        elif self.value() == 'locked':
            return queryset.filter(account_locked_until__isnull=False)


# ================================
# INLINE ADMIN CLASSES
# ================================

class LoginAttemptInline(admin.TabularInline):
    model = LoginAttempt
    extra = 0
    readonly_fields = ('timestamp', 'ip_address', 'is_successful', 'failure_reason')
    fields = ('timestamp', 'ip_address', 'is_successful', 'failure_reason')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-timestamp')[:5]


class PasswordHistoryInline(admin.TabularInline):
    model = PasswordHistory
    extra = 0
    readonly_fields = ('created_at', 'password_hash')
    fields = ('created_at', 'is_current')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')[:5]


# ================================
# MAIN ADMIN CLASSES
# ================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        'display_name', 'name', 'user_count', 'permission_summary',
        'can_view_all_devices', 'can_manage_assignments', 'is_active'
    )
    list_filter = (
        'can_view_all_devices', 'can_manage_assignments', 'can_approve_requests',
        'can_generate_reports', 'can_manage_users', 'can_system_admin', 'is_active'
    )
    search_fields = ('name', 'display_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Core Permissions', {
            'fields': (
                'can_view_all_devices', 'can_manage_assignments', 'can_approve_requests',
                'can_generate_reports', 'can_manage_users', 'can_system_admin'
            )
        }),
        ('Additional Permissions', {
            'fields': (
                'can_manage_maintenance', 'can_manage_vendors', 'can_manage_categories',
                'can_view_sensitive_data', 'can_export_data', 'can_delete_records'
            ),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('allowed_ip_ranges', 'session_timeout_minutes', 'max_concurrent_sessions'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('permissions', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_count(self, obj):
        """Count users with this role"""
        count = obj.user_profiles.count() if hasattr(obj, 'user_profiles') else 0
        return format_html(
            '<a href="{}?role__id__exact={}">{} users</a>',
            reverse('admin:authentication_userprofile_changelist'),
            obj.id,
            count
        )
    user_count.short_description = 'Users'

    def permission_summary(self, obj):
        """Show summary of key permissions"""
        permissions = []
        if obj.can_manage_assignments:
            permissions.append("Assignments")
        if obj.can_generate_reports:
            permissions.append("Reports")
        if obj.can_manage_users:
            permissions.append("Users")
        if obj.can_system_admin:
            permissions.append("Admin")
        
        return ", ".join(permissions) if permissions else "Basic"
    permission_summary.short_description = 'Key Permissions'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'role', 'department', 'phone', 'is_active',
        'last_login_display', 'account_status'
    )
    list_filter = (
        ActiveUserFilter, 'role', 'department', 'created_at',
        'email_verified', 'phone_verified'
    )
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = (
        'created_at', 'updated_at', 'last_login', 'failed_login_attempts'
    )
    inlines = [LoginAttemptInline, PasswordHistoryInline]
    
    fieldsets = (
        ('User Account', {
            'fields': ('user', 'role', 'is_active')
        }),
        ('Personal Information', {
            'fields': (
                'employee_id', 'department', 'designation', 'phone', 'address',
                'date_of_birth', 'emergency_contact', 'profile_picture'
            )
        }),
        ('Verification Status', {
            'fields': ('email_verified', 'phone_verified'),
            'classes': ('collapse',)
        }),
        ('Security Settings', {
            'fields': (
                'two_factor_enabled', 'security_clearance', 'allowed_ip_ranges',
                'session_timeout_minutes', 'max_concurrent_sessions'
            ),
            'classes': ('collapse',)
        }),
        ('Account Status', {
            'fields': (
                'failed_login_attempts', 'account_locked_until',
                'password_change_required', 'last_password_change'
            ),
            'classes': ('collapse',)
        }),
        ('Preferences', {
            'fields': ('language', 'timezone', 'preferences'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    def last_login_display(self, obj):
        """Display formatted last login"""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_login_display.short_description = 'Last Login'

    def account_status(self, obj):
        """Display account status with icons"""
        if not obj.is_active:
            return format_html('<span style="color: red;">🚫 Inactive</span>')
        elif obj.account_locked_until:
            return format_html('<span style="color: orange;">🔒 Locked</span>')
        elif obj.password_change_required:
            return format_html('<span style="color: blue;">🔑 Password Required</span>')
        else:
            return format_html('<span style="color: green;">✅ Active</span>')
    account_status.short_description = 'Status'


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session_key_display', 'ip_address', 'user_agent_display',
        'created_at', 'last_activity', 'is_active'
    )
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address', 'session_key')
    readonly_fields = ('session_key', 'created_at', 'last_activity')

    def session_key_display(self, obj):
        """Display shortened session key"""
        return obj.session_key[:8] + '...' if obj.session_key else '-'
    session_key_display.short_description = 'Session Key'

    def user_agent_display(self, obj):
        """Display shortened user agent"""
        if obj.user_agent:
            return obj.user_agent[:50] + ('...' if len(obj.user_agent) > 50 else '')
        return '-'
    user_agent_display.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'timestamp', 'ip_address', 'is_successful',
        'failure_reason', 'user_agent_display'
    )
    list_filter = ('is_successful', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'failure_reason')
    readonly_fields = ('timestamp',)

    def user_agent_display(self, obj):
        """Display shortened user agent"""
        if obj.user_agent:
            return obj.user_agent[:50] + ('...' if len(obj.user_agent) > 50 else '')
        return '-'
    user_agent_display.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'is_current')
    list_filter = ('is_current', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'password_hash')

    def has_add_permission(self, request):
        return False


@admin.register(SecurityQuestion)
class SecurityQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'question')
    readonly_fields = ('created_at', 'updated_at', 'answer_hash')


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'preference_type', 'updated_at')
    list_filter = ('preference_type', 'updated_at')
    search_fields = ('user__username', 'preference_type')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'activity_type', 'timestamp', 'description_short',
        'ip_address', 'success_status'
    )
    list_filter = ('activity_type', 'is_successful', 'timestamp')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('timestamp',)

    def description_short(self, obj):
        """Display shortened description"""
        return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
    description_short.short_description = 'Description'

    def success_status(self, obj):
        """Display success status with icons"""
        if obj.is_successful:
            return format_html('<span style="color: green;">✅</span>')
        else:
            return format_html('<span style="color: red;">❌</span>')
    success_status.short_description = 'Success'

    def has_add_permission(self, request):
        return False


@admin.register(TwoFactorAuth)
class TwoFactorAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'is_active', 'backup_codes_count', 'last_used')
    list_filter = ('method', 'is_active', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('secret_key', 'backup_codes', 'created_at', 'last_used')

    def backup_codes_count(self, obj):
        """Count remaining backup codes"""
        if obj.backup_codes:
            try:
                codes = obj.backup_codes if isinstance(obj.backup_codes, list) else []
                return len(codes)
            except:
                return 0
        return 0
    backup_codes_count.short_description = 'Backup Codes'


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'key_preview', 'is_active',
        'last_used', 'expires_at', 'usage_count'
    )
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('key', 'created_at', 'last_used', 'usage_count')

    def key_preview(self, obj):
        """Display preview of API key"""
        if obj.key:
            return obj.key[:8] + '...' + obj.key[-4:]
        return '-'
    key_preview.short_description = 'API Key'


# ================================
# ADMIN ACTIONS
# ================================

@admin.action(description='Activate selected users')
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} users were activated.')


@admin.action(description='Deactivate selected users')
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} users were deactivated.')


@admin.action(description='Reset failed login attempts')
def reset_login_attempts(modeladmin, request, queryset):
    for profile in queryset:
        profile.failed_login_attempts = 0
        profile.account_locked_until = None
        profile.save()
    modeladmin.message_user(request, f'Login attempts reset for {queryset.count()} users.')


# Add actions to UserProfile admin
UserProfileAdmin.actions = [activate_users, deactivate_users, reset_login_attempts]

# ================================
# EXTEND DEFAULT USER ADMIN
# ================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fields = ('role', 'department', 'phone', 'is_active')


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - Authentication"
admin.site.site_title = "BPS Authentication Admin"
admin.site.index_title = "User & Role Management"