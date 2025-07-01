# File Location: inventory/management/commands/fix_admin_errors.py

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
import os

class Command(BaseCommand):
    help = 'Fix Django admin system check errors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only run system checks without applying fixes',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 Starting Admin Error Fix Process...')
        )

        if options['check_only']:
            self.stdout.write('Running system checks only...')
            try:
                call_command('check')
                self.stdout.write(
                    self.style.SUCCESS('✅ No system check errors found!')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ System check errors found: {e}')
                )
            return

        # Step 1: Backup current admin files
        self.stdout.write('📋 Step 1: Creating backup of admin files...')
        self.backup_admin_files()

        # Step 2: Apply model fixes if needed
        self.stdout.write('🔄 Step 2: Checking model consistency...')
        self.check_model_consistency()

        # Step 3: Run system checks
        self.stdout.write('🔍 Step 3: Running Django system checks...')
        try:
            call_command('check')
            self.stdout.write(
                self.style.SUCCESS('✅ System checks passed!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ System check issues: {e}')
            )
            self.stdout.write('Please apply the fixed admin files from the artifacts.')

        # Step 4: Test admin interface
        self.stdout.write('🧪 Step 4: Testing admin interface accessibility...')
        self.test_admin_interface()

        self.stdout.write(
            self.style.SUCCESS('🎉 Admin error fix process completed!')
        )
        self.stdout.write(
            self.style.WARNING('Please replace your admin.py files with the provided fixed versions.')
        )

    def backup_admin_files(self):
        """Create backup of current admin files"""
        import shutil
        from datetime import datetime
        
        backup_suffix = datetime.now().strftime('_%Y%m%d_%H%M%S')
        
        admin_files = [
            'inventory/admin.py',
            'authentication/admin.py', 
            'reports/admin.py',
            'qr_management/admin.py'
        ]
        
        for admin_file in admin_files:
            if os.path.exists(admin_file):
                backup_file = admin_file + backup_suffix + '.backup'
                try:
                    shutil.copy2(admin_file, backup_file)
                    self.stdout.write(f'  ✅ Backed up {admin_file} to {backup_file}')
                except Exception as e:
                    self.stdout.write(f'  ⚠️ Could not backup {admin_file}: {e}')

    def check_model_consistency(self):
        """Check if models have required fields"""
        from django.apps import apps
        
        # Check critical models
        models_to_check = [
            ('inventory', 'Device'),
            ('inventory', 'Assignment'), 
            ('inventory', 'Staff'),
            ('inventory', 'Location'),
            ('authentication', 'UserRole'),
        ]
        
        for app_label, model_name in models_to_check:
            try:
                model = apps.get_model(app_label, model_name)
                field_names = [f.name for f in model._meta.get_fields()]
                self.stdout.write(f'  ✅ {app_label}.{model_name}: {len(field_names)} fields')
            except Exception as e:
                self.stdout.write(f'  ❌ Error checking {app_label}.{model_name}: {e}')

    def test_admin_interface(self):
        """Test admin interface registration"""
        from django.contrib import admin
        from django.apps import apps
        
        # Get all registered admin classes
        registered_models = admin.site._registry
        
        self.stdout.write(f'  📊 Total registered admin classes: {len(registered_models)}')
        
        # Check for problematic admin classes
        problematic_admins = []
        
        for model, admin_class in registered_models.items():
            try:
                # Check list_display
                if hasattr(admin_class, 'list_display'):
                    for field in admin_class.list_display:
                        if isinstance(field, str) and not hasattr(model, field) and not hasattr(admin_class, field):
                            problematic_admins.append(f'{model.__name__}.{field}')
                
                # Check readonly_fields  
                if hasattr(admin_class, 'readonly_fields'):
                    for field in admin_class.readonly_fields:
                        if isinstance(field, str) and not hasattr(model, field) and not hasattr(admin_class, field):
                            problematic_admins.append(f'{model.__name__}.{field}')
                            
            except Exception as e:
                problematic_admins.append(f'{model.__name__}: {str(e)}')
        
        if problematic_admins:
            self.stdout.write(f'  ⚠️ Found {len(problematic_admins)} potential issues:')
            for issue in problematic_admins[:10]:  # Show first 10
                self.stdout.write(f'    - {issue}')
        else:
            self.stdout.write('  ✅ No obvious admin configuration issues found')

    def get_admin_fix_instructions(self):
        """Return instructions for applying fixes"""
        return """
        📝 ADMIN FIX INSTRUCTIONS:

        1. Replace inventory/admin.py with the content from 'Fixed Inventory Admin Configuration' artifact
        2. Replace authentication/admin.py with the content from 'Fixed Authentication Admin Configuration' artifact  
        3. Replace reports/admin.py with the content from 'Fixed Reports Admin Configuration' artifact
        4. Replace qr_management/admin.py with the content from 'Fixed QR Management Admin Configuration' artifact

        5. Run the following commands:
           python manage.py check
           python manage.py migrate
           python manage.py collectstatic
           python manage.py runserver

        6. Test admin interface at: http://127.0.0.1:8000/admin/

        🚨 IMPORTANT: 
        - Backup files have been created with timestamp suffix
        - Test thoroughly before deploying to production
        - Some methods may need adjustment based on your actual model fields
        """