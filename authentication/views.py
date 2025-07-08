# authentication/views.py
# Location: bps_inventory/apps/authentication/views.py

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
    """Enhanced login view that handles all user types"""
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
                    
                    # Update last activity for staff users
                    try:
                        from inventory.models import Staff
                        staff = Staff.objects.filter(user=user).first()
                        if staff:
                            staff.last_activity = timezone.now()
                            staff.save(update_fields=['last_activity'])
                    except Exception:
                        pass
                    
                    # Log successful login
                    try:
                        from authentication.models import UserSession
                        UserSession.objects.create(
                            user=user,
                            session_key=request.session.session_key,
                            ip_address=request.META.get('REMOTE_ADDR'),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                            login_time=timezone.now(),
                            last_activity=timezone.now(),
                            is_active=True
                        )
                    except Exception:
                        pass
                    
                    # Determine user type and welcome message
                    if user.is_superuser:
                        user_type = "Administrator"
                    elif user.is_staff:
                        user_type = "Staff Member"
                    else:
                        user_type = "User"
                    
                    messages.success(
                        request, 
                        f'Welcome back, {user.get_full_name() or user.username}! '
                        f'Logged in as {user_type}.'
                    )
                    
                    # Redirect based on user type
                    next_page = request.GET.get('next', 'inventory:dashboard')
                    
                    # Special handling for superusers
                    if user.is_superuser and 'admin' in request.GET.get('from', ''):
                        return redirect('/admin/')
                    
                    return redirect(next_page)
                else:
                    messages.error(request, 'Your account has been deactivated.')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    
    context = {
        'title': 'Login - BPS Inventory',
        'show_remember_me': True,
        'allow_registration': False,  # Set to True if you want to allow user registration
    }
    
    return render(request, 'authentication/login.html', context)

def logout_view(request):
    """Enhanced logout view with session cleanup"""
    try:
        # Update session record
        from authentication.models import UserSession
        UserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            is_active=True
        ).update(
            logout_time=timezone.now(),
            is_active=False
        )
    except Exception:
        pass
    
    user_name = request.user.get_full_name() or request.user.username
    logout(request)
    messages.success(request, f'Goodbye {user_name}! You have been logged out successfully.')
    return redirect('authentication:login')

@login_required
def profile_view(request):
    """Enhanced user profile view"""
    try:
        # Get staff profile if exists
        staff_profile = None
        try:
            from inventory.models import Staff
            staff_profile = Staff.objects.get(user=request.user)
        except Staff.DoesNotExist:
            pass
        
        # Get user profile if exists
        user_profile = None
        try:
            from authentication.models import UserProfile
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            # Create user profile if it doesn't exist
            user_profile = UserProfile.objects.create(user=request.user)
        
        # Get user's role assignments
        user_roles = []
        try:
            from authentication.models import UserRoleAssignment
            user_roles = UserRoleAssignment.objects.filter(
                user=request.user, 
                is_active=True
            ).select_related('role')
        except Exception:
            pass
        
        # Get user's recent activity
        recent_assignments = []
        try:
            from inventory.models import Assignment
            recent_assignments = Assignment.objects.filter(
                assigned_to_staff__user=request.user
            ).select_related('device').order_by('-assigned_at')[:5]
        except Exception:
            pass
        
        # Get user statistics
        user_stats = {}
        try:
            from inventory.models import Assignment, AuditLog
            user_stats = {
                'total_assignments': Assignment.objects.filter(
                    assigned_to_staff__user=request.user
                ).count(),
                'active_assignments': Assignment.objects.filter(
                    assigned_to_staff__user=request.user,
                    is_active=True
                ).count(),
                'total_activities': AuditLog.objects.filter(
                    user=request.user
                ).count(),
                'login_count': request.user.usersession_set.count(),
            }
        except Exception:
            user_stats = {
                'total_assignments': 0, 
                'active_assignments': 0, 
                'total_activities': 0,
                'login_count': 0
            }
        
        context = {
            'user_profile': user_profile,
            'staff_profile': staff_profile,
            'user_roles': user_roles,
            'recent_assignments': recent_assignments,
            'user_stats': user_stats,
            'title': 'My Profile',
            'is_superuser': request.user.is_superuser,
            'is_staff': request.user.is_staff,
        }
        
        return render(request, 'authentication/profile.html', context)
        
    except Exception as e:
        logger.error(f"Error loading profile for user {request.user.id}: {str(e)}")
        messages.error(request, f'Error loading profile: {str(e)}')
        return redirect('inventory:dashboard')

