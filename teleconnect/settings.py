"""
Django settings for teleconnect project.
"""
import os
import ssl
from pathlib import Path
import re
import sys
from decouple import config, Csv
# import dj_database_url  # COMMENTED OUT - Not needed for SQLite

# =========================================================================
# SIMPLE BUILD FIX - JUST DISABLE AppConfig.ready()
# =========================================================================

if 'RENDER' in os.environ:
    print("🚨 RENDER BUILD MODE: Disabling AppConfig.ready() methods", file=sys.stderr)
    
    # ONLY disable AppConfig.ready() - nothing else
    import django.apps
    original_ready = django.apps.AppConfig.ready
    
    def patched_ready(self):
        print(f"⚠ Skipping ready() for {self.name} during build", file=sys.stderr)
        return
    
    django.apps.AppConfig.ready = patched_ready

print("🚨 DEBUG: Current build command should run migrate --run-syncdb", file=sys.stderr)

# =========================================================================
# DISABLE ALL WEBRTC/CHANNELS FEATURES
# =========================================================================
# Disable all non-essential features
os.environ['DISABLE_WEBRTC'] = '1'
os.environ['DISABLE_CHANNELS'] = '1'
os.environ['DISABLE_REDIS'] = '1'
os.environ['DISABLE_CELERY'] = '1'
os.environ['DISABLE_EMERGENCY_FIXES'] = '1'

# Remove problematic environment variables
for var in ['DATABASE_URL', 'REDIS_URL', 'CELERY_BROKER_URL']:
    os.environ.pop(var, None)

print("🚨 EMERGENCY MODE: All non-essential features disabled")

# Rest of your settings.py continues below...

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# =========================================================================
# SECURITY SETTINGS
# =========================================================================

SECRET_KEY = config('SECRET_KEY', default='django-insecure-bcok+%c17r==+dy!s&xx6cc75mp(^i@(_yz&#9xa1d+uiy#2d5')
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = ['dalmas.pythonanywhere.com', 'teleconnect-krga.onrender.com', 'localhost', '127.0.0.1']

# =========================================================================
# APPLICATION DEFINITION
# =========================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    # 'channels',  # COMMENTED OUT - Not needed without WebRTC
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    #'django_celery_results',
    #'django_celery_beat',
    
    # Local apps
    'quickconnect',
    'webrtc',  # COMMENTED OUT - Not needed without WebRTC
    'users',
    'communications',   # Combined calls + chat app
    'calls',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'teleconnect.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'teleconnect.wsgi.application'

# =========================================================================
# DATABASE CONFIGURATION - FORCE SQLITE
# =========================================================================

# Force SQLite regardless of environment variables
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Completely ignore any DATABASE_URL environment variable
import os
# Remove DATABASE_URL from environment to prevent Django from using it
os.environ.pop('DATABASE_URL', None)

print("✅ FORCED SQLITE DATABASE CONFIGURATION")
print(f"   Database file: {DATABASES['default']['NAME']}")

# =========================================================================
# REDIS CONFIGURATION - COMMENTED OUT AS NOT NEEDED FOR BASIC FUNCTIONALITY
# =========================================================================

# Redis is not needed for basic functionality without WebRTC
# Comment out all Redis configuration

"""
# REDIS_URL = os.environ.get('REDIS_URL')
# if not REDIS_URL:
#     raise ValueError("REDIS_URL environment variable is not set!")

# # Ensure it ends with /0 for database 0
# if not REDIS_URL.endswith('/0'):
#     REDIS_URL = REDIS_URL.rsplit('/', 1)[0] + '/0'

# print(f"🔴 Using Redis URL: {REDIS_URL}")

# # For backward compatibility, keep these variables but get them from the parsed URL
# import urllib.parse
# parsed_redis = urllib.parse.urlparse(REDIS_URL)
# REDIS_HOST = parsed_redis.hostname
# REDIS_PORT = parsed_redis.port
# REDIS_PASSWORD = parsed_redis.password

# # Use the same Redis URL for everything (Redis Cloud typically only allows DB 0)
# CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
"""

# =========================================================================
# ASGI & CHANNELS FOR WEBRTC - COMMENTED OUT
# =========================================================================

# ASGI_APPLICATION = 'teleconnect.asgi.application'  # COMMENTED OUT
# WEBSOCKET_URL = '/ws/'  # COMMENTED OUT

