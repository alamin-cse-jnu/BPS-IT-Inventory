# inventory/utils.py - Utility Functions for Inventory Management

from django.db.models import Count, Q, Sum, Avg, Max, Min, F
from django.utils import timezone
from datetime import date, timedelta, datetime
import json
import logging

logger = logging.getLogger(__name__)

def get_device_assignment_summary():
    """Get comprehensive device assignment summary statistics"""
    try:
        from .models import Device, Assignment
        
        today = timezone.now().date()
        
        # Basic counts
        total_devices = Device.objects.count()
        active_assignments = Assignment.objects.filter(is_active=True).count()
        available_devices = Device.objects.filter(status='AVAILABLE').count()
        
        # Overdue assignments
        overdue_assignments = Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=today,
            actual_return_date__isnull=True
        ).count()
        
        # Assignment rate
        assignment_rate = (active_assignments / total_devices * 100) if total_devices > 0 else 0
        
        # Recently assigned (last 7 days)
        week_ago = today - timedelta(days=7)
        recent_assignments = Assignment.objects.filter(
            created_at__date__gte=week_ago
        ).count()
        
        # Recently returned (last 7 days)
        recent_returns = Assignment.objects.filter(
            actual_return_date__gte=week_ago
        ).count()
        
        return {
            'total_devices': total_devices,
            'active_assignments': active_assignments,
            'available_devices': available_devices,
            'overdue_assignments': overdue_assignments,
            'assignment_rate': round(assignment_rate, 1),
            'recent_assignments': recent_assignments,
            'recent_returns': recent_returns,
        }
        
    except Exception as e:
        logger.error(f"Error in get_device_assignment_summary: {e}")
        return {
            'total_devices': 0,
            'active_assignments': 0,
            'available_devices': 0,
            'overdue_assignments': 0,
            'assignment_rate': 0,
            'recent_assignments': 0,
            'recent_returns': 0,
        }

def get_warranty_alerts(days_ahead=30):
    """Get devices with warranties expiring within specified days"""
    try:
        from .models import Device
        
        today = timezone.now().date()
        alert_date = today + timedelta(days=days_ahead)
        
        return Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=alert_date
        ).select_related(
            'device_type__subcategory__category',
            'vendor'
        ).order_by('warranty_end_date')
        
    except Exception as e:
        logger.error(f"Error in get_warranty_alerts: {e}")
        from .models import Device
        return Device.objects.none()

def get_overdue_assignments():
    """Get assignments that are overdue"""
    try:
        from .models import Assignment
        
        today = timezone.now().date()
        
        return Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            expected_return_date__lt=today,
            actual_return_date__isnull=True
        ).select_related(
            'device',
            'assigned_to_staff',
            'assigned_to_department'
        ).order_by('expected_return_date')
        
    except Exception as e:
        logger.error(f"Error in get_overdue_assignments: {e}")
        from .models import Assignment
        return Assignment.objects.none()

def get_device_status_distribution():
    """Get device count by status"""
    try:
        from .models import Device
        
        return Device.objects.values('status').annotate(
            count=Count('id'),
            percentage=Count('id') * 100.0 / Device.objects.count()
        ).order_by('status')
        
    except Exception as e:
        logger.error(f"Error in get_device_status_distribution: {e}")
        return []

def get_assignment_trends(days=30):
    """Get assignment trends over specified days"""
    try:
        from .models import Assignment
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        trends = []
        current_date = start_date
        
        while current_date <= end_date:
            assignments_created = Assignment.objects.filter(
                created_at__date=current_date
            ).count()
            
            assignments_returned = Assignment.objects.filter(
                actual_return_date=current_date
            ).count()
            
            trends.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'created': assignments_created,
                'returned': assignments_returned
            })
            
            current_date += timedelta(days=1)
        
        return trends
        
    except Exception as e:
        logger.error(f"Error in get_assignment_trends: {e}")
        return []

def validate_date_field(date_value, field_name="date"):
    """Validate and safely handle date fields"""
    try:
        if date_value is None:
            return None
        
        if isinstance(date_value, str):
            # Try to parse string date
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(date_value, '%m/%d/%Y').date()
                except ValueError:
                    logger.warning(f"Could not parse date string: {date_value}")
                    return None
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        if isinstance(date_value, date):
            return date_value
        
        logger.warning(f"Unknown date type for {field_name}: {type(date_value)}")
        return None
        
    except Exception as e:
        logger.error(f"Error validating date field {field_name}: {e}")
        return None

