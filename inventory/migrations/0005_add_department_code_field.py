from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_add_missing_maintenance_fields'),  # Adjust this to your latest migration
    ]

    operations = [
        # Add the missing code field to Department
        migrations.AddField(
            model_name='department',
            name='code',
            field=models.CharField(default='TEMP', max_length=20),
            preserve_default=False,
        ),
        
        # Add the unique constraint
        migrations.AlterUniqueTogether(
            name='department',
            unique_together={('floor', 'code')},
        ),
    ]