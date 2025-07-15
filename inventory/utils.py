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
    """
    Enhanced logging function for user activities with better error handling.
    
    Args:
        user: User performing the action
        action: Action type (CREATE, UPDATE, DELETE, etc.)
        model_name: Name of the model being affected
        object_id: ID of the object
        object_repr: String representation of the object
        changes: Dict of changes made (optional)
        ip_address: IP address of the user (optional)
    """
    try:
        from .models import AuditLog
        
        # Create audit log entry
        audit_log = AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            object_repr=object_repr[:200],  # Limit length
            changes=changes or {},
            ip_address=ip_address or 'Unknown',
            timestamp=timezone.now()
        )
        
        # Log to file as well
        logger.info(
            f"User {user.username} performed {action} on {model_name} "
            f"(ID: {object_id}) from IP {ip_address}"
        )
        
        return audit_log
        
    except Exception as e:
        # Don't let logging failures break the main operation
        logger.error(f"Failed to log user activity: {e}")
        return None

def validate_staff_business_rules(staff_data, instance=None):
    """
    Validate business rules for staff creation/updates.
    
    Args:
        staff_data: Dictionary of staff data
        instance: Existing staff instance (for updates)
    
    Returns:
        tuple: (is_valid, errors_list)
    """
    errors = []
    
    try:
        # Rule 1: Employee ID format validation
        employee_id = staff_data.get('employee_id', '').strip()
        if employee_id:
            if len(employee_id) < 3:
                errors.append("Employee ID must be at least 3 characters long")
            elif len(employee_id) > 20:
                errors.append("Employee ID cannot exceed 20 characters")
            elif not employee_id.replace('-', '').replace('_', '').isalnum():
                errors.append("Employee ID can only contain letters, numbers, hyphens, and underscores")
        
        # Rule 2: Designation validation
        designation = staff_data.get('designation', '').strip()
        if designation and len(designation) < 2:
            errors.append("Designation must be at least 2 characters long")
        
        # Rule 3: Phone number validation
        phone = staff_data.get('phone_number', '').strip()
        if phone:
            clean_phone = ''.join(filter(str.isdigit, phone))
            if len(clean_phone) < 10:
                errors.append("Phone number must contain at least 10 digits")
            elif len(clean_phone) > 15:
                errors.append("Phone number cannot exceed 15 digits")
        
        # Rule 4: Joining date validation
        joining_date = staff_data.get('joining_date')
        if joining_date:
            today = timezone.now().date()
            if joining_date > today:
                errors.append("Joining date cannot be in the future")
            elif joining_date < today - timedelta(days=365 * 50):
                errors.append("Joining date cannot be more than 50 years ago")
        
        # Rule 5: Department validation
        department = staff_data.get('department')
        if department and hasattr(department, 'is_active') and not department.is_active:
            errors.append(f"Department '{department.name}' is not active")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        logger.error(f"Error validating staff business rules: {e}")
        return False, ["Validation error occurred"]
    
