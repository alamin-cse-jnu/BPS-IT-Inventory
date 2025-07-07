import logging

from django.conf import settings
from django.utils import timezone
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.contrib.auth import (
    authenticate, login, logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import (
    login_required, user_passes_test
)
from django.contrib.auth.models import User
from django.contrib.auth.forms import (
    AuthenticationForm, UserCreationForm, PasswordChangeForm
)

from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods


logger = logging.getLogger(__name__)

def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Set session expiry
                    if not remember_me:
                        request.session.set_expiry(0)  # Browser close
                    else:
                        request.session.set_expiry(1209600)  # 2 weeks
                    
                    # Update last login activity
                    try:
                        from inventory.models import Staff
                        staff = Staff.objects.filter(user=user).first()
                        if staff:
                            staff.last_activity = timezone.now()
                            staff.save(update_fields=['last_activity'])
                    except:
                        pass
                    
                    messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                    
                    # Redirect to next page or dashboard
                    next_page = request.GET.get('next', 'inventory:dashboard')
                    return redirect(next_page)
                else:
                    messages.error(request, 'Your account has been deactivated.')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    
    context = {
        'title': 'Login - BPS Inventory System',
        'next': request.GET.get('next', ''),
    }
    
    return render(request, 'authentication/login.html', context)

@login_required
def logout_view(request):
    """Custom logout view with audit logging"""
    
    user = request.user
    username = user.username
    
    # Log logout
    logger.info(f"User {username} logged out")
    
    # Create audit log
    try:
        from inventory.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='LOGOUT',
            model_name='User',
            object_id=user.id,
            object_repr=str(user),
            changes={'logout_time': timezone.now().isoformat()},
            ip_address=request.META.get('REMOTE_ADDR')
        )
    except ImportError:
        pass
    
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    
    return redirect('authentication:login')

@login_required
def profile_view(request):
    """User profile management"""
    try:
        # Get staff profile if exists
        staff_profile = None
        try:
            from inventory.models import Staff
            staff_profile = Staff.objects.get(user=request.user)
        except:
            pass
        
        # Get user's recent activity
        recent_assignments = []
        try:
            from inventory.models import Assignment
            recent_assignments = Assignment.objects.filter(
                assigned_to_staff__user=request.user
            ).select_related('device').order_by('-assigned_at')[:5]
        except:
            pass
        
        # Get user statistics
        user_stats = {}
        try:
            from inventory.models import Assignment, AuditLog
            user_stats = {
                'total_assignments': Assignment.objects.filter(assigned_to_staff__user=request.user).count(),
                'active_assignments': Assignment.objects.filter(
                    assigned_to_staff__user=request.user,
                    is_active=True
                ).count(),
                'total_activities': AuditLog.objects.filter(user=request.user).count(),
            }
        except:
            user_stats = {'total_assignments': 0, 'active_assignments': 0, 'total_activities': 0}
        
        context = {
            'staff_profile': staff_profile,
            'recent_assignments': recent_assignments,
            'user_stats': user_stats,
            'title': 'My Profile'
        }
        
        return render(request, 'authentication/profile.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading profile: {str(e)}')
        return redirect('inventory:dashboard')

@login_required
def change_password_view(request):
    """Handle password change"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            
            # Log the activity
            try:
                from inventory.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='UPDATE',
                    model_name='User',
                    object_id=request.user.id,
                    object_repr=str(request.user),
                    changes={'action': 'password_changed'},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            except:
                pass
            
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('authentication:profile')
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'title': 'Change Password'
    }
    
    return render(request, 'authentication/change_password.html', context)

@login_required
@require_http_methods(["POST"])
def update_last_activity(request):
    """AJAX endpoint to update user's last activity"""
    try:
        # Update user's last activity timestamp
        try:
            from inventory.models import Staff
            staff = Staff.objects.filter(user=request.user).first()
            if staff:
                staff.last_activity = timezone.now()
                staff.save(update_fields=['last_activity'])
        except:
            pass
        
        return JsonResponse({
            'status': 'success',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_http_methods(["GET"])
def check_session_status(request):
    """AJAX endpoint to check session status"""
    try:
        session_expiry = request.session.get_expiry_date()
        time_remaining = None
        
        if session_expiry:
            time_remaining = (session_expiry - timezone.now()).total_seconds()
        
        return JsonResponse({
            'authenticated': request.user.is_authenticated,
            'username': request.user.username,
            'expires_at': session_expiry.isoformat() if session_expiry else None,
            'time_remaining_seconds': max(0, time_remaining) if time_remaining else None,
        })
        
    except Exception as e:
        return JsonResponse({
            'authenticated': False,
            'error': str(e)
        }, status=400)

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def user_list(request):
    """List all users (admin only)"""
    try:
        # Get search parameters
        search = request.GET.get('search', '')
        is_active = request.GET.get('is_active', '')
        is_staff = request.GET.get('is_staff', '')
        
        # Build queryset
        users = User.objects.all()
        
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        if is_active:
            users = users.filter(is_active=is_active == 'true')
        
        if is_staff:
            users = users.filter(is_staff=is_staff == 'true')
        
        users = users.order_by('username')
        
        # Pagination
        paginator = Paginator(users, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'is_active': is_active,
            'is_staff': is_staff,
            'title': 'User Management'
        }
        
        return render(request, 'authentication/user_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading users: {str(e)}')
        return redirect('authentication:profile')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def user_detail(request, user_id):
    """View user details (admin only)"""
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Get staff profile if exists
        staff_profile = None
        try:
            from inventory.models import Staff
            staff_profile = Staff.objects.get(user=user)
        except:
            pass
        
        # Get user's assignments
        user_assignments = []
        try:
            from inventory.models import Assignment
            user_assignments = Assignment.objects.filter(
                assigned_to_staff__user=user
            ).select_related('device').order_by('-assigned_at')[:10]
        except:
            pass
        
        # Get user's activity log
        user_activities = []
        try:
            from inventory.models import AuditLog
            user_activities = AuditLog.objects.filter(
                user=user
            ).order_by('-timestamp')[:10]
        except:
            pass
        
        context = {
            'user_profile': user,
            'staff_profile': staff_profile,
            'user_assignments': user_assignments,
            'user_activities': user_activities,
            'title': f'User: {user.get_full_name() or user.username}'
        }
        
        return render(request, 'authentication/user_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading user details: {str(e)}')
        return redirect('authentication:user_list')