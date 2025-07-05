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
    user_count.admin_order_field = 'user_assignments__count'

@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'role', 'department', 'is_active', 
        'effective_from', 'effective_until', 'assigned_by'
    )
    list_filter = (
        'is_active', 'role', 'department', 
        'effective_from', 'created_at'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'role__display_name'
    )
    date_hierarchy = 'effective_from'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('user', 'role', 'department', 'is_active')
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_until')
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
        'user', 'employee_id', 'phone_number', 'department', 
        'last_login_display', 'is_active'
    )
    list_filter = (
        'is_active', 'department', 'created_at',
        'user__last_login', 'user__date_joined'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__email', 'employee_id', 'phone_number'
    )
    readonly_fields = ('created_at', 'updated_at', 'last_login_display')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'department', 'avatar')
        }),
        ('Preferences', {
            'fields': ('theme_preference', 'language_preference'),
            'classes': ('collapse',)
        }),
        ('Activity', {
            'fields': ('last_login_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def last_login_display(self, obj):
        if obj.user.last_login:
            return obj.user.last_login.strftime('%Y-%m-%d %H:%M:%S')
        return 'Never'
    last_login_display.short_description = 'Last Login'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'department'
        )

# ================================
# USER SESSION MANAGEMENT
# ================================

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session_key_short', 'ip_address', 'user_agent_short',
        'is_active', 'created_at', 'last_activity', 'duration'
    )
    list_filter = (
        'is_active', 'created_at', 'last_activity'
    )
    search_fields = (
        'user__username', 'user__email', 'ip_address', 'session_key'
    )
    date_hierarchy = 'created_at'
    readonly_fields = (
        'session_key', 'created_at', 'last_activity', 'duration'
    )
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Connection Details', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Activity Tracking', {
            'fields': ('created_at', 'last_activity', 'duration'),
            'classes': ('collapse',)
        })
    )
    
    def session_key_short(self, obj):
        return f"{obj.session_key[:8]}..."
    session_key_short.short_description = 'Session Key'
    
    def user_agent_short(self, obj):
        if len(obj.user_agent) > 50:
            return f"{obj.user_agent[:47]}..."
        return obj.user_agent
    user_agent_short.short_description = 'User Agent'
    
    def duration(self, obj):
        if obj.last_activity and obj.created_at:
            delta = obj.last_activity - obj.created_at
            hours = delta.total_seconds() / 3600
            return f"{hours:.1f}h"
        return '-'
    duration.short_description = 'Duration'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# ================================
# EXTEND DEFAULT USER ADMIN
# ================================

# Unregister the default User admin
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'role_display', 'is_staff', 'is_active', 'last_login'
    )
    list_filter = (
        'is_staff', 'is_superuser', 'is_active', 
        'date_joined', 'last_login'
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def role_display(self, obj):
        try:
            profile = obj.profile
            roles = obj.role_assignments.filter(is_active=True)
            if roles.exists():
                role_names = [r.role.display_name for r in roles[:2]]
                if roles.count() > 2:
                    role_names.append('...')
                return ', '.join(role_names)
            return 'No Role'
        except:
            return 'No Profile'
    role_display.short_description = 'Roles'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'role_assignments__role'
        )

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

admin.site.site_header = "BPS IT Inventory - Authentication Management"
admin.site.site_title = "BPS Authentication Admin"
admin.site.index_title = "User & Role Management"