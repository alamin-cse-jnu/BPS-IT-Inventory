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
        "verificationUrl": f"{settings.QR_CODE_BASE_URL}/qr/verify/{device.device_id}/"
    }
    
    return json.dumps(qr_data)

def create_qr_code_image(device, format='PNG'):
    """Create QR code image for device"""
    qr_data = generate_qr_code_data(device)
    
    # QR code configuration
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
        img = qr.make_image(fill_color="black", back_color="white")
        return img

@login_required
def qr_index(request):
    """QR Management dashboard"""
    try:
        # Statistics
        total_devices = Device.objects.count()
        devices_with_qr = Device.objects.exclude(qr_code='').count()
        total_scans = QRCodeScan.objects.count()
        successful_scans = QRCodeScan.objects.filter(verification_success=True).count()
        
        # Recent scans
        recent_scans = QRCodeScan.objects.select_related(
            'device', 'scanned_by'
        ).order_by('-timestamp')[:10]
        
        # Most scanned devices
        most_scanned = QRCodeScan.objects.values(
            'device__device_id', 'device__device_name'
        ).annotate(
            scan_count=Count('id')
        ).order_by('-scan_count')[:5]
        
        # Scan success rate by day (last 7 days)
        daily_stats = []
        for i in range(7):
            day = timezone.now().date() - timezone.timedelta(days=i)
            day_scans = QRCodeScan.objects.filter(timestamp__date=day)
            successful = day_scans.filter(verification_success=True).count()
            total = day_scans.count()
            
            daily_stats.append({
                'date': day.strftime('%Y-%m-%d'),
                'total_scans': total,
                'successful_scans': successful,
                'success_rate': (successful / total * 100) if total > 0 else 0
            })
        
        daily_stats.reverse()
        
        context = {
            'stats': {
                'total_devices': total_devices,
                'devices_with_qr': devices_with_qr,
                'qr_coverage': (devices_with_qr / total_devices * 100) if total_devices > 0 else 0,
                'total_scans': total_scans,
                'successful_scans': successful_scans,
                'success_rate': (successful_scans / total_scans * 100) if total_scans > 0 else 0,
            },
            'recent_scans': recent_scans,
            'most_scanned': most_scanned,
            'daily_stats': daily_stats,
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
        
        # Generate QR code image
        qr_img = create_qr_code_image(device)
        
        # Convert to base64 for display
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Update device QR code field if it exists
        try:
            if hasattr(device, 'qr_code'):
                import uuid
                device.qr_code = str(uuid.uuid4())
                device.save()
        except:
            pass
        
        # Log QR generation
        try:
            from inventory.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='QR_GENERATE',
                model_name='Device',
                object_id=device.device_id,
                object_repr=str(device),
                changes={'qr_generated': True},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except:
            pass
        
        context = {
            'device': device,
            'qr_code_b64': qr_b64,
            'qr_data': generate_qr_code_data(device),
        }
        
        return render(request, 'qr_management/qr_generate.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating QR code: {str(e)}")
        return redirect('qr_management:index')

@login_required
def qr_bulk_generate(request):
    """Bulk generate QR codes for multiple devices"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        include_labels = request.POST.get('include_labels') == 'on'
        
        if not device_ids:
            messages.error(request, 'No devices selected for QR generation.')
            return redirect('qr_management:qr_bulk_generate')
        
        try:
            devices = Device.objects.filter(device_id__in=device_ids)
            generated_count = 0
            
            # Create temporary directory for QR codes
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, 'qr_codes.zip')
                
                with zipfile.ZipFile(zip_path, 'w') as zip_file:
                    for device in devices:
                        try:
                            # Generate QR code
                            qr_img = create_qr_code_image(device)
                            
                            # Save QR code image
                            img_buffer = BytesIO()
                            qr_img.save(img_buffer, format='PNG')
                            
                            # Add to zip
                            zip_file.writestr(
                                f'qr_{device.device_id}.png',
                                img_buffer.getvalue()
                            )
                            
                            # Generate label if requested
                            if include_labels:
                                label_img = create_qr_label(device, qr_img)
                                label_buffer = BytesIO()
                                label_img.save(label_buffer, format='PNG')
                                
                                zip_file.writestr(
                                    f'label_{device.device_id}.png',
                                    label_buffer.getvalue()
                                )
                            
                            generated_count += 1
                            
                            # Update device QR code
                            try:
                                if hasattr(device, 'qr_code'):
                                    import uuid
                                    device.qr_code = str(uuid.uuid4())
                                    device.save()
                            except:
                                pass
                            
                        except Exception as e:
                            messages.warning(request, f"Failed to generate QR for {device.device_id}: {str(e)}")
                            continue
                
                # Return zip file
                with open(zip_path, 'rb') as zip_file:
                    response = HttpResponse(zip_file.read(), content_type='application/zip')
                    response['Content-Disposition'] = f'attachment; filename="qr_codes_{generated_count}_devices.zip"'
                    
                    messages.success(request, f"Generated QR codes for {generated_count} devices.")
                    return response
            
        except Exception as e:
            messages.error(request, f"Error during bulk QR generation: {str(e)}")
    
    # GET request - show device selection form
    devices = Device.objects.select_related('device_type').order_by('device_id')
    
    # Search and filter
    search = request.GET.get('search')
    if search:
        devices = devices.filter(
            Q(device_id__icontains=search) |
            Q(device_name__icontains=search) |
            Q(asset_tag__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(devices, 50)
    page_number = request.GET.get('page')
    devices_page = paginator.get_page(page_number)
    
    context = {
        'devices': devices_page,
        'search': search,
    }
    
    return render(request, 'qr_management/qr_bulk_generate.html', context)

def create_qr_label(device, qr_img):
    """Create a printable label with QR code and device info"""
    try:
        # Label dimensions (in pixels, assuming 300 DPI)
        label_width = 600
        label_height = 200
        
        # Create label image
        label = Image.new('RGB', (label_width, label_height), 'white')
        draw = ImageDraw.Draw(label)
        
        # Resize QR code
        qr_size = 150
        qr_resized = qr_img.resize((qr_size, qr_size))
        
        # Paste QR code on label
        qr_x = 20
        qr_y = (label_height - qr_size) // 2
        label.paste(qr_resized, (qr_x, qr_y))
        
        # Add text
        try:
            # Try to use a better font
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_medium = ImageFont.truetype("arial.ttf", 18)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            # Fallback to default font
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Text positioning
        text_x = qr_x + qr_size + 20
        text_y = qr_y
        
        # Device ID
        draw.text((text_x, text_y), f"ID: {device.device_id}", fill='black', font=font_large)
        text_y += 35
        
        # Device name
        device_name = device.device_name
        if len(device_name) > 25:
            device_name = device_name[:25] + "..."
        draw.text((text_x, text_y), device_name, fill='black', font=font_medium)
        text_y += 30
        
        # Asset tag
        if device.asset_tag:
            draw.text((text_x, text_y), f"Asset: {device.asset_tag}", fill='black', font=font_small)
            text_y += 20
        
        # Category
        if device.device_type:
            category = device.device_type.subcategory.category.name
            draw.text((text_x, text_y), f"Type: {category}", fill='black', font=font_small)
            text_y += 20
        
        # Brand/Model
        if device.brand:
            brand_model = f"{device.brand}"
            if device.model:
                brand_model += f" {device.model}"
            if len(brand_model) > 30:
                brand_model = brand_model[:30] + "..."
            draw.text((text_x, text_y), brand_model, fill='black', font=font_small)
        
        # Add border
        draw.rectangle([(0, 0), (label_width-1, label_height-1)], outline='black', width=2)
        
        return label
        
    except Exception as e:
        # Return simple label with just QR code if fancy label fails
        simple_label = Image.new('RGB', (300, 300), 'white')
        qr_resized = qr_img.resize((280, 280))
        simple_label.paste(qr_resized, (10, 10))
        return simple_label

@login_required
def qr_print_labels(request):
    """Generate printable QR labels"""
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        label_size = request.POST.get('label_size', 'standard')
        
        if not device_ids:
            messages.error(request, 'No devices selected for label printing.')
            return redirect('qr_management:qr_print_labels')
        
        try:
            devices = Device.objects.filter(device_id__in=device_ids)
            
            # Create PDF with labels
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image as RLImage
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="qr_labels.pdf"'
                
                doc = SimpleDocTemplate(response, pagesize=A4)
                elements = []
                
                # Create table for labels (2 columns)
                table_data = []
                row = []
                
                for i, device in enumerate(devices):
                    # Generate QR and label
                    qr_img = create_qr_code_image(device)
                    label_img = create_qr_label(device, qr_img)
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        label_img.save(tmp.name, format='PNG')
                        
                        # Add to table
                        rl_img = RLImage(tmp.name, width=3*inch, height=1*inch)
                        row.append(rl_img)
                        
                        # Clean up temp file
                        os.unlink(tmp.name)
                    
                    # Add row every 2 labels
                    if len(row) == 2:
                        table_data.append(row)
                        row = []
                
                # Add remaining label if odd number
                if row:
                    row.append('')  # Empty cell
                    table_data.append(row)
                
                # Create table
                if table_data:
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    
                    elements.append(table)
                
                doc.build(elements)
                return response
                
            except ImportError:
                # Fallback: create zip of individual label images
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = os.path.join(temp_dir, 'labels.zip')
                    
                    with zipfile.ZipFile(zip_path, 'w') as zip_file:
                        for device in devices:
                            qr_img = create_qr_code_image(device)
                            label_img = create_qr_label(device, qr_img)
                            
                            label_buffer = BytesIO()
                            label_img.save(label_buffer, format='PNG')
                            
                            zip_file.writestr(
                                f'label_{device.device_id}.png',
                                label_buffer.getvalue()
                            )
                    
                    with open(zip_path, 'rb') as zip_file:
                        response = HttpResponse(zip_file.read(), content_type='application/zip')
                        response['Content-Disposition'] = 'attachment; filename="qr_labels.zip"'
                        return response
            
        except Exception as e:
            messages.error(request, f"Error generating labels: {str(e)}")
    
    # GET request - show form
    devices = Device.objects.select_related('device_type').order_by('device_id')
    
    context = {
        'devices': devices,
        'label_sizes': [
            ('standard', 'Standard (2x1 inch)'),
            ('large', 'Large (3x2 inch)'),
            ('small', 'Small (1.5x0.75 inch)'),
        ]
    }
    
    return render(request, 'qr_management/qr_print_labels.html', context)

@login_required
def qr_verify(request, device_id):
    """Verify QR code and display device information"""
    try:
        device = get_object_or_404(Device, device_id=device_id)
        
        # Get current assignment
        current_assignment = Assignment.objects.filter(
            device=device, is_active=True
        ).select_related('assigned_to_staff', 'assigned_to_department', 'assigned_to_location').first()
        
        # Get scan location if provided
        scan_location = None
        location_id = request.GET.get('location_id')
        if location_id:
            try:
                scan_location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                pass
        
        # Verification data
        verification_data = {
            'valid': True,
            'device_id': device.device_id,
            'device_name': device.device_name,
            'asset_tag': device.asset_tag,
            'status': device.status,
            'condition': device.condition,
            'brand': device.brand,
            'model': device.model,
            'category': device.device_type.subcategory.category.name if device.device_type else None,
            'current_assignment': None,
            'discrepancies': []
        }
        
        # Add assignment info
        if current_assignment:
            verification_data['current_assignment'] = {
                'assignment_id': current_assignment.assignment_id,
                'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment.assigned_to_staff else None,
                'assigned_department': str(current_assignment.assigned_to_department) if current_assignment.assigned_to_department else None,
                'assigned_location': str(current_assignment.assigned_to_location) if current_assignment.assigned_to_location else None,
                'assignment_date': current_assignment.start_date.isoformat() if current_assignment.start_date else None,
                'is_temporary': current_assignment.is_temporary,
                'expected_return': current_assignment.expected_return_date.isoformat() if current_assignment.expected_return_date else None,
            }
            
            # Check for discrepancies
            if scan_location and current_assignment.assigned_to_location != scan_location:
                verification_data['discrepancies'].append(
                    f"Location mismatch: Expected {current_assignment.assigned_to_location}, found at {scan_location}"
                )
        
        # Log the scan
        scan_record = QRCodeScan.objects.create(
            device=device,
            scan_type='VERIFICATION',
            scanned_by=request.user,
            scan_location=scan_location,
            device_status_at_scan=device.status,
            device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
            assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
            verification_success=True,
            discrepancies_found='; '.join(verification_data['discrepancies']),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        # AJAX response
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(verification_data)
        
        context = {
            'verification_data': verification_data,
            'device': device,
            'current_assignment': current_assignment,
            'scan_location': scan_location,
            'scan_record': scan_record,
        }
        
        return render(request, 'qr_management/verify.html', context)
        
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
        }
        
        return render(request, 'qr_management/verify.html', context)
    
    except Exception as e:
        verification_data = {
            'valid': False,
            'error': str(e),
            'device_id': device_id
        }
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(verification_data)
        
        context = {
            'verification_data': verification_data,
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
        location_data = data.get('location', {})
        
        if not device_id:
            return JsonResponse({'error': 'Device ID is required'}, status=400)
        
        device = get_object_or_404(Device, device_id=device_id)
        
        # Get or create scan location
        scan_location = None
        if location_data.get('location_id'):
            try:
                scan_location = Location.objects.get(id=location_data['location_id'])
            except Location.DoesNotExist:
                pass
        
        # Get current assignment
        current_assignment = Assignment.objects.filter(
            device=device, is_active=True
        ).first()
        
        # Create scan record
        scan_record = QRCodeScan.objects.create(
            device=device,
            scan_type=scan_type,
            scanned_by=request.user,
            scan_location=scan_location,
            device_status_at_scan=device.status,
            device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
            assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
            verification_success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        response_data = {
            'success': True,
            'device': {
                'id': device.device_id,
                'name': device.device_name,
                'status': device.status,
                'condition': device.condition,
            },
            'scan_id': scan_record.id,
            'timestamp': scan_record.timestamp.isoformat(),
        }
        
        if current_assignment:
            response_data['assignment'] = {
                'assigned_to': str(current_assignment.assigned_to_staff) if current_assignment.assigned_to_staff else None,
                'department': str(current_assignment.assigned_to_department) if current_assignment.assigned_to_department else None,
                'location': str(current_assignment.assigned_to_location) if current_assignment.assigned_to_location else None,
            }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=400)

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
            # Get scan location
            scan_location = None
            if location_id:
                scan_location = get_object_or_404(Location, id=location_id)
            
            verification_results = []
            
            for device_id in device_ids:
                try:
                    device = Device.objects.get(device_id=device_id)
                    
                    # Get current assignment
                    current_assignment = Assignment.objects.filter(
                        device=device, is_active=True
                    ).first()
                    
                    # Check for discrepancies
                    discrepancies = []
                    if scan_location and current_assignment and current_assignment.assigned_to_location != scan_location:
                        discrepancies.append(
                            f"Location mismatch: Expected {current_assignment.assigned_to_location}, found at {scan_location}"
                        )
                    
                    # Create scan record
                    scan_record = QRCodeScan.objects.create(
                        device=device,
                        scan_type='BATCH_VERIFICATION',
                        scanned_by=request.user,
                        scan_location=scan_location,
                        device_status_at_scan=device.status,
                        device_location_at_scan=current_assignment.assigned_to_location if current_assignment else None,
                        assigned_staff_at_scan=current_assignment.assigned_to_staff if current_assignment else None,
                        verification_success=len(discrepancies) == 0,
                        discrepancies_found='; '.join(discrepancies),
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    verification_results.append({
                        'device': device,
                        'current_assignment': current_assignment,
                        'discrepancies': discrepancies,
                        'scan_record': scan_record,
                        'success': len(discrepancies) == 0,
                    })
                    
                except Device.DoesNotExist:
                    verification_results.append({
                        'device_id': device_id,
                        'error': 'Device not found',
                        'success': False,
                    })
                except Exception as e:
                    verification_results.append({
                        'device_id': device_id,
                        'error': str(e),
                        'success': False,
                    })
            
            # Calculate summary
            successful_verifications = sum(1 for result in verification_results if result.get('success', False))
            total_verifications = len(verification_results)
            
            messages.success(
                request, 
                f"Batch verification completed: {successful_verifications}/{total_verifications} successful"
            )
            
            context = {
                'verification_results': verification_results,
                'scan_location': scan_location,
                'summary': {
                    'total': total_verifications,
                    'successful': successful_verifications,
                    'failed': total_verifications - successful_verifications,
                    'success_rate': (successful_verifications / total_verifications * 100) if total_verifications > 0 else 0,
                }
            }
            
            return render(request, 'qr_management/batch_verify_results.html', context)
            
        except Exception as e:
            messages.error(request, f"Error during batch verification: {str(e)}")
    
    # GET request - show form
    devices = Device.objects.filter(status__in=['ASSIGNED', 'AVAILABLE']).order_by('device_id')
    locations = Location.objects.filter(is_active=True).order_by('name')
    
    # Search
    search = request.GET.get('search')
    if search:
        devices = devices.filter(
            Q(device_id__icontains=search) |
            Q(device_name__icontains=search) |
            Q(asset_tag__icontains=search)
        )
    
    context = {
        'devices': devices,
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
            scan_count=Count('id')
        ).order_by('-scan_count')[:10]
        
        # Daily scanning trends
        daily_trends = []
        for i in range(30):
            day = end_date - timezone.timedelta(days=i)
            day_scans = period_scans.filter(timestamp__date=day)
            
            daily_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'total_scans': day_scans.count(),
                'successful_scans': day_scans.filter(verification_success=True).count(),
                'failed_scans': day_scans.filter(verification_success=False).count(),
            })
        
        daily_trends.reverse()
        
        # Location-based analytics
        location_analytics = period_scans.filter(
            scan_location__isnull=False
        ).values(
            'scan_location__name'
        ).annotate(
            scan_count=Count('id'),
            success_count=Count('id', filter=Q(verification_success=True))
        ).order_by('-scan_count')[:10]
        
        # Device status at scan analytics
        status_analytics = period_scans.values(
            'device_status_at_scan'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Discrepancy analysis
        discrepancy_scans = period_scans.exclude(discrepancies_found='')
        common_discrepancies = []
        
        # Analyze common discrepancy patterns
        discrepancy_texts = discrepancy_scans.values_list('discrepancies_found', flat=True)
        discrepancy_patterns = {}
        
        for text in discrepancy_texts:
            if 'Location mismatch' in text:
                discrepancy_patterns['Location Mismatch'] = discrepancy_patterns.get('Location Mismatch', 0) + 1
            elif 'Status mismatch' in text:
                discrepancy_patterns['Status Mismatch'] = discrepancy_patterns.get('Status Mismatch', 0) + 1
            elif 'Assignment mismatch' in text:
                discrepancy_patterns['Assignment Mismatch'] = discrepancy_patterns.get('Assignment Mismatch', 0) + 1
            else:
                discrepancy_patterns['Other'] = discrepancy_patterns.get('Other', 0) + 1
        
        for pattern, count in sorted(discrepancy_patterns.items(), key=lambda x: x[1], reverse=True):
            common_discrepancies.append({
                'type': pattern,
                'count': count
            })
        
        # Peak scanning hours
        hourly_distribution = []
        for hour in range(24):
            hour_scans = period_scans.filter(timestamp__hour=hour).count()
            hourly_distribution.append({
                'hour': f"{hour:02d}:00",
                'count': hour_scans
            })
        
        # Device coverage analysis
        total_devices = Device.objects.count()
        scanned_devices = period_scans.values('device').distinct().count()
        coverage_percentage = (scanned_devices / total_devices * 100) if total_devices > 0 else 0
        
        context = {
            'period_start': start_date,
            'period_end': end_date,
            'stats': {
                'total_scans': total_scans,
                'period_scans': period_scans.count(),
                'success_rate': (period_scans.filter(verification_success=True).count() / period_scans.count() * 100) if period_scans.count() > 0 else 0,
                'unique_devices_scanned': scanned_devices,
                'coverage_percentage': round(coverage_percentage, 1),
                'avg_scans_per_day': round(period_scans.count() / 30, 1),
            },
            'scan_types_data': scan_types_data,
            'success_rates': success_rates,
            'most_scanned': most_scanned,
            'user_activity': user_activity,
            'daily_trends': daily_trends,
            'location_analytics': location_analytics,
            'status_analytics': status_analytics,
            'common_discrepancies': common_discrepancies,
            'hourly_distribution': hourly_distribution,
        }
        
        return render(request, 'qr_management/analytics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading QR analytics: {str(e)}")
        return render(request, 'qr_management/analytics.html', {})