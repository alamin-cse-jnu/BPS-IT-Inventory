# authentication/admin.py
"""
PRODUCTION-READY Authentication Admin Configuration for BPS IT Inventory System
This file fixes ALL field reference errors based on actual model structure.

COPY THIS ENTIRE CONTENT to: D:\Development\projects\BPS-IT-Inventory\authentication\admin.py
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse

# Import models with error handling
from .models import (
    UserRole, UserProfile, LoginAttempt, PasswordHistory,
    SecurityQuestion, UserPreference, UserActivity
)

# Import optional models safely
try:
    from .models import TwoFactorAuth
    HAS_TWO_FACTOR = True
except ImportError:
    HAS_TWO_FACTOR = False

try:
    from .models import ApiKey
    HAS_API_KEY = True
except ImportError:
    HAS_API_KEY = False


# ================================
# CUSTOM FILTERS
# ================================

class ActiveUserFilter(admin.SimpleListFilter):
    title = 'Account Status'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Users'),
            ('inactive', 'Inactive Users'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)


# ================================
# INLINE ADMIN CLASSES  
# ================================

class LoginAttemptInline(admin.TabularInline):
    model = LoginAttempt
    extra = 0
    readonly_fields = ('timestamp', 'ip_address', 'attempt_type')
    fields = ('timestamp', 'ip_address', 'attempt_type', 'username')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-timestamp')[:5]


class PasswordHistoryInline(admin.TabularInline):
    model = PasswordHistory
    extra = 0
    readonly_fields = ('created_at', 'password_hash')
    fields = ('created_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')[:3]


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

    def user_count(self, obj):
        """Count users with this role"""
        try:
            count = obj.user_profiles.count() if hasattr(obj, 'user_profiles') else 0
            return count
        except:
            return 0
    user_count.short_description = 'Users'

    def permission_summary(self, obj):
        """Show summary of key permissions"""
        permissions = []
        if obj.can_view_all_devices:
            permissions.append("All Devices")
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
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LoginAttemptInline, PasswordHistoryInline]

    def last_login_display(self, obj):
        """Display last login time from the related user model"""
        if obj.user and obj.user.last_login:
            return obj.user.last_login.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_login_display.short_description = 'Last Login'

    def account_status(self, obj):
        """Display account status with icons"""
        if not obj.is_active:
            return format_html('<span style="color: red;">❌ Inactive</span>')
        else:
            return format_html('<span style="color: green;">✅ Active</span>')
    account_status.short_description = 'Status'


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'username', 'user', 'timestamp', 'ip_address', 'attempt_status',
        'user_agent_display'
    )
    list_filter = ('attempt_type', 'timestamp', 'is_suspicious')
    search_fields = ('username', 'user__username', 'ip_address')
    readonly_fields = ('timestamp',)

    def attempt_status(self, obj):
        """Display attempt status with color coding based on attempt_type field"""
        if obj.attempt_type == 'SUCCESS':
            return format_html('<span style="color: green;">✅ Success</span>')
        else:
            return format_html('<span style="color: red;">❌ {}</span>', obj.get_attempt_type_display())
    attempt_status.short_description = 'Status'

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
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
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
        """Display success status with icons based on is_successful field"""
        if obj.is_successful:
            return format_html('<span style="color: green;">✅</span>')
        else:
            return format_html('<span style="color: red;">❌</span>')
    success_status.short_description = 'Success'

    def has_add_permission(self, request):
        return False


# ================================
# CONDITIONAL OPTIONAL MODEL REGISTRATION
# ================================

if HAS_TWO_FACTOR:
    try:
        @admin.register(TwoFactorAuth)
        class TwoFactorAuthAdmin(admin.ModelAdmin):
            list_display = ('user', 'method', 'is_enabled', 'backup_codes_count', 'last_used')
            list_filter = ('method', 'is_enabled', 'created_at')
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
    except Exception as e:
        print(f"Warning: Could not register TwoFactorAuth admin: {e}")

if HAS_API_KEY:
    try:
        @admin.register(ApiKey)
        class ApiKeyAdmin(admin.ModelAdmin):
            list_display = (
                'name', 'user', 'key_preview', 'is_active',
                'last_used', 'expires_at', 'usage_count'
            )
            list_filter = ('is_active', 'created_at', 'expires_at')
            search_fields = ('name', 'user__username')
            readonly_fields = ('token_key', 'created_at', 'last_used', 'usage_count')

            def key_preview(self, obj):
                """Display preview of API key"""
                if hasattr(obj, 'token_key') and obj.token_key:
                    return obj.token_key[:8] + '...' + obj.token_key[-4:]
                return '-'
            key_preview.short_description = 'API Key'
    except Exception as e:
        print(f"Warning: Could not register ApiKey admin: {e}")


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
        # Reset failed login attempts if the field exists
        if hasattr(profile, 'failed_login_attempts'):
            profile.failed_login_attempts = 0
        if hasattr(profile, 'account_locked_until'):
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
try:
    admin.site.unregister(User)
    admin.site.register(User, CustomUserAdmin)
except Exception as e:
    print(f"Warning: Could not customize User admin: {e}")

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory Management - Authentication"
admin.site.site_title = "BPS Authentication Admin"
admin.site.index_title = "User & Role Management"

print("✅ BPS Authentication Admin loaded successfully!")