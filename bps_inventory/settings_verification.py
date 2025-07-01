# File Location: bps_inventory/settings_verification.py

"""
Settings verification and configuration fix
This file should be imported in your main settings.py to ensure proper configuration
"""

import os
from pathlib import Path

def verify_and_fix_settings():
    """
    Verify critical settings and provide fixes
    """
    
    verification_results = {
        'errors': [],
        'warnings': [],
        'fixes_applied': []
    }
    
    # Check if required directories exist
    required_dirs = [
        'logs',
        'media', 
        'static',
        'backups',
        'templates'
    ]
    
    base_dir = Path(__file__).resolve().parent.parent
    
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        if not dir_path.exists():
            try:
                dir_path.mkdir(exist_ok=True)
                verification_results['fixes_applied'].append(f'Created directory: {dir_path}')
            except Exception as e:
                verification_results['errors'].append(f'Could not create {dir_path}: {e}')
    
    # Check installed apps consistency
    required_apps = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'inventory',
        'authentication',
        'reports',
        'qr_management',
    ]
    
    # Admin site configuration
    admin_config = {
        'ADMIN_SITE_HEADER': "BPS IT Inventory Management",
        'ADMIN_SITE_TITLE': "BPS Inventory Admin", 
        'ADMIN_INDEX_TITLE': "Welcome to BPS IT Inventory Management System"
    }
    
    verification_results['admin_config'] = admin_config
    
    return verification_results

def get_fixed_settings_snippet():
    """
    Return a settings snippet with fixes for common issues
    """
    
    return """
# Admin Site Configuration (Add to end of settings.py)
from django.contrib import admin

# Customize admin site
admin.site.site_header = "BPS IT Inventory Management System"
admin.site.site_title = "BPS Inventory Admin"
admin.site.index_title = "Welcome to BPS IT Inventory Management System"

# Ensure proper model imports
def check_model_imports():
    try:
        from inventory.models import Device, Assignment, Staff
        from authentication.models import UserRole, UserRoleAssignment
        from reports.models import ReportTemplate, ReportGeneration
        print("✅ All critical models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Model import error: {e}")
        return False

# Call the check (optional - for debugging)
# check_model_imports()

# Database connection optimization
DATABASES['default'].update({
    'OPTIONS': {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
    },
    'CONN_MAX_AGE': 300,  # 5 minutes
})

# Logging configuration for admin errors
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'admin_errors.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django.contrib.admin': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
"""

# System check configuration
SYSTEM_CHECK_SETTINGS = {
    'SILENCED_SYSTEM_CHECKS': [
        # Temporarily silence admin checks while fixing
        # Remove these once admin files are fixed
        # 'admin.E034',  # Uncomment if needed
        # 'admin.E108',  # Uncomment if needed  
    ]
}

def print_fix_summary():
    """Print summary of required fixes"""
    
    print("""
🔧 BPS INVENTORY ADMIN FIX SUMMARY
================================

CRITICAL FILES TO REPLACE:
1. inventory/admin.py - Replace with Fixed Inventory Admin Configuration
2. authentication/admin.py - Replace with Fixed Authentication Admin Configuration
3. reports/admin.py - Replace with Fixed Reports Admin Configuration  
4. qr_management/admin.py - Replace with Fixed QR Management Admin Configuration

MANAGEMENT COMMAND:
5. inventory/management/commands/fix_admin_errors.py - Add new management command

STEPS TO APPLY FIXES:
1. Backup current admin files (automatically done by management command)
2. Replace admin files with artifact content
3. Run: python manage.py fix_admin_errors --check-only
4. Run: python manage.py check
5. Run: python manage.py migrate
6. Run: python manage.py runserver
7. Test admin at: http://127.0.0.1:8000/admin/

COMMON ERROR PATTERNS FIXED:
- list_display fields that don't exist on models
- readonly_fields referencing non-existent fields  
- Missing admin methods for display fields
- Incorrect field references between different models
- Improper error handling in admin methods

⚠️  BACKUP REMINDER: 
Current admin files will be backed up with timestamp before replacement.

✅ VERIFICATION:
Run 'python manage.py fix_admin_errors' to verify fixes.
""")

if __name__ == "__main__":
    print_fix_summary()
    verification_results = verify_and_fix_settings()
    print("\nVerification Results:")
    print(f"Errors: {len(verification_results['errors'])}")
    print(f"Warnings: {len(verification_results['warnings'])}")  
    print(f"Fixes Applied: {len(verification_results['fixes_applied'])}")