def get_recent_activities(limit=10):
    """Get recent system activities"""
    try:
        from .models import AuditLog
        
        return AuditLog.objects.select_related('user').order_by('-timestamp')[:limit]
        
    except Exception as e:
        logger.error(f"Error in get_recent_activities: {e}")
        return []

def calculate_device_age_in_days(purchase_date):
    """Calculate device age in days"""
    try:
        if not purchase_date:
            return None
        
        purchase_date = validate_date_field(purchase_date)
        if not purchase_date:
            return None
        
        today = timezone.now().date()
        return (today - purchase_date).days
        
    except Exception as e:
        logger.error(f"Error calculating device age: {e}")
        return None

def calculate_warranty_status(warranty_end_date):
    """Calculate warranty status and remaining days"""
    try:
        if not warranty_end_date:
            return {'status': 'no_warranty', 'days_remaining': None, 'class': 'secondary'}
        
        warranty_end = validate_date_field(warranty_end_date)
        if not warranty_end:
            return {'status': 'unknown', 'days_remaining': None, 'class': 'secondary'}
        
        today = timezone.now().date()
        days_remaining = (warranty_end - today).days
        
        if days_remaining < 0:
            return {
                'status': 'expired',
                'days_remaining': abs(days_remaining),
                'class': 'danger',
                'text': f'Expired {abs(days_remaining)} days ago'
            }
        elif days_remaining <= 7:
            return {
                'status': 'critical',
                'days_remaining': days_remaining,
                'class': 'danger',
                'text': f'Expires in {days_remaining} days'
            }
        elif days_remaining <= 30:
            return {
                'status': 'warning',
                'days_remaining': days_remaining,
                'class': 'warning',
                'text': f'Expires in {days_remaining} days'
            }
        else:
            return {
                'status': 'active',
                'days_remaining': days_remaining,
                'class': 'success',
                'text': f'Active ({days_remaining} days remaining)'
            }
            
    except Exception as e:
        logger.error(f"Error calculating warranty status: {e}")
        return {'status': 'error', 'days_remaining': None, 'class': 'secondary'}

