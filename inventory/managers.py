# 15. CUSTOM MANAGERS AND METHODS
# ================================
from django.db import models

class ActiveDeviceManager(models.Manager):
    """Custom manager for active devices only"""
    def get_queryset(self):
        return super().get_queryset().exclude(status__in=['RETIRED', 'DISPOSED'])

class AssignedDeviceManager(models.Manager):
    """Custom manager for assigned devices"""
    def get_queryset(self):
        return super().get_queryset().filter(status='ASSIGNED', assignments__is_active=True)

# Add custom managers to Device model
# Device.objects = models.Manager()  # Default manager
# Device.active_objects = ActiveDeviceManager()  # Active devices only
# Device.assigned_objects = AssignedDeviceManager()  # Assigned devices only
