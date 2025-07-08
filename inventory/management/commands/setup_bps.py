# inventory/management/commands/setup_bps.py
# Location: bps_inventory/apps/inventory/management/commands/setup_bps.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from inventory.models import (
    Building, Floor, Department, Room, Location,
    DeviceCategory, DeviceSubCategory, DeviceType, Vendor, Staff
)
from authentication.models import UserRole

class Command(BaseCommand):
    help = 'Initial setup for BPS IT Inventory System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Admin username (default: admin)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='123',
            help='Admin password (default: 123)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up BPS IT Inventory Management System...')
        )

        with transaction.atomic():
            # Create organization structure
            self.create_organization_structure()
            
            # Create device categories
            self.create_device_categories()
            
            # Create user roles
            self.create_user_roles()
            
            # Create sample vendor
            self.create_sample_vendor()
            
            # Create superuser if requested
            if options['create_superuser']:
                self.create_superuser(
                    options['admin_username'], 
                    options['admin_password']
                )

        self.stdout.write(
            self.style.SUCCESS('✅ BPS IT Inventory System setup completed!')
        )

    def create_organization_structure(self):
        self.stdout.write('Creating organization structure...')
        
        # Create main building (no organization model based on current structure)
        building, created = Building.objects.get_or_create(
            code='MAIN',
            defaults={
                'name': 'Main Building',
                'address': 'Sher-e-Bangla Nagar, Dhaka-1207, Bangladesh',
                'description': 'Bangladesh Parliament Secretariat Main Building',
                'is_active': True
            }
        )
        
        # Create floors
        floors_data = [
            (0, 'Ground Floor'),
            (1, 'First Floor'),
            (2, 'Second Floor'),
            (3, 'Third Floor'),
        ]
        
        floors = {}
        for floor_num, floor_name in floors_data:
            floor, created = Floor.objects.get_or_create(
                building=building,
                floor_number=floor_num,
                defaults={
                    'name': floor_name,
                    'description': f'{floor_name} of {building.name}',
                    'is_active': True
                }
            )
            floors[floor_num] = floor
        
        # Create departments
        departments_data = [
            ('IT', 'Information Technology Department', 2),
            ('ADMIN', 'Administration Department', 1),
            ('FINANCE', 'Finance Department', 1),
            ('HR', 'Human Resources Department', 2),
            ('SECURITY', 'Security Department', 0),
        ]
        
        departments = {}
        for dept_code, dept_name, floor_num in departments_data:
            dept, created = Department.objects.get_or_create(
                floor=floors[floor_num],
                code=dept_code,
                defaults={
                    'name': dept_name,
                    'head_of_department': f'{dept_name} Head',
                    'contact_email': f'{dept_code.lower()}@parliament.gov.bd',
                    'contact_phone': '+880-2-9123456',
                    'is_active': True
                }
            )
            departments[dept_code] = dept
        
        # Create sample rooms and locations
        for dept_code, dept in departments.items():
            # Create main office room
            room, created = Room.objects.get_or_create(
                department=dept,
                room_number='001',
                defaults={
                    'room_name': f'{dept.name} Main Office',
                    'capacity': 20,
                    'is_active': True
                }
            )
            
            # Create main location for each department (without specific desk assignments)
            location, created = Location.objects.get_or_create(
                building=building,
                floor=dept.floor,
                department=dept,
                room=room,
                defaults={
                    'description': f'Main office location for {dept.name}',
                    'is_active': True
                }
            )

    def create_device_categories(self):
        self.stdout.write('Creating device categories...')
        
        categories_data = [
            ('Data Centre Equipment', [
                ('Servers', ['Physical Server', 'Virtual Server', 'Blade Server']),
                ('Storage Systems', ['NAS', 'SAN', 'Backup System']),
                ('Network Infrastructure', ['Core Switch', 'Router', 'Firewall']),
            ]),
            ('Network Equipment', [
                ('Access Points', ['Indoor AP', 'Outdoor AP', 'Mesh Node']),
                ('Switches', ['Access Switch', 'PoE Switch', 'Managed Switch']),
                ('Routers', ['Edge Router', 'Branch Router', 'Core Router']),
            ]),
            ('End-User Computing Devices', [
                ('Computers', ['Desktop', 'Laptop', 'Tablet']),
                ('Peripherals', ['Monitor', 'Keyboard', 'Mouse', 'Webcam']),
                ('Printing Equipment', ['Laser Printer', 'Inkjet Printer', 'Scanner']),
            ]),
            ('Projectors and Displays', [
                ('Projectors', ['LCD Projector', 'LED Projector']),
                ('Digital Displays', ['LED Display', 'LCD Display', 'Smart TV']),
            ]),
        ]
        
        for cat_name, subcategories in categories_data:
            category, created = DeviceCategory.objects.get_or_create(
                name=cat_name,
                defaults={
                    'description': f'{cat_name} for BPS IT Infrastructure',
                    'is_active': True
                }
            )
            
            for subcat_name, device_types in subcategories:
                subcategory, created = DeviceSubCategory.objects.get_or_create(
                    category=category,
                    name=subcat_name,
                    defaults={
                        'description': f'{subcat_name} subcategory',
                        'is_active': True
                    }
                )
                
                for dtype_name in device_types:
                    DeviceType.objects.get_or_create(
                        subcategory=subcategory,
                        name=dtype_name,
                        defaults={
                            'description': f'{dtype_name} device type',
                            'specifications_template': {},
                            'is_active': True
                        }
                    )

    def create_user_roles(self):
        self.stdout.write('Creating user roles...')
        
        roles_data = [
            ('IT_ADMINISTRATOR', 'IT Administrator', 'Full system access and administration', {
                'can_view_all_devices': True,
                'can_manage_assignments': True,
                'can_approve_requests': True,
                'can_generate_reports': True,
                'can_manage_users': True,
                'can_system_admin': True,
                'can_manage_maintenance': True,
                'can_manage_vendors': True,
                'can_bulk_operations': True,
                'can_export_data': True,
                'restricted_to_own_department': False,
                'can_view_financial_data': True,
                'can_scan_qr_codes': True,
                'can_generate_qr_codes': True
            }),
            ('IT_OFFICER', 'IT Officer', 'Device and assignment management', {
                'can_view_all_devices': True,
                'can_manage_assignments': True,
                'can_approve_requests': False,
                'can_generate_reports': True,
                'can_manage_users': False,
                'can_system_admin': False,
                'can_manage_maintenance': True,
                'can_manage_vendors': False,
                'can_bulk_operations': True,
                'can_export_data': True,
                'restricted_to_own_department': False,
                'can_view_financial_data': False,
                'can_scan_qr_codes': True,
                'can_generate_qr_codes': True
            }),
            ('DEPARTMENT_HEAD', 'Department Head', 'Department-level oversight', {
                'can_view_all_devices': False,
                'can_manage_assignments': True,
                'can_approve_requests': True,
                'can_generate_reports': True,
                'can_manage_users': False,
                'can_system_admin': False,
                'can_manage_maintenance': False,
                'can_manage_vendors': False,
                'can_bulk_operations': False,
                'can_export_data': True,
                'restricted_to_own_department': True,
                'can_view_financial_data': False,
                'can_scan_qr_codes': True,
                'can_generate_qr_codes': False
            }),
            ('GENERAL_STAFF', 'General Staff', 'View personal assignments only', {
                'can_view_all_devices': False,
                'can_manage_assignments': False,
                'can_approve_requests': False,
                'can_generate_reports': False,
                'can_manage_users': False,
                'can_system_admin': False,
                'can_manage_maintenance': False,
                'can_manage_vendors': False,
                'can_bulk_operations': False,
                'can_export_data': False,
                'restricted_to_own_department': True,
                'can_view_financial_data': False,
                'can_scan_qr_codes': True,
                'can_generate_qr_codes': False
            }),
        ]
        
        for role_name, display_name, description, permissions in roles_data:
            UserRole.objects.get_or_create(
                name=role_name,
                defaults={
                    'display_name': display_name,
                    'description': description,
                    'permissions': {},  # Using the JSONField for additional permissions
                    'is_active': True,
                    **permissions
                }
            )

    def create_sample_vendor(self):
        self.stdout.write('Creating sample vendor...')
        
        Vendor.objects.get_or_create(
            name='Dell Technologies Bangladesh',
            defaults={
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Sales Manager',
                'phone': '+880-2-9876543',
                'email': 'sales@dell.com.bd',
                'address': 'Gulshan, Dhaka, Bangladesh',
                'website': 'https://www.dell.com',
                'tax_id': 'BIN-123456789',
                'is_active': True
            }
        )

    def create_superuser(self, username, password):
        self.stdout.write(f'Creating superuser: {username}')
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User {username} already exists, skipping...')
            )
            return
        
        user = User.objects.create_superuser(
            username=username,
            email='admin@parliament.gov.bd',
            password=password,
            first_name='Al-Amin',
            last_name='Hossain'
        )
        
        # Create staff profile using correct field names
        it_dept = Department.objects.filter(code='IT').first()
        if it_dept:
            Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': '110100091',
                    'department': it_dept,
                    'designation': 'Computer Programmer',
                    'employment_type': 'PERMANENT',
                    'phone_number': '+880-1712345678',
                    'is_active': True,
                    'joining_date': '2025-01-01'
                }
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Superuser created: {username} / {password}')
        )