# 9. QR CODE & VERIFICATION MODELS
# ================================
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from inventory.models import Device, Location, Staff

class QRCodeScan(models.Model):
    """Log all QR code scans for tracking and verification"""
    SCAN_TYPES = [
        ('VERIFICATION', 'Device Verification'),
        ('LOCATION_UPDATE', 'Location Update'),
        ('ASSIGNMENT_CHECK', 'Assignment Check'),
        ('MAINTENANCE', 'Maintenance Scan'),
        ('AUDIT', 'Audit Scan'),
        ('GENERAL', 'General Scan'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='qr_scans')
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPES, default='VERIFICATION')
    
    # Scan details
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    scan_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Device verification at time of scan
    device_status_at_scan = models.CharField(max_length=20)
    device_location_at_scan = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='scan_verifications')
    assigned_staff_at_scan = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='scan_verifications')
    
    # Technical details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    gps_coordinates = models.CharField(max_length=100, blank=True)
    
    # Results
    verification_success = models.BooleanField(default=True)
    discrepancies_found = models.TextField(blank=True)
    actions_taken = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR Scan: {self.device.device_id} - {self.scan_type} at {self.timestamp}"