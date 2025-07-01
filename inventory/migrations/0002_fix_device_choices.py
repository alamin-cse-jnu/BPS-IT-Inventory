from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        # Fix Device model choice field names
        migrations.AlterField(
            model_name='device',
            name='status',
            field=models.CharField(
                choices=[
                    ('AVAILABLE', 'Available'),
                    ('ASSIGNED', 'Assigned'),
                    ('IN_USE', 'In Use'),
                    ('MAINTENANCE', 'Under Maintenance'),
                    ('REPAIR', 'Under Repair'),
                    ('RETIRED', 'Retired'),
                    ('DISPOSED', 'Disposed'),
                    ('LOST', 'Lost/Missing'),
                    ('DAMAGED', 'Damaged'),
                ],
                default='AVAILABLE',
                max_length=20
            ),
        ),
        migrations.AlterField(
            model_name='device',
            name='condition',
            field=models.CharField(
                choices=[
                    ('NEW', 'New'),
                    ('EXCELLENT', 'Excellent'),
                    ('GOOD', 'Good'),
                    ('FAIR', 'Fair'),
                    ('POOR', 'Poor'),
                    ('DAMAGED', 'Damaged'),
                    ('NOT_WORKING', 'Not Working'),
                ],
                default='NEW',
                max_length=20
            ),
        ),
    ]