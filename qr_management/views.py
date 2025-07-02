from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Avg
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import json
from PIL import Image, ImageDraw, ImageFont
import zipfile
import tempfile
import os

from inventory.models import Device, Location, Staff, Assignment
from .models import QRCodeScan

def generate_qr_code_data(device):
    """Generate QR code data structure for device"""
    current_assignment = device.assignments.filter(is_active=True).first()
    
    qr_data = {
        "deviceId": device.device_id,
        "assetTag": device.asset_tag,
        "deviceName": device.device_name,
        "category": device.device_type.subcategory.category.name if device.device_type else "Unknown",
        "assignedTo": str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else None,
        "assignedDepartment": str(current_assignment.assigned_to_department) if current_assignment and current_assignment.assigned_to_department else None,
        "location": str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else None,
        "lastUpdated": timezone.now().isoformat(),
        "verifyUrl": f"/verify/{device.device_id}/"
    }
    
    return qr_data

@login_required
def qr_scan_history(request):
    """View QR code scanning history"""
    try:
        # Get filter parameters
        device_filter = request.GET.get('device')
        scan_type_filter = request.GET.get('scan_type')
        user_filter = request.GET.get('user')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        verification_status = request.GET.get('verification_status')
        
        # Base queryset
        scans = QRCodeScan.objects.select_related(
            'device', 'scanned_by', 'scan_location',
            'device_location_at_scan', 'assigned_staff_at_scan'
        ).order_by('-timestamp')
        
        # Apply filters
        if device_filter:
            scans = scans.filter(
                Q(device__device_id__icontains=device_filter) |
                Q(device__device_name__icontains=device_filter)
            )
        if scan_type_filter:
            scans = scans.filter(scan_type=scan_type_filter)
        if user_filter:
            scans = scans.filter(scanned_by__username__icontains=user_filter)
        if date_from:
            scans = scans.filter(timestamp__date__gte=date_from)
        if date_to:
            scans = scans.filter(timestamp__date__lte=date_to)
        if verification_status:
            if verification_status == 'success':
                scans = scans.filter(verification_success=True)
            elif verification_status == 'failed':
                scans = scans.filter(verification_success=False)
        
        # Pagination
        paginator = Paginator(scans, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        total_scans = scans.count()
        successful_scans = scans.filter(verification_success=True).count()
        failed_scans = scans.filter(verification_success=False).count()
        today_scans = scans.filter(timestamp__date=timezone.now().date()).count()
        
        context = {
            'page_obj': page_obj,
            'scan_types': [
                ('VERIFICATION', 'Verification'),
                ('INVENTORY', 'Inventory Check'),
                ('ASSIGNMENT', 'Assignment'),
                ('MAINTENANCE', 'Maintenance'),
                ('AUDIT', 'Audit'),
            ],
            'filters': {
                'device': device_filter,
                'scan_type': scan_type_filter,
                'user': user_filter,
                'date_from': date_from,
                'date_to': date_to,
                'verification_status': verification_status,
            },
            'stats': {
                'total_scans': total_scans,
                'successful_scans': successful_scans,
                'failed_scans': failed_scans,
                'today_scans': today_scans,
                'success_rate': (successful_scans / total_scans * 100) if total_scans > 0 else 0,
            }
        }
        
        return render(request, 'qr_management/scan_history.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading scan history: {str(e)}")
        return render(request, 'qr_management/scan_history.html', {})

@login_required
def qr_index(request):
    """Main QR management dashboard"""
    try:
        # Quick statistics
        total_devices = Device.objects.count()
        devices_with_qr = Device.objects.exclude(qr_code__isnull=True).exclude(qr_code='').count()
        total_scans = QRCodeScan.objects.count()
        successful_scans = QRCodeScan.objects.filter(verification_success=True).count()
        
        # Recent QR scans
        recent_scans = QRCodeScan.objects.select_related(
            'device', 'scanned_by'
        ).order_by('-timestamp')[:10]
        
        # QR code generation stats by category
        category_stats = Device.objects.values(
            'device_type__subcategory__category__name'
        ).annotate(
            total_count=Count('id'),
            qr_count=Count('id', filter=~Q(qr_code__isnull=True) & ~Q(qr_code=''))
        ).order_by('-total_count')
        
        # Scanning activity (last 7 days)
        seven_days_ago = timezone.now().date() - timezone.timedelta(days=7)
        daily_scans = QRCodeScan.objects.filter(
            timestamp__date__gte=seven_days_ago
        ).extra(
            select={'day': "DATE(timestamp)"}
        ).values('day').annotate(
            count=Count('id'),
            successful=Count('id', filter=Q(verification_success=True))
        ).order_by('day')
        
        context = {
            'total_devices': total_devices,
            'devices_with_qr': devices_with_qr,
            'qr_coverage': (devices_with_qr / total_devices * 100) if total_devices > 0 else 0,
            'total_scans': total_scans,
            'successful_scans': successful_scans,
            'success_rate': (successful_scans / total_scans * 100) if total_scans > 0 else 0,
            'recent_scans': recent_scans,
            'category_stats': category_stats,
            'daily_scans': daily_scans,
        }
        
        return render(request, 'qr_management/index.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading QR management dashboard: {str(e)}")
        return render(request, 'qr_management/index.html', {})

@login_required
def qr_generate(request, device_id):
    """Generate QR code for a specific device"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        if request.method == 'POST':
            # Generate QR code
            qr_data = generate_qr_code_data(device)
            qr_json = json.dumps(qr_data)
            
            # Create QR code image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_json)
            qr.make(fit=True)
            
            # Generate image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code to device
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_code_data = base64.b64encode(buffer.getvalue()).decode()
            
            # Update device with QR code
            device.qr_code = qr_code_data
            device.save()
            
            messages.success(request, f'QR code generated successfully for device {device.device_id}')
            return redirect('qr_management:qr_generate', device_id=device_id)
        
        # Display current QR code if exists
        qr_image_data = None
        if device.qr_code:
            qr_image_data = f"data:image/png;base64,{device.qr_code}"
        
        context = {
            'device': device,
            'qr_image_data': qr_image_data,
            'qr_url': request.build_absolute_uri(
                reverse('public_qr_verify', args=[device.device_id])
            )
        }
        
        return render(request, 'qr_management/generate.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating QR code: {str(e)}")
        return redirect('qr_management:index')
@login_required
def qr_bulk_generate(request):
    """Bulk generate QR codes for multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        
        if not device_ids:
            messages.error(request, 'No devices selected for QR code generation.')
            return redirect('qr_management:qr_bulk_generate')
        
        try:
            generated_count = 0
            failed_count = 0
            
            for device_id in device_ids:
                try:
                    device = Device.objects.get(device_id=device_id)
                    
                    # Generate QR code data
                    qr_data = generate_qr_code_data(device)
                    qr_json = json.dumps(qr_data)
                    
                    # Create QR code
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_json)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Convert to base64
                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    qr_code_data = base64.b64encode(buffer.getvalue()).decode()
                    
                    # Update device
                    device.qr_code = qr_code_data
                    device.save()
                    
                    generated_count += 1
                    
                except Device.DoesNotExist:
                    failed_count += 1
                    continue
                except Exception as e:
                    failed_count += 1
                    continue
            
            messages.success(request, f'Generated QR codes for {generated_count} devices. {failed_count} failed.')
            return redirect('qr_management:qr_bulk_generate')
            
        except Exception as e:
            messages.error(request, f'Error in bulk QR generation: {str(e)}')
    
    # GET request - show device selection
    devices = Device.objects.select_related(
        'device_type__subcategory__category'
    ).order_by('device_id')
    
    # Filter options
    category = request.GET.get('category')
    status = request.GET.get('status')
    has_qr = request.GET.get('has_qr')
    
    if category:
        devices = devices.filter(device_type__subcategory__category_id=category)
    if status:
        devices = devices.filter(status=status)
    if has_qr == 'yes':
        devices = devices.exclude(qr_code__isnull=True).exclude(qr_code='')
    elif has_qr == 'no':
        devices = devices.filter(Q(qr_code__isnull=True) | Q(qr_code=''))
    
    # Pagination
    paginator = Paginator(devices, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': Device.objects.values_list(
            'device_type__subcategory__category__id',
            'device_type__subcategory__category__name'
        ).distinct(),
        'filters': {
            'category': category,
            'status': status,
            'has_qr': has_qr,
        }
    }
    
    return render(request, 'qr_management/bulk_generate.html', context)

def create_qr_label(device, size='medium', include_text=True):
    """Create a printable QR label for a device"""
    try:
        # Size configurations
        sizes = {
            'small': (200, 100),
            'medium': (300, 200),
            'large': (400, 300),
        }
        
        width, height = sizes.get(size, sizes['medium'])
        
        # Create image
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Generate QR code
        if device.qr_code:
            qr_img_data = base64.b64decode(device.qr_code)
            qr_img = Image.open(BytesIO(qr_img_data))
            
            # Resize QR code to fit
            qr_size = min(width - 20, height - (40 if include_text else 20))
            qr_img = qr_img.resize((qr_size, qr_size))
            
            # Paste QR code
            qr_x = (width - qr_size) // 2
            qr_y = 10
            img.paste(qr_img, (qr_x, qr_y))
            
            # Add text if requested
            if include_text:
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                
                text_y = qr_y + qr_size + 10
                
                # Device ID
                text = f"ID: {device.device_id}"
                text_width = draw.textlength(text, font=font)
                text_x = (width - text_width) // 2
                draw.text((text_x, text_y), text, fill='black', font=font)
                
                # Device name (truncated if too long)
                text_y += 15
                device_name = device.device_name
                if len(device_name) > 25:
                    device_name = device_name[:22] + "..."
                
                text_width = draw.textlength(device_name, font=font)
                text_x = (width - text_width) // 2
                draw.text((text_x, text_y), device_name, fill='black', font=font)
        
        return img
        
    except Exception as e:
        # Return a blank image with error message
        img = Image.new('RGB', (300, 200), 'white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 90), f"Error: {str(e)}", fill='red')
        return img
    
@login_required
def qr_print_labels(request):
    """Generate printable QR code labels"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        label_size = request.POST.get('label_size', 'medium')
        include_text = request.POST.get('include_text') == 'on'
        
        if not device_ids:
            messages.error(request, 'No devices selected for label printing.')
            return redirect('qr_management:qr_print_labels')
        
        try:
            # Create a ZIP file with all labels
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        
                        if not device.qr_code:
                            continue
                        
                        # Create label image
                        label_img = create_qr_label(device, label_size, include_text)
                        
                        # Save to ZIP
                        img_buffer = BytesIO()
                        label_img.save(img_buffer, format='PNG')
                        
                        zip_file.writestr(
                            f"qr_label_{device.device_id}.png",
                            img_buffer.getvalue()
                        )
                        
                    except Device.DoesNotExist:
                        continue
            
            # Return ZIP file
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="qr_labels.zip"'
            return response
            
        except Exception as e:
            messages.error(request, f'Error generating labels: {str(e)}')
    
    # GET request - show label options
    devices = Device.objects.exclude(
        Q(qr_code__isnull=True) | Q(qr_code='')
    ).select_related('device_type__subcategory__category')
    
    context = {
        'devices': devices[:100],  # Limit for display
        'label_sizes': [
            ('small', 'Small (2x1 inch)'),
            ('medium', 'Medium (3x2 inch)'),
            ('large', 'Large (4x3 inch)'),
        ]
    }
    
    return render(request, 'qr_management/print_labels.html', context)

@login_required
def qr_verify(request, device_id):
    """Verify QR code for a device (authenticated users)"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        current_assignment = device.assignments.filter(is_active=True).first()
        
        # Create scan record
        scan = QRCodeScan.objects.create(
            device=device,
            scanned_by=request.user,
            scan_type='VERIFICATION',
            verification_success=True,
            device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
            assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
            scan_location=None,  # Could be set based on user's location
            additional_data={
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': request.META.get('REMOTE_ADDR', ''),
                'verification_method': 'web_interface'
            }
        )
        
        context = {
            'device': device,
            'assignment': current_assignment,
            'verification_successful': True,
            'scan': scan,
            'timestamp': timezone.now(),
        }
        
        return render(request, 'qr_management/verify.html', context)
        
    except Exception as e:
        # Create failed scan record
        try:
            QRCodeScan.objects.create(
                device_id=device_id,
                scanned_by=request.user,
                scan_type='VERIFICATION',
                verification_success=False,
                error_message=str(e),
                additional_data={
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': request.META.get('REMOTE_ADDR', ''),
                    'verification_method': 'web_interface'
                }
            )
        except:
            pass
        
        context = {
            'error': f"Device {device_id} not found or error occurred: {str(e)}",
            'device_id': device_id,
            'verification_successful': False,
        }
        return render(request, 'qr_management/verify.html', context)

@login_required
def qr_scan_mobile(request):
    """Mobile-optimized QR scanning interface"""
    try:
        if request.method == 'POST':
            device_id = request.POST.get('device_id')
            scan_type = request.POST.get('scan_type', 'VERIFICATION')
            location_id = request.POST.get('location_id')
            notes = request.POST.get('notes', '')
            
            if not device_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Device ID is required'
                })
            
            try:
                device = Device.objects.get(device_id=device_id)
                current_assignment = device.assignments.filter(is_active=True).first()
                
                # Get location if provided
                scan_location = None
                if location_id:
                    try:
                        scan_location = Location.objects.get(id=location_id)
                    except Location.DoesNotExist:
                        pass
                
                # Create scan record
                scan = QRCodeScan.objects.create(
                    device=device,
                    scanned_by=request.user,
                    scan_type=scan_type,
                    verification_success=True,
                    device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                    assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                    scan_location=scan_location,
                    notes=notes,
                    additional_data={
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': request.META.get('REMOTE_ADDR', ''),
                        'verification_method': 'mobile_interface'
                    }
                )
                
                return JsonResponse({
                    'success': True,
                    'device': {
                        'id': device.device_id,
                        'name': device.device_name,
                        'status': device.get_status_display(),
                        'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else None,
                        'location': str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else None,
                    },
                    'scan_id': scan.id,
                    'timestamp': scan.timestamp.isoformat()
                })
                
            except Device.DoesNotExist:
                # Create failed scan record
                QRCodeScan.objects.create(
                    device_id=device_id,
                    scanned_by=request.user,
                    scan_type=scan_type,
                    verification_success=False,
                    error_message=f"Device {device_id} not found",
                    scan_location=scan_location,
                    notes=notes,
                    additional_data={
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': request.META.get('REMOTE_ADDR', ''),
                        'verification_method': 'mobile_interface'
                    }
                )
                
                return JsonResponse({
                    'success': False,
                    'error': f'Device {device_id} not found'
                })
        
        # GET request - show mobile interface
        locations = Location.objects.all().order_by('name')
        scan_types = [
            ('VERIFICATION', 'Verification'),
            ('INVENTORY', 'Inventory Check'),
            ('ASSIGNMENT', 'Assignment'),
            ('MAINTENANCE', 'Maintenance'),
            ('AUDIT', 'Audit'),
        ]
        
        context = {
            'locations': locations,
            'scan_types': scan_types,
        }
        
        return render(request, 'qr_management/mobile_scan.html', context)
        
    except Exception as e:
        if request.method == 'POST':
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        else:
            messages.error(request, f"Error loading mobile scan interface: {str(e)}")
            return redirect('qr_management:index')

