// static/js/notifications.js

/* ========================================
   BPS IT Inventory Management System
   Notifications and Real-time Updates
======================================== */

const BPSNotifications = {
    config: {
        checkInterval: 30000, // 30 seconds
        maxNotifications: 10,
        soundEnabled: true,
        types: {
            'assignment_due': {
                icon: 'clock',
                color: 'warning',
                sound: 'notification.mp3'
            },
            'warranty_expiring': {
                icon: 'exclamation-triangle',
                color: 'warning',
                sound: 'alert.mp3'
            },
            'maintenance_due': {
                icon: 'tools',
                color: 'info',
                sound: 'notification.mp3'
            },
            'device_missing': {
                icon: 'exclamation-circle',
                color: 'danger',
                sound: 'error.mp3'
            },
            'new_assignment': {
                icon: 'user-plus',
                color: 'success',
                sound: 'success.mp3'
            },
            'system_update': {
                icon: 'info-circle',
                color: 'info',
                sound: 'notification.mp3'
            }
        }
    },
    
    notifications: [],
    lastCheck: null,
    isInitialized: false,
    
    init: function() {
        if (this.isInitialized) return;
        
        this.setupEventListeners();
        this.requestPermission();
        this.loadInitialNotifications();
        this.startPeriodicCheck();
        
        this.isInitialized = true;
        console.log('BPS Notifications initialized');
    },
    
    setupEventListeners: function() {
        // Mark notification as read when clicked
        $(document).on('click', '.notification-item', function() {
            const notificationId = $(this).data('notification-id');
            if (notificationId) {
                BPSNotifications.markAsRead(notificationId);
            }
        });
        
        // Clear all notifications
        $(document).on('click', '.clear-all-notifications', function(e) {
            e.preventDefault();
            BPSNotifications.clearAll();
        });
        
        // Toggle notification sound
        $(document).on('click', '.toggle-notification-sound', function(e) {
            e.preventDefault();
            BPSNotifications.toggleSound();
        });
        
        // Notification settings
        $(document).on('click', '.notification-settings', function(e) {
            e.preventDefault();
            BPSNotifications.showSettings();
        });
    },
    
    requestPermission: function() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(function(permission) {
                if (permission === 'granted') {
                    console.log('Browser notifications enabled');
                } else {
                    console.log('Browser notifications denied');
                }
            });
        }
    },
    
    loadInitialNotifications: function() {
        $.get('/api/notifications/')
            .done(function(data) {
                BPSNotifications.updateNotificationDisplay(data);
            })
            .fail(function() {
                console.warn('Failed to load initial notifications');
            });
    },
    
    startPeriodicCheck: function() {
        setInterval(function() {
            BPSNotifications.checkForUpdates();
        }, this.config.checkInterval);
    },
    
    checkForUpdates: function() {
        const params = {};
        if (this.lastCheck) {
            params.since = this.lastCheck;
        }
        
        $.get('/api/notifications/', params)
            .done(function(data) {
                if (data.new_notifications && data.new_notifications.length > 0) {
                    BPSNotifications.handleNewNotifications(data.new_notifications);
                }
                BPSNotifications.updateNotificationDisplay(data);
                BPSNotifications.lastCheck = new Date().toISOString();
            })
            .fail(function() {
                console.warn('Failed to check for notification updates');
            });
    },
    
    handleNewNotifications: function(newNotifications) {
        newNotifications.forEach(notification => {
            this.showNotification(notification);
            this.playSound(notification.type);
            this.showBrowserNotification(notification);
        });
    },
    
    showNotification: function(notification) {
        const config = this.config.types[notification.type] || this.config.types.system_update;
        
        const toast = $(`
            <div class="toast align-items-center text-white bg-${config.color} border-0" role="alert" data-notification-id="${notification.id}">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${config.icon} me-2"></i>
                        <strong>${notification.title}</strong><br>
                        ${notification.message}
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
        const bsToast = new bootstrap.Toast(toast[0], { delay: 8000 });
        bsToast.show();
        
        // Mark as read when toast is dismissed
        toast[0].addEventListener('hidden.bs.toast', function() {
            BPSNotifications.markAsRead(notification.id);
            toast.remove();
        });
    },
    
    showBrowserNotification: function(notification) {
        if ('Notification' in window && Notification.permission === 'granted') {
            const browserNotification = new Notification(notification.title, {
                body: notification.message,
                icon: '/static/img/bps-favicon.ico',
                tag: `bps-${notification.id}`,
                requireInteraction: notification.priority === 'high'
            });
            
            browserNotification.onclick = function() {
                window.focus();
                this.close();
                
                // Navigate to relevant page if URL is provided
                if (notification.url) {
                    window.location.href = notification.url;
                }
            };
            
            // Auto-close after 5 seconds for non-critical notifications
            if (notification.priority !== 'high') {
                setTimeout(function() {
                    browserNotification.close();
                }, 5000);
            }
        }
    },
    
    playSound: function(type) {
        if (!this.config.soundEnabled) return;
        
        const soundConfig = this.config.types[type];
        if (soundConfig && soundConfig.sound) {
            const audio = new Audio(`/static/sounds/${soundConfig.sound}`);
            audio.volume = 0.3;
            audio.play().catch(function() {
                console.log('Could not play notification sound');
            });
        }
    },
    
    updateNotificationDisplay: function(data) {
        // Update notification count
        const unreadCount = data.unread_count || 0;
        $('#notification-count').text(unreadCount);
        $('#notification-count').toggle(unreadCount > 0);
        
        // Update notification dropdown
        this.updateNotificationDropdown(data.notifications || []);
        
        // Update page title with unread count
        if (unreadCount > 0) {
            document.title = `(${unreadCount}) BPS IT Inventory`;
        } else {
            document.title = 'BPS IT Inventory Management System';
        }
    },
    
    updateNotificationDropdown: function(notifications) {
        const $container = $('#notification-list');
        
        if (notifications.length === 0) {
            $container.html(`
                <div class="text-center p-3 text-muted">
                    <i class="fas fa-bell-slash fa-2x mb-2"></i>
                    <div>No notifications</div>
                </div>
            `);
            return;
        }
        
        let html = '';
        notifications.slice(0, this.config.maxNotifications).forEach(notification => {
            const config = this.config.types[notification.type] || this.config.types.system_update;
            const readClass = notification.is_read ? 'opacity-75' : '';
            
            html += `
                <div class="notification-item p-3 border-bottom ${readClass}" 
                     data-notification-id="${notification.id}"
                     style="cursor: pointer;">
                    <div class="d-flex align-items-start">
                        <div class="notification-icon me-3">
                            <i class="fas fa-${config.icon} text-${config.color}"></i>
                        </div>
                        <div class="flex-grow-1">
                            <div class="fw-bold mb-1">${notification.title}</div>
                            <div class="text-muted small mb-1">${notification.message}</div>
                            <div class="text-muted small">
                                <i class="fas fa-clock me-1"></i>${notification.time_ago}
                            </div>
                        </div>
                        ${!notification.is_read ? '<div class="notification-badge bg-primary rounded-circle" style="width: 8px; height: 8px;"></div>' : ''}
                    </div>
                </div>
            `;
        });
        
        // Add "View All" link
        html += `
            <div class="p-2 text-center border-top">
                <a href="/notifications/" class="btn btn-sm btn-outline-primary">
                    <i class="fas fa-eye me-1"></i>View All Notifications
                </a>
                <button class="btn btn-sm btn-outline-secondary ms-2 clear-all-notifications">
                    <i class="fas fa-check-double me-1"></i>Mark All Read
                </button>
            </div>
        `;
        
        $container.html(html);
    },
    
    markAsRead: function(notificationId) {
        $.post('/api/notifications/mark-read/', {
            notification_id: notificationId
        })
        .done(function() {
            $(`.notification-item[data-notification-id="${notificationId}"]`).addClass('opacity-75');
            BPSNotifications.updateUnreadCount();
        })
        .fail(function() {
            console.warn('Failed to mark notification as read');
        });
    },
    
    clearAll: function() {
        $.post('/api/notifications/mark-all-read/')
            .done(function() {
                $('.notification-item').addClass('opacity-75');
                $('#notification-count').text('0').hide();
                BPS.toast.success('All notifications marked as read');
            })
            .fail(function() {
                BPS.toast.error('Failed to clear notifications');
            });
    },
    
    updateUnreadCount: function() {
        const unreadCount = $('.notification-item:not(.opacity-75)').length;
        $('#notification-count').text(unreadCount);
        $('#notification-count').toggle(unreadCount > 0);
    },
    
    toggleSound: function() {
        this.config.soundEnabled = !this.config.soundEnabled;
        localStorage.setItem('bps_notifications_sound', this.config.soundEnabled);
        
        const status = this.config.soundEnabled ? 'enabled' : 'disabled';
        BPS.toast.info(`Notification sounds ${status}`);
    },
    
    showSettings: function() {
        const modal = $(`
            <div class="modal fade" id="notificationSettingsModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Notification Settings</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" id="soundEnabled" ${this.config.soundEnabled ? 'checked' : ''}>
                                    <label class="form-check-label" for="soundEnabled">
                                        Enable notification sounds
                                    </label>
                                </div>
                            </div>
                            <div class="mb-3">
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" id="browserNotifications" ${Notification.permission === 'granted' ? 'checked' : ''}>
                                    <label class="form-check-label" for="browserNotifications">
                                        Enable browser notifications
                                    </label>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="checkInterval" class="form-label">Check interval (seconds)</label>
                                <select class="form-select" id="checkInterval">
                                    <option value="15000" ${this.config.checkInterval === 15000 ? 'selected' : ''}>15 seconds</option>
                                    <option value="30000" ${this.config.checkInterval === 30000 ? 'selected' : ''}>30 seconds</option>
                                    <option value="60000" ${this.config.checkInterval === 60000 ? 'selected' : ''}>1 minute</option>
                                    <option value="300000" ${this.config.checkInterval === 300000 ? 'selected' : ''}>5 minutes</option>
                                </select>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="saveNotificationSettings">Save Settings</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        modal.modal('show');
        
        // Handle settings save
        modal.on('click', '#saveNotificationSettings', function() {
            const soundEnabled = $('#soundEnabled').is(':checked');
            const browserNotifications = $('#browserNotifications').is(':checked');
            const checkInterval = parseInt($('#checkInterval').val());
            
            BPSNotifications.config.soundEnabled = soundEnabled;
            BPSNotifications.config.checkInterval = checkInterval;
            
            // Request browser notification permission if enabled
            if (browserNotifications && Notification.permission !== 'granted') {
                Notification.requestPermission();
            }
            
            // Save settings to localStorage
            localStorage.setItem('bps_notification_settings', JSON.stringify({
                soundEnabled: soundEnabled,
                checkInterval: checkInterval
            }));
            
            BPS.toast.success('Notification settings saved');
            modal.modal('hide');
        });
        
        // Clean up modal after hiding
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    },
    
    loadSettings: function() {
        const saved = localStorage.getItem('bps_notification_settings');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.config.soundEnabled = settings.soundEnabled !== false;
                this.config.checkInterval = settings.checkInterval || 30000;
            } catch (e) {
                console.warn('Failed to load notification settings');
            }
        }
    },
    
    // Priority notification for critical alerts
    showCriticalAlert: function(title, message, actions = []) {
        const modal = $(`
            <div class="modal fade" id="criticalAlertModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-danger">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title">
                                <i class="fas fa-exclamation-triangle me-2"></i>${title}
                            </h5>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-danger mb-0">
                                <i class="fas fa-exclamation-circle me-2"></i>
                                ${message}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Dismiss</button>
                            ${actions.map(action => `<button type="button" class="btn btn-${action.type}" onclick="${action.onclick}">${action.text}</button>`).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        modal.modal('show');
        
        // Play critical alert sound
        this.playSound('device_missing');
        
        // Auto-remove modal after hiding
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    },
    
    // Warranty expiration alerts
    checkWarrantyAlerts: function() {
        $.get('/api/warranty-alerts/')
            .done(function(data) {
                if (data.critical_alerts && data.critical_alerts.length > 0) {
                    data.critical_alerts.forEach(alert => {
                        BPSNotifications.showNotification({
                            id: `warranty_${alert.device_id}`,
                            type: 'warranty_expiring',
                            title: 'Warranty Expiring',
                            message: `${alert.device_name} warranty expires in ${alert.days_remaining} days`,
                            priority: 'high'
                        });
                    });
                }
            });
    },
    
    // Assignment due alerts
    checkAssignmentAlerts: function() {
        $.get('/api/assignment-alerts/')
            .done(function(data) {
                if (data.overdue && data.overdue.length > 0) {
                    data.overdue.forEach(assignment => {
                        BPSNotifications.showNotification({
                            id: `assignment_${assignment.id}`,
                            type: 'assignment_due',
                            title: 'Assignment Overdue',
                            message: `${assignment.device_name} return is overdue by ${assignment.days_overdue} days`,
                            priority: 'high',
                            url: `/inventory/assignments/${assignment.id}/`
                        });
                    });
                }
            });
    },
    
    // System maintenance notifications
    showMaintenanceNotice: function(message, scheduledTime) {
        const notice = $(`
            <div class="alert alert-warning alert-dismissible fade show maintenance-notice" role="alert">
                <i class="fas fa-tools me-2"></i>
                <strong>Scheduled Maintenance:</strong> ${message}
                <br><small>Scheduled for: ${scheduledTime}</small>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        $('.main-content').prepend(notice);
        
        // Auto-hide after 10 seconds
        setTimeout(function() {
            notice.fadeOut();
        }, 10000);
    },
    
    // Real-time status updates
    updateDeviceStatus: function(deviceId, newStatus) {
        $(`.device-status[data-device-id="${deviceId}"]`).each(function() {
            const $status = $(this);
            $status.removeClass().addClass(`device-status badge badge-${newStatus.toLowerCase()}`);
            $status.text(newStatus);
        });
        
        // Show notification for status change
        this.showNotification({
            id: `status_${deviceId}_${Date.now()}`,
            type: 'system_update',
            title: 'Device Status Updated',
            message: `Device ${deviceId} status changed to ${newStatus}`,
            priority: 'low'
        });
    },
    
    // Connection status monitoring
    monitorConnection: function() {
        let wasOffline = false;
        
        window.addEventListener('online', function() {
            if (wasOffline) {
                BPSNotifications.showNotification({
                    id: 'connection_restored',
                    type: 'system_update',
                    title: 'Connection Restored',
                    message: 'Internet connection has been restored',
                    priority: 'low'
                });
                wasOffline = false;
            }
        });
        
        window.addEventListener('offline', function() {
            wasOffline = true;
            BPSNotifications.showCriticalAlert(
                'Connection Lost',
                'Internet connection has been lost. Some features may not work properly.',
                [{
                    text: 'Retry',
                    type: 'primary',
                    onclick: 'window.location.reload()'
                }]
            );
        });
    }
};

// Initialize notifications when document is ready
$(document).ready(function() {
    // Load saved settings
    BPSNotifications.loadSettings();
    
    // Initialize notifications system
    BPSNotifications.init();
    
    // Start connection monitoring
    BPSNotifications.monitorConnection();
    
    // Check for warranty alerts every hour
    setInterval(function() {
        BPSNotifications.checkWarrantyAlerts();
    }, 3600000);
    
    // Check for assignment alerts every 30 minutes
    setInterval(function() {
        BPSNotifications.checkAssignmentAlerts();
    }, 1800000);
});

// Expose to global scope for external access
window.BPSNotifications = BPSNotifications;