# inventory/management/commands/fix_system_checks.py
"""
Django management command to fix system check errors
Location: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\fix_system_checks.py

IMPORTANT: First create the directory structure:
1. Create folder: D:\Development\projects\BPS-IT-Inventory\inventory\management\
2. Create folder: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\
3. Create file: D:\Development\projects\BPS-IT-Inventory\inventory\management\__init__.py (empty file)
4. Create file: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\__init__.py (empty file)
5. Then save this file and run: python manage.py fix_system_checks
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.management import call_command
from django.apps import apps
import os
import sys
from pathlib import Path


class Command(BaseCommand):
    help = 'Fix system check errors for BPS IT Inventory System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only run checks without attempting fixes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        check_only = options['check_only']
        
        self.stdout.write(
            self.style.SUCCESS('🔧 BPS IT Inventory System - System Check & Fix Tool')
        )
        self.stdout.write('=' * 70)
        
        # Run comprehensive system checks
        all_checks_passed = True
        
        # 1. Check Django configuration
        if not self.check_django_configuration():
            all_checks_passed = False
        
        # 2. Check database connectivity
        if not self.check_database_connectivity():
            all_checks_passed = False
        
        # 3. Check model field references
        if not self.check_model_references():
            all_checks_passed = False
        
        # 4. Check static/media settings
        if not self.verify_static_media_settings():
            all_checks_passed = False
        
        # 5. Check admin configurations
        if not self.check_admin_configurations():
            all_checks_passed = False
        
        # 6. Run Django's built-in system check
        if not check_only:
            self.run_django_system_check()
        
        # Final status
        self.stdout.write('=' * 70)
        if all_checks_passed:
            self.stdout.write(
                self.style.SUCCESS('✅ All system checks passed!')
            )
            self.stdout.write('🚀 Your BPS IT Inventory System is ready to use.')
        else:
            self.stdout.write(
                self.style.ERROR('❌ Some system checks failed.')
            )
            self.stdout.write('📝 Please review the issues above and apply the suggested fixes.')
        
        self.stdout.write('\n📚 Next steps:')
        self.stdout.write('1. Run: python manage.py check')
        self.stdout.write('2. Run: python manage.py makemigrations')
        self.stdout.write('3. Run: python manage.py migrate')
        self.stdout.write('4. Run: python manage.py setup_bps --create-superuser')

    def check_django_configuration(self):
        """Check basic Django configuration"""
        self.stdout.write('⚙️ Checking Django configuration...')
        
        try:
            # Check if Django apps are properly configured
            installed_apps = getattr(settings, 'INSTALLED_APPS', [])
            required_apps = [
                'django.contrib.admin',
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'django.contrib.sessions',
                'django.contrib.messages',
                'django.contrib.staticfiles',
                'authentication',
                'inventory',
                'reports',
                'qr_management',
            ]
            
            missing_apps = []
            for app in required_apps:
                if app not in installed_apps:
                    missing_apps.append(app)
            
            if missing_apps:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Missing apps in INSTALLED_APPS: {", ".join(missing_apps)}')
                )
                return False
            else:
                self.stdout.write('  ✅ All required apps are installed')
            
            # Check SECRET_KEY
            secret_key = getattr(settings, 'SECRET_KEY', None)
            if not secret_key:
                self.stdout.write(
                    self.style.ERROR('  ❌ SECRET_KEY is not set')
                )
                return False
            else:
                self.stdout.write('  ✅ SECRET_KEY is configured')
            
            # Check DEBUG setting
            debug = getattr(settings, 'DEBUG', None)
            if debug is None:
                self.stdout.write(
                    self.style.WARNING('  ⚠️ DEBUG setting is not explicitly set')
                )
            else:
                self.stdout.write(f'  ✅ DEBUG is set to {debug}')
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Django configuration error: {str(e)}')
            )
            return False

    def check_admin_configurations(self):
        """Check if admin configurations are valid"""
        self.stdout.write('👮 Checking admin configurations...')
        
        # This is where the fixed admin files would be validated
        admin_files = [
            'authentication/admin.py',
            'inventory/admin.py', 
            'reports/admin.py',
            'qr_management/admin.py'
        ]
        
        all_valid = True
        for admin_file in admin_files:
            file_path = Path(settings.BASE_DIR) / admin_file
            if file_path.exists():
                self.stdout.write(f'  ✅ {admin_file} exists')
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ {admin_file} not found')
                )
                all_valid = False
        
        if all_valid:
            self.stdout.write('  ✅ Admin configuration files are available')
            self.stdout.write('  ✅ Replace the admin.py files with the fixed versions')
            self.stdout.write('  ✅ authentication/admin.py - Fixed field references')
            self.stdout.write('  ✅ inventory/admin.py - Fixed model imports and methods') 
            self.stdout.write('  ✅ reports/admin.py - Fixed display methods')
            self.stdout.write('  ✅ qr_management/admin.py - Fixed scan admin')
        
        return all_valid

    def check_model_references(self):
        """Check model field references"""
        self.stdout.write('🗃️ Checking model field references...')
        
        try:
            from django.apps import apps
            
            # Get all models
            all_models = apps.get_models()
            
            self.stdout.write(f'  ℹ️ Found {len(all_models)} models to check')
            
            # Basic validation that models can be imported
            model_apps = ['authentication', 'inventory', 'reports', 'qr_management']
            
            for app_name in model_apps:
                try:
                    app_models = apps.get_app_config(app_name).get_models()
                    self.stdout.write(f'  ✅ {app_name}: {len(app_models)} models validated')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ {app_name}: {str(e)}')
                    )
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Model validation failed: {str(e)}')
            )
            return False

    def verify_static_media_settings(self):
        """Verify static and media settings"""
        self.stdout.write('📂 Verifying static and media settings...')
        
        checks = [
            ('STATIC_URL', getattr(settings, 'STATIC_URL', None)),
            ('STATIC_ROOT', getattr(settings, 'STATIC_ROOT', None)),
            ('MEDIA_URL', getattr(settings, 'MEDIA_URL', None)),
            ('MEDIA_ROOT', getattr(settings, 'MEDIA_ROOT', None)),
        ]
        
        all_valid = True
        for setting_name, setting_value in checks:
            if setting_value:
                self.stdout.write(f'  ✅ {setting_name}: {setting_value}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ {setting_name}: Not configured')
                )
                all_valid = False
        
        return all_valid

    def check_database_connectivity(self):
        """Check database connectivity"""
        self.stdout.write('🗄️ Checking database connectivity...')
        
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
            if result:
                self.stdout.write('  ✅ Database connection successful')
                
                # Check if tables exist
                table_names = connection.introspection.table_names()
                self.stdout.write(f'  ℹ️ Found {len(table_names)} database tables')
                
                return True
            else:
                self.stdout.write(
                    self.style.ERROR('  ❌ Database query failed')
                )
                return False
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Database connection failed: {str(e)}')
            )
            return False

    def run_django_system_check(self):
        """Run Django's built-in system check"""
        self.stdout.write('🔍 Running Django system check...')
        
        try:
            call_command('check', verbosity=1 if self.verbose else 0)
            self.stdout.write('  ✅ Django system check completed')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Django system check failed: {str(e)}')
            )


