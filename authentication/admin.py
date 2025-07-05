# authentication/admin.py
# Location: bps_inventory/apps/authentication/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import UserRole, UserRoleAssignment, UserProfile, UserSession
from django.urls import reverse
from django.utils import timezone

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
    list_display = (
        'user', 'role', 'department', 'is_active', 'assigned_by'
    )
    list_filter = (
        'is_active', 'role', 'department'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'role__display_name'
    )
    readonly_fields = ('assigned_at', 'updated_at')
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('user', 'role', 'department', 'is_active')
        }),
        ('Assignment Context', {
            'fields': ('assignment_reason', 'assigned_by'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('assigned_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ================================
# USER PROFILE MANAGEMENT
# ================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'department', 'phone_number', 'is_active', 'last_login_date'
    )
    list_filter = (
        'department', 'is_active', 'last_login_date'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'phone_number', 'employee_id'
    )
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id', 'department')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'emergency_contact', 'emergency_phone')
        }),
        ('Settings', {
            'fields': ('language_preference', 'timezone', 'notification_preferences'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'last_login_date'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

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
        'is_active', 'login_time', 'last_activity'
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
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Login Details', {
            'fields': ('ip_address', 'user_agent', 'login_time')
        }),
        ('Activity Tracking', {
            'fields': ('last_activity', 'logout_time'),
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

class UserRoleAssignmentInline(admin.TabularInline):
    model = UserRoleAssignment
    extra = 0
    readonly_fields = ('assigned_at', 'updated_at')

class ExtendedUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, UserRoleAssignmentInline)
    list_display = BaseUserAdmin.list_display + ('get_department', 'get_roles')
    
    def get_department(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.department if profile else 'No Department'
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