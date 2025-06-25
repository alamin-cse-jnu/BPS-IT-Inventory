/* static/js/main.js - BPS IT Inventory Management JavaScript */

// Global BPS object
window.BPS = {
    config: {
        ajaxTimeout: 30000,
        chartColors: {
            primary: '#0d6efd',
            success: '#198754',
            warning: '#ffc107',
            danger: '#dc3545',
            info: '#0dcaf0',
            secondary: '#6c757d'
        }
    },
    
    utils: {},
    forms: {},
    tables: {},
    charts: {},
    qr: {},
    notifications: {}
};

// ================================
// UTILITY FUNCTIONS
// ================================

BPS.utils = {
    // Get CSRF token from cookies
    getCookie: function(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },
    
    // Format currency
    formatCurrency: function(amount) {
        if (amount === null || amount === undefined) return 'N/A';
        return new Intl.NumberFormat('en-BD', {
            style: 'currency',
            currency: 'BDT',
            minimumFractionDigits: 2
        }).format(amount);
    },
    
    // Format date
    formatDate: function(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },
    
    // Show loading spinner
    showLoading: function() {
        $('#loading-spinner').removeClass('d-none');
    },
    
    // Hide loading spinner
    hideLoading: function() {
        $('#loading-spinner').addClass('d-none');
    },
    
    // Debounce function
    debounce: function(func, wait, immediate) {
        let timeout;
        return function executedFunction() {
            const context = this;
            const args = arguments;
            const later = function() {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    },
    
    // Copy to clipboard
    copyToClipboard: function(text) {
        navigator.clipboard.writeText(text).then(function() {
            BPS.notifications.success('Copied to clipboard');
        }).catch(function() {
            BPS.notifications.error('Failed to copy to clipboard');
        });
    }
};

// ================================
// FORM UTILITIES
// ================================

BPS.forms = {
    // Initialize form enhancements
    init: function() {
        this.setupValidation();
        this.setupDynamicSelects();
        this.setupFileUploads();
        this.setupDatePickers();
    },
    
    // Setup form validation
    setupValidation: function() {
        // Bootstrap validation
        const forms = document.querySelectorAll('.needs-validation');
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                    BPS.notifications.warning('Please fill in all required fields correctly.');
                }
                form.classList.add('was-validated');
            });
        });
        
        // Custom validation rules
        $('input[type="email"]').on('blur', function() {
            const email = $(this).val();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (email && !emailRegex.test(email)) {
                $(this).addClass('is-invalid');
                $(this).siblings('.invalid-feedback').text('Please enter a valid email address.');
            } else {
                $(this).removeClass('is-invalid');
            }
        });
        
        // Phone number validation
        $('input[data-validation="phone"]').on('blur', function() {
            const phone = $(this).val();
            const phoneRegex = /^[\+]?[0-9\-\(\)\s]+$/;
            if (phone && !phoneRegex.test(phone)) {
                $(this).addClass('is-invalid');
                $(this).siblings('.invalid-feedback').text('Please enter a valid phone number.');
            } else {
                $(this).removeClass('is-invalid');
            }
        });
    },
    
    // Setup dynamic select dropdowns
    setupDynamicSelects: function() {
        // Category -> Subcategory -> Device Type cascade
        $('#id_category').on('change', function() {
            const categoryId = $(this).val();
            const subcategorySelect = $('#id_subcategory');
            const deviceTypeSelect = $('#id_device_type');
            
            // Reset dependent selects
            subcategorySelect.html('<option value="">Select Subcategory</option>');
            deviceTypeSelect.html('<option value="">Select Device Type</option>');
            
            if (categoryId) {
                $.ajax({
                    url: '/inventory/ajax/subcategories/',
                    data: { category_id: categoryId },
                    success: function(data) {
                        data.subcategories.forEach(function(item) {
                            subcategorySelect.append(
                                $('<option></option>').val(item.id).text(item.name)
                            );
                        });
                    },
                    error: function() {
                        BPS.notifications.error('Failed to load subcategories');
                    }
                });
            }
        });
        
        $('#id_subcategory').on('change', function() {
            const subcategoryId = $(this).val();
            const deviceTypeSelect = $('#id_device_type');
            
            deviceTypeSelect.html('<option value="">Select Device Type</option>');
            
            if (subcategoryId) {
                $.ajax({
                    url: '/inventory/ajax/device-types/',
                    data: { subcategory_id: subcategoryId },
                    success: function(data) {
                        data.device_types.forEach(function(item) {
                            deviceTypeSelect.append(
                                $('<option></option>').val(item.id).text(item.name)
                            );
                        });
                    },
                    error: function() {
                        BPS.notifications.error('Failed to load device types');
                    }
                });
            }
        });
        
        // Building -> Room -> Location cascade
        $('#id_building').on('change', function() {
            const buildingId = $(this).val();
            const roomSelect = $('#id_room');
            const locationSelect = $('#id_location');
            
            roomSelect.html('<option value="">Select Room</option>');
            locationSelect.html('<option value="">Select Location</option>');
            
            if (buildingId) {
                $.ajax({
                    url: `/inventory/ajax/rooms-by-building/${buildingId}/`,
                    success: function(data) {
                        data.rooms.forEach(function(item) {
                            roomSelect.append(
                                $('<option></option>').val(item.id).text(item.name)
                            );
                        });
                    },
                    error: function() {
                        BPS.notifications.error('Failed to load rooms');
                    }
                });
            }
        });
        
        $('#id_room').on('change', function() {
            const roomId = $(this).val();
            const locationSelect = $('#id_location');
            
            locationSelect.html('<option value="">Select Location</option>');
            
            if (roomId) {
                $.ajax({
                    url: `/inventory/ajax/locations-by-room/${roomId}/`,
                    success: function(data) {
                        data.locations.forEach(function(item) {
                            locationSelect.append(
                                $('<option></option>').val(item.id).text(item.name)
                            );
                        });
                    },
                    error: function() {
                        BPS.notifications.error('Failed to load locations');
                    }
                });
            }
        });
        
        // Department -> Staff cascade
        $('#id_department').on('change', function() {
            const departmentId = $(this).val();
            const staffSelect = $('#id_assigned_to_staff');
            
            if (staffSelect.length) {
                staffSelect.html('<option value="">Select Staff Member</option>');
                
                if (departmentId) {
                    $.ajax({
                        url: `/inventory/ajax/staff-by-department/${departmentId}/`,
                        success: function(data) {
                            data.staff_members.forEach(function(item) {
                                staffSelect.append(
                                    $('<option></option>').val(item.id).text(`${item.name} (${item.employee_id})`)
                                );
                            });
                        },
                        error: function() {
                            BPS.notifications.error('Failed to load staff members');
                        }
                    });
                }
            }
        });
    },
    
    // Setup file upload enhancements
    setupFileUploads: function() {
        $('input[type="file"]').on('change', function() {
            const file = this.files[0];
            const label = $(this).siblings('label');
            
            if (file) {
                label.text(file.name);
                
                // Validate file size (5MB limit)
                if (file.size > 5 * 1024 * 1024) {
                    BPS.notifications.error('File size should not exceed 5MB');
                    $(this).val('');
                    label.text('Choose file...');
                }
            } else {
                label.text('Choose file...');
            }
        });
    },
    
    // Setup date picker enhancements
    setupDatePickers: function() {
        // Set max date for date inputs to today (for past dates)
        $('input[type="date"][data-max-today]').attr('max', new Date().toISOString().split('T')[0]);
        
        // Set min date for date inputs to today (for future dates)
        $('input[type="date"][data-min-today]').attr('min', new Date().toISOString().split('T')[0]);
    },
    
    // Submit form via AJAX
    submitAjax: function(form, successCallback, errorCallback) {
        const formData = new FormData(form);
        
        BPS.utils.showLoading();
        
        $.ajax({
            url: $(form).attr('action') || window.location.href,
            method: $(form).attr('method') || 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                BPS.utils.hideLoading();
                if (successCallback) successCallback(response);
            },
            error: function(xhr) {
                BPS.utils.hideLoading();
                if (errorCallback) {
                    errorCallback(xhr);
                } else {
                    BPS.notifications.error('An error occurred while submitting the form');
                }
            }
        });
    }
};

