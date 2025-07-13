# bps_inventory/settings.py
"""
Django settings for BPS IT Inventory Management System.
Enhanced with Phase 3 functionality and all necessary configurations.
"""

from pathlib import Path
import os
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-bps-inventory-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,*', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    'drf_spectacular',
    'django_extensions',
    
    # BPS Local apps
    'inventory',
    'authentication',
    'reports',
    'qr_management',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # Custom Authentication Middleware (moved after MessageMiddleware)
    'authentication.middleware.AuthenticationManagementMiddleware',
    'authentication.middleware.SessionSecurityMiddleware',
    'authentication.middleware.RoleBasedAccessMiddleware',
    'authentication.middleware.DeviceAccessControlMiddleware',
    
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Add debug toolbar middleware for development
if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        
        # Debug toolbar settings - FIXED
        import socket
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        # FIX: Properly handle string slicing and concatenation
        INTERNAL_IPS = [ip[:ip.rfind(".")] + ".1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]
        
        DEBUG_TOOLBAR_PANELS = [
            'debug_toolbar.panels.versions.VersionsPanel',
            'debug_toolbar.panels.timer.TimerPanel',
            'debug_toolbar.panels.settings.SettingsPanel',
            'debug_toolbar.panels.headers.HeadersPanel',
            'debug_toolbar.panels.request.RequestPanel',
            'debug_toolbar.panels.sql.SQLPanel',
            'debug_toolbar.panels.staticfiles.StaticFilesPanel',
            'debug_toolbar.panels.templates.TemplatesPanel',
            'debug_toolbar.panels.cache.CachePanel',
            'debug_toolbar.panels.signals.SignalsPanel',
            'debug_toolbar.panels.logging.LoggingPanel',
            'debug_toolbar.panels.redirects.RedirectsPanel',
            'debug_toolbar.panels.profiling.ProfilingPanel',
        ]
        
        DEBUG_TOOLBAR_CONFIG = {
            'DISABLE_PANELS': ['debug_toolbar.panels.redirects.RedirectsPanel'],
            'SHOW_TEMPLATE_CONTEXT': True,
        }
    except ImportError:
        pass

ROOT_URLCONF = 'bps_inventory.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                
                # BPS Custom Context Processors
                'bps_inventory.context_processors.bps_settings',
                'bps_inventory.context_processors.user_context',
                'bps_inventory.context_processors.navigation_context',
                'bps_inventory.context_processors.notification_context',
                'bps_inventory.context_processors.system_stats_context',
                
                # Legacy inventory context processors (for backward compatibility)
                'inventory.context_processors.bps_settings',
                'inventory.context_processors.notifications',
                'inventory.context_processors.quick_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'bps_inventory.wsgi.application'

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='bps_inventory'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3307'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'BPS IT Inventory API',
    'DESCRIPTION': 'API for Bangladesh Parliament Secretariat IT Inventory Management System',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'bps_inventory': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'inventory': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'authentication': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@parliament.gov.bd')

# BPS Specific Settings
BPS_SYSTEM_NAME = "BPS IT Inventory Management System"
BPS_VERSION = "1.0.0"
BPS_ORGANIZATION = "Bangladesh Parliament Secretariat"
BPS_CONTACT_EMAIL = config('BPS_CONTACT_EMAIL', default='it@parliament.gov.bd')
BPS_ADMIN_NAME = config('BPS_ADMIN_NAME', default='System Administrator')

# QR Code Settings
QR_CODE_BASE_URL = config('QR_CODE_BASE_URL', default='http://127.0.0.1:8000')
QR_CODE_SIZE = config('QR_CODE_SIZE', default=10, cast=int)
QR_CODE_BORDER = config('QR_CODE_BORDER', default=4, cast=int)
QR_CODE_ERROR_CORRECTION = 'L'  # L, M, Q, H

# Pagination Settings
PAGINATE_BY = 25
ITEMS_PER_PAGE_CHOICES = [10, 25, 50, 100]

# Report Generation Settings
REPORT_GENERATION_TIMEOUT = 300  # 5 minutes
MAX_REPORT_RECORDS = 10000  # Maximum records per report
REPORT_CACHE_TIMEOUT = 3600  # 1 hour

# Audit Settings
AUDIT_LOG_RETENTION_DAYS = 730  # 2 years
AUTO_LOGOUT_MINUTES = 60  # Auto logout after 60 minutes of inactivity

# Device Assignment Settings
MAX_DEVICES_PER_STAFF = config('MAX_DEVICES_PER_STAFF', default=5, cast=int)
ASSIGNMENT_NOTIFICATION_DAYS = config('ASSIGNMENT_NOTIFICATION_DAYS', default=7, cast=int)
WARRANTY_ALERT_DAYS = config('WARRANTY_ALERT_DAYS', default=30, cast=int)

# Backup Settings
DBBACKUP_STORAGE = 'django.core.files.storage.FileSystemStorage'
DBBACKUP_STORAGE_OPTIONS = {'location': BASE_DIR / 'backups'}

# Create backups directory if it doesn't exist
os.makedirs(BASE_DIR / 'backups', exist_ok=True)

# Custom Authentication Settings
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/inventory/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Message Framework Settings
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'alert-info',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
}

# Date and Number Formatting
DATE_FORMAT = 'Y-m-d'
DATETIME_FORMAT = 'Y-m-d H:i:s'
SHORT_DATE_FORMAT = 'd/m/Y'
TIME_FORMAT = 'H:i:s'

# Locale Settings
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','
DECIMAL_SEPARATOR = '.'