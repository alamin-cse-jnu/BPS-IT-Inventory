# authentication/admin.py
# Location: bps_inventory/apps/authentication/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import UserRole, UserRoleAssignment, UserProfile, UserSession
from django.urls import reverse

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
        'user', 'role', 'department', 'is_active', 
        'created_at', 'assigned_by'  # Removed non-existent fields
    )
    list_filter = (
        'is_active', 'role', 'department', 'created_at'  # Removed non-existent fields
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'role__display_name'
    )
    date_hierarchy = 'created_at'  # Changed from non-existent 'effective_from'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('user', 'role', 'department', 'is_active')
        }),
        ('Assignment Context', {
            'fields': ('assignment_reason', 'assigned_by'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'role', 'department', 'assigned_by'
        )

# ================================
# USER PROFILE MANAGEMENT
# ================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'theme', 'language', 'created_at'  # Removed 'is_active' if it doesn't exist
    )
    list_filter = (
        'theme', 'language', 'created_at'  # Removed 'is_active' if it doesn't exist
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name', 'user__email'
    )
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Preferences', {
            'fields': ('theme', 'language')
        }),
        ('Profile Settings', {
            'fields': ('notification_email', 'notification_in_app', 'notification_sms'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# ================================
# USER SESSION MANAGEMENT
# ================================

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session_key_short', 'session_type', 'ip_address', 
        'is_active', 'login_time', 'last_activity'
    )
    list_filter = (
        'is_active', 'session_type', 'login_time', 'last_activity'
    )
    search_fields = (
        'user__username', 'user__email', 'ip_address', 'session_key'
    )
    date_hierarchy = 'login_time'
    readonly_fields = (
        'session_key', 'login_time', 'last_activity', 'logout_time'
    )
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'session_type', 'is_active')
        }),
        ('Connection Details', {
            'fields': ('ip_address', 'user_agent', 'device_info')
        }),
        ('Activity Tracking', {
            'fields': ('login_time', 'last_activity', 'logout_time'),
            'classes': ('collapse',)
        })
    )
    
    def session_key_short(self, obj):
        return obj.session_key[:8] + '...' if obj.session_key else ''
    session_key_short.short_description = 'Session Key'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# ================================
# EXTEND DEFAULT USER ADMIN
# ================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    extra = 0

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

# Unregister and re-register User admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)