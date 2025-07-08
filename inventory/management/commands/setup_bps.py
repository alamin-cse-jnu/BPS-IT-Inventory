# inventory/management/commands/setup_bps.py
# Location: bps_inventory/apps/inventory/management/commands/setup_bps.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from inventory.models import (
    Building, Floor, Department, Room, Location,
    DeviceCategory, DeviceSubCategory, DeviceType, 
    Vendor, Staff
)
from authentication.models import UserRole, UserRoleAssignment

class Command(BaseCommand):
    help = 'Initial setup for BPS IT Inventory Management System'

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
            self.style.SUCCESS('🏛️ Setting up BPS IT Inventory Management System...')
        )

        try:
            with transaction.atomic():
                # Reset data if requested
                if options['reset_data']:
                    self.reset_data()
                
                # Create organizational structure
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
            Floor, Building, UserRole
        ]
        
        for model in models_to_clear:
            try:
                count = model.objects.count()
                model.objects.all().delete()
                self.stdout.write(f'  Cleared {count} {model.__name__} records')
            except Exception as e:
                self.stdout.write(f'  Warning: Could not clear {model.__name__}: {e}')

    def create_organization_structure(self):
        """Create Bangladesh Parliament Secretariat organizational structure"""
        self.stdout.write('🏢 Creating organizational structure...')
        
        # Main Parliament Building - Fixed code length
        main_building, created = Building.objects.get_or_create(
            code='BPS-MAIN-BLDG',  # Fixed: shortened from 'BPS-MAIN-BUILDING' to fit max_length=50
            defaults={
                'name': 'Bangladesh Parliament Secretariat - Main Building',
                'address': 'Sher-e-Bangla Nagar, Dhaka 1207, Bangladesh',
                'description': 'Main Parliament Building housing all administrative departments and IT infrastructure',
                'is_active': True
            }
        )
        self.stdout.write(f'  {"Created" if created else "Found"} building: {main_building.name}')

        # Create floors
        floors_data = [
            {'floor_number': 0, 'name': 'Ground Floor', 'description': 'Reception, Security, Public Areas'},
            {'floor_number': 1, 'name': 'First Floor', 'description': 'Administrative Offices, Security Department'},
            {'floor_number': 2, 'name': 'Second Floor', 'description': 'Administration Department, Finance'},
            {'floor_number': 3, 'name': 'Third Floor', 'description': 'IT Department, Senior Management Offices'},
            {'floor_number': 4, 'name': 'Fourth Floor', 'description': 'Legal Affairs, Committee Rooms, Archives'},
        ]

        for floor_data in floors_data:
            floor, created = Floor.objects.get_or_create(
                building=main_building,
                floor_number=floor_data['floor_number'],
                defaults={
                    'name': floor_data['name'],
                    'description': floor_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'    Created floor: {floor.name}')

        # Create departments with proper codes
        departments_data = [
            # IT Department (Floor 3)
            {
                'floor_number': 3,
                'name': 'Information Technology Department',
                'code': 'BPS-IT-DEPT',
                'head_of_department': 'Director (IT)',
                'contact_email': 'it@parliament.gov.bd',
                'contact_phone': '+880-2-9559022'
            },
        ]

        for dept_data in departments_data:
            floor = Floor.objects.get(
                building=main_building, 
                floor_number=dept_data['floor_number']
            )
            
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={
                    'floor': floor,
                    'building': main_building,  # Set building reference
                    'name': dept_data['name'],
                    'head_of_department': dept_data['head_of_department'],
                    'contact_email': dept_data['contact_email'],
                    'contact_phone': dept_data['contact_phone'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'    Created department: {dept.name}')

            # Create sample rooms for each department
            self.create_department_rooms(dept)

    def create_department_rooms(self, department):
        """Create rooms for a department"""
        rooms_config = {
            'BPS-IT-DEPT': [
                {'room_number': 'IT-301', 'room_name': 'IT Director Office', 'capacity': 5},
                {'room_number': 'IT-302', 'room_name': 'Server Room', 'capacity': 10},
                {'room_number': 'IT-303', 'room_name': 'IT Support Office', 'capacity': 4},
                {'room_number': 'IT-304', 'room_name': 'Network Operations Center', 'capacity': 3},
                {'room_number': 'IT-305', 'room_name': 'Development Lab', 'capacity': 6},
            ],
            'BPS-ADMIN-DEPT': [
                {'room_number': 'AD-201', 'room_name': 'Deputy Secretary Office', 'capacity': 3},
                {'room_number': 'AD-202', 'room_name': 'Administrative Office', 'capacity': 8},
                {'room_number': 'AD-203', 'room_name': 'HR Office', 'capacity': 4},
                {'room_number': 'AD-204', 'room_name': 'General Administration', 'capacity': 6},
            ],
            'BPS-FIN-DEPT': [
                {'room_number': 'FN-205', 'room_name': 'Deputy Secretary Finance Office', 'capacity': 2},
                {'room_number': 'FN-206', 'room_name': 'Accounts Office', 'capacity': 6},
                {'room_number': 'FN-207', 'room_name': 'Audit Office', 'capacity': 3},
                {'room_number': 'FN-208', 'room_name': 'Budget Planning', 'capacity': 4},
            ],
            'BPS-SEC-DEPT': [
                {'room_number': 'SC-101', 'room_name': 'Security Control Room', 'capacity': 3},
                {'room_number': 'SC-102', 'room_name': 'Guard Room', 'capacity': 4},
                {'room_number': 'SC-103', 'room_name': 'Security Office', 'capacity': 2},
            ],
            'BPS-LEGAL-DEPT': [
                {'room_number': 'LG-401', 'room_name': 'Legal Adviser Office', 'capacity': 2},
                {'room_number': 'LG-402', 'room_name': 'Legal Documentation', 'capacity': 3},
                {'room_number': 'LG-403', 'room_name': 'Legal Research', 'capacity': 4},
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
                    # Create location for each room
                    location, loc_created = Location.objects.get_or_create(
                        building=department.building,
                        floor=department.floor,
                        department=department,
                        room=room,
                        defaults={
                            'description': f"{room_data['room_name']} - {room_data['room_number']}",
                            'is_active': True
                        }
                    )
                    if loc_created:
                        self.stdout.write(f'      Created room: {room.room_number} - {room.room_name}')

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
                    'can_manage_users': True,
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
                    'can_view_financial_data': True,
                    'can_scan_qr_codes': True,
                    'can_generate_qr_codes': False,
                }
            },
            {
                'name': 'MANAGER',
                'display_name': 'Manager',
                'description': 'Departmental management and reporting access',
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
                'name': 'GENERAL_STAFF',
                'display_name': 'General Staff',
                'description': 'Basic device viewing and request capabilities',
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
                'description': 'Audit and compliance review access',
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
                'name': 'READONLY',
                'display_name': 'Read Only User',
                'description': 'View-only access for reporting and monitoring',
                'permissions': {
                    'can_view_all_devices': False,
                    'can_manage_assignments': False,
                    'can_approve_requests': False,
                    'can_generate_reports': True,
                    'can_manage_users': False,
                    'can_system_admin': False,
                    'can_manage_maintenance': False,
                    'can_manage_vendors': False,
                    'can_bulk_operations': False,
                    'can_export_data': False,
                    'restricted_to_own_department': True,
                    'can_view_financial_data': False,
                    'can_scan_qr_codes': False,
                    'can_generate_qr_codes': False,
                }
            },
        ]

        for role_data in roles_data:
            permissions = role_data.pop('permissions')
            
            # Create or update the role
            role, created = UserRole.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    **role_data,
                    **permissions,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing role with new permissions
                for key, value in {**role_data, **permissions}.items():
                    setattr(role, key, value)
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
                            {'name': 'Enterprise Router', 'description': 'Enterprise-grade router'},
                            {'name': 'Wireless Router', 'description': 'Wireless router/access point'},
                            {'name': 'VPN Router', 'description': 'VPN-enabled router'},
                        ]
                    },
                    {
                        'name': 'Access Points',
                        'description': 'Wireless access points',
                        'types': [
                            {'name': 'Indoor Access Point', 'description': 'Indoor wireless access point'},
                            {'name': 'Outdoor Access Point', 'description': 'Outdoor wireless access point'},
                        ]
                    },
                ]
            },
            {
                'name': 'Peripherals',
                'description': 'Computer peripherals and accessories',
                'subcategories': [
                    {
                        'name': 'Input Devices',
                        'description': 'Keyboards, mice, and input devices',
                        'types': [
                            {'name': 'Keyboard', 'description': 'Computer keyboard'},
                            {'name': 'Mouse', 'description': 'Computer mouse'},
                            {'name': 'Headphone', 'description': 'Computer headphones'},
                            {'name': 'WebCam', 'description': 'Computer webcam'},
                            {'name': 'Microphone', 'description': 'Computer microphone'},
                        ]
                    },
                    {
                        'name': 'Display Devices',
                        'description': 'Monitors and display equipment',
                        'types': [
                            {'name': 'Smart Display', 'description': 'Smart display monitor'},
                            {'name': 'LCD Monitor', 'description': 'LCD display monitor'},
                            {'name': 'LED Monitor', 'description': 'LED display monitor'},
                            {'name': 'Projector', 'description': 'Digital projector'},
                            {'name': 'Interactive Whiteboard', 'description': 'Interactive digital whiteboard'},
                        ]
                    },
                ]
            },
            {
                'name': 'Servers',
                'description': 'Server hardware and infrastructure',
                'subcategories': [
                    {
                        'name': 'Physical Servers',
                        'description': 'Physical server hardware',
                        'types': [
                            {'name': 'Rack Server', 'description': 'Rack-mounted server'},
                            {'name': 'Tower Server', 'description': 'Tower server'},
                            {'name': 'Blade Server', 'description': 'Blade server'},
                        ]
                    },
                    {
                        'name': 'Storage Devices',
                        'description': 'Network storage devices',
                        'types': [
                            {'name': 'NAS Device', 'description': 'Network Attached Storage'},
                            {'name': 'SAN Device', 'description': 'Storage Area Network device'},
                        ]
                    },
                ]
            },
            {
                'name': 'Office Equipment',
                'description': 'Office and business equipment',
                'subcategories': [
                    {
                        'name': 'Printers',
                        'description': 'Printing devices',
                        'types': [
                            {'name': 'Network Printer', 'description': 'Network printer'},
                            {'name': 'Laser Printer', 'description': 'Laser printer'},
                            {'name': 'Inkjet Printer', 'description': 'Inkjet printer'},
                            {'name': 'Multifunction Printer', 'description': 'Multifunction printer/scanner'},
                            {'name': '3D Printer', 'description': '3D printer'},
                        ]
                    },
                    {
                        'name': 'Scanners',
                        'description': 'Document scanning devices',
                        'types': [
                            {'name': 'Flatbed Scanner', 'description': 'Flatbed document scanner'},
                            {'name': 'Sheet-fed Scanner', 'description': 'Sheet-fed document scanner'},
                        ]
                    },
                ]
            },
            {
                'name': 'Security Equipment',
                'description': 'Security and surveillance equipment',
                'subcategories': [
                    {
                        'name': 'Surveillance',
                        'description': 'Surveillance equipment',
                        'types': [
                            {'name': 'IP Camera', 'description': 'Network IP camera'},
                            {'name': 'NVR System', 'description': 'Network Video Recorder'},
                        ]
                    },
                    {
                        'name': 'Access Control',
                        'description': 'Access control devices',
                        'types': [
                            {'name': 'Card Reader', 'description': 'Access control card reader'},
                            {'name': 'Biometric Scanner', 'description': 'Biometric access scanner'},
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
                'name': 'Dell Technologies Bangladesh Ltd.',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Sales Manager',
                'email': 'sales@dell.com.bd',
                'phone': '+880-2-9876543',
                'address': 'Gulshan, Dhaka-1212, Bangladesh',
                'website': 'https://www.dell.com.bd',
                'tax_id': 'TIN-DELL-BD-001',
            },
            {
                'name': 'Microsoft Bangladesh',
                'vendor_type': 'SOFTWARE_VENDOR',
                'contact_person': 'Enterprise Sales Team',
                'email': 'enterprise@microsoft.com.bd',
                'phone': '+880-2-8765432',
                'address': 'Dhanmondi, Dhaka-1205, Bangladesh',
                'website': 'https://www.microsoft.com.bd',
                'tax_id': 'TIN-MSFT-BD-001',
            },
            {
                'name': 'Cisco Systems Bangladesh',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Channel Partner Manager',
                'email': 'sales@cisco.com.bd',
                'phone': '+880-2-7654321',
                'address': 'Banani, Dhaka-1213, Bangladesh',
                'website': 'https://www.cisco.com.bd',
                'tax_id': 'TIN-CISCO-BD-001',
            },
            {
                'name': 'HP Bangladesh Ltd.',
                'vendor_type': 'HARDWARE_SUPPLIER',
                'contact_person': 'Business Development Manager',
                'email': 'business@hp.com.bd',
                'phone': '+880-2-6543210',
                'address': 'Uttara, Dhaka-1230, Bangladesh',
                'website': 'https://www.hp.com.bd',
                'tax_id': 'TIN-HP-BD-001',
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
        """Create superuser with IT Administrator role"""
        self.stdout.write(f'👤 Creating superuser: {username}...')
        
        try:
            # Create or get the user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': 'alamin@parliament.gov.bd',
                    'first_name': 'Al-Amin',
                    'last_name': 'Hossain',
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f'  Created superuser: {username}')
            else:
                # Update existing user
                user.set_password(password)
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()
                self.stdout.write(f'  Updated existing user: {username}')

            # Create staff profile
            IT_department = Department.objects.filter(code='BPS-IT-DEPT').first()
            if IT_department:
                staff, staff_created = Staff.objects.get_or_create(
                    user=user,
                    defaults={
                        'employee_id': '110100091',
                        'department': IT_department,
                        'designation': 'Computer Programmer',
                        'employment_type': 'PERMANENT',
                        'phone_number': '+880-1914219285',
                        'is_active': True,
                        'joining_date': timezone.now().date(),
                    }
                )
                
                if staff_created:
                    self.stdout.write(f'  Created staff profile for: {username}')

                # Assign IT Administrator role
                try:
                    it_admin_role = UserRole.objects.get(name='IT_ADMINISTRATOR')
                    
                    # Deactivate any existing role assignments
                    UserRoleAssignment.objects.filter(
                        user=user, 
                        is_active=True
                    ).update(is_active=False, deactivated_at=timezone.now())
                    
                    # Create new role assignment
                    role_assignment, role_created = UserRoleAssignment.objects.get_or_create(
                        user=user,
                        role=it_admin_role,
                        defaults={
                            'department': IT_department,
                            'assigned_by': user,  # Self-assigned for setup
                            'is_active': True,
                            'assigned_at': timezone.now(),
                        }
                    )
                    
                    if role_created:
                        self.stdout.write(f'  Assigned IT Administrator role to: {username}')
                except UserRole.DoesNotExist:
                    self.stdout.write(f'  Warning: IT Administrator role not found')
            else:
                self.stdout.write(f'  Warning: IT Department not found')
            
            return user
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  Failed to create superuser: {str(e)}')
            )
            raise
            