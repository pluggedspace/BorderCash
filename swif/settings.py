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
SECRET_KEY = 'django-insecure-^g9!=@fy()kp51jpxu2e99d0n#7%_d4-5+28-*c_o!@0=5n!%n'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
APP_NAME = "Border Cash"

ALLOWED_HOSTS = ['api.border.cash', '136.244.105.63', '45.77.138.21', 'localhost', '127.0.0.1', 'api2.border.cash']

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
CSRF_TRUSTED_ORIGINS = ['https://api.border.com', 'http://api.border.cash','https://api2.border.cash', 'http://api2.border.cash']
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
     "https://border.cash",]

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
SERVER_JWT_KEY = '0fteaFpuDHH3J07b5BiYh8suLU_u1Sw67soOOjzgMIY'


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

FRONTEND_URL = 'https://border.cash'  
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
DEFAULT_FROM_EMAIL = 'mail@border.cash'
SUPPORT_EMAIL = 'mail@border.cash '

CHANGELLY_PUBLIC_KEY = os.getenv("CHANGELLY_PUBLIC_KEY")
CHANGELLY_API_PRIVATE_KEY = os.getenv("CHANGELLY_API_PRIVATE_KEY")
CHANGELLY_API_KEY = os.getenv("CHANGELLY_API_KEY")
CHANGELLY_API_URL = 'https://api.changelly.com/v2/'
CHANGELLY_FEE_PERCENTAGE = 0.25