def generate_device_id(category_code=None, department_code=None):
    """Generate unique device ID"""
    try:
        from .models import Device
        
        # Get current year
        year = timezone.now().year
        
        # Build prefix
        prefix_parts = ['BPS']
        if category_code:
            prefix_parts.append(category_code.upper())
        if department_code:
            prefix_parts.append(department_code.upper())
        
        prefix = '-'.join(prefix_parts)
        
        # Find last device with this prefix pattern
        pattern = f"{prefix}-{year}-"
        last_device = Device.objects.filter(
            device_id__startswith=pattern
        ).order_by('-device_id').first()
        
        if last_device:
            # Extract sequence number
            try:
                last_seq = int(last_device.device_id.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        # Generate new device ID
        new_device_id = f"{prefix}-{year}-{next_seq:04d}"
        
        # Ensure uniqueness
        while Device.objects.filter(device_id=new_device_id).exists():
            next_seq += 1
            new_device_id = f"{prefix}-{year}-{next_seq:04d}"
        
        return new_device_id
        
    except Exception as e:
        logger.error(f"Error generating device ID: {e}")
        # Fallback to timestamp-based ID
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f"BPS-DEV-{timestamp}"

def generate_assignment_id():
    """Generate unique assignment ID"""
    try:
        from .models import Assignment
        
        today = timezone.now().date()
        prefix = f"ASN-{today.strftime('%Y%m%d')}-"
        
        # Find last assignment today
        last_assignment = Assignment.objects.filter(
            assignment_id__startswith=prefix
        ).order_by('-assignment_id').first()
        
        if last_assignment:
            try:
                last_seq = int(last_assignment.assignment_id.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        new_assignment_id = f"{prefix}{next_seq:04d}"
        
        # Ensure uniqueness
        while Assignment.objects.filter(assignment_id=new_assignment_id).exists():
            next_seq += 1
            new_assignment_id = f"{prefix}{next_seq:04d}"
        
        return new_assignment_id
        
    except Exception as e:
        logger.error(f"Error generating assignment ID: {e}")
        # Fallback
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f"ASN-{timestamp}"

def format_currency(amount):
    """Format currency amount"""
    try:
        if amount is None:
            return "N/A"
        return f"৳{amount:,.2f}"
    except:
        return "N/A"

def get_device_location_history(device):
    """Get device location change history"""
    try:
        from .models import Assignment
        
        assignments = Assignment.objects.filter(
            device=device
        ).select_related(
            'assigned_to_location',
            'assigned_to_staff',
            'assigned_to_department'
        ).order_by('-created_at')
        
        history = []
        for assignment in assignments:
            location = None
            if assignment.assigned_to_location:
                location = str(assignment.assigned_to_location)
            elif assignment.assigned_to_staff:
                location = f"Assigned to {assignment.assigned_to_staff}"
            elif assignment.assigned_to_department:
                location = f"Department: {assignment.assigned_to_department}"
            
            if location:
                history.append({
                    'date': assignment.created_at,
                    'location': location,
                    'assignment_id': assignment.assignment_id,
                    'is_active': assignment.is_active
                })
        
        return history
        
    except Exception as e:
        logger.error(f"Error getting device location history: {e}")
        return []

def export_data_to_dict(queryset, fields):
    """Convert queryset to dictionary for export"""
    try:
        data = []
        for obj in queryset:
            row = {}
            for field in fields:
                try:
                    if '.' in field:
                        # Handle related fields
                        value = obj
                        for part in field.split('.'):
                            value = getattr(value, part, None)
                            if value is None:
                                break
                    else:
                        value = getattr(obj, field, None)
                    
                    # Format dates
                    if isinstance(value, (date, datetime)):
                        value = value.strftime('%Y-%m-%d')
                    elif isinstance(value, bool):
                        value = 'Yes' if value else 'No'
                    elif value is None:
                        value = ''
                    
                    row[field] = str(value)
                except:
                    row[field] = ''
            
            data.append(row)
        
        return data
        
    except Exception as e:
        logger.error(f"Error exporting data to dict: {e}")
        return []

def send_notification_email(subject, message, recipient_list):
    """Send notification email (placeholder for future implementation)"""
    try:
        # TODO: Implement email notification
        logger.info(f"Email notification: {subject} to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Error sending notification email: {e}")
        return False

def log_user_activity(user, action, model_name, object_id, object_repr, changes=None, ip_address=None):
    """Log user activity in audit log"""
    try:
        from .models import AuditLog
        
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id else None,
            object_repr=object_repr,
            changes=changes or {},
            ip_address=ip_address
        )
        return True
        
    except Exception as e:
        logger.error(f"Error logging user activity: {e}")
        return False

def get_client_ip(request):
    """Get client IP address from request"""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    except:
        return None

# Device condition scoring
CONDITION_SCORES = {
    'EXCELLENT': 5,
    'GOOD': 4,
    'FAIR': 3,
    'POOR': 2,
    'DAMAGED': 1
}

def calculate_device_condition_score(device):
    """Calculate numerical score for device condition"""
    try:
        return CONDITION_SCORES.get(device.condition, 0)
    except:
        return 0

def get_maintenance_due_devices():
    """Get devices that are due for maintenance"""
    try:
        from .models import Device
        
        # Devices without any maintenance in last 6 months
        six_months_ago = timezone.now().date() - timedelta(days=180)
        
        return Device.objects.filter(
            Q(last_maintenance_date__isnull=True) |
            Q(last_maintenance_date__lt=six_months_ago)
        ).filter(
            status__in=['AVAILABLE', 'ASSIGNED']
        ).order_by('last_maintenance_date')
        
    except Exception as e:
        logger.error(f"Error getting maintenance due devices: {e}")
        from .models import Device
        return Device.objects.none()

def validate_import_data(data, model_type):
    """Validate data for bulk import"""
    try:
        errors = []
        warnings = []
        
        if model_type == 'device':
            required_fields = ['device_name', 'device_type']
            for i, row in enumerate(data):
                for field in required_fields:
                    if not row.get(field):
                        errors.append(f"Row {i+1}: Missing required field '{field}'")
        
        elif model_type == 'staff':
            required_fields = ['first_name', 'last_name', 'employee_id']
            for i, row in enumerate(data):
                for field in required_fields:
                    if not row.get(field):
                        errors.append(f"Row {i+1}: Missing required field '{field}'")
        
        return {'errors': errors, 'warnings': warnings}
        
    except Exception as e:
        logger.error(f"Error validating import data: {e}")
        return {'errors': [str(e)], 'warnings': []}