from django.db import migrations
import re


def populate_department_codes(apps, schema_editor):
    """Generate codes for existing departments"""
    Department = apps.get_model('inventory', 'Department')
    
    for dept in Department.objects.all():
        if not dept.code or dept.code == 'TEMP':
            # Generate code from department name
            # Remove special characters and take first 6 chars of each word
            name_parts = re.sub(r'[^a-zA-Z\s]', '', dept.name).split()
            if len(name_parts) == 1:
                code = name_parts[0][:6].upper()
            else:
                code = ''.join([part[:2].upper() for part in name_parts[:3]])
            
            # Ensure uniqueness within the floor
            base_code = code
            counter = 1
            while Department.objects.filter(floor=dept.floor, code=code).exists():
                code = f"{base_code}{counter:02d}"
                counter += 1
            
            dept.code = code
            dept.save()


def reverse_populate_department_codes(apps, schema_editor):
    """Reverse the population - set codes back to TEMP"""
    Department = apps.get_model('inventory', 'Department')
    Department.objects.all().update(code='TEMP')


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_add_department_code_field'),
    ]

    operations = [
        migrations.RunPython(
            populate_department_codes,
            reverse_populate_department_codes,
        ),
    ]