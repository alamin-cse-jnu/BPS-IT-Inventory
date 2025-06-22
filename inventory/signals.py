# ================================
# SIGNALS AND POST-SAVE OPERATIONS
# ================================

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import Device, AuditLog, Assignment, AssignmentHistory

@receiver(post_save, sender=Device)
def create_device_audit_log(sender, instance, created, **kwargs):
    """Create audit log entry when device is created or updated"""
    action = 'CREATE' if created else 'UPDATE'
    AuditLog.objects.create(
        user=getattr(instance, '_current_user', None),
        action=action,
        model_name='Device',
        object_id=instance.device_id,
        object_repr=str(instance),
        changes=getattr(instance, '_field_changes', {})
    )

@receiver(post_save, sender=Assignment)
def update_device_status_on_assignment(sender, instance, created, **kwargs):
    """Update device status when assignment is created"""
    if created and instance.is_active:
        instance.device.status = 'ASSIGNED'
        instance.device.save()
        
        # Create assignment history record
        AssignmentHistory.objects.create(
            device=instance.device,
            assignment=instance,
            action='ASSIGNED',
            new_staff=instance.assigned_to_staff,
            new_department=instance.assigned_to_department,
            new_location=instance.assigned_to_location,
            reason=f"New assignment: {instance.assignment_type}",
            changed_by=getattr(instance, '_current_user', None)
        )

@receiver(pre_save, sender=Assignment)
def track_assignment_changes(sender, instance, **kwargs):
    """Track changes in assignment before saving"""
    if instance.pk:  # Existing assignment
        try:
            old_instance = Assignment.objects.get(pk=instance.pk)
            changes = {}
            
            # Check for changes in assignment targets
            if old_instance.assigned_to_staff != instance.assigned_to_staff:
                changes['staff'] = {
                    'old': str(old_instance.assigned_to_staff) if old_instance.assigned_to_staff else None,
                    'new': str(instance.assigned_to_staff) if instance.assigned_to_staff else None
                }
            
            if old_instance.assigned_to_location != instance.assigned_to_location:
                changes['location'] = {
                    'old': str(old_instance.assigned_to_location) if old_instance.assigned_to_location else None,
                    'new': str(instance.assigned_to_location) if instance.assigned_to_location else None
                }
            
            if changes:
                instance._assignment_changes = changes
                instance._old_assignment = old_instance
                
        except Assignment.DoesNotExist:
            pass