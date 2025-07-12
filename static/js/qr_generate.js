// QR Code Generation JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const deviceSelect = document.getElementById('device');
    const searchDevice = document.getElementById('search-device');
    const deviceInfoCard = document.getElementById('device-info-card');
    const deviceInfoContent = document.getElementById('device-info-content');
    const includeLabelCheck = document.getElementById('include-label');
    const labelOptions = document.getElementById('label-options');
    const qrPreviewCard = document.getElementById('qr-preview-card');
    const qrPreviewContainer = document.getElementById('qr-preview-container');
    const qrActions = document.getElementById('qr-actions');
    const qrForm = document.getElementById('qr-generate-form');
    const qrSizeSelect = document.getElementById('qr-size');
    const qrFormatSelect = document.getElementById('qr-format');
    const errorCorrectionSelect = document.getElementById('error-correction');

    let currentQRData = null;
    let generatedQRCode = null;

    // Device selection and search functionality
    if (deviceSelect) {
        deviceSelect.addEventListener('change', handleDeviceSelection);
    }

    if (searchDevice) {
        searchDevice.addEventListener('input', handleDeviceSearch);
    }

    if (includeLabelCheck) {
        includeLabelCheck.addEventListener('change', toggleLabelOptions);
    }

    // QR options change handlers
    if (qrSizeSelect) {
        qrSizeSelect.addEventListener('change', updatePreview);
    }

    if (qrFormatSelect) {
        qrFormatSelect.addEventListener('change', updatePreview);
    }

    if (errorCorrectionSelect) {
        errorCorrectionSelect.addEventListener('change', updatePreview);
    }

    // Form submission
    if (qrForm) {
        qrForm.addEventListener('submit', handleQRGeneration);
    }

    // Device selection handler
    function handleDeviceSelection() {
        const selectedOption = deviceSelect.options[deviceSelect.selectedIndex];
        
        if (selectedOption.value) {
            const deviceName = selectedOption.getAttribute('data-device-name');
            const assetTag = selectedOption.getAttribute('data-asset-tag');
            const category = selectedOption.getAttribute('data-category');
            const deviceId = selectedOption.value;
            
            // Update device info display
            if (deviceInfoContent) {
                deviceInfoContent.innerHTML = `
                    <div class="device-info">
                        <p><strong>Device:</strong> ${deviceName}</p>
                        <p><strong>Asset Tag:</strong> ${assetTag}</p>
                        <p><strong>Category:</strong> ${category}</p>
                        <p><strong>Device ID:</strong> ${deviceId}</p>
                    </div>
                `;
                deviceInfoCard.style.display = 'block';
            }

            // Generate preview QR data
            generatePreviewQR(deviceId, deviceName, assetTag, category);
        } else {
            if (deviceInfoCard) {
                deviceInfoCard.style.display = 'none';
            }
            if (qrPreviewCard) {
                qrPreviewCard.style.display = 'none';
            }
        }
    }

    // Device search functionality
    function handleDeviceSearch() {
        const searchTerm = searchDevice.value.toLowerCase();
        const options = deviceSelect.options;
        
        for (let i = 1; i < options.length; i++) {
            const option = options[i];
            const deviceName = option.getAttribute('data-device-name').toLowerCase();
            const assetTag = option.getAttribute('data-asset-tag').toLowerCase();
            
            if (deviceName.includes(searchTerm) || assetTag.includes(searchTerm)) {
                option.style.display = 'block';
            } else {
                option.style.display = 'none';
            }
        }
    }

    // Toggle label options
    function toggleLabelOptions() {
        if (labelOptions) {
            labelOptions.style.display = includeLabelCheck.checked ? 'block' : 'none';
        }
        updatePreview();
    }

    // Generate preview QR code
    function generatePreviewQR(deviceId, deviceName, assetTag, category) {
        const qrData = {
            deviceId: deviceId,
            assetTag: assetTag,
            deviceName: deviceName,
            category: category,
            verifyUrl: `/verify/${deviceId}/`,
            lastUpdated: new Date().toISOString()
        };

        currentQRData = qrData;
        
        // Generate QR code using library (if available)
        if (typeof QRCode !== 'undefined') {
            try {
                const qrContainer = document.createElement('div');
                qrContainer.style.textAlign = 'center';
                
                new QRCode(qrContainer, {
                    text: JSON.stringify(qrData),
                    width: 200,
                    height: 200,
                    colorDark: '#000000',
                    colorLight: '#ffffff',
                    correctLevel: QRCode.CorrectLevel.M
                });

                if (qrPreviewContainer) {
                    qrPreviewContainer.innerHTML = '';
                    qrPreviewContainer.appendChild(qrContainer);
                    
                    if (includeLabelCheck && includeLabelCheck.checked) {
                        const label = document.createElement('div');
                        label.className = 'qr-label mt-2';
                        label.innerHTML = `<small><strong>${deviceName}</strong><br>${assetTag}</small>`;
                        qrPreviewContainer.appendChild(label);
                    }
                }

                if (qrPreviewCard) {
                    qrPreviewCard.style.display = 'block';
                }

                if (qrActions) {
                    qrActions.style.display = 'block';
                }
            } catch (error) {
                console.error('Error generating preview QR:', error);
            }
        } else {
            // Fallback: show placeholder
            if (qrPreviewContainer) {
                qrPreviewContainer.innerHTML = `
                    <div class="qr-placeholder">
                        <div class="placeholder-qr">
                            <i class="fas fa-qrcode fa-5x text-muted"></i>
                            <p class="mt-2 text-muted">QR Preview</p>
                        </div>
                    </div>
                `;
                qrPreviewCard.style.display = 'block';
            }
        }
    }

    // Update preview based on options
    function updatePreview() {
        if (currentQRData && deviceSelect.value) {
            const selectedDevice = deviceSelect.options[deviceSelect.selectedIndex];
            generatePreviewQR(
                selectedDevice.value,
                selectedDevice.getAttribute('data-device-name'),
                selectedDevice.getAttribute('data-asset-tag'),
                selectedDevice.getAttribute('data-category')
            );
        }
    }

    // Handle form submission
    function handleQRGeneration(e) {
        e.preventDefault();
        
        const formData = new FormData(qrForm);
        const submitBtn = qrForm.querySelector('button[type="submit"]');
        
        // Disable submit button and show loading
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
        
        // Make AJAX request
        fetch(qrForm.action || window.location.pathname, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Show success modal with generated QR code
                showGenerationModal(data);
                generatedQRCode = data;
            } else {
                showError('Error generating QR code: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('An error occurred while generating the QR code.');
        })
        .finally(() => {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-qrcode"></i> Generate QR Code';
        });
    }

    // Show generation success modal
    function showGenerationModal(data) {
        const modal = document.getElementById('qr-generation-modal');
        
        if (modal) {
            // Update modal content
            const qrDisplay = document.getElementById('generated-qr-display');
            const deviceName = document.getElementById('generated-device-name');
            const deviceInfo = document.getElementById('generated-device-info');
            
            if (qrDisplay && data.qr_code_html) {
                qrDisplay.innerHTML = data.qr_code_html;
            }
            
            if (deviceName && data.device_name) {
                deviceName.textContent = data.device_name;
            }
            
            if (deviceInfo && data.device_info) {
                deviceInfo.textContent = data.device_info;
            }
            
            // Setup modal action buttons
            setupModalActions(data);
            
            // Show modal
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
        }
    }

    // Setup modal action buttons
    function setupModalActions(data) {
        const downloadBtn = document.getElementById('modal-download-qr');
        const printBtn = document.getElementById('modal-print-qr');
        const generateAnotherBtn = document.getElementById('generate-another');
        
        if (downloadBtn) {
            downloadBtn.onclick = () => downloadQRCode(data);
        }
        
        if (printBtn) {
            printBtn.onclick = () => printQRCode(data);
        }
        
        if (generateAnotherBtn) {
            generateAnotherBtn.onclick = () => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('qr-generation-modal'));
                modal.hide();
                resetForm();
            };
        }
    }

    // Download QR code
    function downloadQRCode(data) {
        if (data.download_url) {
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.filename || 'qr_code.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else if (data.qr_code_base64) {
            const link = document.createElement('a');
            link.href = 'data:image/png;base64,' + data.qr_code_base64;
            link.download = data.filename || 'qr_code.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    // Print QR code
    function printQRCode(data) {
        const printWindow = window.open('', '_blank');
        
        if (printWindow) {
            printWindow.document.write(`
                <html>
                <head>
                    <title>Print QR Code - ${data.device_name}</title>
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            text-align: center; 
                            margin: 20px; 
                        }
                        .qr-container { 
                            display: inline-block; 
                            border: 1px solid #ddd; 
                            padding: 20px; 
                            margin: 10px; 
                        }
                        .device-info { 
                            margin-top: 10px; 
                            font-size: 12px; 
                        }
                        @media print {
                            body { margin: 0; }
                            .qr-container { 
                                page-break-inside: avoid; 
                                border: 1px solid #000;
                            }
                        }
                    </style>
                </head>
                <body>
                    <div class="qr-container">
                        ${data.qr_code_html}
                        <div class="device-info">
                            <strong>${data.device_name}</strong><br>
                            ${data.device_info}
                        </div>
                    </div>
                </body>
                </html>
            `);
            
            printWindow.document.close();
            printWindow.focus();
            
            setTimeout(() => {
                printWindow.print();
                printWindow.close();
            }, 250);
        }
    }

    // Reset form
    function resetForm() {
        if (qrForm) {
            qrForm.reset();
        }
        
        if (deviceInfoCard) {
            deviceInfoCard.style.display = 'none';
        }
        
        if (qrPreviewCard) {
            qrPreviewCard.style.display = 'none';
        }
        
        if (searchDevice) {
            searchDevice.value = '';
        }
        
        // Reset device options visibility
        const options = deviceSelect.options;
        for (let i = 1; i < options.length; i++) {
            options[i].style.display = 'block';
        }
        
        currentQRData = null;
        generatedQRCode = null;
    }

    // Show error message
    function showError(message) {
        // Try to show in an alert or toast
        if (typeof bootstrap !== 'undefined' && document.querySelector('.toast-container')) {
            showToast('Error', message, 'danger');
        } else {
            alert(message);
        }
    }

    // Show toast notification
    function showToast(title, message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container') || createToastContainer();
        
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${title}</strong><br>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toast = new bootstrap.Toast(toastContainer.lastElementChild);
        toast.show();
    }

    // Create toast container if it doesn't exist
    function createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }

    // Get CSRF token
    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }

    // Preview and action button handlers
    const previewDownloadBtn = document.getElementById('download-qr');
    const previewPrintBtn = document.getElementById('print-qr');
    
    if (previewDownloadBtn) {
        previewDownloadBtn.addEventListener('click', function() {
            if (generatedQRCode) {
                downloadQRCode(generatedQRCode);
            } else {
                showError('Please generate a QR code first');
            }
        });
    }
    
    if (previewPrintBtn) {
        previewPrintBtn.addEventListener('click', function() {
            if (generatedQRCode) {
                printQRCode(generatedQRCode);
            } else {
                showError('Please generate a QR code first');
            }
        });
    }

    // Initialize label options visibility
    if (includeLabelCheck && labelOptions) {
        labelOptions.style.display = includeLabelCheck.checked ? 'block' : 'none';
    }
});

// Utility functions for QR code manipulation
const QRUtils = {
    // Generate QR data object
    generateQRData: function(deviceId, deviceName, assetTag, category) {
        return {
            deviceId: deviceId,
            assetTag: assetTag,
            deviceName: deviceName,
            category: category,
            verifyUrl: `/verify/${deviceId}/`,
            lastUpdated: new Date().toISOString(),
            source: 'BPS-IT-Inventory'
        };
    },

    // Format QR data as JSON string
    formatQRDataAsJSON: function(qrData) {
        return JSON.stringify(qrData, null, 2);
    },

    // Parse QR data from string
    parseQRData: function(qrString) {
        try {
            return JSON.parse(qrString);
        } catch (e) {
            // If not JSON, treat as simple device ID
            return { deviceId: qrString };
        }
    },

    // Validate QR data structure
    validateQRData: function(qrData) {
        return qrData && 
               qrData.deviceId && 
               typeof qrData.deviceId === 'string' &&
               qrData.deviceId.length > 0;
    }
};

// Export utilities for use in other modules
window.QRUtils = QRUtils;