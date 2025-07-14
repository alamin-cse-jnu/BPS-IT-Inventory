from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from inventory.models import (
    Building, Block, Floor, Department, Room, Location,
    DeviceCategory, DeviceSubCategory, DeviceType, 
    Vendor, Staff
)
from authentication.models import UserRole, UserRoleAssignment

class Command(BaseCommand):
    help = 'Initial setup for BPS IT Inventory Management System with Block support'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-data',
            action='store_true',
            help='Reset all data (WARNING: This will delete existing data)',
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='alamin',
            help='Admin username (default: alamin)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='123',
            help='Admin password (default: 123)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏛️ Setting up BPS IT Inventory Management System with Block Support...')
        )

        try:
            with transaction.atomic():
                # Reset data if requested
                if options['reset_data']:
                    self.reset_data()
                
                # Create organizational structure with blocks
                self.create_organization_structure()
                
                # Create user roles
                self.create_user_roles()
                
                # Create device categories and types
                self.create_device_categories()
                
                # Create sample vendors
                self.create_sample_vendors()
                
                # Create superuser (IT Administrator)
                self.create_superuser(
                    options['admin_username'], 
                    options['admin_password']
                )

            # Display setup summary
            self.display_setup_summary()
            
            self.stdout.write(
                self.style.SUCCESS('✅ BPS IT Inventory System setup completed successfully!')
            )
            self.stdout.write(
                self.style.WARNING(f'🔑 Admin Login: {options["admin_username"]} / {options["admin_password"]}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Setup failed: {str(e)}')
            )
            raise

    def reset_data(self):
        """Reset all data in the system"""
        self.stdout.write('⚠️ Resetting all data...')
        
        # Delete in reverse dependency order
        models_to_clear = [
            UserRoleAssignment, Staff, DeviceType, DeviceSubCategory, 
            DeviceCategory, Vendor, Location, Room, Department, 
            Floor, Block, Building, UserRole
        ]
        
        for model in models_to_clear:
            try:
                count = model.objects.count()
                model.objects.all().delete()
                self.stdout.write(f'  Cleared {count} {model.__name__} records')
            except Exception as e:
                self.stdout.write(f'  Warning: Could not clear {model.__name__}: {e}')

    def create_organization_structure(self):
        """Create Bangladesh Parliament Secretariat organizational structure with blocks"""
        self.stdout.write('🏢 Creating organizational structure with blocks...')
        
        # Main Parliament Building
        main_building, created = Building.objects.get_or_create(
            code='BPS-MAIN-BLDG',
            defaults={
                'name': 'Bangladesh Parliament Secretariat - Main Building',
                'address': 'Sher-e-Bangla Nagar, Dhaka 1207, Bangladesh',
                'description': 'Main Parliament Building housing all administrative departments and IT infrastructure',
                'is_active': True
            }
        )
        self.stdout.write(f'  {"Created" if created else "Found"} building: {main_building.name}')

        # Create blocks within the main building - FIXED: Added Central Block
        blocks_data = [
            {'code': 'EB', 'name': 'East Block', 'description': 'Eastern section of Parliament Building'},
            {'code': 'WB', 'name': 'West Block', 'description': 'Western section of Parliament Building'},
            {'code': 'NB', 'name': 'North Block', 'description': 'Northern section of Parliament Building'},
            {'code': 'SB', 'name': 'South Block', 'description': 'Southern section of Parliament Building'},
            {'code': 'PB', 'name': 'Parliament Block', 'description': 'Parliament Block of Parliament Building'},
            {'code': 'CB', 'name': 'Central Block', 'description': 'Central administration block of Parliament Building'},
        ]

        blocks = {}
        for block_data in blocks_data:
            block, created = Block.objects.get_or_create(
                building=main_building,
                code=block_data['code'],
                defaults={
                    'name': block_data['name'],
                    'description': block_data['description'],
                    'is_active': True
                }
            )
            blocks[block_data['code']] = block
            if created:
                self.stdout.write(f'    Created block: {block.name} ({block.code})')

        # Create floors for each block
        floors_data = [
            # East Block - IT and Administration
            {'block_code': 'EB', 'floor_number': 0, 'name': 'Ground Floor', 'description': 'Reception, Security Check'},
            {'block_code': 'EB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Security Department, Guard Offices'},
            {'block_code': 'EB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Administration Department'},
            {'block_code': 'EB', 'floor_number': 3, 'name': 'Third Floor', 'description': 'IT Department'},
            {'block_code': 'EB', 'floor_number': 4, 'name': 'Fourth Floor', 'description': 'Senior Management, Director Offices'},
            
            # West Block - Legislative Affairs
            {'block_code': 'WB', 'floor_number': 0, 'name': 'Ground Floor', 'description': 'Session Hall Ground Level, Public Gallery'},
            {'block_code': 'WB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Main Session Hall, Speaker Chamber'},
            {'block_code': 'WB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Committee Rooms, MP Lounges'},
            {'block_code': 'WB', 'floor_number': 3, 'name': 'Third Floor', 'description': 'Parliamentary Services, Protocol'},
            
            # North Block - Legal and Security
            {'block_code': 'NB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Legal Affairs Department'},
            {'block_code': 'NB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Security Control Center'},
            {'block_code': 'NB', 'floor_number': 3, 'name': 'Third Floor', 'description': 'Legal Research, Documentation'},
            
            # South Block - Archives and Services
            {'block_code': 'SB', 'floor_number': 0, 'name': 'Ground Floor', 'description': 'Public Services, Information Desk'},
            {'block_code': 'SB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Archives Department'},
            {'block_code': 'SB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Records Management'},
            
            # Parliament Block - Main Parliament Activities
            {'block_code': 'PB', 'floor_number': 0, 'name': 'Ground Floor', 'description': 'Parliament Ground Level'},
            {'block_code': 'PB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Parliament First Floor'},
            {'block_code': 'PB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Parliament Second Floor'},
            
            # Central Block - Main Administration
            {'block_code': 'CB', 'floor_number': 1, 'name': 'First Floor', 'description': 'Secretary Office'},
            {'block_code': 'CB', 'floor_number': 2, 'name': 'Second Floor', 'description': 'Administrative Hub'},
            {'block_code': 'CB', 'floor_number': 3, 'name': 'Third Floor', 'description': 'Executive Offices'},
        ]

        floors = {}
        for floor_data in floors_data:
            block = blocks[floor_data['block_code']]
            floor, created = Floor.objects.get_or_create(
                building=main_building,
                block=block,
                floor_number=floor_data['floor_number'],
                defaults={
                    'name': floor_data['name'],
                    'description': floor_data['description'],
                    'is_active': True
                }
            )
            floors[f"{floor_data['block_code']}-{floor_data['floor_number']}"] = floor
            if created:
                self.stdout.write(f'      Created floor: {block.name} - {floor.name}')

        # Create departments with proper block assignments
        departments_data = [
            # East Block Departments
            {
                'block_code': 'EB',
                'floor_number': 3,
                'name': 'Information Technology Department',
                'code': 'BPS-IT-DEPT',
                'head_of_department': 'Director (IT)',
                'contact_email': 'it@parliament.gov.bd',
                'contact_phone': '+880-2-9559022'
            },
            {
                'block_code': 'EB',
                'floor_number': 2,
                'name': 'Administration Department',
                'code': 'BPS-ADMIN-DEPT',
                'head_of_department': 'Deputy Secretary (Administration)',
                'contact_email': 'admin@parliament.gov.bd',
                'contact_phone': '+880-2-9559011'
            },
            {
                'block_code': 'EB',
                'floor_number': 2,
                'name': 'Finance Department',
                'code': 'BPS-FIN-DEPT',
                'head_of_department': 'Deputy Secretary (Finance)',
                'contact_email': 'finance@parliament.gov.bd',
                'contact_phone': '+880-2-9559012'
            },
            {
                'block_code': 'EB',
                'floor_number': 1,
                'name': 'Security Department',
                'code': 'BPS-SEC-DEPT',
                'head_of_department': 'Security Officer',
                'contact_email': 'security@parliament.gov.bd',
                'contact_phone': '+880-2-9559013'
            },
            # North Block Departments
            {
                'block_code': 'NB',
                'floor_number': 1,
                'name': 'Legal Affairs Department',
                'code': 'BPS-LEGAL-DEPT',
                'head_of_department': 'Legal Adviser',
                'contact_email': 'legal@parliament.gov.bd',
                'contact_phone': '+880-2-9559014'
            },
            # South Block Departments
            {
                'block_code': 'SB',
                'floor_number': 1,
                'name': 'Archives Department',
                'code': 'BPS-ARCH-DEPT',
                'head_of_department': 'Chief Archivist',
                'contact_email': 'archives@parliament.gov.bd',
                'contact_phone': '+880-2-9559015'
            },
            # West Block Departments
            {
                'block_code': 'WB',
                'floor_number': 3,
                'name': 'Parliamentary Services Department',
                'code': 'BPS-PARL-DEPT',
                'head_of_department': 'Director (Parliamentary Services)',
                'contact_email': 'parliamentary@parliament.gov.bd',
                'contact_phone': '+880-2-9559016'
            },
            # Central Block Departments
            {
                'block_code': 'CB',
                'floor_number': 2,
                'name': 'Executive Administration',
                'code': 'BPS-EXEC-DEPT',
                'head_of_department': 'Secretary',
                'contact_email': 'secretary@parliament.gov.bd',
                'contact_phone': '+880-2-9559001'
            },
        ]

        departments = {}
        for dept_data in departments_data:
            floor_key = f"{dept_data['block_code']}-{dept_data['floor_number']}"
            floor = floors[floor_key]
            
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={
                    'floor': floor,
                    'name': dept_data['name'],
                    'head_of_department': dept_data['head_of_department'],
                    'contact_email': dept_data['contact_email'],
                    'contact_phone': dept_data['contact_phone'],
                    'is_active': True
                }
            )
            departments[dept_data['code']] = dept
            if created:
                self.stdout.write(f'        Created department: {dept.name} in {floor.block.name}')

            # Create sample rooms for each department
            self.create_department_rooms(dept)

    def create_department_rooms(self, department):
        """Create rooms for a department with block-aware naming"""
        block_code = department.floor.block.code
        floor_num = department.floor.floor_number
        
        rooms_config = {
            'BPS-IT-DEPT': [
                {'room_number': f'IT-{block_code}{floor_num}01', 'room_name': 'IT Director Office', 'capacity': 5},
                {'room_number': f'IT-{block_code}{floor_num}02', 'room_name': 'Server Room', 'capacity': 10},
                {'room_number': f'IT-{block_code}{floor_num}03', 'room_name': 'IT Support Office', 'capacity': 4},
                {'room_number': f'IT-{block_code}{floor_num}04', 'room_name': 'Network Operations Center', 'capacity': 3},
                {'room_number': f'IT-{block_code}{floor_num}05', 'room_name': 'Development Lab', 'capacity': 6},
            ],
            'BPS-ADMIN-DEPT': [
                {'room_number': f'AD-{block_code}{floor_num}01', 'room_name': 'Deputy Secretary Office', 'capacity': 3},
                {'room_number': f'AD-{block_code}{floor_num}02', 'room_name': 'Administrative Office', 'capacity': 8},
                {'room_number': f'AD-{block_code}{floor_num}03', 'room_name': 'HR Office', 'capacity': 4},
                {'room_number': f'AD-{block_code}{floor_num}04', 'room_name': 'General Administration', 'capacity': 6},
            ],
            'BPS-FIN-DEPT': [
                {'room_number': f'FN-{block_code}{floor_num}01', 'room_name': 'Deputy Secretary Finance Office', 'capacity': 2},
                {'room_number': f'FN-{block_code}{floor_num}02', 'room_name': 'Accounts Office', 'capacity': 6},
                {'room_number': f'FN-{block_code}{floor_num}03', 'room_name': 'Audit Office', 'capacity': 3},
                {'room_number': f'FN-{block_code}{floor_num}04', 'room_name': 'Budget Planning', 'capacity': 4},
            ],
            'BPS-SEC-DEPT': [
                {'room_number': f'SC-{block_code}{floor_num}01', 'room_name': 'Security Control Room', 'capacity': 3},
                {'room_number': f'SC-{block_code}{floor_num}02', 'room_name': 'Guard Room', 'capacity': 4},
                {'room_number': f'SC-{block_code}{floor_num}03', 'room_name': 'Security Office', 'capacity': 2},
            ],
            'BPS-LEGAL-DEPT': [
                {'room_number': f'LG-{block_code}{floor_num}01', 'room_name': 'Legal Adviser Office', 'capacity': 2},
                {'room_number': f'LG-{block_code}{floor_num}02', 'room_name': 'Legal Documentation', 'capacity': 3},
                {'room_number': f'LG-{block_code}{floor_num}03', 'room_name': 'Legal Research', 'capacity': 4},
            ],
            'BPS-ARCH-DEPT': [
                {'room_number': f'AR-{block_code}{floor_num}01', 'room_name': 'Chief Archivist Office', 'capacity': 2},
                {'room_number': f'AR-{block_code}{floor_num}02', 'room_name': 'Archive Storage', 'capacity': 8},
                {'room_number': f'AR-{block_code}{floor_num}03', 'room_name': 'Document Processing', 'capacity': 4},
            ],
            'BPS-PARL-DEPT': [
                {'room_number': f'PS-{block_code}{floor_num}01', 'room_name': 'Director Office', 'capacity': 3},
                {'room_number': f'PS-{block_code}{floor_num}02', 'room_name': 'Parliamentary Affairs', 'capacity': 6},
                {'room_number': f'PS-{block_code}{floor_num}03', 'room_name': 'Protocol Office', 'capacity': 4},
            ],
            'BPS-EXEC-DEPT': [
                {'room_number': f'EX-{block_code}{floor_num}01', 'room_name': 'Secretary Office', 'capacity': 2},
                {'room_number': f'EX-{block_code}{floor_num}02', 'room_name': 'Executive Suite', 'capacity': 5},
                {'room_number': f'EX-{block_code}{floor_num}03', 'room_name': 'Executive Meeting Room', 'capacity': 10},
            ],
        }

        if department.code in rooms_config:
            for room_data in rooms_config[department.code]:
                room, created = Room.objects.get_or_create(
                    department=department,
                    room_number=room_data['room_number'],
                    defaults={
                        'room_name': room_data['room_name'],
                        'capacity': room_data['capacity'],
                        'is_active': True
                    }
                )
                if created:
                    # Create location for each room (now with block support)
                    location, loc_created = Location.objects.get_or_create(
                        building=department.floor.building,
                        block=department.floor.block,
                        floor=department.floor,
                        department=department,
                        room=room,
                        defaults={
                            'description': f"{room_data['room_name']} - {room_data['room_number']} in {department.floor.block.name}",
                            'is_active': True
                        }
                    )
                    if loc_created:
                        self.stdout.write(f'          Created room: {room.room_number} - {room.room_name} in {department.floor.block.name}')

    def create_user_roles(self):
        """Create user roles for the BPS system"""
        self.stdout.write('👥 Creating user roles...')
        
        roles_data = [
            {
                'name': 'IT_ADMINISTRATOR',
                'display_name': 'IT Administrator',
                'description': 'Full system access and administration capabilities',
                'permissions': {
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
                    'can_generate_qr_codes': True,
                }
            },
            {
                'name': 'IT_OFFICER',
                'display_name': 'IT Officer',
                'description': 'IT operations and device management',
                'permissions': {
                    'can_view_all_devices': True,
                    'can_manage_assignments': True,
                    'can_approve_requests': True,
                    'can_generate_reports': True,
                    'can_manage_users': False,
                    'can_system_admin': False,
                    'can_manage_maintenance': True,
                    'can_manage_vendors': True,
                    'can_bulk_operations': True,
                    'can_export_data': True,
                    'restricted_to_own_department': False,
                    'can_view_financial_data': True,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': True,
                }
            },
            {
                'name': 'DEPARTMENT_HEAD',
                'display_name': 'Department Head',
                'description': 'Department-level device oversight and approval',
                'permissions': {
                    'can_view_all_devices': False,
                    'can_manage_assignments': False,
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
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'MANAGER',
                'display_name': 'Manager',
                'description': 'Mid-level management with departmental device access',
                'permissions': {
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
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'GENERAL_STAFF',
                'display_name': 'General Staff',
                'description': 'Basic staff access to assigned devices',
                'permissions': {
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
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'AUDITOR',
                'display_name': 'Auditor',
                'description': 'Audit and inspection access across all departments',
                'permissions': {
                    'can_view_all_devices': True,
                    'can_manage_assignments': False,
                    'can_approve_requests': False,
                    'can_generate_reports': True,
                    'can_manage_users': False,
                    'can_system_admin': False,
                    'can_manage_maintenance': False,
                    'can_manage_vendors': False,
                    'can_bulk_operations': False,
                    'can_export_data': True,
                    'restricted_to_own_department': False,
                    'can_view_financial_data': True,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'VENDOR',
                'display_name': 'Vendor/External',
                'description': 'External vendor access for maintenance and support',
                'permissions': {
                    'can_view_all_devices': False,
                    'can_manage_assignments': False,
                    'can_approve_requests': False,
                    'can_generate_reports': False,
                    'can_manage_users': False,
                    'can_system_admin': False,
                    'can_manage_maintenance': True,
                    'can_manage_vendors': False,
                    'can_bulk_operations': False,
                    'can_export_data': False,
                    'restricted_to_own_department': True,
                    'can_view_financial_data': False,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'READONLY',
                'display_name': 'Read Only User',
                'description': 'Read-only access for reporting and monitoring',
                'permissions': {
                    'can_view_all_devices': True,
                    'can_manage_assignments': False,
                    'can_approve_requests': False,
                    'can_generate_reports': True,
                    'can_manage_users': False,
                    'can_system_admin': False,
                    'can_manage_maintenance': False,
                    'can_manage_vendors': False,
                    'can_bulk_operations': False,
                    'can_export_data': True,
                    'restricted_to_own_department': False,
                    'can_view_financial_data': False,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': False,
                }
            },
        ]

        for role_data in roles_data:
            permissions = role_data.pop('permissions')
            role, created = UserRole.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'display_name': role_data['display_name'],
                    'description': role_data['description'],
                    'permissions': permissions,
                    **permissions,  # Unpack permissions to individual fields
                    'is_active': True
                }
            )
            if not created:
                # Update existing role permissions
                for field, value in permissions.items():
                    setattr(role, field, value)
                role.permissions = permissions
                role.save()
              
            self.stdout.write(f'  {"Created" if created else "Updated"} role: {role.display_name}')

    def create_device_categories(self):
        """Create device categories and types"""
        self.stdout.write('💻 Creating device categories...')
        
        categories_data = [
            {
                'name': 'Computing Devices',
                'description': 'Desktop computers, laptops, and computing equipment',
                'subcategories': [
                    {
                        'name': 'Desktop Computers',
                        'description': 'Desktop PC systems',
                        'types': [
                            {'name': 'Desktop PC', 'description': 'Standard desktop computer'},
                            {'name': 'Workstation', 'description': 'High-performance workstation'},
                            {'name': 'All-in-One PC', 'description': 'All-in-one desktop computer'},
                            {'name': 'Mini PC', 'description': 'Compact desktop computer'},
                        ]
                    },
                    {
                        'name': 'Laptops',
                        'description': 'Portable laptop computers',
                        'types': [
                            {'name': 'Business Laptop', 'description': 'Standard business laptop'},
                            {'name': 'Gaming Laptop', 'description': 'High-performance gaming laptop'},
                            {'name': 'Ultrabook', 'description': 'Ultra-thin laptop'},
                            {'name': 'Convertible Laptop', 'description': '2-in-1 convertible laptop'},
                        ]
                    },
                    {
                        'name': 'Tablets',
                        'description': 'Tablet computers and mobile devices',
                        'types': [
                            {'name': 'Android Tablet', 'description': 'Android-based tablet'},
                            {'name': 'iPad', 'description': 'Apple iPad tablet'},
                            {'name': 'Windows Tablet', 'description': 'Windows-based tablet'},
                        ]
                    },
                ]
            },
            {
                'name': 'Network Equipment',
                'description': 'Networking and connectivity devices',
                'subcategories': [
                    {
                        'name': 'Switches',
                        'description': 'Network switches and hubs',
                        'types': [
                            {'name': 'Managed Switch', 'description': 'Managed network switch'},
                            {'name': 'Unmanaged Switch', 'description': 'Unmanaged network switch'},
                            {'name': 'PoE Switch', 'description': 'Power over Ethernet switch'},
                        ]
                    },
                    {
                        'name': 'Routers',
                        'description': 'Network routers and gateways',
                        'types': [
                            {'name': 'Wireless Router', 'description': 'Wi-Fi enabled router'},
                            {'name': 'Enterprise Router', 'description': 'Enterprise-grade router'},
                            {'name': 'Firewall Router', 'description': 'Router with firewall features'},
                        ]
                    },
                    {
                        'name': 'Access Points',
                        'description': 'Wireless access points and controllers',
                        'types': [
                            {'name': 'Indoor Access Point', 'description': 'Indoor wireless access point'},
                            {'name': 'Outdoor Access Point', 'description': 'Outdoor wireless access point'},
                            {'name': 'Mesh Access Point', 'description': 'Mesh network access point'},
                        ]
                    },
                ]
            },
            {
                'name': 'Peripherals',
                'description': 'Input/output devices and peripherals',
                'subcategories': [
                    {
                        'name': 'Monitors',
                        'description': 'Display monitors and screens',
                        'types': [
                            {'name': 'LED Monitor', 'description': 'LED display monitor'},
                            {'name': 'LCD Monitor', 'description': 'LCD display monitor'},
                            {'name': 'Curved Monitor', 'description': 'Curved display monitor'},
                            {'name': '4K Monitor', 'description': '4K resolution monitor'},
                        ]
                    },
                    {
                        'name': 'Printers',
                        'description': 'Printing devices',
                        'types': [
                            {'name': 'Laser Printer', 'description': 'Laser printing technology'},
                            {'name': 'Inkjet Printer', 'description': 'Inkjet printing technology'},
                            {'name': 'Multifunction Printer', 'description': 'Print, scan, copy device'},
                            {'name': 'Dot Matrix Printer', 'description': 'Impact dot matrix printer'},
                        ]
                    },
                    {
                        'name': 'Input Devices',
                        'description': 'Keyboards, mice, and input devices',
                        'types': [
                            {'name': 'Keyboard', 'description': 'Computer keyboard'},
                            {'name': 'Mouse', 'description': 'Computer mouse'},
                            {'name': 'Webcam', 'description': 'Web camera'},
                            {'name': 'Microphone', 'description': 'Audio input device'},
                        ]
                    },
                ]
            },
            {
                'name': 'Server Equipment',
                'description': 'Server hardware and data center equipment',
                'subcategories': [
                    {
                        'name': 'Servers',
                        'description': 'Server systems',
                        'types': [
                            {'name': 'Rack Server', 'description': 'Rack-mounted server'},
                            {'name': 'Tower Server', 'description': 'Tower form factor server'},
                            {'name': 'Blade Server', 'description': 'Blade server system'},
                        ]
                    },
                    {
                        'name': 'Storage',
                        'description': 'Storage systems and arrays',
                        'types': [
                            {'name': 'NAS Storage', 'description': 'Network Attached Storage'},
                            {'name': 'SAN Storage', 'description': 'Storage Area Network'},
                            {'name': 'External HDD', 'description': 'External hard drive'},
                        ]
                    },
                ]
            },
            {
                'name': 'Security Equipment',
                'description': 'Security and surveillance devices',
                'subcategories': [
                    {
                        'name': 'Surveillance',
                        'description': 'Camera and monitoring systems',
                        'types': [
                            {'name': 'IP Camera', 'description': 'Network IP camera'},
                            {'name': 'NVR System', 'description': 'Network Video Recorder'},
                            {'name': 'DVR System', 'description': 'Digital Video Recorder'},
                        ]
                    },
                    {
                        'name': 'Access Control',
                        'description': 'Access control devices',
                        'types': [
                            {'name': 'Card Reader', 'description': 'Access control card reader'},
                            {'name': 'Biometric Scanner', 'description': 'Biometric access scanner'},
                            {'name': 'Access Controller', 'description': 'Access controller'},
                        ]
                    },
                ]
            },
        ]

        for cat_data in categories_data:
            subcategories_data = cat_data.pop('subcategories')
            
            category, created = DeviceCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Created category: {category.name}')

            for subcat_data in subcategories_data:
                types_data = subcat_data.pop('types')
                
                subcategory, created = DeviceSubCategory.objects.get_or_create(
                    category=category,
                    name=subcat_data['name'],
                    defaults={
                        'description': subcat_data['description'],
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'    Created subcategory: {subcategory.name}')

                for type_data in types_data:
                    device_type, created = DeviceType.objects.get_or_create(
                        subcategory=subcategory,
                        name=type_data['name'],
                        defaults={
                            'description': type_data['description'],
                            'is_active': True
                        }
                    )
                    if created:
                        self.stdout.write(f'      Created type: {device_type.name}')

    def create_sample_vendors(self):
        """Create sample vendor records"""
        self.stdout.write('🏢 Creating sample vendors...')
        
        vendors_data = [
            {
                'name': 'Dell Technologies Bangladesh',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Sales Manager',
                'email': 'sales@dell.com.bd',
                'phone': '+880-2-9876543',
                'address': 'Gulshan, Dhaka, Bangladesh',
                'website': 'https://www.dell.com.bd',
                'tax_id': 'TIN-DELL-BD-001',
            },
            {
                'name': 'Microsoft Bangladesh',
                'vendor_type': 'SOFTWARE_VENDOR',
                'contact_person': 'Enterprise Sales',
                'email': 'enterprise@microsoft.com.bd',
                'phone': '+880-2-8765432',
                'address': 'Dhanmondi, Dhaka, Bangladesh',
                'website': 'https://www.microsoft.com.bd',
                'tax_id': 'TIN-MSFT-BD-001',
            },
            {
                'name': 'Cisco Systems Bangladesh',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Channel Partner',
                'email': 'sales@cisco.com.bd',
                'phone': '+880-2-7654321',
                'address': 'Banani, Dhaka, Bangladesh',
                'website': 'https://www.cisco.com.bd',
                'tax_id': 'TIN-CISCO-BD-001',
            },
            {
                'name': 'HP Enterprise Bangladesh',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Enterprise Sales Team',
                'email': 'enterprise@hpe.com.bd',
                'phone': '+880-2-6543210',
                'address': 'Uttara, Dhaka, Bangladesh',
                'website': 'https://www.hpe.com.bd',
                'tax_id': 'TIN-HPE-BD-001',
            },
        ]

        for vendor_data in vendors_data:
            vendor, created = Vendor.objects.get_or_create(
                name=vendor_data['name'],
                defaults={
                    **vendor_data,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Created vendor: {vendor.name}')

    def create_superuser(self, username, password):
        """Create superuser account"""
        self.stdout.write('👤 Creating superuser account...')
        
        try:
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                self.stdout.write(f'  User "{username}" already exists, updating...')
                
                # Update user details
                user.email = 'admin@parliament.gov.bd'
                user.first_name = 'Al-Amin'
                user.last_name = 'Hossain'
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                user.set_password(password)
                user.save()
            else:
                # Create new superuser
                user = User.objects.create_superuser(
                    username=username,
                    email='admin@parliament.gov.bd',
                    password=password,
                    first_name='Al-Amin',
                    last_name='Hossain'
                )
                self.stdout.write(f'  Created superuser: {username}')

            # Create or update Staff profile
            it_department = Department.objects.get(code='BPS-IT-DEPT')
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': '110100091',
                    'designation': 'Computer Programmer',
                    'department': it_department,
                    'phone_number': '+880-2-9559022',
                    'joining_date': timezone.now().date(),
                    'is_active': True,
                }
            )
            
            if staff_created:
                self.stdout.write(f'  Created staff profile for: {user.get_full_name()}')

            # Assign IT Administrator role
            it_admin_role = UserRole.objects.get(name='IT_ADMINISTRATOR')
            role_assignment, role_created = UserRoleAssignment.objects.get_or_create(
                user=user,
                role=it_admin_role,
                defaults={
                    'department': it_department,
                    'assigned_by': user,
                    'assigned_at': timezone.now(),
                    'is_active': True,
                    'notes': 'Initial system setup - IT Administrator role'
                }
            )
            
            if role_created:
                self.stdout.write(f'  Assigned IT Administrator role to: {username}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create superuser: {str(e)}'))
            raise

    def display_setup_summary(self):
        """Display setup summary statistics"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('📊 BPS SETUP SUMMARY WITH BLOCK SUPPORT'))
        self.stdout.write('='*70)
        
        # Count created objects
        buildings_count = Building.objects.count()
        blocks_count = Block.objects.count()
        floors_count = Floor.objects.count()
        departments_count = Department.objects.count()
        rooms_count = Room.objects.count()
        locations_count = Location.objects.count()
        categories_count = DeviceCategory.objects.count()
        subcategories_count = DeviceSubCategory.objects.count()
        device_types_count = DeviceType.objects.count()
        vendors_count = Vendor.objects.count()
        roles_count = UserRole.objects.count()
        users_count = User.objects.count()
        
        self.stdout.write(f'🏢 Buildings Created: {buildings_count}')
        self.stdout.write(f'🧱 Blocks Created: {blocks_count}')
        self.stdout.write(f'🏬 Floors Created: {floors_count}')
        self.stdout.write(f'🏛️ Departments Created: {departments_count}')
        self.stdout.write(f'🚪 Rooms Created: {rooms_count}')
        self.stdout.write(f'📍 Locations Created: {locations_count}')
        self.stdout.write(f'📂 Device Categories: {categories_count}')
        self.stdout.write(f'📁 Device Subcategories: {subcategories_count}')
        self.stdout.write(f'🔧 Device Types: {device_types_count}')
        self.stdout.write(f'🏪 Vendors Created: {vendors_count}')
        self.stdout.write(f'👥 User Roles: {roles_count}')
        self.stdout.write(f'👤 Users: {users_count}')
        
        # Display block summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('🧱 BLOCK STRUCTURE SUMMARY'))
        self.stdout.write('='*70)
        
        for building in Building.objects.all():
            self.stdout.write(f'\n🏢 {building.name}:')
            for block in building.blocks.all():
                floors_in_block = block.floors.count()
                departments_in_block = sum(floor.departments.count() for floor in block.floors.all())
                self.stdout.write(f'  🧱 {block.name} ({block.code}): {floors_in_block} floors, {departments_in_block} departments')
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('🎯 NEXT STEPS'))
        self.stdout.write('='*70)
        self.stdout.write('1. 🌐 Access the system at: http://localhost:8000')
        self.stdout.write('2. 🔑 Login with the admin credentials provided above')
        self.stdout.write('3. 📱 Start adding devices through the web interface')
        self.stdout.write('4. 👥 Create additional user accounts and assign roles')
        self.stdout.write('5. 🏷️ Generate QR codes for existing devices')
        self.stdout.write('6. 📊 Begin device assignments and tracking')
        self.stdout.write('7. 🧱 Explore the new block-based location hierarchy')
        self.stdout.write('\n' + '='*70)
        
        # Location hierarchy examples
        self.stdout.write(self.style.SUCCESS('📍 LOCATION HIERARCHY EXAMPLES'))
        self.stdout.write('='*70)
        sample_locations = Location.objects.all()[:3]
        for loc in sample_locations:
            self.stdout.write(f'  📍 {loc}')
        self.stdout.write('\n' + '='*70)