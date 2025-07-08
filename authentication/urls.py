# authentication/urls.py
# Location: bps_inventory/apps/authentication/urls.py

from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # ================================
    # BASIC AUTHENTICATION - Enhanced
    # ================================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ================================
    # USER PROFILE MANAGEMENT - Enhanced
    # ================================
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # ================================
    # SESSION MANAGEMENT - Enhanced
    # ================================
    path('ajax/update-activity/', views.update_last_activity, name='update_last_activity'),
    path('ajax/check-session/', views.check_session_status, name='check_session_status'),
    
    # ================================
    # USER MANAGEMENT - ADMIN ONLY - Enhanced
    # ================================
    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/create/', views.create_staff_user, name='create_staff_user'),
    path('users/<int:user_id>/edit-roles/', views.edit_user_roles, name='edit_user_roles'),
    path('users/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
]