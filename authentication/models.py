# 13. USER ROLE & PERMISSION MODELS
# ================================
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from inventory.models import Department

class UserRole(models.Model):
    """Extended user roles beyond Django's default groups"""
    ROLE_TYPES = [
        ('IT_ADMINISTRATOR', 'IT Administrator'),
        ('IT_OFFICER', 'IT Officer'),
        ('DEPARTMENT_HEAD', 'Department Head'),
        ('MANAGER', 'Manager'),
        ('GENERAL_STAFF', 'General Staff'),
        ('AUDITOR', 'Auditor'),
        ('VENDOR', 'Vendor/External'),
    ]

    name = models.CharField(max_length=50, choices=ROLE_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Permissions
    permissions = models.JSONField(default=dict, help_text="Detailed permissions configuration")
    
    # Access restrictions
    can_view_all_devices = models.BooleanField(default=False)
    can_manage_assignments = models.BooleanField(default=False)
    can_approve_requests = models.BooleanField(default=False)
    can_generate_reports = models.BooleanField(default=True)
    can_manage_users = models.BooleanField(default=False)
    can_system_admin = models.BooleanField(default=False)
    
    # Departmental restrictions
    restricted_to_own_department = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

class UserRoleAssignment(models.Model):
    """Assign roles to users with additional context"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(UserRole, on_delete=models.CASCADE, related_name='user_assignments')
    
    # Assignment scope
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, help_text="Department scope for this role")
    
    # Temporal assignment
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'role', 'department']

    def __str__(self):
        scope = f" in {self.department.name}" if self.department else ""
        return f"{self.user.username} - {self.role.display_name}{scope}"