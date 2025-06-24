// static/js/main.js

/* ========================================
   BPS IT Inventory Management System
   Main JavaScript Functions
======================================== */

// Global Configuration
const BPS = {
    config: {
        ajaxTimeout: 30000,
        refreshInterval: 300000, // 5 minutes
        animationDuration: 300,
        debounceDelay: 500,
        maxFileSize: 10 * 1024 * 1024, // 10MB
        allowedFileTypes: ['.csv', '.xlsx', '.xls', '.pdf'],
        dateFormat: 'YYYY-MM-DD',
        timeFormat: 'HH:mm:ss'
    },
    
    // Utility functions
    utils: {
        formatCurrency: function(amount) {
            return new Intl.NumberFormat('en-BD', {
                style: 'currency',
                currency: 'BDT',
                minimumFractionDigits: 0
            }).format(amount);
        },
        
        formatDate: function(date, format = 'DD/MM/YYYY') {
            if (!date) return '';
            const d = new Date(date);
            const day = String(d.getDate()).padStart(2, '0');
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const year = d.getFullYear();
            
            switch(format) {
                case 'DD/MM/YYYY':
                    return `${day}/${month}/${year}`;
                case 'YYYY-MM-DD':
                    return `${year}-${month}-${day}`;
                case 'MM/DD/YYYY':
                    return `${month}/${day}/${year}`;
                default:
                    return d.toLocaleDateString('en-BD');
            }
        },
        
        showLoading: function(element) {
            const $el = $(element);
            $el.prop('disabled', true);
            const originalText = $el.text();
            $el.data('original-text', originalText);
            $el.html('<i class="fas fa-spinner fa-spin me-1"></i> Loading...');
        },
        
        hideLoading: function(element) {
            const $el = $(element);
            $el.prop('disabled', false);
            const originalText = $el.data('original-text');
            if (originalText) {
                $el.text(originalText);
            }
        },
        
        debounce: function(func, delay) {
            let timeoutId;
            return function (...args) {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => func.apply(this, args), delay);
            };
        },
        
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
        }
    },
    
    // Toast notifications
    toast: {
        show: function(message, type = 'info', duration = 5000) {
            const iconMap = {
                'success': 'fas fa-check-circle',
                'error': 'fas fa-exclamation-triangle',
                'warning': 'fas fa-exclamation-circle',
                'info': 'fas fa-info-circle'
            };
            
            const toast = $(`
                <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="${iconMap[type]} me-2"></i>${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `);
            
            // Create toast container if it doesn't exist
            if ($('#toast-container').length === 0) {
                $('body').append('<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 11000;"></div>');
            }
            
            $('#toast-container').append(toast);
            const bsToast = new bootstrap.Toast(toast[0], { delay: duration });
            bsToast.show();
            
            // Remove toast element after it's hidden
            toast[0].addEventListener('hidden.bs.toast', function() {
                toast.remove();
            });
        },
        
        success: function(message) {
            this.show(message, 'success');
        },
        
        error: function(message) {
            this.show(message, 'danger');
        },
        
        warning: function(message) {
            this.show(message, 'warning');
        },
        
        info: function(message) {
            this.show(message, 'info');
        }
    }
};

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
    this.setupFormValidation();
    this.setupTableFeatures();
    this.setupSearchFilters();
    this.setupModals();
    this.setupTooltips();
    this.setupDropdowns();
    this.setupFormControls();
    this.setupKeyboardShortcuts();
    this.startPeriodicTasks();
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
                BPS.toast.error('Access denied. Please check your permissions.');
            } else if (xhr.status === 404) {
                BPS.toast.error('The requested resource was not found.');
            } else if (xhr.status === 500) {
                BPS.toast.error('Internal server error. Please try again later.');
            } else if (status === 'timeout') {
                BPS.toast.error('Request timeout. Please check your connection.');
            } else {
                BPS.toast.error('An unexpected error occurred. Please try again.');
            }
        }
    });
};

// Form Validation
BPS.setupFormValidation = function() {
    // Bootstrap validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                BPS.toast.warning('Please fill in all required fields correctly.');
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
    $('input[type="tel"], input[name*="phone"]').on('blur', function() {
        const phone = $(this).val();
        const phoneRegex = /^(\+88)?01[3-9]\d{8}$/;
        if (phone && !phoneRegex.test(phone)) {
            $(this).addClass('is-invalid');
            $(this).siblings('.invalid-feedback').text('Please enter a valid phone number.');
        } else {
            $(this).removeClass('is-invalid');
        }
    });
};