// ================================
// TABLE UTILITIES
// ================================

BPS.tables = {
    // Initialize table enhancements
    init: function() {
        this.setupSorting();
        this.setupFiltering();
        this.setupBulkActions();
        this.setupRowActions();
    },
    
    // Setup table sorting
    setupSorting: function() {
        $('.table-sortable th[data-sort]').on('click', function() {
            const column = $(this).data('sort');
            const currentOrder = $(this).data('order') || 'asc';
            const newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
            
            // Update URL with sort parameters
            const url = new URL(window.location);
            url.searchParams.set('sort', column);
            url.searchParams.set('order', newOrder);
            
            window.location.href = url.toString();
        });
    },
    
    // Setup table filtering
    setupFiltering: function() {
        // Real-time search
        $('#table-search').on('input', BPS.utils.debounce(function() {
            const query = $(this).val().toLowerCase();
            const rows = $('.table tbody tr');
            
            rows.each(function() {
                const text = $(this).text().toLowerCase();
                $(this).toggle(text.includes(query));
            });
        }, 300));
        
        // Column filters
        $('.column-filter').on('change', function() {
            const column = $(this).data('column');
            const value = $(this).val();
            const rows = $('.table tbody tr');
            
            if (value === '') {
                rows.show();
            } else {
                rows.each(function() {
                    const cellValue = $(this).find(`td[data-column="${column}"]`).text().trim();
                    $(this).toggle(cellValue === value);
                });
            }
        });
    },
    
    // Setup bulk actions
    setupBulkActions: function() {
        // Select all checkbox
        $('#select-all').on('change', function() {
            const checked = $(this).prop('checked');
            $('.row-select').prop('checked', checked);
            BPS.tables.updateBulkActions();
        });
        
        // Individual row checkboxes
        $('.row-select').on('change', function() {
            BPS.tables.updateBulkActions();
        });
        
        // Bulk action buttons
        $('.bulk-action').on('click', function() {
            const action = $(this).data('action');
            const selectedRows = $('.row-select:checked');
            
            if (selectedRows.length === 0) {
                BPS.notifications.warning('Please select at least one item');
                return;
            }
            
            const selectedIds = selectedRows.map(function() {
                return $(this).val();
            }).get();
            
            BPS.tables.performBulkAction(action, selectedIds);
        });
    },
    
    // Update bulk action button states
    updateBulkActions: function() {
        const selectedCount = $('.row-select:checked').length;
        const totalCount = $('.row-select').length;
        
        $('.bulk-actions').toggle(selectedCount > 0);
        $('.selected-count').text(selectedCount);
        
        // Update select all checkbox state
        if (selectedCount === 0) {
            $('#select-all').prop('indeterminate', false).prop('checked', false);
        } else if (selectedCount === totalCount) {
            $('#select-all').prop('indeterminate', false).prop('checked', true);
        } else {
            $('#select-all').prop('indeterminate', true).prop('checked', false);
        }
    },
    
    // Perform bulk action
    performBulkAction: function(action, selectedIds) {
        if (confirm(`Are you sure you want to ${action} ${selectedIds.length} items?`)) {
            BPS.utils.showLoading();
            
            $.ajax({
                url: `/inventory/bulk/${action}/`,
                method: 'POST',
                data: {
                    'ids': selectedIds,
                    'csrfmiddlewaretoken': BPS.utils.getCookie('csrftoken')
                },
                success: function(response) {
                    BPS.utils.hideLoading();
                    BPS.notifications.success(response.message || 'Bulk action completed successfully');
                    location.reload();
                },
                error: function() {
                    BPS.utils.hideLoading();
                    BPS.notifications.error('Failed to perform bulk action');
                }
            });
        }
    },
    
    // Setup row actions
    setupRowActions: function() {
        // Quick view
        $('.btn-quick-view').on('click', function() {
            const id = $(this).data('id');
            const type = $(this).data('type');
            BPS.tables.showQuickView(type, id);
        });
        
        // Quick edit
        $('.btn-quick-edit').on('click', function() {
            const id = $(this).data('id');
            const type = $(this).data('type');
            BPS.tables.showQuickEdit(type, id);
        });
    },
    
    // Show quick view modal
    showQuickView: function(type, id) {
        $.ajax({
            url: `/inventory/ajax/${type}-quick-info/${id}/`,
            success: function(data) {
                $('#quick-view-modal .modal-body').html(data.html);
                $('#quick-view-modal').modal('show');
            },
            error: function() {
                BPS.notifications.error('Failed to load quick view');
            }
        });
    },
    
    // Show quick edit modal
    showQuickEdit: function(type, id) {
        // Implementation depends on specific requirements
        BPS.notifications.info('Quick edit feature coming soon');
    }
};

