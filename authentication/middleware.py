# authentication/middleware.py
# Location: bps_inventory/apps/authentication/middleware.py

import logging
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class AuthenticationManagementMiddleware(MiddlewareMixin):
    """
    Middleware to handle authentication flow and user access management
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # URLs that don't require authentication
        self.exempt_urls = [
            '/auth/login/',
            '/admin/login/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
        
        # URLs that require staff access
        self.staff_required_urls = [
            '/auth/users/',
            '/inventory/',
            '/reports/',
            '/qr/',
        ]
        
        # URLs that require superuser access
        self.superuser_required_urls = [
            '/admin/',
        ]

    def process_request(self, request):
        """Process incoming requests for authentication requirements"""
        
        # Skip exempt URLs
        if any(request.path.startswith(url) for url in self.exempt_urls):
            return None
        
        # Handle API requests differently
        if request.path.startswith('/api/'):
            return self.handle_api_request(request)
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Redirect to login for non-AJAX requests
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.warning(request, 'Please log in to access this page.')
                return redirect(f"{reverse('authentication:login')}?next={request.path}")
            else:
                return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Check if user account is active
        if not request.user.is_active:
            logout(request)
            messages.error(request, 'Your account has been deactivated. Please contact administrator.')
            return redirect('authentication:login')
        
        # Update last activity for authenticated users
        self.update_user_activity(request)
        
        # Check access permissions
        return self.check_access_permissions(request)
    
    def handle_api_request(self, request):
        """Handle API authentication requirements"""
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        if not request.user.is_active:
            return JsonResponse({'error': 'Account deactivated'}, status=403)
        
        return None
    
    def check_access_permissions(self, request):
        """Check if user has required permissions for the requested URL"""
        
        # Superuser URLs - only superusers can access
        if any(request.path.startswith(url) for url in self.superuser_required_urls):
            if not request.user.is_superuser:
                messages.error(request, 'You do not have permission to access this area.')
                return redirect('inventory:dashboard')
        
        # Staff URLs - staff or superuser can access
        elif any(request.path.startswith(url) for url in self.staff_required_urls):
            if not (request.user.is_staff or request.user.is_superuser):
                messages.error(request, 'Staff access required for this area.')
                return redirect('authentication:profile')
        
        # Special handling for specific views
        if '/auth/users/' in request.path and not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'You do not have permission to manage users.')
            return redirect('inventory:dashboard')
        
        return None
    
    def update_user_activity(self, request):
        """Update user's last activity timestamp"""
        try:
            # Update staff profile if exists
            from inventory.models import Staff
            staff = Staff.objects.filter(user=request.user).first()
            if staff:
                # Only update if last activity was more than 5 minutes ago
                if not staff.last_activity or \
                   (timezone.now() - staff.last_activity).total_seconds() > 300:
                    staff.last_activity = timezone.now()
                    staff.save(update_fields=['last_activity'])
            
            # Update session record if exists
            from authentication.models import UserSession
            UserSession.objects.filter(
                user=request.user,
                session_key=request.session.session_key,
                is_active=True
            ).update(last_activity=timezone.now())
            
        except Exception as e:
            # Don't break the request if activity update fails
            logger.warning(f"Failed to update user activity: {str(e)}")
    
    def process_response(self, request, response):
        """Process responses for additional security measures"""
        
        # Add security headers for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            response['X-Frame-Options'] = 'DENY'
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-XSS-Protection'] = '1; mode=block'
        
        return response


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to handle session security and timeout
    """
    
    def process_request(self, request):
        """Check session validity and timeout"""
        
        if not request.user.is_authenticated:
            return None
        
        # Check session timeout
        session_timeout = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 60)
        
        try:
            from authentication.models import UserSession
            user_session = UserSession.objects.filter(
                user=request.user,
                session_key=request.session.session_key,
                is_active=True
            ).first()
            
            if user_session:
                # Check if session has timed out
                time_since_activity = timezone.now() - user_session.last_activity
                if time_since_activity.total_seconds() > (session_timeout * 60):
                    # Session timed out
                    user_session.is_active = False
                    user_session.logout_time = timezone.now()
                    user_session.save()
                    
                    logout(request)
                    messages.warning(request, f'Your session has expired after {session_timeout} minutes of inactivity.')
                    return redirect('authentication:login')
            
        except Exception as e:
            logger.warning(f"Session security check failed: {str(e)}")
        
        return None


class RoleBasedAccessMiddleware(MiddlewareMixin):
    """
    Middleware to enforce role-based access control
    """
    
    def process_request(self, request):
        """Check role-based permissions"""
        
        if not request.user.is_authenticated:
            return None
        
        # Skip for superusers (they have all access)
        if request.user.is_superuser:
            return None
        
        # Get user's active roles
        try:
            from authentication.models import UserRoleAssignment
            user_roles = UserRoleAssignment.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('role').values_list('role__name', flat=True)
            
            # Store roles in request for easy access in views
            request.user_roles = list(user_roles)
            
        except Exception as e:
            logger.warning(f"Failed to get user roles: {str(e)}")
            request.user_roles = []
        
        return None


class DeviceAccessControlMiddleware(MiddlewareMixin):
    """
    Middleware to control device access based on department restrictions
    """
    
    def process_request(self, request):
        """Check device access permissions"""
        
        if not request.user.is_authenticated:
            return None
        
        # Only apply to device-related URLs
        if not any(path in request.path for path in ['/inventory/devices/', '/api/devices/']):
            return None
        
        # Skip for superusers
        if request.user.is_superuser:
            return None
        
        try:
            from authentication.models import UserRoleAssignment
            
            # Check if user has roles that allow viewing all devices
            can_view_all = UserRoleAssignment.objects.filter(
                user=request.user,
                is_active=True,
                role__can_view_all_devices=True
            ).exists()
            
            # Store permission in request
            request.can_view_all_devices = can_view_all
            
            # Get user's department restrictions
            user_departments = UserRoleAssignment.objects.filter(
                user=request.user,
                is_active=True,
                department__isnull=False
            ).values_list('department_id', flat=True)
            
            request.user_departments = list(user_departments)
            
        except Exception as e:
            logger.warning(f"Device access control check failed: {str(e)}")
            request.can_view_all_devices = False
            request.user_departments = []
        
        return None