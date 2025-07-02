
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta

from .models import (
    UserRole, UserProfile, LoginAttempt, UserSession,
    PasswordHistory, SecurityQuestion, UserPreference,
    UserActivity, TwoFactorAuth, ApiKey
)


# ================================
# CUSTOM FILTERS
# ================================

class UserStatusFilter(SimpleListFilter):
    title = 'User Status'
    parameter_name = 'user_status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active Users'),
            ('inactive', 'Inactive Users'),
            ('staff', 'Staff Users'),
            ('superuser', 'Superusers'),
            ('recent_login', 'Recent Login (7 days)'),
            ('no_login', 'Never Logged In'),
        ]

    def queryset(self, request, queryset):
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        elif self.value() == 'staff':
            return queryset.filter(is_staff=True)
        elif self.value() == 'superuser':
            return queryset.filter(is_superuser=True)
        elif self.value() == 'recent_login':
            return queryset.filter(last_login__gte=seven_days_ago)
        elif self.value() == 'no_login':
            return queryset.filter(last_login__isnull=True)
        return queryset


class LoginAttemptStatusFilter(SimpleListFilter):
    title = 'Login Status'
    parameter_name = 'login_status'

    def lookups(self, request, model_admin):
        return [
            ('successful', 'Successful'),
            ('failed', 'Failed'),
            ('blocked', 'Blocked'),
            ('suspicious', 'Suspicious'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'successful':
            return queryset.filter(is_successful=True)
        elif self.value() == 'failed':
            return queryset.filter(is_successful=False)
        elif self.value() == 'blocked':
            return queryset.filter(is_blocked=True)
        elif self.value() == 'suspicious':
            return queryset.filter(is_suspicious=True)
        return queryset


class SessionStatusFilter(SimpleListFilter):
    title = 'Session Status'
    parameter_name = 'session_status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active Sessions'),
            ('expired', 'Expired Sessions'),
            ('ended', 'Manually Ended'),
            ('long_duration', 'Long Duration (>8 hours)'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        eight_hours_ago = now - timedelta(hours=8)
        
        if self.value() == 'active':
            return queryset.filter(is_active=True, expires_at__gt=now)
        elif self.value() == 'expired':
            return queryset.filter(expires_at__lte=now)
        elif self.value() == 'ended':
            return queryset.filter(is_active=False, ended_at__isnull=False)
        elif self.value() == 'long_duration':
            return queryset.filter(
                started_at__lte=eight_hours_ago,
                is_active=True
            )
        return queryset


# ================================
# INLINE ADMIN CLASSES
# ================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fields = (
        'role', 'department', 'phone_number', 'employee_id',
        'profile_picture', 'timezone', 'language', 'theme_preference'
    )


class UserSessionInline(admin.TabularInline):
    model = UserSession
    extra = 0
    readonly_fields = ('session_key', 'started_at', 'last_activity', 'expires_at', 'ip_address')
    fields = ('session_key', 'started_at', 'last_activity', 'is_active', 'ip_address', 'user_agent')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-started_at')[:10]  # Show last 10 sessions


class LoginAttemptInline(admin.TabularInline):
    model = LoginAttempt
    extra = 0
    readonly_fields = ('timestamp', 'ip_address', 'user_agent', 'is_successful')
    fields = ('timestamp', 'ip_address', 'is_successful', 'failure_reason')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-timestamp')[:5]  # Show last 5 attempts


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
        'get_display_name', 'name', 'user_count', 'permission_summary',
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

    def get_display_name(self, obj):
        return obj.display_name
    get_display_name.short_description = 'Role Name'

    def user_count(self, obj):
        count = obj.user_profiles.count()
        return format_html(
            '<a href="{}?role__id__exact={}">{} users</a>',
            reverse('admin:authentication_userprofile_changelist'),
            obj.id,
            count
        )
    user_count.short_description = 'Users'

    def permission_summary(self, obj):
        permissions = []
        if obj.can_view_all_devices:
            permissions.append('View All')
        if obj.can_manage_assignments:
            permissions.append('Manage Assignments')
        if obj.can_approve_requests:
            permissions.append('Approve Requests')
        if obj.can_system_admin:
            permissions.append('System Admin')
        
        return ', '.join(permissions[:3]) + ('...' if len(permissions) > 3 else '')
    permission_summary.short_description = 'Key Permissions'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'employee_id', 'role', 'department', 'phone_number',
        'last_login_display', 'is_active', 'actions'
    )
    list_filter = ('role', 'department', 'timezone', 'language', 'theme_preference')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'employee_id', 'phone_number'
    )
    readonly_fields = ('created_at', 'updated_at', 'last_login_ip', 'login_count')
    
    fieldsets = (
        ('User Account', {
            'fields': ('user', 'employee_id', 'role', 'department')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'emergency_contact', 'address')
        }),
        ('Profile Settings', {
            'fields': ('profile_picture', 'timezone', 'language', 'theme_preference')
        }),
        ('Security Settings', {
            'fields': (
                'two_factor_enabled', 'password_expires_at', 'force_password_change',
                'account_locked_until', 'failed_login_attempts'
            ),
            'classes': ('collapse',)
        }),
        ('Preferences', {
            'fields': ('notification_preferences', 'dashboard_preferences'),
            'classes': ('collapse',)
        }),
        ('Activity Tracking', {
            'fields': (
                'last_login_ip', 'login_count', 'last_password_change',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )

    def last_login_display(self, obj):
        if obj.user.last_login:
            return format_html(
                '<span title="{}">{}</span>',
                obj.user.last_login.strftime('%Y-%m-%d %H:%M:%S'),
                obj.user.last_login.strftime('%m/%d %H:%M')
            )
        return format_html('<span style="color: red;">Never</span>')
    last_login_display.short_description = 'Last Login'

    def is_active(self, obj):
        if obj.user.is_active:
            return format_html('<span style="color: green;">✅ Active</span>')
        else:
            return format_html('<span style="color: red;">❌ Inactive</span>')
    is_active.short_description = 'Status'

    def actions(self, obj):
        actions_html = []
        
        if obj.user.is_active:
            actions_html.append(
                f'<a class="button" href="{reverse("admin:auth_user_change", args=[obj.user.pk])}">Edit User</a>'
            )
        
        if obj.account_locked_until and obj.account_locked_until > timezone.now():
            actions_html.append('<span style="color: red;">🔒 Locked</span>')
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'


# Extend the default User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, UserSessionInline, LoginAttemptInline, PasswordHistoryInline)
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role_display',
        'last_login', 'is_active', 'is_staff', 'login_attempts'
    )
    list_filter = (UserStatusFilter, 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    
    def role_display(self, obj):
        try:
            profile = obj.userprofile
            return profile.role.display_name if profile.role else 'No Role'
        except UserProfile.DoesNotExist:
            return 'No Profile'
    role_display.short_description = 'Role'

    def login_attempts(self, obj):
        failed_attempts = obj.login_attempts.filter(
            is_successful=False,
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        if failed_attempts > 0:
            return format_html(
                '<span style="color: red;">{} failed (24h)</span>',
                failed_attempts
            )
        return 'No failures'
    login_attempts.short_description = 'Recent Login Attempts'


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'timestamp', 'ip_address', 'success_status',
        'failure_reason', 'is_suspicious', 'user_agent_short'
    )
    list_filter = (LoginAttemptStatusFilter, 'timestamp', 'is_suspicious')
    search_fields = ('user__username', 'ip_address', 'failure_reason')
    readonly_fields = ('timestamp',)
    
    fieldsets = (
        ('Login Information', {
            'fields': ('user', 'timestamp', 'ip_address', 'is_successful')
        }),
        ('Failure Details', {
            'fields': ('failure_reason', 'is_blocked', 'is_suspicious'),
        }),
        ('Client Information', {
            'fields': ('user_agent', 'session_key'),
            'classes': ('collapse',)
        }),
    )

    def success_status(self, obj):
        if obj.is_successful:
            return format_html('<span style="color: green;">✅ Success</span>')
        elif obj.is_blocked:
            return format_html('<span style="color: red;">🚫 Blocked</span>')
        elif obj.is_suspicious:
            return format_html('<span style="color: orange;">⚠️ Suspicious</span>')
        else:
            return format_html('<span style="color: red;">❌ Failed</span>')
    success_status.short_description = 'Status'

    def user_agent_short(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + ('...' if len(obj.user_agent) > 50 else '')
        return '-'
    user_agent_short.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False  # Login attempts are created automatically


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session_key_short', 'started_at', 'last_activity',
        'session_status', 'ip_address', 'duration', 'actions'
    )
    list_filter = (SessionStatusFilter, 'started_at', 'is_active')
    search_fields = ('user__username', 'session_key', 'ip_address')
    readonly_fields = ('session_key', 'started_at', 'last_activity', 'expires_at')
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Timing', {
            'fields': ('started_at', 'last_activity', 'expires_at', 'ended_at')
        }),
        ('Client Information', {
            'fields': ('ip_address', 'user_agent', 'device_info'),
        }),
        ('Activity Data', {
            'fields': ('page_views', 'last_url', 'session_data'),
            'classes': ('collapse',)
        }),
    )

    def session_key_short(self, obj):
        return obj.session_key[:12] + '...' if obj.session_key else '-'
    session_key_short.short_description = 'Session Key'

    def session_status(self, obj):
        now = timezone.now()
        if obj.is_active and obj.expires_at > now:
            return format_html('<span style="color: green;">🟢 Active</span>')
        elif obj.expires_at <= now:
            return format_html('<span style="color: orange;">⏰ Expired</span>')
        else:
            return format_html('<span style="color: gray;">⭕ Ended</span>')
    session_status.short_description = 'Status'

    def duration(self, obj):
        if obj.ended_at:
            duration = obj.ended_at - obj.started_at
        elif obj.is_active:
            duration = timezone.now() - obj.started_at
        else:
            duration = obj.expires_at - obj.started_at
        
        hours = duration.total_seconds() / 3600
        if hours < 1:
            return f"{int(duration.total_seconds() / 60)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            return f"{int(hours / 24)}d {int(hours % 24)}h"
    duration.short_description = 'Duration'

    def actions(self, obj):
        if obj.is_active:
            return format_html('<a class="button" href="#" onclick="endSession(\'{}\')">End Session</a>', obj.pk)
        return '-'
    actions.short_description = 'Actions'


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'is_current', 'password_strength')
    list_filter = ('is_current', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'password_hash')

    def password_strength(self, obj):
        # This would normally check password strength
        # For security, we'll just show if it meets basic requirements
        return 'Strong' if obj.is_current else 'Previous'
    password_strength.short_description = 'Strength'

    def has_add_permission(self, request):
        return False


@admin.register(SecurityQuestion)
class SecurityQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
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
        return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
    description_short.short_description = 'Description'

    def success_status(self, obj):
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