@login_required
def change_password_view(request):
    """Handle password change with enhanced security"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            
            # Update user profile password change timestamp
            try:
                from authentication.models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.last_password_change = timezone.now()
                profile.save(update_fields=['last_password_change'])
            except Exception:
                pass
            
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
            except Exception:
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
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def user_list(request):
    """Enhanced user list with better filtering and role information"""
    try:
        # Get search parameters
        search = request.GET.get('search', '')
        is_active = request.GET.get('is_active', '')
        is_staff = request.GET.get('is_staff', '')
        role_filter = request.GET.get('role', '')
        
        # Build queryset
        users = User.objects.select_related('user_profile').prefetch_related(
            'role_assignments__role', 'staff_profile'
        )
        
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
        
        if role_filter:
            users = users.filter(
                role_assignments__role__name=role_filter,
                role_assignments__is_active=True
            )
        
        users = users.distinct().order_by('username')
        
        # Get available roles for filter
        available_roles = []
        try:
            from authentication.models import UserRole
            available_roles = UserRole.objects.filter(is_active=True)
        except Exception:
            pass
        
        # Pagination
        paginator = Paginator(users, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'is_active': is_active,
            'is_staff': is_staff,
            'role_filter': role_filter,
            'available_roles': available_roles,
            'title': 'User Management',
            'total_users': users.count(),
        }
        
        return render(request, 'authentication/user_list.html', context)
        
    except Exception as e:
        logger.error(f"Error loading user list: {str(e)}")
        messages.error(request, f'Error loading users: {str(e)}')
        return redirect('authentication:profile')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def user_detail(request, user_id):
    """Enhanced user detail view with role management"""
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Get staff profile if exists
        staff_profile = None
        try:
            from inventory.models import Staff
            staff_profile = Staff.objects.get(user=user)
        except Staff.DoesNotExist:
            pass
        
        # Get user profile if exists
        user_profile = None
        try:
            from authentication.models import UserProfile
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            pass
        
        # Get user's role assignments
        user_roles = []
        try:
            from authentication.models import UserRoleAssignment
            user_roles = UserRoleAssignment.objects.filter(
                user=user, 
                is_active=True
            ).select_related('role', 'department')
        except Exception:
            pass
        
        # Get user's assignments
        user_assignments = []
        try:
            from inventory.models import Assignment
            user_assignments = Assignment.objects.filter(
                assigned_to_staff__user=user
            ).select_related('device').order_by('-assigned_at')[:10]
        except Exception:
            pass
        
        # Get user's activity log
        user_activities = []
        try:
            from inventory.models import AuditLog
            user_activities = AuditLog.objects.filter(
                user=user
            ).order_by('-timestamp')[:10]
        except Exception:
            pass
        
        # Get user sessions
        user_sessions = []
        try:
            from authentication.models import UserSession
            user_sessions = UserSession.objects.filter(
                user=user
            ).order_by('-login_time')[:5]
        except Exception:
            pass
        
        context = {
            'user_profile': user,
            'extended_profile': user_profile,
            'staff_profile': staff_profile,
            'user_roles': user_roles,
            'user_assignments': user_assignments,
            'user_activities': user_activities,
            'user_sessions': user_sessions,
            'title': f'User: {user.get_full_name() or user.username}',
            'can_edit': request.user.is_superuser or request.user.has_perm('auth.change_user'),
        }
        
        return render(request, 'authentication/user_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading user detail for user {user_id}: {str(e)}")
        messages.error(request, f'Error loading user details: {str(e)}')
        return redirect('authentication:user_list')

# AJAX Views for session management
@login_required
@require_http_methods(["POST"])
def update_last_activity(request):
    """AJAX endpoint to update user's last activity"""
    try:
        # Update staff activity if exists
        try:
            from inventory.models import Staff
            staff = Staff.objects.filter(user=request.user).first()
            if staff:
                staff.last_activity = timezone.now()
                staff.save(update_fields=['last_activity'])
        except Exception:
            pass
        
        # Update session activity
        try:
            from authentication.models import UserSession
            UserSession.objects.filter(
                user=request.user,
                session_key=request.session.session_key,
                is_active=True
            ).update(last_activity=timezone.now())
        except Exception:
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
            'user_type': 'superuser' if request.user.is_superuser else 'staff' if request.user.is_staff else 'user',
            'expires_at': session_expiry.isoformat() if session_expiry else None,
            'time_remaining_seconds': max(0, time_remaining) if time_remaining else None,
        })
        
    except Exception as e:
        return JsonResponse({
            'authenticated': False,
            'error': str(e)
        }, status=400)
    