@login_required
def qr_scan_history(request):
    """View QR code scan history"""
    try:
        # Filters
        device_filter = request.GET.get('device')
        scan_type_filter = request.GET.get('scan_type')
        user_filter = request.GET.get('user')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        verification_status = request.GET.get('verification_status')
        
        # Base queryset
        scans = QRCodeScan.objects.select_related(
            'device', 'scanned_by', 'scan_location', 'assigned_staff_at_scan'
        ).order_by('-timestamp')
        
        # Apply filters
        if device_filter:
            scans = scans.filter(device__device_id__icontains=device_filter)
        
        if scan_type_filter:
            scans = scans.filter(scan_type=scan_type_filter)
        
        if user_filter:
            scans = scans.filter(scanned_by__username__icontains=user_filter)
        
        if date_from:
            scans = scans.filter(timestamp__date__gte=date_from)
        
        if date_to:
            scans = scans.filter(timestamp__date__lte=date_to)
        
        if verification_status == 'success':
            scans = scans.filter(verification_success=True, discrepancies_found='')
        elif verification_status == 'success_with_notes':
            scans = scans.filter(verification_success=True).exclude(discrepancies_found='')
        elif verification_status == 'failed':
            scans = scans.filter(verification_success=False)
        
        # Pagination
        paginator = Paginator(scans, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        total_scans = QRCodeScan.objects.count()
        successful_scans = QRCodeScan.objects.filter(verification_success=True).count()
        failed_scans = QRCodeScan.objects.filter(verification_success=False).count()
        today_scans = QRCodeScan.objects.filter(timestamp__date=timezone.now().date()).count()
        
        context = {
            'page_obj': page_obj,
            'scan_types': [
                ('VERIFICATION', 'Verification'),
                ('INVENTORY', 'Inventory Check'),
                ('ASSIGNMENT', 'Assignment'),
                ('MAINTENANCE', 'Maintenance'),
                ('AUDIT', 'Audit'),
            ],
            'filters': {
                'device': device_filter,
                'scan_type': scan_type_filter,
                'user': user_filter,
                'date_from': date_from,
                'date_to': date_to,
                'verification_status': verification_status,
            },
            'stats': {
                'total_scans': total_scans,
                'successful_scans': successful_scans,
                'failed_scans': failed_scans,
                'today_scans': today_scans,
                'success_rate': (successful_scans / total_scans * 100) if total_scans > 0 else 0,
            }
        }
        
        return render(request, 'qr_management/scan_history.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading scan history: {str(e)}")
        return render(request, 'qr_management/scan_history.html', {})

@login_required
def qr_scan_detail(request, scan_id):
    """Detailed view of a QR code scan"""
    try:
        scan = get_object_or_404(
            QRCodeScan.objects.select_related(
                'device', 'scanned_by', 'scan_location', 
                'device_location_at_scan', 'assigned_staff_at_scan'
            ),
            id=scan_id
        )
        
        context = {
            'scan': scan,
        }
        
        return render(request, 'qr_management/scan_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading scan details: {str(e)}")
        return redirect('qr_management:scan_history')

@login_required
def qr_batch_verify(request):
    """Batch verification of multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        location_id = request.POST.get('location_id')
        
        if not device_ids:
            messages.error(request, 'No devices selected for verification.')
            return redirect('qr_management:qr_batch_verify')
        
        try:
            verified_count = 0
            failed_count = 0
            scan_location = None
            
            if location_id:
                try:
                    scan_location = Location.objects.get(id=location_id)
                except Location.DoesNotExist:
                    pass
            
            for device_id in device_ids:
                try:
                    device = Device.objects.get(device_id=device_id)
                    current_assignment = device.assignments.filter(is_active=True).first()
                    
                    # Create scan record
                    QRCodeScan.objects.create(
                        device=device,
                        scanned_by=request.user,
                        scan_type='BATCH_VERIFICATION',
                        verification_success=True,
                        device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                        assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                        scan_location=scan_location,
                        additional_data={
                            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                            'ip_address': request.META.get('REMOTE_ADDR', ''),
                            'verification_method': 'batch_verification'
                        }
                    )
                    
                    verified_count += 1
                    
                except Device.DoesNotExist:
                    # Create failed scan record
                    QRCodeScan.objects.create(
                        device_id=device_id,
                        scanned_by=request.user,
                        scan_type='BATCH_VERIFICATION',
                        verification_success=False,
                        error_message=f"Device {device_id} not found",
                        scan_location=scan_location,
                        additional_data={
                            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                            'ip_address': request.META.get('REMOTE_ADDR', ''),
                            'verification_method': 'batch_verification'
                        }
                    )
                    failed_count += 1
            
            messages.success(request, f'Verified {verified_count} devices. {failed_count} failed.')
            
        except Exception as e:
            messages.error(request, f'Error in batch verification: {str(e)}')
    
    # GET request - show device selection
    search = request.GET.get('search', '')
    devices = Device.objects.select_related('device_type__subcategory__category')
    locations = Location.objects.all().order_by('name')
    
    if search:
        devices = devices.filter(
            Q(device_id__icontains=search) |
            Q(device_name__icontains=search) |
            Q(asset_tag__icontains=search)
        )
    
    context = {
        'devices': devices[:100],  # Limit for display
        'locations': locations,
        'search': search,
    }
    
    return render(request, 'qr_management/batch_verify.html', context)

@login_required
def qr_analytics(request):
    """QR code scanning analytics dashboard"""
    try:
        # Date range for analytics
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        # Basic statistics
        total_scans = QRCodeScan.objects.count()
        period_scans = QRCodeScan.objects.filter(timestamp__date__gte=start_date)
        
        # Scan types distribution
        scan_types_data = period_scans.values('scan_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Success rate by scan type
        success_rates = []
        scan_type_choices = [
            ('VERIFICATION', 'Verification'),
            ('INVENTORY', 'Inventory Check'),
            ('ASSIGNMENT', 'Assignment'),
            ('MAINTENANCE', 'Maintenance'),
            ('AUDIT', 'Audit'),
            ('BATCH_VERIFICATION', 'Batch Verification'),
        ]
        
        for scan_type, scan_type_display in scan_type_choices:
            total = period_scans.filter(scan_type=scan_type).count()
            successful = period_scans.filter(
                scan_type=scan_type, 
                verification_success=True
            ).count()
            
            if total > 0:
                success_rates.append({
                    'scan_type': scan_type_display,
                    'total': total,
                    'successful': successful,
                    'rate': (successful / total * 100)
                })
        
        # Most scanned devices
        most_scanned = period_scans.values(
            'device__device_id', 'device__device_name'
        ).annotate(
            scan_count=Count('id')
        ).order_by('-scan_count')[:10]
        
        # Scanning activity by user
        user_activity = period_scans.values(
            'scanned_by__username', 'scanned_by__first_name', 'scanned_by__last_name'
        ).annotate(
            scan_count=Count('id'),
            success_count=Count('id', filter=Q(verification_success=True))
        ).order_by('-scan_count')[:10]
        
        # Daily scanning trends
        daily_trends = period_scans.extra(
            select={'day': "DATE(timestamp)"}
        ).values('day').annotate(
            count=Count('id'),
            successful=Count('id', filter=Q(verification_success=True))
        ).order_by('day')
        
        context = {
            'total_scans': total_scans,
            'period_scans_count': period_scans.count(),
            'scan_types_data': scan_types_data,
            'success_rates': success_rates,
            'most_scanned': most_scanned,
            'user_activity': user_activity,
            'daily_trends': daily_trends,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        return render(request, 'qr_management/analytics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading QR analytics: {str(e)}")
        return render(request, 'qr_management/analytics.html', {})