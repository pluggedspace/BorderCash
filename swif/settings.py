import os
from datetime import timedelta
from pathlib import Path
import sentry_sdk
import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv
from storages.backends.dropbox import DropboxStorage
load_dotenv()
from celery.schedules import crontab
import dj_database_url 


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Load the Firebase credentials
FIREBASE_CRED = os.path.join(BASE_DIR, 'swif-wallet-firebase-adminsdk-fbsvc-8eeebe7f1f.json') # Update with actual path


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-replace-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
APP_NAME = "Border Cash"

ALLOWED_HOSTS = ['localhost', '127.0.0.1', ]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_yasg',
    'django_countries',
    'django_celery_beat',
    'django_celery_results',
    'channels',
    'import_export',
    'app',
    'kyc',
    'iban',
    'storages',
    'django.contrib.sites',
    'invest',
    'monica',
    'drac',
    'backup',

]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]

ROOT_URLCONF = 'swif.urls'
CSRF_TRUSTED_ORIGINS = ['localhost', '127.0.0.1']
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
     "http://localhost:3000",
     "http://127.0.0.1:3000"
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'swif.wsgi.application'

# WebSocket settings
CELERY_BROKER_URL = 'redis://:SwifLockRedis@redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://:SwifLockRedis@redis:6379/0'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("redis://:SwifLockRedis@redis:6379")],
        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',  # Authenticated users: 1000 requests/day
        'anon': '100/hour',   # Unauthenticated users: 100 requests/hour
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1440),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
SERVER_JWT_KEY = os.getenv('SERVER_JWT_KEY', 'dev-jwt-key-replace-in-production')


CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

#CELERY_TIMEZONE = 'Africa/Lagos'
#CELERY_ENABLE_UTC = False
CELERY_TRACK_STARTED = True
CELERY_TASK_RESULT_EXPIRES = 86400  # 1 day in seconds

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

#CELERY_BEAT_SCHEDULE = {
#    'reconcile_every_day': {
#        'task': 'app.tasks.auto_run_reconciliation',
#        'schedule': crontab(hour=0, minute=0),  # Runs every day at midnight
#    },
#    'check_stop_loss_and_take_profit': {
#        'task': 'invest.tasks.check_stop_loss_and_take_profit',
#        'schedule': crontab(minute='*/30'),  # Every 30 minutes
#    },
#    'update_tokenized_stock_prices': {
#        'task': 'invest.tasks.update_tokenized_stock_prices',
#        'schedule': crontab(minute='*/30'),  # Every 30 minutes
#    },
#    'update_exchange_rates': {
#        'task': 'app.tasks.update_exchange_rates',
#        'schedule': crontab(hour=0, minute=5),   # Runs at 12:05 AM daily
#    }
#}



# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# If you want to use HSTS (recommended for production)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        default='postgresql://BC:CashBorderless2025@db:5432/border',
        conn_max_age=600,
        ssl_require=not DEBUG  # Enable SSL in production
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

#TIME_ZONE = 'UTC'
USE_TZ = True
TIME_ZONE = 'Africa/Lagos' 

FRONTEND_URL = 'https://localhost:3000'  # Update this to your actual frontend URL in production  
USE_I18N = True

# Email Verification Settings
EMAIL_VERIFICATION_TIMEOUT_HOURS = 24


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# Define STATIC_ROOT to specify where static files will be collected

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Dropbox Authentication
DROPBOX_OAUTH2_TOKEN = os.getenv("DROPBOX_OAUTH2_TOKEN")
DROPBOX_ROOT_PATH = "/media/"

DEFAULT_FILE_STORAGE = 'storages.backends.dropbox.DropBoxStorage'

# Set Dropbox Storage Backend
class PrivateDropboxStorage(DropboxStorage):
    """ Custom storage backend for private Dropbox files """
    def url(self, name):
        return f"/protected/media/{name}"

# Media Settings
MEDIA_URL = f"https://www.dropbox.com/home{DROPBOX_ROOT_PATH}"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings (for password reset and email verification)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.zeptomail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'emailapikey'
EMAIL_HOST_PASSWORD = os.getenv("ZEPTO_API_KEY") 
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'mail@example.com')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'mail@example.com')

CHANGELLY_PUBLIC_KEY = os.getenv("CHANGELLY_PUBLIC_KEY")
CHANGELLY_API_PRIVATE_KEY = os.getenv("CHANGELLY_API_PRIVATE_KEY")
CHANGELLY_API_KEY = os.getenv("CHANGELLY_API_KEY")
CHANGELLY_API_URL = 'https://api.changelly.com/v2/'
CHANGELLY_FEE_PERCENTAGE = 0.25

CHANGELLY_FIAT_URL = 'https://fiat-api.changelly.com/v1'
CHANGELLY_FIAT_API_KEY = os.getenv("CHANGELLY_FIAT_API_KEY", "your-api-key")
CHANGELLY_FIAT_PRIVATE_KEY = os.getenv("CHANGELLY_FIAT_PRIVATE_KEY", "your-private-key")

RELOADLY_CLIENT_ID = os.getenv("RELOADLY_CLIENT_ID") 
RELOADLY_CLIENT_SECRET = os.getenv("RELOADLY_CLIENT_SECRET") 
RELOADLY_AUTH_URL = "https://auth.reloadly.com/oauth/token"
RELOADLY_TOPUP_URL = "https://topups.reloadly.com/"

ALIEXPRESS_API_KEY = os.getenv("ALIEXPRESS_API_KEY") 

GROQ_API_KEY = os.getenv("GROQ_API_KEY")



TRANSAK_API_KEY = os.getenv("TRANSAK_API_KEY", "your-api-key")
TRANSAK_REDIRECT_URL = ''

RAILSR_API_KEY = os.getenv("RAILSR_API_KEY", "your-railsr-api-key")
RAILSR_BASE_URL = os.getenv("RAILSR_BASE_URL", "https://api.railsr.com")

STELLAR_PLATFORM_SECRET = os.getenv("STELLAR_PLATFORM_SECRET")
PLATFORM_CUSTODY_STELLAR_ACCOUNT = os.getenv("PLATFORM_CUSTODY_STELLAR_ACCOUNT")

USDC_ISSUER_PUBLIC_KEY = os.getenv("USDC_ISSUER_PUBLIC_KEY")


INVESTMENT_ACCOUNT_SECRET = os.getenv("INVESTMENT_ACCOUNT_SECRET", "your-secret")


INVESTMENT_POOL_PUBLIC = os.getenv("INVESTMENT_POOL_PUBLIC", "your-public-key")

LINK_API_KEY = os.getenv("LINK_API_KEY")

# URL to redirect users after a successful transaction
SUCCESS_REDIRECT_URL = "https://yourdomain.com/payment/success/"

# URL to redirect users after a failed transaction
FAILURE_REDIRECT_URL = "https://yourdomain.com/payment/failure/"

# Set payment deadline duration (e.g., 1 hour from now)
PAYMENT_DEADLINE = timedelta(hours=1)

AUTH_USER_MODEL = 'app.User'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

sentry_sdk.init(
    dsn="sentry+https://dsn-example@sentry.io/12345",
    # Add data like request headers and IP for users,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
)




SOCIAL_MEDIA_CREDENTIALS = {
    "twitter_api_key": "your_twitter_api_key",
    "twitter_api_secret": "your_twitter_api_secret",
    "twitter_access_token": "your_access_token",
    "twitter_access_secret": "your_access_secret",
    "facebook_access_token": "your_facebook_access_token",
    "linkedin_access_token": "your_linkedin_access_token",
}