# Channel layers for WebRTC signaling - COMMENTED OUT
"""
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "prefix": "teleconnect_websocket",
            # capacity and expiry are optional tuning params
            "capacity": 1500,
            "expiry": 10,
            "group_expiry": 60,
            "channel_capacity": {
                "http.request": 200,
                "http.response!*": 10,
            },
        },
    }
}
"""

# =========================================================================
# WEBRTC SPECIFIC SETTINGS - COMMENTED OUT
# =========================================================================

# Metered TURN Server Configuration - COMMENTED OUT
"""
METERED_TURN_CONFIG = {
    'enabled': True,
    'username': config('TURN_USERNAME', default='9f3dd018a79d6c1b2d74019f'),
    'password': config('TURN_PASSWORD', default='E+hnBT4XZgOITsS/'),
    'quota_mb': 500,
    'plan': 'free_trial_500mb',
}

# WebRTC ICE Servers Configuration
# TURN envs (from your .env)
TURN_USERNAME = config('TURN_USERNAME', default=METERED_TURN_CONFIG['username'])
TURN_PASSWORD = config('TURN_PASSWORD', default=METERED_TURN_CONFIG['password'])
TURN_SERVER_URL = config('TURN_SERVER_URL', default='turn:global.relay.metered.ca:80')
TURN_SERVER_URL_TLS = config('TURN_SERVER_URL_TLS', default='turns:global.relay.metered.ca:443')

def _build_webrtc_ice():
    ice = [
        {"urls": "stun:stun.relay.metered.ca:80"},
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
        {"urls": "stun:stun2.l.google.com:19302"},
    ]
    # Add TURN if available
    if TURN_USERNAME and TURN_PASSWORD and TURN_SERVER_URL:
        ice.append({
            "urls": TURN_SERVER_URL,
            "username": TURN_USERNAME,
            "credential": TURN_PASSWORD
        })
    if TURN_USERNAME and TURN_PASSWORD and TURN_SERVER_URL_TLS:
        ice.append({
            "urls": TURN_SERVER_URL_TLS,
            "username": TURN_USERNAME,
            "credential": TURN_PASSWORD
        })
    return ice

WEBRTC_CONFIG = {
    'iceServers': _build_webrtc_ice(),
    'iceTransportPolicy': 'all',
    'bundlePolicy': 'max-bundle',
    'rtcpMuxPolicy': 'require',
}

# Call settings for mobile apps
CALL_SETTINGS = {
    'MAX_CALL_DURATION': 3600,  # 1 hour
    'RING_TIMEOUT': 45,  # Seconds
    'RECONNECT_TIMEOUT': 30,
    'MAX_RECONNECT_ATTEMPTS': 3,
    'ICE_GATHERING_TIMEOUT': 10,
}
"""

# =========================================================================
# CELERY CONFIGURATION WITH REDIS - COMMENTED OUT
# =========================================================================

# Celery is not needed without Redis/WebRTC
"""
CELERY_BROKER_URL = CELERY_BROKER_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Nairobi'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Redis connection options for Celery
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
    'health_check_interval': 10,
}

# WebRTC background tasks - COMMENTED OUT
CELERY_BEAT_SCHEDULE = {
    'cleanup-stale-calls': {
        'task': 'webrtc.tasks.cleanup_stale_calls',
        'schedule': 60.0,  # Every minute
    },
    'check-turn-server-status': {
        'task': 'webrtc.tasks.check_turn_server_status',
        'schedule': 300.0,  # Every 5 minutes
    },
}
"""

# =========================================================================
# REST FRAMEWORK FOR MOBILE API
# =========================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'webrtc': '60/minute',  # Higher limit for WebRTC operations
        'call': '30/minute',  # Call initiation rate limit
    }
}

# =========================================================================
# CORS SETTINGS FOR MOBILE APPS & WEB
# =========================================================================

CORS_ALLOW_ALL_ORIGINS = DEBUG

CORS_ALLOWED_ORIGINS = [
    # Web development
    "http://localhost:8081",
    "http://localhost:8082",
    "http://localhost:19006",
    "http://localhost:19000",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:8082",
    "http://127.0.0.1:19006",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    
    # Android emulator
    "http://10.0.2.2:8000",
    "http://10.0.2.2:8080",
    "http://10.0.2.2:19000",
    
    # Local network for mobile testing
    "http://10.106.110.181:8081",
    "http://10.106.110.181:8082",
    "http://192.168.100.38:8081",
    "http://192.168.100.38:8082",
    "http://192.168.0.122:8081",
    "http://192.168.0.122:8082",
    "http://192.168.0.192:8081",
    "http://192.168.0.192:8082",
    
    # Production
    "https://teleconnect-krga.onrender.com",
]

