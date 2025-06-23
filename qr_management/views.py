# qr_management/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import json
from PIL import Image, ImageDraw, ImageFont

from inventory.models import Device, Location, Staff, Assignment
from .models import QRCodeScan

def generate_qr_code_data(device):
    """Generate QR code data structure for device"""
    current_assignment = device.assignments.filter(is_active=True).first()
    
    qr_data = {
        "deviceId": device.device_id,
        "assetTag": device.asset_tag,
        "deviceName": device.device_name,
        "category": device.device_type.subcategory.category.name,
        "assignedTo": str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else None,
        "location": str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else None,
        "lastUpdated": timezone.now().isoformat(),
        "verificationUrl": f"{settings.QR_CODE_BASE_URL}/qr/verify/{device.device_id}/"
    }
    
    return json.dumps(qr_data)

def create_qr_code_image(device, format='PNG'):
    """Create QR code image for device"""
    qr_data = generate_qr_code_data(device)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=getattr(settings, 'QR_CODE_SIZE', 10),
        border=getattr(settings, 'QR_CODE_BORDER', 4),
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    if format.upper() == 'SVG':
        factory = qrcode.image.svg.SvgPathImage
        img = qr.make_image(image_factory=factory)
        return img
    else:
        # Create PIL image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Create a larger image with device info
        final_img = Image.new('RGB', (400, 500), 'white')
        
        # Resize QR code to fit
        qr_img = img.resize((300, 300))
        final_img.paste(qr_img, (50, 50))
        
        # Add device information text
        draw = ImageDraw.Draw(final_img)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Device ID
        draw.text((50, 360), f"Device ID: {device.device_id}", fill="black", font=font)
        
        # Asset Tag
        draw.text((50, 380), f"Asset Tag: {device.asset_tag}", fill="black", font=font_small)
        
        # Device Name
        device_name = device.device_name[:30] + "..." if len(device.device_name) > 30 else device.device_name
        draw.text((50, 400), f"Name: {device_name}", fill="black", font=font_small)
        
        # BPS Logo/Text
        draw.text((50, 430), "Bangladesh Parliament Secretariat", fill="black", font=font_small)
        draw.text((50, 450), "IT Inventory Management System", fill="black", font=font_small)
        
        return final_img

@login_required
def qr_generate(request, device_id):
    """Generate QR code for a device"""
    device = get_object_or_404(Device, device_id=device_id)
    
    format_type = request.GET.get('format', 'PNG').upper()
    download = request.GET.get('download') == '1'
    
    if format_type == 'SVG':
        img = create_qr_code_image(device, 'SVG')
        response = HttpResponse(img.to_string(), content_type='image/svg+xml')
        if download:
            response['Content-Disposition'] = f'attachment; filename="{device.device_id}_qr.svg"'
    else:
        img = create_qr_code_image(device, 'PNG')
        
        # Save to BytesIO
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        response = HttpResponse(img_io.getvalue(), content_type='image/png')
        if download:
            response['Content-Disposition'] = f'attachment; filename="{device.device_id}_qr.png"'
    
    return response