CHANGELLY_FIAT_URL = 'https://fiat-api.changelly.com/v1'
CHANGELLY_FIAT_API_KEY = "454178e034b3c87a76511090819bfca36c96390304a4a9dcad11b00c36694822"
CHANGELLY_FIAT_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2Z0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktnd2dnU2tBZ0VBQW9JQkFRQ3dFOVpHY25lb1RXTU8KOHFkeDF6b0t1MlhFMkFmdjA2czFiVkE4V3VSVlg2Q1RnZFhpU3JydzV2cktlU2hibWMxRlQyZ1Y0U2hYemprbAo0QklFcndJeE51WWNkSGNLRFV0ODFsQkxqTHFvWm5MRCtGajJQa2dwMU43S0wvRXpVVHM4bzlHdnRPNDVwUFo4CmFQTCtyL1lzQ3VoY2pGTWZWYmZUTkMxUFV0UzRtd1ZFUzVJalJ3OU1rT2w4T0ZtSGc2VE1qRnVsUE5tNFlPYUgKbGFKT0FOTDk5QkFJMEl5cFFXUEsxQ0NGa1BnWExpeWFWeVZaekw0Tk52ZjZyNDVhZ0UzaHIza1VIQ090a3JKUgpMUDh2WnRxQUVuODk4VkpGZTFrbUJVSytnbFVWSVRYbjlXRFFON2VlcUx0MVY0eU9qa3g0T2ZQTXA3eldTSXhSCm5vd0hodTJUQWdNQkFBRUNnZ0VBRG5sQVRWL1R4SWdXb3ZWcnNlTnRHQ2NVWHF4d0VUK1hNaGZ2YkZsVkEwdzQKNFF5Si9pL1hhR2hoa3RXSHd1a3ZJdlNSTnBuZ3NrQmlRK0h2TStjR1BwdTlLYUgzTm1KN3VJek9EVHAwWTRCYwpZYmlKNk4vd3d2amJ3WEgvR1R2NFZjRS9sM3BxSDE5QjRGM1RlbFVRM3NqeUZjZ2hLR1pvUUcrOXVSTmRmTGtrCjY4NTJVNC9Pa0tBSXNLMGI1TnBFeUphK2I0N0lncU9KQ0VTVHVQeVBudlFwcGFySmovTjB5OXF1YStUb3U0bVUKeCs2ZTh0Y1B6Qk9YVkdxY01LZWhYRGJ6MmNpQnY4eVBHM2xFcU1BcHBiTjZ3a2NCczIxOUVTcWVTWVpXdWlpTwppc1JUZEJrRFM4eXpnTEFiKzV0NTY2aUdhMXlWQk0zeUdRMzNVWVREdFFLQmdRQzV4SDVscmZjRURHWXFOVjluCkpaQW9WTDRib2x1UWgzWTZHOGJEZDl4ZS9uSXFWSURCaUNXeG5NbEMzZkwyQ0ZTb1pTMnlRd3dlZkZtay81RysKaWJVSEtJZitTdHdkS1NJOWN3YWMvS1pDcG5uRG1uTGlLd0ZtemdUTTNTNEp2aDFxNVpUVkRLZk1uRytxNnNqSwo5ajAwVi91TVZvZmd2TFdUcExDbWRNR0FId0tCZ1FEeXBYMmFPcWFBVGUxbU5yRXhWVU5zdnRydHkyM2hLQ3U0CmdqRmhiV0xicWJwR2Z0cTdaNVI1R2VFSTZ4NjRBZzFDUmNaaUhERnFDeUc3NyttVTlQMUVWcm1Id1lMVVlIT2wKRTFyWS80cXhzUkpTMWc4TEdCbG95ZXhLVUNZTmprQnJZQU9xTmxWVW1aRkJoQ2NsVm5xeWJSQWZvY09PbzZOaQo2a1pteWk4VURRS0JnUUNKK3Q3L1d6WE1kZ0UwZkt3K0N2S0dZbHRLWDArdmpFNU9YdTlGcExPMGd6MzlId0w3CnZNcHlvRWdGT0tJTUNLZ0k1QTRMQ0MzcVB1YSszVzA5bno4czcvZ0M4MHVIQlZSL1cvNmZnREZsOUEwaE1vaisKWUg4TUF4NGhwRzlib1RCc2c5WUdZUDRKeG5CUy9VempJLzdWOER2UlF6eHR1djBMaXhvQ3FWcElkUUtCZ1FEWQpNajNVWW5laUVFejY2clk4aDRUWTZzQzBhYkpRa0hOTUpheUw2MlBPNXM2VEswb0crb1plMUlFZWFpZm51ZVJJCmJWVVNhNTVYcHUxNnY0dTI3Z2FQa2xvaXJIZStkT1gxYW1aaXZHVytaMUExUUljTTBuOHBUK2phV2NsZUFLWkQKUmJ4ZU42VVdDUEpVbHNRdVQzeHBhQ1dhbVk1ZGxFM3F2MlRWQjBhbExRS0JnSFptbGJaemxyTithamlHZDU1MAo1akp6SkdZOE5NN3ZBcE5zZGZTUmhUY3FqQUk3Q3RUcWwvbjhydEF5bnBZVG5qYjFzUDY5dzZZVHlkcThtT2xSCm5zd0paYTRoVU1rKzR6YU9UemVpemxnSTc0M096TDVUL0tQSGJESXRTdXU2SFkweFN0Vk9HTm9ZRWVIOEFlamIKWCtlVXkrcjBLcjJEMURreWlGUmFtMk9lCi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0K
-----END PRIVATE KEY-----"""

RELOADLY_CLIENT_ID = os.getenv("RELOADLY_CLIENT_ID") 
RELOADLY_CLIENT_SECRET = os.getenv("RELOADLY_CLIENT_SECRET") 
RELOADLY_AUTH_URL = "https://auth.reloadly.com/oauth/token"
RELOADLY_TOPUP_URL = "https://topups.reloadly.com/"

ALIEXPRESS_API_KEY = os.getenv("ALIEXPRESS_API_KEY") 

GROQ_API_KEY = os.getenv("GROQ_API_KEY")



TRANSAK_API_KEY = "98ddbeda-799f-4de5-bb06-dcd6d729306d"
TRANSAK_REDIRECT_URL = ''

STELLAR_PLATFORM_SECRET = os.getenv("STELLAR_PLATFORM_SECRET")
PLATFORM_CUSTODY_STELLAR_ACCOUNT = os.getenv("PLATFORM_CUSTODY_STELLAR_ACCOUNT")

USDC_ISSUER_PUBLIC_KEY = os.getenv("USDC_ISSUER_PUBLIC_KEY")


INVESTMENT_ACCOUNT_SECRET = "SCT6662WJWFLAXLOWPZT6WXKPCREH4L4VDNMK7SI6ZTRZDS625CHFVHX"


INVESTMENT_POOL_PUBLIC = "GC7IEVYV34GCHDFRLH7U7QWFKG6GJLP4AGILUY4PSHO2KC2EYJ7WAPTH"

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
    dsn="https://f634fed9af121dd7daee5a2dc3e1f7e4@o4508674534670336.ingest.de.sentry.io/4508674536702032",
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
