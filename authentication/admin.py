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
    permissions_summary.short_description = "Key Permissions"
    
    def access_level(self, obj):
        """Display access level based on permissions"""
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
    access_level.short_description = "Access Level"

@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'role', 'department', 'scope_info', 'assignment_period', 
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
        ('Assignment Audit', {
            'fields': ('assigned_by', 'assigned_at'),
            'classes': ('collapse',)
        })
    )
    
    def scope_info(self, obj):
        """Display scope information for the role assignment"""
        if obj.department:
            return f"Department: {obj.department.name}"
        elif obj.role.restricted_to_own_department:
            return "Own Department Only"
        else:
            return "Organization Wide"
    scope_info.short_description = "Scope"
    
    def assignment_period(self, obj):
        """Display assignment period"""
        if obj.end_date:
            return f"{obj.start_date} to {obj.end_date}"
        else:
            return f"From {obj.start_date} (Ongoing)"
    assignment_period.short_description = "Period"

# ================================
# EXTENDED USER ADMIN (SIMPLIFIED)
# ================================

class UserRoleAssignmentInline(admin.TabularInline):
    """Inline for managing user role assignments"""
    model = UserRoleAssignment
    extra = 0
    fields = ['role', 'department', 'start_date', 'end_date', 'is_active']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('role', 'department')

# Simple approach - don't extend BaseUserAdmin for now
# Just register the inline separately if needed

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

# Custom admin site headers and titles
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Welcome to BPS IT Inventory Management"