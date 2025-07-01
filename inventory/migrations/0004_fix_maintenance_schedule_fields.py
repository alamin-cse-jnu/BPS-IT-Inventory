from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_add_missing_models'),
    ]

    operations = [
        # Add all the missing fields to MaintenanceSchedule
        migrations.AddField(
            model_name='maintenanceschedule',
            name='title',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='scheduled_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='scheduled_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='status',
            field=models.CharField(
                choices=[
                    ('SCHEDULED', 'Scheduled'),
                    ('IN_PROGRESS', 'In Progress'),
                    ('COMPLETED', 'Completed'),
                    ('CANCELLED', 'Cancelled'),
                    ('POSTPONED', 'Postponed'),
                ],
                default='SCHEDULED',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='vendor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='maintenance_schedules',
                to='inventory.vendor'
            ),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='technician_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='technician_contact',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='estimated_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='actual_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='parts_used',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='work_performed',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='maintenanceschedule',
            name='completion_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]