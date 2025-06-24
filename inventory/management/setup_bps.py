# inventory/management/commands/setup_bps.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from inventory.models import (
    Organization, Building, Floor, Department, Room, Location,
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
            default='admin123',
            help='Admin password (default: admin123)',
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
        
        # Create organization
        org, created = Organization.objects.get_or_create(
            code='BPS',
            defaults={
                'name': 'Bangladesh Parliament Secretariat',
                'address': 'Sher-e-Bangla Nagar, Dhaka-1207, Bangladesh',
                'contact_phone': '+880-2-9123456',
                'contact_email': 'info@parliament.gov.bd'
            }
        )
        
        # Create main building
        building, created = Building.objects.get_or_create(
            organization=org,
            code='MAIN',
            defaults={
                'name': 'Main Building',
                'address': 'Sher-e-Bangla Nagar, Dhaka-1207, Bangladesh',
                'contact_person': 'IT Administrator'
            }
        )
        
        # Create floors
        floors_data = [
            ('G', 'Ground Floor'),
            ('1', 'First Floor'),
            ('2', 'Second Floor'),
            ('3', 'Third Floor'),
        ]
        
        floors = {}
        for floor_num, floor_name in floors_data:
            floor, created = Floor.objects.get_or_create(
                building=building,
                floor_number=floor_num,
                defaults={'name': floor_name}
            )
            floors[floor_num] = floor
        
        # Create departments
        departments_data = [
            ('IT', 'Information Technology Department', '2'),
            ('ADMIN', 'Administration Department', '1'),
            ('FINANCE', 'Finance Department', '1'),
            ('HR', 'Human Resources Department', '2'),
            ('SECURITY', 'Security Department', 'G'),
        ]
        
        departments = {}
        for dept_code, dept_name, floor_num in departments_data:
            dept, created = Department.objects.get_or_create(
                floor=floors[floor_num],
                code=dept_code,
                defaults={
                    'name': dept_name,
                    'contact_email': f'{dept_code.lower()}@parliament.gov.bd'
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
                    'name': f'{dept.name} Main Office',
                    'room_type': 'OFFICE',
                    'capacity': 20
                }
            )
            
            # Create sample locations in the room
            for i in range(1, 6):
                Location.objects.get_or_create(
                    room=room,
                    location_code=f'DESK-{i:02d}',
                    defaults={
                        'name': f'Desk {i}',
                        'location_type': 'DESK',
                        'capacity': 1
                    }
                )

    def create_device_categories(self):
        self.stdout.write('Creating device categories...')
        
        categories_data = [
            ('DATA_CENTER', 'Data Centre Equipment', [
                ('SERVERS', 'Servers', ['PHYSICAL_SERVER', 'VIRTUAL_SERVER', 'BLADE_SERVER']),
                ('STORAGE', 'Storage Systems', ['NAS', 'SAN', 'BACKUP_SYSTEM']),
                ('NETWORK_INFRA', 'Network Infrastructure', ['CORE_SWITCH', 'ROUTER', 'FIREWALL']),
            ]),
            ('NETWORK', 'Network Equipment', [
                ('ACCESS_POINTS', 'Access Points', ['INDOOR_AP', 'OUTDOOR_AP', 'MESH_NODE']),
                ('SWITCHES', 'Switches', ['ACCESS_SWITCH', 'POE_SWITCH', 'MANAGED_SWITCH']),
                ('ROUTERS', 'Routers', ['EDGE_ROUTER', 'BRANCH_ROUTER', 'CORE_ROUTER']),
            ]),
            ('COMPUTING', 'End-User Computing Devices', [
                ('COMPUTERS', 'Computers', ['DESKTOP', 'LAPTOP', 'WORKSTATION', 'TABLET']),
                ('PERIPHERALS', 'Peripherals', ['MONITOR', 'KEYBOARD', 'MOUSE', 'WEBCAM']),
                ('PRINTERS', 'Printing Equipment', ['LASER_PRINTER', 'INKJET_PRINTER', 'SCANNER']),
            ]),
            ('DISPLAY', 'Projectors and Displays', [
                ('PROJECTORS', 'Projectors', ['DLP_PROJECTOR', 'LCD_PROJECTOR', 'LED_PROJECTOR']),
                ('DISPLAYS', 'Digital Displays', ['LED_DISPLAY', 'LCD_DISPLAY', 'SMART_TV']),
            ]),
        ]
        
        for cat_type, cat_name, subcategories in categories_data:
            category, created = DeviceCategory.objects.get_or_create(
                category_type=cat_type,
                defaults={
                    'name': cat_name,
                    'description': f'{cat_name} for BPS IT Infrastructure',
                    'is_active': True
                }
            )
            
            for subcat_code, subcat_name, device_types in subcategories:
                subcategory, created = DeviceSubCategory.objects.get_or_create(
                    category=category,
                    code=subcat_code,
                    defaults={
                        'name': subcat_name,
                        'description': f'{subcat_name} subcategory',
                        'is_active': True
                    }
                )
                
                for dtype_code in device_types:
                    DeviceType.objects.get_or_create(
                        subcategory=subcategory,
                        code=dtype_code,
                        defaults={
                            'name': dtype_code.replace('_', ' ').title(),
                            'description': f'{dtype_code.replace("_", " ").title()} device type',
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
                'restricted_to_own_department': False
            }),
            ('IT_OFFICER', 'IT Officer', 'Device and assignment management', {
                'can_view_all_devices': True,
                'can_manage_assignments': True,
                'can_approve_requests': False,
                'can_generate_reports': True,
                'can_manage_users': False,
                'can_system_admin': False,
                'restricted_to_own_department': False
            }),
            ('DEPARTMENT_HEAD', 'Department Head', 'Department-level oversight', {
                'can_view_all_devices': False,
                'can_manage_assignments': True,
                'can_approve_requests': True,
                'can_generate_reports': True,
                'can_manage_users': False,
                'can_system_admin': False,
                'restricted_to_own_department': True
            }),
            ('GENERAL_STAFF', 'General Staff', 'View personal assignments only', {
                'can_view_all_devices': False,
                'can_manage_assignments': False,
                'can_approve_requests': False,
                'can_generate_reports': True,
                'can_manage_users': False,
                'can_system_admin': False,
                'restricted_to_own_department': True
            }),
        ]
        
        for role_name, display_name, description, permissions in roles_data:
            UserRole.objects.get_or_create(
                name=role_name,
                defaults={
                    'display_name': display_name,
                    'description': description,
                    **permissions
                }
            )

    def create_sample_vendor(self):
        self.stdout.write('Creating sample vendor...')
        
        Vendor.objects.get_or_create(
            vendor_code='DELL001',
            defaults={
                'name': 'Dell Technologies Bangladesh',
                'vendor_type': 'MANUFACTURER',
                'contact_person': 'Sales Manager',
                'phone': '+880-2-9876543',
                'email': 'sales@dell.com.bd',
                'address': 'Dhaka, Bangladesh',
                'website': 'https://www.dell.com',
                'is_active': True,
                'performance_rating': 4.5
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
            first_name='System',
            last_name='Administrator'
        )
        
        # Create staff profile
        it_dept = Department.objects.filter(code='IT').first()
        if it_dept:
            Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': '110100091',
                    'full_name': f'{user.first_name} {user.last_name}',
                    'designation': 'Computer Programmer',
                    'department': it_dept,
                    'email': user.email,
                    'security_clearance': 'TOP_SECRET',
                    'date_joined': '2025-01-01',
                    'is_active': True
                }
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Superuser created: {username} / {password}')
        )