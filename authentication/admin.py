# File Location: authentication/admin.py

from django.contrib import admin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserRole, UserRoleAssignment

# ================================
# USER ROLE & PERMISSION ADMIN
# ================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'name', 'permissions_summary', 'access_level', 
        'is_active', 'created_at'
    ]
    list_filter = [
        'name', 'is_active', 'can_view_all_devices', 'can_manage_assignments',
        'can_approve_requests', 'can_manage_users', 'can_system_admin'
    ]
    search_fields = ['display_name', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description')
        }),
        ('Core Permissions', {
            'fields': (
                'can_view_all_devices', 'can_manage_assignments', 
                'can_approve_requests', 'can_generate_reports',
                'can_manage_users', 'can_system_admin'
            )
        }),
        ('Access Restrictions', {
            'fields': ('restricted_to_own_department',)
        }),
        ('Advanced Permissions', {
            'fields': ('permissions',),
            'classes': ('collapse',),
            'description': 'JSON configuration for detailed permissions'
        }),
        ('Status & Audit', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def permissions_summary(self, obj):
        """Display a summary of key permissions"""
        permissions = []
        try:
            if obj.can_view_all_devices:
                permissions.append("View All")
            if obj.can_manage_assignments:
                permissions.append("Manage Assignments")
            if obj.can_approve_requests:
                permissions.append("Approve Requests")
            if obj.can_manage_users:
                permissions.append("Manage Users")
            if obj.can_system_admin:
                permissions.append("System Admin")
            
            return ", ".join(permissions[:3]) + ("..." if len(permissions) > 3 else "")
        except:
            return "Unknown"
    permissions_summary.short_description = "Key Permissions"
    
    def access_level(self, obj):
        """Display access level based on permissions"""
        try:
            if obj.can_system_admin:
                return format_html('<span style="color: red; font-weight: bold;">🔴 System Admin</span>')
            elif obj.can_manage_users:
                return format_html('<span style="color: orange; font-weight: bold;">🟠 Administrator</span>')
            elif obj.can_manage_assignments:
                return format_html('<span style="color: blue; font-weight: bold;">🔵 Manager</span>')
            elif obj.can_generate_reports:
                return format_html('<span style="color: green;">🟢 Staff</span>')
            else:
                return format_html('<span style="color: gray;">⚪ Limited</span>')
        except:
            return format_html('<span style="color: gray;">⚪ Unknown</span>')
    access_level.short_description = "Access Level"

@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'role', 'department', 'get_scope_info', 'get_assignment_period', 
        'is_active', 'assigned_by'
    ]
    list_filter = [
        'role', 'department', 'is_active', 'start_date', 'end_date'
    ]
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'role__display_name', 'department__name'
    ]
    readonly_fields = ['assigned_at']
    
    fieldsets = (
        ('Assignment Information', {
            'fields': ('user', 'role', 'department')
        }),
        ('Assignment Period', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Assignment Details', {
            'fields': ('assigned_by', 'assigned_at', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def get_scope_info(self, obj):
        """Display scope information"""
        try:
            if obj.department:
                return f"Department: {obj.department.name}"
            return "Organization-wide"
        except:
            return "Unknown"
    get_scope_info.short_description = "Scope"
    
    def get_assignment_period(self, obj):
        """Display assignment period"""
        try:
            if obj.end_date:
                return f"{obj.start_date} to {obj.end_date}"
            return f"From {obj.start_date}"
        except:
            return "Unknown"
    get_assignment_period.short_description = "Period"

# ================================
# EXTENDED USER ADMIN
# ================================

class UserRoleAssignmentInline(admin.TabularInline):
    model = UserRoleAssignment
    extra = 0
    readonly_fields = ['assigned_at']
    fields = ['role', 'department', 'start_date', 'end_date', 'is_active']

class CustomUserAdmin(BaseUserAdmin):
    """Extended User admin with role assignments"""
    inlines = [UserRoleAssignmentInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('role_assignments')

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)