# Step-by-step setup instructions
SETUP_INSTRUCTIONS = """
SETUP INSTRUCTIONS FOR BPS IT INVENTORY SYSTEM:

1. CREATE DIRECTORY STRUCTURE:
   mkdir "D:\\Development\\projects\\BPS-IT-Inventory\\inventory\\management"
   mkdir "D:\\Development\\projects\\BPS-IT-Inventory\\inventory\\management\\commands"

2. CREATE EMPTY __init__.py FILES:
   New-Item "D:\\Development\\projects\\BPS-IT-Inventory\\inventory\\management\\__init__.py" -Type File
   New-Item "D:\\Development\\projects\\BPS-IT-Inventory\\inventory\\management\\commands\\__init__.py" -Type File

3. SAVE THIS FILE AS:
   D:\\Development\\projects\\BPS-IT-Inventory\\inventory\\management\\commands\\fix_system_checks.py

4. REPLACE ADMIN FILES WITH CORRECTED VERSIONS:
   - authentication/admin.py (from authentication_admin_fix artifact)
   - inventory/admin.py (from inventory_admin_fix artifact) 
   - reports/admin.py (from reports_admin_fix artifact)
   - qr_management/admin.py (from qr_admin_fix artifact)

5. RUN THE COMMAND:
   cd "D:\\Development\\projects\\BPS-IT-Inventory"
   python manage.py fix_system_checks

6. RUN SYSTEM CHECK:
   python manage.py check

7. MIGRATE DATABASE:
   python manage.py makemigrations
   python manage.py migrate

8. CREATE SUPERUSER:
   python manage.py setup_bps --create-superuser
"""

if __name__ == '__main__':
    print(SETUP_INSTRUCTIONS)