def get_staff_statistics():
    """
    Get comprehensive staff statistics for dashboard and reporting.
    
    Returns:
        dict: Statistics about staff members
    """
    try:
        from .models import Staff, Assignment
        from django.db.models import Count, Q
        
        stats = {
            'total_staff': Staff.objects.count(),
            'active_staff': Staff.objects.filter(is_active=True).count(),
            'inactive_staff': Staff.objects.filter(is_active=False).count(),
            'staff_with_assignments': Staff.objects.filter(
                assignments__is_active=True
            ).distinct().count(),
            'staff_by_department': Staff.objects.filter(
                is_active=True
            ).values(
                'department__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10],
            'recent_joiners': Staff.objects.filter(
                joining_date__gte=timezone.now().date() - timedelta(days=30),
                is_active=True
            ).count(),
            'staff_without_department': Staff.objects.filter(
                department__isnull=True,
                is_active=True
            ).count()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting staff statistics: {e}")
        return {}

def send_staff_notification(staff, notification_type, context=None):
    """
    Send notifications to staff members (email, system notifications, etc.).
    
    Args:
        staff: Staff instance
        notification_type: Type of notification
        context: Additional context for the notification
    
    Returns:
        bool: Success status
    """
    try:
        # This is a placeholder for future notification implementation
        # You can integrate with email services, SMS, or push notifications
        
        logger.info(
            f"Notification '{notification_type}' sent to staff {staff.employee_id} "
            f"({staff.get_full_name()})"
        )
        
        # TODO: Implement actual notification sending
        # Examples:
        # - Email notifications for account creation
        # - SMS for urgent assignments
        # - Push notifications for mobile apps
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending notification to staff {staff.employee_id}: {e}")
        return False

def cleanup_inactive_staff_data():
    """
    Cleanup data related to inactive staff members.
    This function can be called periodically (e.g., via cron job).
    
    Returns:
        dict: Cleanup statistics
    """
    try:
        from .models import Staff, Assignment
        
        stats = {
            'inactive_staff_checked': 0,
            'assignments_updated': 0,
            'errors': []
        }
        
        # Find staff members inactive for more than 1 year
        cutoff_date = timezone.now().date() - timedelta(days=365)
        inactive_staff = Staff.objects.filter(
            is_active=False,
            leaving_date__lt=cutoff_date
        )
        
        stats['inactive_staff_checked'] = inactive_staff.count()
        
        for staff in inactive_staff:
            try:
                # Close any remaining active assignments
                active_assignments = Assignment.objects.filter(
                    assigned_to_staff=staff,
                    is_active=True
                )
                
                for assignment in active_assignments:
                    assignment.is_active = False
                    assignment.actual_return_date = timezone.now().date()
                    assignment.return_reason = 'Staff member no longer active'
                    assignment.save()
                    stats['assignments_updated'] += 1
                    
            except Exception as e:
                error_msg = f"Error processing staff {staff.employee_id}: {e}"
                stats['errors'].append(error_msg)
                logger.error(error_msg)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error during staff data cleanup: {e}")
        return {'error': str(e)}

# ================================
# STAFF EXPORT UTILITIES
# ================================

def export_staff_data(queryset, format='excel', include_assignments=False):
    """
    Export staff data in various formats.
    
    Args:
        queryset: Staff queryset to export
        format: Export format ('excel', 'csv', 'json')
        include_assignments: Whether to include assignment data
    
    Returns:
        tuple: (success, data_or_error_message)
    """
    try:
        import pandas as pd
        from io import BytesIO
        
        # Prepare data
        data = []
        for staff in queryset.select_related('user', 'department').prefetch_related('assignments'):
            row = {
                'Employee ID': staff.employee_id,
                'First Name': staff.user.first_name,
                'Last Name': staff.user.last_name,
                'Email': staff.user.email,
                'Designation': staff.designation,
                'Department': str(staff.department) if staff.department else '',
                'Phone Number': staff.phone_number,
                'Joining Date': staff.joining_date.strftime('%Y-%m-%d') if staff.joining_date else '',
                'Is Active': 'Yes' if staff.is_active else 'No',
                'Last Activity': staff.last_activity.strftime('%Y-%m-%d %H:%M') if staff.last_activity else ''
            }
            
            # Include assignment data if requested
            if include_assignments:
                active_assignments = staff.assignments.filter(is_active=True).count()
                total_assignments = staff.assignments.count()
                row.update({
                    'Active Assignments': active_assignments,
                    'Total Assignments': total_assignments
                })
            
            data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Export based on format
        if format.lower() == 'excel':
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Staff Data', index=False)
            return True, buffer.getvalue()
            
        elif format.lower() == 'csv':
            return True, df.to_csv(index=False)
            
        elif format.lower() == 'json':
            return True, df.to_json(orient='records', indent=2)
            
        else:
            return False, f"Unsupported format: {format}"
            
    except Exception as e:
        logger.error(f"Error exporting staff data: {e}")
        return False, str(e)

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