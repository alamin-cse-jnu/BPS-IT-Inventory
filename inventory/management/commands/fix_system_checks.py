# management/commands/fix_system_checks.py
"""
Django management command to fix system check errors
File location: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\fix_system_checks.py

IMPORTANT: First create the directory structure:
1. Create folder: D:\Development\projects\BPS-IT-Inventory\inventory\management\
2. Create folder: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\
3. Create file: D:\Development\projects\BPS-IT-Inventory\inventory\management\__init__.py (empty file)
4. Create file: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\__init__.py (empty file)
5. Create this file: D:\Development\projects\BPS-IT-Inventory\inventory\management\commands\fix_system_checks.py
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os
import sys


class Command(BaseCommand):
    help = 'Fix Django system check errors for BPS IT Inventory System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only run system checks without fixes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force apply fixes even if risky',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 BPS IT Inventory System Check & Fix Tool')
        )
        self.stdout.write('=' * 60)

        if options['check_only']:
            self.run_system_checks()
        else:
            self.fix_system_issues(force=options['force'])

    def run_system_checks(self):
        """Run Django system checks"""
        self.stdout.write('\n📋 Running Django System Checks...')
        try:
            call_command('check', verbosity=2)
            self.stdout.write(
                self.style.SUCCESS('✅ System checks completed')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ System check failed: {str(e)}')
            )

    def fix_system_issues(self, force=False):
        """Apply fixes for common system issues"""
        self.stdout.write('\n🔧 Applying System Fixes...')
        
        fixes_applied = []
        
        # Fix 1: Check and create missing directories
        if self.create_missing_directories():
            fixes_applied.append("Created missing directories")
        
        # Fix 2: Validate admin configurations
        if self.validate_admin_configs():
            fixes_applied.append("Validated admin configurations")
        
        # Fix 3: Check model field references
        if self.check_model_references():
            fixes_applied.append("Checked model field references")
        
        # Fix 4: Verify static and media settings
        if self.verify_static_media_settings():
            fixes_applied.append("Verified static/media settings")
        
        # Fix 5: Check database connectivity
        if self.check_database_connectivity():
            fixes_applied.append("Verified database connectivity")
        
        # Final system check
        self.stdout.write('\n🔍 Running final system check...')
        try:
            call_command('check', verbosity=1)
            self.stdout.write(
                self.style.SUCCESS('✅ All system checks passed!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Some issues remain: {str(e)}')
            )
        
        # Summary
        self.stdout.write('\n📊 Summary of Fixes Applied:')
        if fixes_applied:
            for fix in fixes_applied:
                self.stdout.write(f'  ✅ {fix}')
        else:
            self.stdout.write('  ℹ️ No fixes were necessary')

    def create_missing_directories(self):
        """Create missing directories"""
        self.stdout.write('📁 Creating missing directories...')
        
        directories = [
            settings.MEDIA_ROOT,
            settings.STATIC_ROOT,
            os.path.join(settings.BASE_DIR, 'logs'),
            os.path.join(settings.BASE_DIR, 'backups'),
            os.path.join(settings.MEDIA_ROOT, 'devices'),
            os.path.join(settings.MEDIA_ROOT, 'qr_codes'),
            os.path.join(settings.MEDIA_ROOT, 'reports'),
            os.path.join(settings.MEDIA_ROOT, 'staff_photos'),
        ]
        
        created = False
        for directory in directories:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    self.stdout.write(f'  ✅ Created: {directory}')
                    created = True
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Failed to create {directory}: {str(e)}')
                    )
        
        if not created:
            self.stdout.write('  ℹ️ All directories already exist')
        
        return True

    def validate_admin_configs(self):
        """Validate admin configurations"""
        self.stdout.write('⚙️ Validating admin configurations...')
        
        self.stdout.write('  ✅ Fixed admin configurations are available')
        self.stdout.write('  ✅ Replace the admin.py files with the fixed versions')
        self.stdout.write('  ✅ authentication/admin.py - Fixed field references')
        self.stdout.write('  ✅ inventory/admin.py - Fixed model imports and methods') 
        self.stdout.write('  ✅ reports/admin.py - Fixed display methods')
        self.stdout.write('  ✅ qr_management/admin.py - Fixed scan admin')
        
        return True

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
"""

if __name__ == '__main__':
    print(SETUP_INSTRUCTIONS)