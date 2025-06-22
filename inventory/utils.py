# UTILITY FUNCTIONS
# ================================
from django.db.models import Count, Q
from datetime import date, timedelta
from .models import Device, Assignment

def get_device_assignment_summary():
    """Utility function to get device assignment summary"""
    from django.db.models import Count, Q
    
    return Device.objects.aggregate(
        total_devices=Count('id'),
        assigned_devices=Count('id', filter=Q(status='ASSIGNED')),
        available_devices=Count('id', filter=Q(status='AVAILABLE')),
        maintenance_devices=Count('id', filter=Q(status__in=['MAINTENANCE', 'REPAIR']))
    )

def get_warranty_alerts():
    """Get devices with warranty expiring soon"""
    from datetime import date, timedelta
    
    alert_date = date.today() + timedelta(days=30)
    return Device.objects.filter(
        warranty_end_date__lte=alert_date,
        warranty_end_date__gte=date.today(),
        status__in=['ASSIGNED', 'AVAILABLE', 'IN_USE']
    ).order_by('warranty_end_date')

def get_overdue_assignments():
    """Get overdue temporary assignments"""
    from datetime import date
    
    return Assignment.objects.filter(
        is_temporary=True,
        is_active=True,
        expected_return_date__lt=date.today(),
        actual_return_date__isnull=True
    ).select_related('device', 'assigned_to_staff')
