from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.management import call_command
import os


class Command(BaseCommand):
    help = 'Clean up maintenance schedule migration conflicts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-migrations',
            action='store_true',
            help='Reset migrations and recreate them (WARNING: Data loss possible)',
        )
        parser.add_argument(
            '--backup-data',
            action='store_true',
            help='Create data backup before cleanup',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING('Starting maintenance schedule migration cleanup...')
        )

        if options['backup_data']:
            self.backup_maintenance_data()

        if options['reset_migrations']:
            self.reset_migrations()
        else:
            self.fix_migration_conflicts()

        self.stdout.write(
            self.style.SUCCESS('Migration cleanup completed successfully!')
        )

    def backup_maintenance_data(self):
        """Backup maintenance data to JSON"""
        self.stdout.write('Creating data backup...')
        call_command('dumpdata', 'inventory.MaintenanceSchedule', 
                    output='maintenance_backup.json')
        self.stdout.write(
            self.style.SUCCESS('Backup created: maintenance_backup.json')
        )

    def fix_migration_conflicts(self):
        """Try to fix migration conflicts without data loss"""
        try:
            # First, try to fake apply conflicting migrations
            self.stdout.write('Attempting to resolve migration conflicts...')
            
            # Create the new migration
            call_command('makemigrations', 'inventory', 
                        name='fix_maintenance_schedule_fields')
            
            # Apply the migration
            call_command('migrate', 'inventory')
            
            self.stdout.write(
                self.style.SUCCESS('Migration conflicts resolved!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to fix migrations: {e}')
            )
            self.stdout.write(
                'Consider using --reset-migrations option (WARNING: Data loss)'
            )

    def reset_migrations(self):
        """Reset migrations (WARNING: Data loss)"""
        self.stdout.write(
            self.style.WARNING('WARNING: This will reset migrations and may cause data loss!')
        )
        
        response = input('Are you sure you want to continue? (yes/no): ')
        if response.lower() != 'yes':
            self.stdout.write('Operation cancelled.')
            return

        try:
            # Reset migrations
            call_command('migrate', 'inventory', 'zero')
            
            # Remove migration files (keep __init__.py)
            migrations_dir = 'inventory/migrations'
            for filename in os.listdir(migrations_dir):
                if filename.endswith('.py') and filename != '__init__.py':
                    os.remove(os.path.join(migrations_dir, filename))
            
            # Create fresh migrations
            call_command('makemigrations', 'inventory')
            call_command('migrate', 'inventory')
            
            self.stdout.write(
                self.style.SUCCESS('Migrations reset successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to reset migrations: {e}')
            )