# Expo development servers and mobile testing
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://192\.168\.\d+\.\d+:\d+$",
    r"^http://10\.\d+\.\d+\.\d+:\d+$",
    r"^http://10\.0\.2\.\d+:\d+$",  # Android emulator
     r"^https://teleconnect-krga\.onrender\.com$",
]

CSRF_TRUSTED_ORIGINS = [
    "https://teleconnect-krga.onrender.com",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:19000",
    "http://10.0.2.2:8000",  # Android emulator
    "wss://teleconnect-krga.onrender.com",  # Add WebSocket origin
    # Include wss scheme for WebSocket origin checks (some deployments expect it)
    config('WS_TRUSTED_ORIGIN', default='wss://teleconnect-krga.onrender.com'),
]

CORS_ALLOW_METHODS = [
    'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-webrtc-token',
    'x-call-id',
    'x-session-id',
]

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken', 'X-WebRTC-Token']
CORS_PREFLIGHT_MAX_AGE = 86400

# =========================================================================
# M-PESA CONFIGURATION - KEEP INTACT
# =========================================================================

MPESA_CONFIG = {
    'environment': config('MPESA_ENVIRONMENT', default='sandbox'),
    'consumer_key': config('MPESA_CONSUMER_KEY', default='AUJGjjBscXAZUF6sENrFb58aWchWXsfG7XJ5DipNMWBPsqgj'),
    'consumer_secret': config('MPESA_CONSUMER_SECRET', default='va2IOGXwsD4BMpGe0iPQdO9h14Aoj53koEnhxA1P7RSO0WgIIz03Y2mxLHPQugbS'),
    'business_shortcode': config('MPESA_BUSINESS_SHORTCODE', default='174379'),
    'passkey': config('MPESA_PASSKEY', default='bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'),
    'callback_url': config('MPESA_CALLBACK_URL', default='https://teleconnect-krga.onrender.com/api/mpesa/callback/'),
}

# Simplified M-Pesa variables for backward compatibility
MPESA_ENVIRONMENT = MPESA_CONFIG['environment']
MPESA_CONSUMER_KEY = MPESA_CONFIG['consumer_key']
MPESA_CONSUMER_SECRET = MPESA_CONFIG['consumer_secret']
MPESA_BUSINESS_SHORTCODE = MPESA_CONFIG['business_shortcode']
MPESA_PASSKEY = MPESA_CONFIG['passkey']
MPESA_CALLBACK_URL = MPESA_CONFIG['callback_url']

# =========================================================================
# PASSWORD VALIDATION
# =========================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =========================================================================
# STATIC & MEDIA FILES
# =========================================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# WebRTC recordings directory - COMMENTED OUT
# RECORDINGS_DIR = os.path.join(MEDIA_ROOT, 'recordings')
# os.makedirs(RECORDINGS_DIR, exist_ok=True)

# =========================================================================
# INTERNATIONALIZATION
# =========================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =========================================================================
# SECURITY SETTINGS
# =========================================================================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_AGE = 86400  # 24 hours for mobile sessions
SESSION_SAVE_EVERY_REQUEST = True

# =========================================================================
# EMAIL CONFIGURATION
# =========================================================================

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='TeleConnect <noreply@teleconnect.com>')

# =========================================================================
# CACHE CONFIGURATION - COMMENTED OUT (NOT NEEDED WITHOUT REDIS)
# =========================================================================

# Using local memory cache instead of Redis for simplicity
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

CACHE_TTL = 60 * 15

# =========================================================================
# AGORA SETTINGS - COMMENTED OUT
# =========================================================================

# AGORA_SERVICE_URL = env('AGORA_SERVICE_URL', default='http://localhost:8001')  # teleconnect service
# AGORA_APP_ID = config('AGORA_APP_ID')  # COMMENTED OUT
# AGORA_APP_CERTIFICATE = config('AGORA_APP_CERTIFICATE')  # COMMENTED OUT