// Table Features
BPS.setupTableFeatures = function() {
    // Sortable tables
    $('.sortable-table th[data-sort]').on('click', function() {
        const $th = $(this);
        const column = $th.data('sort');
        const $table = $th.closest('table');
        const $tbody = $table.find('tbody');
        const rows = $tbody.find('tr').toArray();
        
        const isAsc = $th.hasClass('sort-asc');
        
        // Remove existing sort classes
        $table.find('th').removeClass('sort-asc sort-desc');
        
        // Add new sort class
        $th.addClass(isAsc ? 'sort-desc' : 'sort-asc');
        
        // Sort rows
        rows.sort((a, b) => {
            const aVal = $(a).find(`td:nth-child(${$th.index() + 1})`).text().trim();
            const bVal = $(b).find(`td:nth-child(${$th.index() + 1})`).text().trim();
            
            if (isAsc) {
                return bVal.localeCompare(aVal, undefined, { numeric: true });
            } else {
                return aVal.localeCompare(bVal, undefined, { numeric: true });
            }
        });
        
        $tbody.empty().append(rows);
    });
    
    // Row selection
    $('.selectable-table').each(function() {
        const $table = $(this);
        const $checkAll = $table.find('thead input[type="checkbox"]');
        const $rowChecks = $table.find('tbody input[type="checkbox"]');
        
        $checkAll.on('change', function() {
            $rowChecks.prop('checked', this.checked);
            $table.trigger('selection:changed');
        });
        
        $rowChecks.on('change', function() {
            const totalRows = $rowChecks.length;
            const checkedRows = $rowChecks.filter(':checked').length;
            
            $checkAll.prop('checked', checkedRows === totalRows);
            $checkAll.prop('indeterminate', checkedRows > 0 && checkedRows < totalRows);
            $table.trigger('selection:changed');
        });
    });
};

// Search and Filter Setup
BPS.setupSearchFilters = function() {
    // Live search
    const debouncedSearch = BPS.utils.debounce(function(query, target) {
        if (target) {
            $(target).trigger('search:query', [query]);
        }
    }, BPS.config.debounceDelay);
    
    $('[data-live-search]').on('input', function() {
        const query = $(this).val();
        const target = $(this).data('live-search');
        debouncedSearch(query, target);
    });
    
    // Advanced filters
    $('.filter-form').on('submit', function(e) {
        e.preventDefault();
        const $form = $(this);
        const formData = $form.serialize();
        const target = $form.data('target') || window.location.href;
        
        window.location.href = target + '?' + formData;
    });
    
    // Clear filters
    $('.clear-filters').on('click', function(e) {
        e.preventDefault();
        const $form = $(this).closest('form');
        $form[0].reset();
        $form.find('select').val('').trigger('change');
        $form.submit();
    });
};

// Modal Setup
BPS.setupModals = function() {
    // Auto-focus first input in modals
    $('.modal').on('shown.bs.modal', function() {
        $(this).find('input:visible:first').focus();
    });
    
    // Confirm delete modals
    $('[data-confirm-delete]').on('click', function(e) {
        e.preventDefault();
        const $btn = $(this);
        const message = $btn.data('confirm-delete') || 'Are you sure you want to delete this item?';
        const url = $btn.attr('href') || $btn.data('url');
        
        if (confirm(message)) {
            if ($btn.data('method') === 'delete') {
                // Send DELETE request
                $.ajax({
                    url: url,
                    method: 'DELETE',
                    success: function(response) {
                        BPS.toast.success(response.message || 'Item deleted successfully');
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    }
                });
            } else {
                window.location.href = url;
            }
        }
    });
    
    // Dynamic modal loading
    $('[data-modal-url]').on('click', function(e) {
        e.preventDefault();
        const url = $(this).data('modal-url');
        const target = $(this).data('modal-target') || '#dynamicModal';
        
        $.get(url)
            .done(function(data) {
                $(target).find('.modal-content').html(data);
                $(target).modal('show');
            })
            .fail(function() {
                BPS.toast.error('Failed to load modal content');
            });
    });
};

// Tooltips and Popovers
BPS.setupTooltips = function() {
    // Initialize Bootstrap tooltips
    $('[data-bs-toggle="tooltip"]').each(function() {
        new bootstrap.Tooltip(this);
    });
    
    // Initialize Bootstrap popovers
    $('[data-bs-toggle="popover"]').each(function() {
        new bootstrap.Popover(this);
    });
    
    // Dynamic tooltips for truncated text
    $('.text-truncate').each(function() {
        const $el = $(this);
        if (this.scrollWidth > this.clientWidth) {
            $el.attr('title', $el.text());
            new bootstrap.Tooltip(this);
        }
    });
};

