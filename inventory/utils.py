# inventory/utils.py - FIXED VERSION

from django.utils import timezone
from datetime import timedelta, datetime, date
from django.db.models import Count, Q
from django.core.exceptions import ObjectDoesNotExist


def get_warranty_alerts(days_ahead=30):
    """Get devices with warranty alerts - FIXED VERSION"""
    from .models import Device
    
    # Calculate dates properly using timezone-aware dates
    today = timezone.now().date()
    alert_date = today + timedelta(days=days_ahead)
    
    try:
        # Query with proper date filtering
        devices = Device.objects.filter(
            warranty_end_date__gte=today,
            warranty_end_date__lte=alert_date,
            status__in=['AVAILABLE', 'ASSIGNED', 'MAINTENANCE']
        ).order_by('warranty_end_date')
        
        # Ensure all date fields are proper date objects
        processed_devices = []
        for device in devices:
            # Verify warranty_end_date is a proper date object
            if device.warranty_end_date:
                if isinstance(device.warranty_end_date, str):
                    try:
                        device.warranty_end_date = datetime.strptime(device.warranty_end_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        continue  # Skip invalid dates
                
                # Add warranty_expires_soon property dynamically
                days_remaining = (device.warranty_end_date - today).days
                device.warranty_expires_soon = 0 <= days_remaining <= 7
                
                processed_devices.append(device)
        
        return processed_devices
        
    except Exception as e:
        print(f"Error in get_warranty_alerts: {e}")
        return []


def get_device_assignment_summary():
    """Get device assignment summary - FIXED VERSION"""
    from .models import Device, Assignment
    
    try:
        # Use proper aggregation with error handling
        today = timezone.now().date()
        
        # Basic counts
        total_devices = Device.objects.count()
        active_assignments = Assignment.objects.filter(is_active=True).count()
        available_devices = Device.objects.filter(status='AVAILABLE').count()
        under_maintenance = Device.objects.filter(status='MAINTENANCE').count()
        
        # Overdue assignments with proper date handling
        try:
            overdue_assignments = Assignment.objects.filter(
                is_temporary=True,
                is_active=True,
                expected_return_date__lt=today,
                actual_return_date__isnull=True
            ).count()
        except Exception:
            overdue_assignments = 0
        
        summary = {
            'total_devices': total_devices,
            'active_assignments': active_assignments,
            'available_devices': available_devices,
            'under_maintenance': under_maintenance,
            'overdue_assignments': overdue_assignments,
            'total_staff_assignments': Assignment.objects.filter(
                is_active=True,
                assigned_to_staff__isnull=False
            ).count(),
            'total_department_assignments': Assignment.objects.filter(
                is_active=True,
                assigned_to_department__isnull=False
            ).count(),
        }
        
        return summary
        
    except Exception as e:
        print(f"Error in get_device_assignment_summary: {e}")
        # Return safe fallback
        return {
            'total_devices': 0,
            'active_assignments': 0,
            'available_devices': 0,
            'under_maintenance': 0,
            'overdue_assignments': 0,
            'total_staff_assignments': 0,
            'total_department_assignments': 0,
        }


def get_device_status_distribution():
    """Get device status distribution for charts"""
    from .models import Device
    
    try:
        status_distribution = Device.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        return list(status_distribution)
    except Exception as e:
        print(f"Error in get_device_status_distribution: {e}")
        return []


def get_assignment_trends(days=30):
    """Get assignment trends for the last N days"""
    from .models import Assignment
    
    try:
        start_date = timezone.now().date() - timedelta(days=days)
        
        assignments = Assignment.objects.filter(
            created_at__date__gte=start_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        return list(assignments)
    except Exception as e:
        print(f"Error in get_assignment_trends: {e}")
        return []


def validate_date_field(date_value, field_name="date"):
    """Validate and convert date field to proper date object"""
    if date_value is None:
        return None
    
    if isinstance(date_value, date):
        return date_value
    
    if isinstance(date_value, datetime):
        return date_value.date()
    
    if isinstance(date_value, str):
        try:
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                try:
                    parsed_date = datetime.strptime(date_value, fmt)
                    return parsed_date.date()
                except ValueError:
                    continue
            
            # If no format worked, raise error
            raise ValueError(f"Unable to parse date: {date_value}")
            
        except Exception as e:
            print(f"Error parsing {field_name}: {date_value} - {e}")
            return None
    
    return None


def safe_date_difference(date1, date2):
    """Safely calculate difference between two dates"""
    try:
        if date1 and date2:
            date1 = validate_date_field(date1)
            date2 = validate_date_field(date2)
            
            if date1 and date2:
                return (date1 - date2).days
        return None
    except Exception:
        return None


def get_recent_activities(limit=10):
    """Get recent system activities with proper date handling"""
    from .models import Assignment, Device
    
    try:
        activities = []
        
        # Recent assignments
        recent_assignments = Assignment.objects.select_related(
            'device', 'assigned_to_staff', 'created_by'
        ).order_by('-created_at')[:limit]
        
        for assignment in recent_assignments:
            activities.append({
                'type': 'assignment',
                'description': f"Device {assignment.device.device_name} assigned",
                'timestamp': assignment.created_at,
                'user': assignment.created_by,
                'object': assignment
            })
        
        # Recent device updates
        recent_devices = Device.objects.select_related(
            'updated_by'
        ).order_by('-updated_at')[:limit]
        
        for device in recent_devices:
            activities.append({
                'type': 'device_update',
                'description': f"Device {device.device_name} updated",
                'timestamp': device.updated_at,
                'user': device.updated_by,
                'object': device
            })
        
        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return activities[:limit]
        
    except Exception as e:
        print(f"Error in get_recent_activities: {e}")
        return []


def format_device_summary(device):
    """Format device summary with safe date handling"""
    try:
        summary = {
            'device_id': device.device_id,
            'device_name': device.device_name,
            'status': device.status,
            'category': device.device_type.subcategory.category.name if device.device_type else 'Unknown',
            'purchase_date': device.purchase_date.strftime('%Y-%m-%d') if device.purchase_date else 'N/A',
            'warranty_end': device.warranty_end_date.strftime('%Y-%m-%d') if device.warranty_end_date else 'N/A',
            'is_warranty_active': device.is_warranty_active if hasattr(device, 'is_warranty_active') else False,
        }
        
        return summary
    except Exception as e:
        print(f"Error formatting device summary: {e}")
        return {'error': 'Unable to format device summary'}


def get_overdue_returns():
    """Get overdue assignment returns with proper date validation"""
    from .models import Assignment
    
    try:
        today = timezone.now().date()
        
        overdue = Assignment.objects.filter(
            is_temporary=True,
            is_active=True,
            actual_return_date__isnull=True
        ).select_related('device', 'assigned_to_staff')
        
        # Filter with proper date validation
        validated_overdue = []
        for assignment in overdue:
            if assignment.expected_return_date:
                expected_date = validate_date_field(assignment.expected_return_date)
                if expected_date and expected_date < today:
                    # Calculate days overdue
                    assignment.days_overdue = (today - expected_date).days
                    validated_overdue.append(assignment)
        
        return validated_overdue
        
    except Exception as e:
        print(f"Error in get_overdue_returns: {e}")
        return []


def get_overdue_assignments():
    """Alias for get_overdue_returns - for compatibility with views.py import"""
    return get_overdue_returns()


def cleanup_invalid_dates():
    """Utility function to cleanup invalid date entries"""
    from .models import Device, Assignment
    
    cleaned_count = 0
    
    try:
        # Check devices
        for device in Device.objects.all():
            updated = False
            
            # Check purchase_date
            if device.purchase_date and isinstance(device.purchase_date, str):
                validated_date = validate_date_field(device.purchase_date)
                if validated_date:
                    device.purchase_date = validated_date
                    updated = True
                else:
                    device.purchase_date = None
                    updated = True
            
            # Check warranty_end_date
            if device.warranty_end_date and isinstance(device.warranty_end_date, str):
                validated_date = validate_date_field(device.warranty_end_date)
                if validated_date:
                    device.warranty_end_date = validated_date
                    updated = True
                else:
                    device.warranty_end_date = None
                    updated = True
            
            if updated:
                device.save()
                cleaned_count += 1
        
        # Check assignments
        for assignment in Assignment.objects.all():
            updated = False
            
            # Check start_date
            if hasattr(assignment, 'start_date') and assignment.start_date and isinstance(assignment.start_date, str):
                validated_date = validate_date_field(assignment.start_date)
                if validated_date:
                    assignment.start_date = validated_date
                    updated = True
                else:
                    assignment.start_date = None
                    updated = True
            
            # Check expected_return_date
            if assignment.expected_return_date and isinstance(assignment.expected_return_date, str):
                validated_date = validate_date_field(assignment.expected_return_date)
                if validated_date:
                    assignment.expected_return_date = validated_date
                    updated = True
                else:
                    assignment.expected_return_date = None
                    updated = True
            
            if updated:
                assignment.save()
                cleaned_count += 1
        
        return cleaned_count
        
    except Exception as e:
        print(f"Error in cleanup_invalid_dates: {e}")
        return 0