# WebSocket config - COMMENTED OUT
# ASGI_APPLICATION = 'teleconnect.asgi.application'
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             "hosts": [('localhost', 6379)],
#         },
#     },
# }

# =========================================================================
# LOGGING CONFIGURATION
# =========================================================================

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
        'webrtc': {
            'format': '{asctime} - {levelname} - {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # 'webrtc_file': {  # COMMENTED OUT
        #     'level': 'DEBUG',
        #     'class': 'logging.FileHandler',
        #     'filename': str(BASE_DIR / 'logs' / 'webrtc.log'),
        #     'formatter': 'webrtc',
        # },
        'calls_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'calls.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        # 'webrtc': {  # COMMENTED OUT
        #     'handlers': ['console', 'webrtc_file'],
        #     'level': 'DEBUG',
        #     'propagate': False,
        # },
        'quickconnect': {
            'handlers': ['console', 'calls_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # 'channels': {  # COMMENTED OUT
        #     'handlers': ['console'],
        #     'level': 'WARNING',
        #     'propagate': False,
        # },
        # 'celery': {  # COMMENTED OUT
        #     'handlers': ['console'],
        #     'level': 'INFO',
        #     'propagate': True,
        # },
    },
}

# Create logs directory
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# =========================================================================
# APP SPECIFIC SETTINGS
# =========================================================================

SESSION_PAYMENT_TIMEOUT = 1800
MAX_CONCURRENT_SESSIONS = 3
PAYMENT_RETRY_ATTEMPTS = 3
PAYMENT_RETRY_DELAY = 30
WEBHOOK_VERIFICATION_ENABLED = True

DEFAULT_USER_SETTINGS = {
    'preferred_payment_method': 'mpesa',
    'auto_renew_sessions': False,
    'payment_reminders': True,
}

# =========================================================================
# WEBRTC MOBILE APP SETTINGS - COMMENTED OUT
# =========================================================================

# API and WebSocket URLs for mobile apps - WebSocket part commented out
# WEBSOCKET_BASE_URL = config('WEBSOCKET_BASE_URL', default='wss://teleconnect-krga.onrender.com' if not DEBUG else 'ws://localhost:8000')
API_BASE_URL = config('API_BASE_URL', default='https://teleconnect-krga.onrender.com/api' if not DEBUG else 'http://localhost:8000/api')

# ZEGO Configuration - COMMENTED OUT
# ZEGO_APP_ID = 408880662  # Your ZEGO App ID
# ZEGO_SERVER_SECRET = "ab2b6cf242c1e4f9d1b5ca4654f76b96"  # Keep secure!

# =========================================================================
# PRINT CONFIGURATION SUMMARY
# =========================================================================

if DEBUG:
    print("\n" + "="*70)
    print("🎯 TELE CONNECT - BASIC APP (Without WebRTC)")
    print("="*70)
    
    # Database Status
    print("\n💾 DATABASE:")
    db_config = DATABASES['default']
    print(f"   Engine: {db_config.get('ENGINE', 'Unknown')}")
    print(f"   Name: {db_config.get('NAME', 'Unknown')}")
    print(f"   SQLite: ✅ Configured")
    
    # M-Pesa Status
    print("\n💰 M-PESA:")
    print(f"   Environment: {MPESA_ENVIRONMENT}")
    print(f"   Business Shortcode: {MPESA_BUSINESS_SHORTCODE}")
    print(f"   Callback URL: {MPESA_CALLBACK_URL}")
    
    # API Endpoints
    print("\n🌐 API ENDPOINTS:")
    print(f"   REST API: {API_BASE_URL}")
    # print(f"   WebSocket: {WEBSOCKET_BASE_URL}")  # COMMENTED OUT
    
    # Features Status
    print("\n⚙️  FEATURES:")
    print(f"   WebRTC Calls: ❌ Disabled")
    print(f"   Real-time Chat: ❌ Disabled (requires Redis)")
    print(f"   M-Pesa Payments: ✅ Enabled")
    print(f"   User Management: ✅ Enabled")
    print(f"   REST API: ✅ Enabled")
    
    # Mobile App Support
    print("\n📱 MOBILE APP SUPPORT:")
    print(f"   Android Emulator: ✅ Enabled")
    try:
        cors_len = len(CORS_ALLOWED_ORIGINS)
    except Exception:
        cors_len = 'Unknown'
    print(f"   CORS Origins: {cors_len} allowed")
    
    print("="*70 + "\n")