// ================================
// NOTIFICATION SYSTEM
// ================================

BPS.notifications = {
    show: function(message, type = 'info', duration = 5000) {
        const alertClass = `alert-${type}`;
        const iconClass = this.getIconClass(type);
        
        const alert = $(`
            <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
                 style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
                <i class="${iconClass} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        $('body').append(alert);
        
        // Auto-hide after duration
        setTimeout(() => {
            alert.fadeOut(() => alert.remove());
        }, duration);
    },
    
    getIconClass: function(type) {
        const icons = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle',
            'danger': 'fas fa-exclamation-circle'
        };
        return icons[type] || icons['info'];
    },
    
    success: function(message, duration) {
        this.show(message, 'success', duration);
    },
    
    error: function(message, duration) {
        this.show(message, 'danger', duration);
    },
    
    warning: function(message, duration) {
        this.show(message, 'warning', duration);
    },
    
    info: function(message, duration) {
        this.show(message, 'info', duration);
    }
};

// ================================
// QR CODE FUNCTIONALITY
// ================================

BPS.qr = {
    scanner: null,
    
    // Initialize QR scanner
    init: function() {
        $('#start-scan').on('click', this.startScanning);
        $('#stop-scan').on('click', this.stopScanning);
    },
    
    startScanning: function() {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            .then(function(stream) {
                const video = document.getElementById('qr-video');
                video.srcObject = stream;
                video.play();
                
                $('#start-scan').hide();
                $('#stop-scan').show();
                
                BPS.qr.scanner = stream;
                BPS.qr.scanFrame();
            })
            .catch(function(err) {
                BPS.notifications.error('Camera access denied or not available');
                console.error('Camera error:', err);
            });
    },
    
    stopScanning: function() {
        if (BPS.qr.scanner) {
            const tracks = BPS.qr.scanner.getTracks();
            tracks.forEach(track => track.stop());
            BPS.qr.scanner = null;
        }
        
        $('#start-scan').show();
        $('#stop-scan').hide();
        $('#qr-result').hide();
    },
    
    scanFrame: function() {
        const video = document.getElementById('qr-video');
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
            
            // QR code detection would go here with jsQR library
            // For now, this is a placeholder
            
        }
        
        if (BPS.qr.scanner) {
            requestAnimationFrame(BPS.qr.scanFrame);
        }
    },
    
    handleQRResult: function(result) {
        $('#qr-result-text').text(result);
        $('#qr-result').show();
        
        // Process QR code result
        try {
            const data = JSON.parse(result);
            if (data.deviceId) {
                window.location.href = `/inventory/devices/${data.deviceId}/`;
            }
        } catch (e) {
            // If not JSON, treat as device ID
            window.location.href = `/verify/${result}/`;
        }
    }
};

// ================================
// INITIALIZATION
// ================================

// Document Ready Functions
$(document).ready(function() {
    console.log('BPS Inventory Management System initialized');
    
    // Initialize all components
    BPS.init();
});

// Main Initialization
BPS.init = function() {
    this.setupCSRF();
    this.setupAjaxDefaults();
    this.forms.init();
    this.tables.init();
    this.qr.init();
    this.setupTooltips();
    this.setupModals();
    this.setupKeyboardShortcuts();
};

// CSRF Setup for Django
BPS.setupCSRF = function() {
    const csrfToken = BPS.utils.getCookie('csrftoken');
    if (csrfToken) {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                }
            }
        });
    }
};

// AJAX Defaults
BPS.setupAjaxDefaults = function() {
    $.ajaxSetup({
        timeout: this.config.ajaxTimeout,
        cache: false,
        error: function(xhr, status, error) {
            console.error('AJAX Error:', error);
            
            if (xhr.status === 403) {
                BPS.notifications.error('Access denied. Please check your permissions.');
            } else if (xhr.status === 404) {
                BPS.notifications.error('The requested resource was not found.');
            } else if (xhr.status === 500) {
                BPS.notifications.error('Internal server error. Please try again later.');
            } else if (status === 'timeout') {
                BPS.notifications.error('Request timeout. Please check your connection.');
            } else if (xhr.status !== 0) { // Don't show error for cancelled requests
                BPS.notifications.error('An unexpected error occurred. Please try again.');
            }
        }
    });
};

// Setup tooltips
BPS.setupTooltips = function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
};

// Setup modals
BPS.setupModals = function() {
    // Auto-focus first input in modals
    $('.modal').on('shown.bs.modal', function() {
        $(this).find('input[type="text"], input[type="email"], textarea').first().focus();
    });
    
    // Clear forms when modal is closed
    $('.modal').on('hidden.bs.modal', function() {
        $(this).find('form')[0]?.reset();
        $(this).find('.is-invalid').removeClass('is-invalid');
        $(this).find('.was-validated').removeClass('was-validated');
    });
};

// Setup keyboard shortcuts
BPS.setupKeyboardShortcuts = function() {
    $(document).on('keydown', function(e) {
        // Ctrl+/ or Cmd+/ for global search
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            $('#global-search-input').focus();
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            $('.modal.show').modal('hide');
        }
    });
};