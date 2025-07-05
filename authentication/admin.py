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
        'user', 'theme', 'language', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'theme', 'language', 'created_at'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name', 'user__email'
    )
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'is_active')
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
        }),
        ('Security', {
            'fields': ('is_suspicious', 'failed_login_attempts', 'location_data'),
            'classes': ('collapse',)
        })
    )
    
    def session_key_short(self, obj):
        return f"{obj.session_key[:8]}..."
    session_key_short.short_description = 'Session Key'
    
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
        'staff_info', 'is_staff', 'is_active', 'last_login'
    )
    list_filter = (
        'is_staff', 'is_superuser', 'is_active', 
        'date_joined', 'last_login'
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def staff_info(self, obj):
        try:
            if hasattr(obj, 'staff_profile'):
                staff = obj.staff_profile
                return f"{staff.employee_id} - {staff.designation}"
            return 'No Staff Profile'
        except:
            return 'No Staff Profile'
    staff_info.short_description = 'Staff Info'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('staff_profile')

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================
admin.site.site_header = "BPS IT Inventory - Authentication Management"
admin.site.site_title = "BPS Authentication Admin"
admin.site.index_title = "User & Role Management"