@login_required
@user_passes_test(lambda u: u.is_superuser or (u.is_staff and u.has_perm('auth.add_user')))
def create_staff_user(request):
    """Create new staff user with proper role assignment"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                username = request.POST.get('username')
                email = request.POST.get('email')
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                password = request.POST.get('password')
                confirm_password = request.POST.get('confirm_password')
                employee_id = request.POST.get('employee_id')
                phone_number = request.POST.get('phone_number')
                department_id = request.POST.get('department')
                role_name = request.POST.get('role')
                is_staff = request.POST.get('is_staff') == 'on'
                
                # Validation
                if password != confirm_password:
                    messages.error(request, 'Passwords do not match.')
                    return redirect('authentication:create_staff_user')
                
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists.')
                    return redirect('authentication:create_staff_user')
                
                if email and User.objects.filter(email=email).exists():
                    messages.error(request, 'Email already exists.')
                    return redirect('authentication:create_staff_user')
                
                # Create Django User
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=is_staff,
                    is_active=True
                )
                
                # Create UserProfile
                from authentication.models import UserProfile
                user_profile = UserProfile.objects.create(
                    user=user,
                    phone_number=phone_number,
                    employee_id=employee_id,
                )
                
                # Set default department if provided
                if department_id:
                    try:
                        from inventory.models import Department
                        department = Department.objects.get(id=department_id)
                        user_profile.default_department = department
                        user_profile.save()
                    except Department.DoesNotExist:
                        pass
                
                # Create Staff profile if required
                if is_staff and employee_id:
                    try:
                        from inventory.models import Staff, Department
                        department = None
                        if department_id:
                            department = Department.objects.get(id=department_id)
                        
                        Staff.objects.create(
                            user=user,
                            employee_id=employee_id,
                            phone_number=phone_number,
                            department=department,
                            is_active=True
                        )
                    except Exception as e:
                        logger.error(f"Error creating staff profile: {str(e)}")
                
                # Assign role
                if role_name:
                    try:
                        from authentication.models import UserRole, UserRoleAssignment
                        role = UserRole.objects.get(name=role_name, is_active=True)
                        
                        UserRoleAssignment.objects.create(
                            user=user,
                            role=role,
                            department_id=department_id if department_id else None,
                            assigned_by=request.user,
                            is_active=True
                        )
                    except UserRole.DoesNotExist:
                        logger.error(f"Role {role_name} not found")
                
                # Log the activity
                try:
                    from inventory.models import AuditLog
                    AuditLog.objects.create(
                        user=request.user,
                        action='CREATE',
                        model_name='User',
                        object_id=user.id,
                        object_repr=str(user),
                        changes={
                            'username': username,
                            'email': email,
                            'role': role_name,
                            'department': department_id,
                            'is_staff': is_staff
                        },
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except Exception:
                    pass
                
                messages.success(
                    request, 
                    f'User {username} created successfully with role {role_name}!'
                )
                return redirect('authentication:user_detail', user_id=user.id)
                
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            messages.error(request, f'Error creating user: {str(e)}')
    
    # Get available departments and roles
    departments = []
    roles = []
    try:
        from inventory.models import Department
        from authentication.models import UserRole
        departments = Department.objects.filter(is_active=True)
        roles = UserRole.objects.filter(is_active=True)
    except Exception:
        pass
    
    context = {
        'title': 'Create New Staff User',
        'departments': departments,
        'roles': roles,
    }
    
    return render(request, 'authentication/create_staff_user.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or (u.is_staff and u.has_perm('auth.change_user')))
def edit_user_roles(request, user_id):
    """Edit user roles and permissions"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get new role assignments
                new_roles = request.POST.getlist('roles')
                departments = request.POST.getlist('departments')
                
                # Deactivate current role assignments
                from authentication.models import UserRoleAssignment
                UserRoleAssignment.objects.filter(
                    user=user, 
                    is_active=True
                ).update(
                    is_active=False,
                    deactivated_by=request.user,
                    deactivated_at=timezone.now()
                )
                
                # Create new role assignments
                from authentication.models import UserRole
                for i, role_name in enumerate(new_roles):
                    try:
                        role = UserRole.objects.get(name=role_name, is_active=True)
                        department_id = departments[i] if i < len(departments) and departments[i] else None
                        
                        UserRoleAssignment.objects.create(
                            user=user,
                            role=role,
                            department_id=department_id,
                            assigned_by=request.user,
                            is_active=True
                        )
                    except (UserRole.DoesNotExist, IndexError):
                        continue
                
                # Update user staff status based on roles
                has_staff_role = UserRoleAssignment.objects.filter(
                    user=user,
                    role__name__in=['IT_ADMINISTRATOR', 'IT_OFFICER', 'DEPARTMENT_HEAD', 'MANAGER'],
                    is_active=True
                ).exists()
                
                if has_staff_role and not user.is_staff:
                    user.is_staff = True
                    user.save(update_fields=['is_staff'])
                
                # Log the activity
                try:
                    from inventory.models import AuditLog
                    AuditLog.objects.create(
                        user=request.user,
                        action='UPDATE',
                        model_name='UserRoleAssignment',
                        object_id=user.id,
                        object_repr=f"Roles for {user.username}",
                        changes={'new_roles': new_roles},
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                except Exception:
                    pass
                
                messages.success(request, f'Roles updated successfully for {user.username}!')
                return redirect('authentication:user_detail', user_id=user.id)
                
        except Exception as e:
            logger.error(f"Error updating user roles: {str(e)}")
            messages.error(request, f'Error updating roles: {str(e)}')
    
    # Get current assignments and available options
    current_assignments = []
    departments = []
    roles = []
    
    try:
        from authentication.models import UserRoleAssignment, UserRole
        from inventory.models import Department
        
        current_assignments = UserRoleAssignment.objects.filter(
            user=user, 
            is_active=True
        ).select_related('role', 'department')
        
        departments = Department.objects.filter(is_active=True)
        roles = UserRole.objects.filter(is_active=True)
    except Exception:
        pass
    
    context = {
        'user_profile': user,
        'current_assignments': current_assignments,
        'departments': departments,
        'roles': roles,
        'title': f'Edit Roles: {user.get_full_name() or user.username}',
    }
    
    return render(request, 'authentication/edit_user_roles.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_status(request, user_id):
    """Toggle user active/inactive status (superuser only)"""
    if request.method == 'POST':
        try:
            user = get_object_or_404(User, id=user_id)
            
            # Don't allow deactivating superusers (except self)
            if user.is_superuser and user != request.user:
                messages.error(request, 'Cannot deactivate other superuser accounts.')
                return redirect('authentication:user_detail', user_id=user.id)
            
            # Toggle status
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            
            # Force logout if deactivating
            if not user.is_active:
                try:
                    from authentication.models import UserSession
                    UserSession.objects.filter(
                        user=user,
                        is_active=True
                    ).update(
                        is_active=False,
                        logout_time=timezone.now()
                    )
                except Exception:
                    pass
            
            # Log the activity
            try:
                from inventory.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='UPDATE',
                    model_name='User',
                    object_id=user.id,
                    object_repr=str(user),
                    changes={
                        'is_active': user.is_active,
                        'action': 'activated' if user.is_active else 'deactivated'
                    },
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            except Exception:
                pass
            
            status = 'activated' if user.is_active else 'deactivated'
            messages.success(request, f'User {user.username} has been {status}.')
            
        except Exception as e:
            logger.error(f"Error toggling user status: {str(e)}")
            messages.error(request, f'Error updating user status: {str(e)}')
    
    return redirect('authentication:user_detail', user_id=user_id)