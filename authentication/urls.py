
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Basic authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User profile management
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # Session management
    path('ajax/update-activity/', views.update_last_activity, name='update_last_activity'),
    path('ajax/check-session/', views.check_session_status, name='check_session_status'),
    
    # User management (admin only)
    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
]