// Dropdown Enhancements
BPS.setupDropdowns = function() {
    // Searchable dropdowns
    $('.dropdown-search').each(function() {
        const $dropdown = $(this);
        const $input = $dropdown.find('.dropdown-search-input');
        const $items = $dropdown.find('.dropdown-item');
        
        $input.on('input', function() {
            const query = $(this).val().toLowerCase();
            $items.each(function() {
                const text = $(this).text().toLowerCase();
                $(this).toggle(text.includes(query));
            });
        });
    });
    
    // Multi-select dropdowns
    $('.dropdown-multiselect').each(function() {
        const $dropdown = $(this);
        const $button = $dropdown.find('.dropdown-toggle');
        const $checkboxes = $dropdown.find('input[type="checkbox"]');
        
        $checkboxes.on('change', function() {
            const selected = $checkboxes.filter(':checked').length;
            const total = $checkboxes.length;
            
            if (selected === 0) {
                $button.text('Select items');
            } else if (selected === total) {
                $button.text('All selected');
            } else {
                $button.text(`${selected} selected`);
            }
        });
    });
};

// Form Controls
BPS.setupFormControls = function() {
    // Auto-resize textareas
    $('textarea[data-auto-resize]').each(function() {
        const $textarea = $(this);
        
        function resize() {
            $textarea.css('height', 'auto');
            $textarea.css('height', $textarea[0].scrollHeight + 'px');
        }
        
        $textarea.on('input', resize);
        resize(); // Initial resize
    });
    
    // Number input formatting
    $('input[data-format="currency"]').on('blur', function() {
        const value = parseFloat($(this).val());
        if (!isNaN(value)) {
            $(this).val(BPS.utils.formatCurrency(value));
        }
    });
    
    // Date picker setup
    $('input[type="date"]').each(function() {
        const $input = $(this);
        if (!$input.val() && $input.data('default') === 'today') {
            $input.val(new Date().toISOString().split('T')[0]);
        }
    });
    
    // File upload enhancements
    $('input[type="file"]').on('change', function() {
        const $input = $(this);
        const file = this.files[0];
        const $feedback = $input.siblings('.file-feedback');
        
        if (file) {
            // Check file size
            if (file.size > BPS.config.maxFileSize) {
                $input.addClass('is-invalid');
                $feedback.text('File size exceeds 10MB limit');
                return;
            }
            
            // Check file type
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            if (!BPS.config.allowedFileTypes.includes(extension)) {
                $input.addClass('is-invalid');
                $feedback.text('Invalid file type. Allowed: ' + BPS.config.allowedFileTypes.join(', '));
                return;
            }
            
            $input.removeClass('is-invalid');
            $feedback.text(`Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
        }
    });
    
    // Dependent dropdowns
    $('[data-depends-on]').each(function() {
        const $dependent = $(this);
        const parentSelector = $dependent.data('depends-on');
        const $parent = $(parentSelector);
        const url = $dependent.data('url');
        
        $parent.on('change', function() {
            const parentValue = $(this).val();
            
            if (!parentValue) {
                $dependent.empty().append('<option value="">Select...</option>');
                return;
            }
            
            BPS.utils.showLoading($dependent);
            
            $.get(url, { parent_id: parentValue })
                .done(function(data) {
                    $dependent.empty().append('<option value="">Select...</option>');
                    $.each(data, function(index, item) {
                        $dependent.append(`<option value="${item.id}">${item.name}</option>`);
                    });
                })
                .fail(function() {
                    BPS.toast.error('Failed to load dependent options');
                })
                .always(function() {
                    BPS.utils.hideLoading($dependent);
                });
        });
    });
};

// Keyboard Shortcuts
BPS.setupKeyboardShortcuts = function() {
    $(document).on('keydown', function(e) {
        // Ctrl+S to save forms
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const $form = $('form:visible').first();
            if ($form.length) {
                $form.submit();
                BPS.toast.info('Form submitted');
            }
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            $('.modal.show').modal('hide');
        }
        
        // Ctrl+F to focus search
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const $search = $('[data-live-search], input[type="search"]').first();
            if ($search.length) {
                $search.focus();
            }
        }
    });
};

// Periodic Tasks
BPS.startPeriodicTasks = function() {
    // Refresh notifications every 5 minutes
    setInterval(function() {
        BPS.refreshNotifications();
    }, BPS.config.refreshInterval);
    
    // Auto-save form drafts every 30 seconds
    setInterval(function() {
        BPS.autoSaveFormDrafts();
    }, 30000);
};

// Notification Functions
BPS.refreshNotifications = function() {
    $.get('/api/notifications/')
        .done(function(data) {
            $('#notification-count').text(data.unread_count);
            
            if (data.notifications && data.notifications.length > 0) {
                let html = '';
                data.notifications.forEach(function(notification) {
                    html += `
                        <div class="notification-item p-2 border-bottom">
                            <div class="d-flex align-items-start">
                                <i class="fas fa-${notification.icon} me-2 mt-1 text-${notification.type}"></i>
                                <div class="flex-grow-1">
                                    <div class="fw-bold">${notification.title}</div>
                                    <div class="text-muted small">${notification.message}</div>
                                    <div class="text-muted small">${notification.time_ago}</div>
                                </div>
                            </div>
                        </div>
                    `;
                });
                $('#notification-list').html(html);
            }
        })
        .fail(function() {
            console.warn('Failed to refresh notifications');
        });
};

// Auto-save Form Drafts
BPS.autoSaveFormDrafts = function() {
    $('form[data-auto-save]').each(function() {
        const $form = $(this);
        const formId = $form.data('auto-save');
        const formData = $form.serialize();
        
        // Only save if form has been modified
        if (formData !== $form.data('last-saved')) {
            localStorage.setItem(`form_draft_${formId}`, formData);
            $form.data('last-saved', formData);
        }
    });
};

// Load Form Drafts
BPS.loadFormDrafts = function() {
    $('form[data-auto-save]').each(function() {
        const $form = $(this);
        const formId = $form.data('auto-save');
        const savedData = localStorage.getItem(`form_draft_${formId}`);
        
        if (savedData) {
            const params = new URLSearchParams(savedData);
            params.forEach((value, key) => {
                const $field = $form.find(`[name="${key}"]`);
                if ($field.length) {
                    if ($field.is(':checkbox') || $field.is(':radio')) {
                        $field.filter(`[value="${value}"]`).prop('checked', true);
                    } else {
                        $field.val(value);
                    }
                }
            });
            
            BPS.toast.info('Form draft restored');
        }
    });
};

// Clear Form Drafts
BPS.clearFormDraft = function(formId) {
    localStorage.removeItem(`form_draft_${formId}`);
};

// Bulk Actions
BPS.setupBulkActions = function() {
    $('.bulk-action-btn').on('click', function(e) {
        e.preventDefault();
        const $btn = $(this);
        const action = $btn.data('action');
        const $table = $($btn.data('table'));
        const selectedIds = [];
        
        $table.find('tbody input[type="checkbox"]:checked').each(function() {
            selectedIds.push($(this).val());
        });
        
        if (selectedIds.length === 0) {
            BPS.toast.warning('Please select at least one item');
            return;
        }
        
        const message = $btn.data('confirm') || `Are you sure you want to ${action} ${selectedIds.length} item(s)?`;
        
        if (confirm(message)) {
            const url = $btn.data('url');
            
            $.post(url, {
                action: action,
                selected_ids: selectedIds
            })
            .done(function(response) {
                BPS.toast.success(response.message || 'Bulk action completed successfully');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            })
            .fail(function() {
                BPS.toast.error('Bulk action failed');
            });
        }
    });
};

// Export Functions
BPS.exportData = function(format, url, params = {}) {
    const exportUrl = new URL(url, window.location.origin);
    exportUrl.searchParams.append('export', format);
    
    Object.keys(params).forEach(key => {
        exportUrl.searchParams.append(key, params[key]);
    });
    
    BPS.toast.info(`Preparing ${format.toUpperCase()} export...`);
    
    // Create temporary link and click it
    const link = document.createElement('a');
    link.href = exportUrl.toString();
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

// QR Code Functions
BPS.qr = {
    generate: function(deviceId, format = 'png') {
        const url = `/qr/generate/${deviceId}/?format=${format}&download=1`;
        window.open(url, '_blank');
    },
    
    scan: function(onSuccess, onError) {
        if ('mediaDevices' in navigator && 'getUserMedia' in navigator.mediaDevices) {
            // QR scanning implementation would go here
            // This is a placeholder for future QR scanning functionality
            BPS.toast.info('QR scanning feature coming soon!');
        } else {
            BPS.toast.error('Camera not supported in this browser');
            if (onError) onError('Camera not supported');
        }
    },
    
    verify: function(deviceId) {
        const url = `/qr/verify/${deviceId}/`;
        window.open(url, '_blank');
    }
};

// Device Functions
BPS.device = {
    quickInfo: function(deviceId, callback) {
        $.get(`/inventory/ajax/device/${deviceId}/info/`)
            .done(function(data) {
                if (callback) callback(null, data);
            })
            .fail(function() {
                if (callback) callback('Failed to load device info');
            });
    },
    
    assign: function(deviceId) {
        window.location.href = `/inventory/assignments/create/${deviceId}/`;
    },
    
    return: function(assignmentId) {
        window.location.href = `/inventory/assignments/${assignmentId}/return/`;
    }
};

// Initialize when DOM is ready
$(document).ready(function() {
    // Load any saved form drafts
    BPS.loadFormDrafts();
    
    // Setup bulk actions
    BPS.setupBulkActions();
    
    // Auto-hide success messages
    setTimeout(function() {
        $('.alert-success').fadeOut();
    }, 5000);
    
    console.log('BPS Inventory System ready');
});