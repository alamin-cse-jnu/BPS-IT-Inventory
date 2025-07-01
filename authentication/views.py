# authentication/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

@csrf_protect
@never_cache
def login_view(request):
    """Custom login view with enhanced security and logging"""
    
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Log successful login
                    logger.info(f"User {username} logged in successfully from IP {request.META.get('REMOTE_ADDR')}")
                    
                    # Create audit log if model exists
                    try:
                        from inventory.models import AuditLog
                        AuditLog.objects.create(
                            user=user,
                            action='LOGIN',
                            model_name='User',
                            object_id=user.id,
                            object_repr=str(user),
                            changes={'login_time': timezone.now().isoformat()},
                            ip_address=request.META.get('REMOTE_ADDR'),
                            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                        )
                    except ImportError:
                        pass
                    
                    # Set session variables
                    request.session['last_activity'] = timezone.now().isoformat()
                    request.session['login_time'] = timezone.now().isoformat()
                    
                    messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                    
                    # Redirect to next parameter or dashboard
                    next_url = request.GET.get('next', 'inventory:dashboard')
                    return redirect(next_url)
                else:
                    messages.error(request, 'Your account has been deactivated. Please contact administrator.')
                    logger.warning(f"Inactive user {username} attempted login from IP {request.META.get('REMOTE_ADDR')}")
            else:
                messages.error(request, 'Invalid username or password.')
                logger.warning(f"Failed login attempt for username {username} from IP {request.META.get('REMOTE_ADDR')}")
        else:
            messages.error(request, 'Please correct the errors below.')
            logger.warning(f"Login form validation failed from IP {request.META.get('REMOTE_ADDR')}")
    else:
        form = AuthenticationForm()
    
    context = {
        'form': form,
        'title': 'Login - BPS Inventory System',
        'system_name': 'BPS IT Inventory Management System',
        'organization': 'Bangladesh Parliament Secretariat'
    }
    
    return render(request, 'registration/login.html', context)

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
    """User profile view"""
    
    user = request.user
    
    # Get user's recent activity
    recent_activity = []
    try:
        from inventory.models import AuditLog
        recent_activity = AuditLog.objects.filter(
            user=user
        ).order_by('-timestamp')[:10]
    except ImportError:
        pass
    
    # Get user's assignments if they're a staff member
    staff_assignments = []
    try:
        from inventory.models import Staff, Assignment
        staff = Staff.objects.filter(user=user).first()
        if staff:
            staff_assignments = Assignment.objects.filter(
                assigned_to_staff=staff,
                is_active=True
            ).select_related('device')[:5]
    except ImportError:
        pass
    
    context = {
        'user': user,
        'recent_activity': recent_activity,
        'staff_assignments': staff_assignments,
    }
    
    return render(request, 'authentication/profile.html', context)

@login_required
def change_password_view(request):
    """Change password view"""
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important for keeping user logged in
            
            # Log password change
            logger.info(f"User {user.username} changed password")
            
            # Create audit log
            try:
                from inventory.models import AuditLog
                AuditLog.objects.create(
                    user=user,
                    action='PASSWORD_CHANGE',
                    model_name='User',
                    object_id=user.id,
                    object_repr=str(user),
                    changes={'password_changed': timezone.now().isoformat()},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            except ImportError:
                pass
            
            messages.success(request, 'Your password has been successfully changed.')
            return redirect('authentication:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'title': 'Change Password'
    }
    
    return render(request, 'registration/password_change_form.html', context)

@login_required
@require_http_methods(["POST"])
def update_last_activity(request):
    """AJAX endpoint to update user's last activity"""
    
    request.session['last_activity'] = timezone.now().isoformat()
    
    return JsonResponse({
        'success': True,
        'timestamp': timezone.now().isoformat()
    })

@require_http_methods(["GET"])
def check_session_status(request):
    """Check if user session is still valid"""
    
    if not request.user.is_authenticated:
        return JsonResponse({
            'authenticated': False,
            'redirect_url': reverse_lazy('authentication:login')
        })
    
    # Check session timeout
    last_activity = request.session.get('last_activity')
    if last_activity:
        try:
            from datetime import datetime
            last_activity_time = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            timeout_minutes = getattr(settings, 'AUTO_LOGOUT_MINUTES', 60)
            
            if (timezone.now() - last_activity_time).total_seconds() > (timeout_minutes * 60):
                logout(request)
                return JsonResponse({
                    'authenticated': False,
                    'timeout': True,
                    'redirect_url': reverse_lazy('authentication:login')
                })
        except:
            pass
    
    return JsonResponse({
        'authenticated': True,
        'user': {
            'username': request.user.username,
            'full_name': request.user.get_full_name(),
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser
        }
    })

# User management views for admins
@login_required
def user_list(request):
    """List all users (admin only)"""
    
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('inventory:dashboard')
    
    users = User.objects.all().order_by('username')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        from django.db.models import Q
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'title': 'User Management'
    }
    
    return render(request, 'authentication/user_list.html', context)

@login_required
def user_detail(request, user_id):
    """User detail view (admin only)"""
    
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('inventory:dashboard')
    
    from django.shortcuts import get_object_or_404
    user = get_object_or_404(User, id=user_id)
    
    # Get user's audit logs
    recent_activity = []
    try:
        from inventory.models import AuditLog
        recent_activity = AuditLog.objects.filter(
            user=user
        ).order_by('-timestamp')[:20]
    except ImportError:
        pass
    
    context = {
        'user_detail': user,  # Renamed to avoid conflict with request.user
        'recent_activity': recent_activity,
        'title': f'User: {user.username}'
    }
    
    return render(request, 'authentication/user_detail.html', context)