@login_required
def qr_bulk_generate(request):
    """Generate QR codes for multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        devices = Device.objects.filter(device_id__in=device_ids)
        
        if not devices.exists():
            messages.error(request, 'No devices selected.')
            return redirect('inventory:device_list')
        
        # Create a ZIP file with all QR codes
        import zipfile
        from django.http import StreamingHttpResponse
        
        def generate_zip():
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for device in devices:
                    img = create_qr_code_image(device)
                    img_buffer = BytesIO()
                    img.save(img_buffer, 'PNG')
                    zip_file.writestr(f"{device.device_id}_qr.png", img_buffer.getvalue())
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
        
        response = HttpResponse(generate_zip(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="qr_codes.zip"'
        return response
    
    return redirect('inventory:device_list')

@login_required
def qr_print_labels(request):
    """Generate printable QR code labels"""
    device_ids = request.GET.get('devices', '').split(',')
    devices = Device.objects.filter(device_id__in=device_ids) if device_ids[0] else Device.objects.none()
    
    if request.method == 'POST':
        selected_devices = request.POST.getlist('selected_devices')
        devices = Device.objects.filter(device_id__in=selected_devices)
        
        # Generate PDF with multiple QR codes
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="qr_labels.pdf"'
        
        # Create PDF
        p = canvas.Canvas(response, pagesize=A4)
        width, height = A4
        
        # Label dimensions (4 labels per row, 10 rows per page)
        label_width = width / 4
        label_height = height / 10
        
        x_positions = [i * label_width for i in range(4)]
        y_positions = [height - (i + 1) * label_height for i in range(10)]
        
        current_x = 0
        current_y = 0
        
        for device in devices:
            # Generate QR code as base64 for embedding
            qr_img = create_qr_code_image(device)
            img_buffer = BytesIO()
            qr_img.save(img_buffer, 'PNG')
            img_buffer.seek(0)
            
            # Position for this label
            x = x_positions[current_x] + 10
            y = y_positions[current_y] + 10
            
            # Draw QR code
            p.drawInlineImage(img_buffer, x, y + 30, width=label_width-20, height=label_height-60)
            
            # Add device info
            p.setFont("Helvetica", 8)
            p.drawString(x, y + 20, f"ID: {device.device_id}")
            p.drawString(x, y + 10, f"Tag: {device.asset_tag}")
            p.drawString(x, y, device.device_name[:20] + "..." if len(device.device_name) > 20 else device.device_name)
            
            # Move to next position
            current_x += 1
            if current_x >= 4:
                current_x = 0
                current_y += 1
                if current_y >= 10:
                    current_y = 0
                    p.showPage()  # New page
        
        p.save()
        return response
    
    context = {
        'devices': devices,
        'all_devices': Device.objects.filter(status__in=['AVAILABLE', 'ASSIGNED', 'IN_USE'])
    }
    
    return render(request, 'qr_management/print_labels.html', context)

def qr_verify(request, device_id):
    """Public QR code verification endpoint"""
    try:
        device = Device.objects.select_related(
            'device_type__subcategory__category'
        ).get(device_id=device_id)
        
        current_assignment = device.assignments.filter(is_active=True).first()
        
        # Create basic verification data (public info only)
        verification_data = {
            'valid': True,
            'device_id': device.device_id,
            'asset_tag': device.asset_tag,
            'device_name': device.device_name,
            'category': device.device_type.subcategory.category.name,
            'status': device.get_status_display(),
            'last_verified': timezone.now().isoformat(),
        }
        
        # Add assignment info if user is authenticated
        if request.user.is_authenticated:
            if current_assignment:
                verification_data.update({
                    'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment.assigned_to_staff else None,
                    'assigned_department': str(current_assignment.assigned_to_department) if current_assignment.assigned_to_department else None,
                    'assigned_location': str(current_assignment.assigned_to_location) if current_assignment.assigned_to_location else None,
                    'assignment_date': current_assignment.start_date.isoformat(),
                })
        
        # Log the scan if user is authenticated
        if request.user.is_authenticated:
            scan_location = None
            if 'location_id' in request.GET:
                try:
                    scan_location = Location.objects.get(id=request.GET['location_id'])
                except Location.DoesNotExist:
                    pass
            
            QRCodeScan.objects.create(
                device=device,
                scan_type='VERIFICATION',
                scanned_by=request.user,
                scan_location=scan_location,
                device_status_at_scan=device.status,
                device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                verification_success=True,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
    except Device.DoesNotExist:
        verification_data = {
            'valid': False,
            'error': 'Device not found',
            'device_id': device_id
        }
    
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse(verification_data)
    
    context = {
        'verification_data': verification_data,
        'device': device if verification_data['valid'] else None,
        'current_assignment': current_assignment if verification_data['valid'] else None,
    }
    
    return render(request, 'qr_management/verify.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def qr_scan_mobile(request):
    """Mobile QR code scanning endpoint"""
    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        scan_type = data.get('scan_type', 'VERIFICATION')
        location_id = data.get('location_id')
        gps_coordinates = data.get('gps_coordinates')
        notes = data.get('notes', '')
        
        if not device_id:
            return JsonResponse({'success': False, 'error': 'Device ID required'}, status=400)
        
        device = Device.objects.get(device_id=device_id)
        current_assignment = device.assignments.filter(is_active=True).first()
        
        # Determine scan location
        scan_location = None
        if location_id:
            try:
                scan_location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                pass
        
        # Check for discrepancies
        discrepancies = []
        
        # Location verification
        if scan_location and current_assignment and current_assignment.assigned_to_location:
            if scan_location != current_assignment.assigned_to_location:
                discrepancies.append(f"Device scanned at {scan_location} but assigned to {current_assignment.assigned_to_location}")
        
        # Status verification
        if scan_type == 'VERIFICATION' and device.status not in ['ASSIGNED', 'IN_USE']:
            discrepancies.append(f"Device status is {device.get_status_display()} - unexpected for verification scan")
        
        # Create scan record
        scan = QRCodeScan.objects.create(
            device=device,
            scan_type=scan_type,
            scanned_by=request.user,
            scan_location=scan_location,
            device_status_at_scan=device.status,
            device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
            assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
            verification_success=len(discrepancies) == 0,
            discrepancies_found='; '.join(discrepancies),
            actions_taken=notes,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            gps_coordinates=gps_coordinates
        )
        
        response_data = {
            'success': True,
            'device_info': {
                'device_id': device.device_id,
                'device_name': device.device_name,
                'status': device.get_status_display(),
                'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment and current_assignment.assigned_to_staff else None,
                'location': str(current_assignment.assigned_to_location) if current_assignment and current_assignment.assigned_to_location else None,
            },
            'scan_id': scan.id,
            'verification_success': scan.verification_success,
            'discrepancies': discrepancies,
            'timestamp': scan.timestamp.isoformat()
        }
        
        return JsonResponse(response_data)
        
    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Device not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def qr_scan_history(request):
    """View QR code scan history"""
    scans = QRCodeScan.objects.select_related(
        'device', 'scanned_by', 'scan_location'
    ).order_by('-timestamp')
    
    # Filters
    device_filter = request.GET.get('device')
    scan_type_filter = request.GET.get('scan_type')
    user_filter = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    verification_status = request.GET.get('verification_status')
    
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
    from django.core.paginator import Paginator
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
        'scan_types': QRCodeScan.SCAN_TYPES,
        'total_scans': total_scans,
        'successful_scans': successful_scans,
        'failed_scans': failed_scans,
        'today_scans': today_scans,
        'success_rate': (successful_scans / total_scans * 100) if total_scans > 0 else 0,
        'filters': {
            'device': device_filter,
            'scan_type': scan_type_filter,
            'user': user_filter,
            'date_from': date_from,
            'date_to': date_to,
            'verification_status': verification_status,
        }
    }
    
    return render(request, 'qr_management/scan_history.html', context)

@login_required
def qr_scan_detail(request, scan_id):
    """Detailed view of a QR code scan"""
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

@login_required
def qr_batch_verify(request):
    """Batch verification of multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        location_id = request.POST.get('location_id')
        
        if not device_ids:
            messages.error(request, 'No devices selected for verification.')
            return redirect('inventory:device_list')
        
        devices = Device.objects.filter(device_id__in=device_ids)
        scan_location = None
        
        if location_id:
            try:
                scan_location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                pass
        
        verification_results = []
        
        for device in devices:
            current_assignment = device.assignments.filter(is_active=True).first()
            discrepancies = []
            
            # Check if device should be at the scan location
            if scan_location and current_assignment and current_assignment.assigned_to_location:
                if scan_location != current_assignment.assigned_to_location:
                    discrepancies.append(f"Expected at {current_assignment.assigned_to_location}, found at {scan_location}")
            
            # Create scan record
            scan = QRCodeScan.objects.create(
                device=device,
                scan_type='AUDIT',
                scanned_by=request.user,
                scan_location=scan_location,
                device_status_at_scan=device.status,
                device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                verification_success=len(discrepancies) == 0,
                discrepancies_found='; '.join(discrepancies),
                actions_taken='Batch verification',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            verification_results.append({
                'device': device,
                'scan': scan,
                'discrepancies': discrepancies
            })
        
        context = {
            'verification_results': verification_results,
            'scan_location': scan_location,
        }
        
        return render(request, 'qr_management/batch_verify_results.html', context)
    
    # GET request - show form
    devices = Device.objects.filter(status__in=['ASSIGNED', 'IN_USE'])
    locations = Location.objects.filter(is_active=True)
    
    context = {
        'devices': devices,
        'locations': locations,
    }
    
    return render(request, 'qr_management/batch_verify.html', context)

@login_required
def qr_analytics(request):
    """QR code scanning analytics dashboard"""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Date range for analytics
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Scan statistics
    total_scans = QRCodeScan.objects.count()
    period_scans = QRCodeScan.objects.filter(timestamp__date__gte=start_date)
    
    # Scan types distribution
    scan_types_data = period_scans.values('scan_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Success rate by scan type
    success_rates = []
    for scan_type_choice in QRCodeScan.SCAN_TYPES:
        scan_type = scan_type_choice[0]
        total = period_scans.filter(scan_type=scan_type).count()
        successful = period_scans.filter(
            scan_type=scan_type, 
            verification_success=True
        ).count()
        
        if total > 0:
            success_rates.append({
                'scan_type': scan_type_choice[1],
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
        scan_count=Count('id')
    ).order_by('-scan_count')[:10]
    
    # Daily scan counts for chart
    daily_scans = []
    for i in range(30):
        date = end_date - timedelta(days=i)
        count = QRCodeScan.objects.filter(timestamp__date=date).count()
        daily_scans.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    daily_scans.reverse()
    
    context = {
        'total_scans': total_scans,
        'period_scans_count': period_scans.count(),
        'scan_types_data': scan_types_data,
        'success_rates': success_rates,
        'most_scanned': most_scanned,
        'user_activity': user_activity,
        'daily_scans': daily_scans,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'qr_management/analytics.html', context)
@login_required
def qr_index(request):
    """Main QR code management dashboard"""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Get recent statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # QR scan statistics
    total_scans = QRCodeScan.objects.count()
    recent_scans = QRCodeScan.objects.filter(timestamp__date__gte=week_ago).count()
    successful_scans = QRCodeScan.objects.filter(verification_success=True).count()
    failed_scans = QRCodeScan.objects.filter(verification_success=False).count()
    
    # Calculate success rate
    success_rate = (successful_scans / total_scans * 100) if total_scans > 0 else 0
    
    context = {
        'total_scans': total_scans,
        'recent_scans': recent_scans,
        'successful_scans': successful_scans,
        'failed_scans': failed_scans,
        'success_rate': round(success_rate, 2),
    }
    
    return render(request, 'qr_management/index.html', context)