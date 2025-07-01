from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from datetime import date

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_fix_device_choices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create Assignment model
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assignment_id', models.CharField(editable=False, max_length=20, unique=True)),
                ('is_temporary', models.BooleanField(default=False, help_text='Is this a temporary assignment?')),
                ('expected_return_date', models.DateField(blank=True, help_text='Required for temporary assignments', null=True)),
                ('actual_return_date', models.DateField(blank=True, null=True)),
                ('start_date', models.DateField(default=date.today)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('purpose', models.CharField(help_text='Purpose of assignment', max_length=200)),
                ('conditions', models.TextField(blank=True, help_text='Special conditions or requirements')),
                ('notes', models.TextField(blank=True)),
                ('return_notes', models.TextField(blank=True, help_text='Notes when device is returned')),
                ('return_condition', models.CharField(blank=True, help_text='Device condition when returned', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_made', to=settings.AUTH_USER_MODEL)),
                ('assigned_to_department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='inventory.department')),
                ('assigned_to_location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='inventory.location')),
                ('assigned_to_staff', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='inventory.staff')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_created', to=settings.AUTH_USER_MODEL)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='inventory.device')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_requested', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-assigned_at'],
            },
        ),
        
        # Create AssignmentHistory model
        migrations.CreateModel(
            name='AssignmentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=50)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('reason', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history_records', to='inventory.assignment')),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_history', to='inventory.device')),
            ],
            options={
                'ordering': ['-changed_at'],
            },
        ),
        
        # Create MaintenanceSchedule model
        migrations.CreateModel(
            name='MaintenanceSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maintenance_type', models.CharField(choices=[('PREVENTIVE', 'Preventive Maintenance'), ('CORRECTIVE', 'Corrective Maintenance'), ('EMERGENCY', 'Emergency Repair'), ('UPGRADE', 'Hardware/Software Upgrade'), ('INSPECTION', 'Routine Inspection')], max_length=20)),
                ('frequency', models.CharField(choices=[('WEEKLY', 'Weekly'), ('MONTHLY', 'Monthly'), ('QUARTERLY', 'Quarterly'), ('SEMI_ANNUAL', 'Semi-Annual'), ('ANNUAL', 'Annual'), ('AS_NEEDED', 'As Needed')], max_length=20)),
                ('description', models.TextField()),
                ('next_due_date', models.DateField()),
                ('last_completed_date', models.DateField(blank=True, null=True)),
                ('estimated_duration', models.DurationField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_technician', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maintenance_assignments', to='inventory.staff')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_schedules', to='inventory.device')),
            ],
            options={
                'ordering': ['next_due_date'],
            },
        ),
        
        # Create MaintenanceRecord model
        migrations.CreateModel(
            name='MaintenanceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maintenance_type', models.CharField(choices=[('PREVENTIVE', 'Preventive Maintenance'), ('CORRECTIVE', 'Corrective Maintenance'), ('EMERGENCY', 'Emergency Repair'), ('UPGRADE', 'Hardware/Software Upgrade'), ('INSPECTION', 'Routine Inspection')], max_length=20)),
                ('description', models.TextField()),
                ('scheduled_date', models.DateField()),
                ('completed_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('SCHEDULED', 'Scheduled'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled'), ('POSTPONED', 'Postponed')], default='SCHEDULED', max_length=20)),
                ('work_performed', models.TextField(blank=True)),
                ('parts_used', models.TextField(blank=True)),
                ('cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='maintenance_records_created', to=settings.AUTH_USER_MODEL)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_records', to='inventory.device')),
                ('maintenance_schedule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='records', to='inventory.maintenanceschedule')),
                ('technician', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maintenance_records', to='inventory.staff')),
            ],
            options={
                'ordering': ['-scheduled_date'],
            },
        ),
    ]