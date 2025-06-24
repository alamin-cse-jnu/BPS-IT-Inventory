# inventory/context_processors.py

from django.conf import settings

def bps_settings(request):
    """Add BPS settings to template context"""
    return {
        'settings': {
            'BPS_VERSION': getattr(settings, 'BPS_VERSION', '1.0.0'),
            'BPS_ORGANIZATION': getattr(settings, 'BPS_ORGANIZATION', 'Bangladesh Parliament Secretariat'),
            'QR_CODE_BASE_URL': getattr(settings, 'QR_CODE_BASE_URL', 'http://127.0.0.1:8000'),
        }
    }

def notifications(request):
    """Add notification context"""
    if request.user.is_authenticated:
        # You can add real notification logic here
        return {
            'unread_notifications': 0,
            'notification_count': 0,
        }
    return {}

def quick_stats(request):
    """Add quick statistics to context"""
    if request.user.is_authenticated:
        try:
            from .models import Device, Assignment
            return {
                'quick_stats': {
                    'total_devices': Device.objects.count(),
                    'active_assignments': Assignment.objects.filter(is_active=True).count(),
                }
            }
        except:
            return {'quick_stats': {'total_devices': 0, 'active_assignments': 0}}
    return {}