import os
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-^g9!=@fy()kp51jpxu2e99d0n#7%_d4-5+28-*c_o!@0=5n!%n'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*']

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
    'app',
    'kyc',
    'iban',
    'utils',
    'invest',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'swif.urls'

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

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1440),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = []

CORS_ALLOWED_ORIGIN_REGEXES = []

CORS_ALLOW_CREDENTIALS = True

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
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

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# Define STATIC_ROOT to specify where static files will be collected
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",  # If you have additional static directories
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings (for password reset and email verification)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.your-email-provider.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-email-password'

CHANGELLY_PUBLIC_KEY = "MIIBCgKCAQEAwIFJ8kyiMj+sqrQaQswPnXCxitZsXR4I7+TXA2xbs2X+mU1bL/m6XuecUTa5ROGarpcE+CashI3UGURWOSkAFnLmEzYiwhbqbKRfRZ4uzfg1oUDTMIQFra3rgy6JXjsdp57PCXgOJojvs6IJ2dvpDEkh32+dV3qiAObk0WNb4va7Y1wb+2AfFnn5r/YOH6DbxXjh7BcG+AdrJ0bxCCfkC1HG09uudqJEF9wkSLBAfOAhyn1X+FE+3Ev/ZdzQWiDAanfDiNlmjD3iAK0SBdTcGksC3mbmLC94zeIzUQqF4903G/TX41Qo+vsTipMeT5pQVM0dlVsBKVzN8BJQrqgvGwIDAQAB"
CHANGELLY_API_PRIVATE_KEY = "308204be020100300d06092a864886f70d0101010500048204a8308204a40201000282010100c08149f24ca2323facaab41a42cc0f9d70b18ad66c5d1e08efe4d7036c5bb365fe994d5b2ff9ba5ee79c5136b944e19aae9704f826ac848dd41944563929001672e6133622c216ea6ca45f459e2ecdf835a140d3308405adadeb832e895e3b1da79ecf09780e2688efb3a209d9dbe90c4921df6f9d577aa200e6e4d1635be2f6bb635c1bfb601f1679f9aff60e1fa0dbc578e1ec1706f8076b2746f10827e40b51c6d3dbae76a24417dc2448b0407ce021ca7d57f8513edc4bff65dcd05a20c06a77c388d9668c3de200ad1205d4dc1a4b02de66e62c2f78cde233510a85e3dd371bf4d7e35428fafb138a931e4f9a5054cd1d955b01295ccdf01250aea82f1b02030100010282010001a1ac386f9bd6164cbc00c0c439b8150cbd20eb8d6d1ed544c7acbc2c94d1f016951809bf08ae063ec79d61edaf62528e11cf274e5f457eff90317b13d20dea781ff02e6963729e0ce739f5436cf25947a314ca58fbeacc6741babc573c26e28e7504e385fd4b61342d19af79b036e58ac2778319e18196e7774664f85c46ac43c941b35af147c296cf22d054b72487a70567bc1860b16a6d6e6d847dd61224354693fc453e3ec775b729fb7f02efeca3efa8742df66aa93cf70f7e243e709750fb3dc001a237ea23ac2308b67671b7bab90b15cb469fa9fe0fadcd66d523570bf2244c7f707c823b1fb4ea0044073a121110486eed43b22c5b71f8d8710e5102818100e61d8ea13b9632cb2c1147e10cc8ca34e50d3c5290080db737cb627c18f8143b1d241283c6ad1d05c1d43855940c3eacbc6d50b10d0d96f9eb776252d61765b6e8c3747ed01b96192239fd3e588e230829668a0581bed59dbe399c9c7ba9aa640e38970a9485eb76fd97c0d043824e1e3d4e6e343d34f6e7c36c063b39ba95d302818100d628b21b7530953ee7b76b24f19aae719ebe0de3a0bfeb62664705ad9d5981d85c51e0581b7a082b9f067930c526daff12787e9cb09c1d9f42554f3cab48565e263dee993f85f5848c8a7f17c32c51575e8d9e4cf257d1b602577bbb47fe18ebbd2848f8cdb63f218751ad03662ec79e37079d1fd43ed36a01a09fd8536e4c990281806f72492d952a3d1761144d7795357998fc85d87d33fc728815a18ee50342c2a98e8775e0144cab0daabe193a792525058b8c75d409ba57305af5cacccb9b314bd09738c86209ba3c19f373ceca1caca2bb4a49f638cc2fb0e1fc0cf94c7af366d9ec565a6d6c1e89d66fb49628dbe6f1864781e012f49fcfc7397e1b18ee60b902818100d6262fa3e155c987f3b1a804734c57efe9eae67c9e7c0b66841bb503dcfa6a2aee76393e218bafabdf035c2076a4da0c826dd73ddc24e04226d4a3bd691196bbe2c5bf57a2fbd37cce0497fe2cfe9e001ddec352f26afa9b645012bc3dcb4b24402c8e7bad48f66c12a28bbd806a7ad62cf5021b97e39308c7c3d4d33eea66d102818100db6832a18366c32703e1a7df11360546905ac4f5620a21dc02969ca25a64b3a74f31c391addbfe4115df1950de3ac9cdd08a4ce05395fd71f375649e16c7d4c5e241b4e1ae21810b45729a716f1858a622fa0e384e8005b67c7dd98beb2da41ebdef6e69ce6856357fb94334b6d4a4935103f0e4d2e66dad6139baa7935f34e1"
CHANGELLY_API_KEY = "jwy+ksj7ZSAhOAqVjttdjxciOgAvKn8DRStZuzlK/FA="
CHANGELLY_API_URL = 'https://api.changelly.com/v2/'
CHANGELLY_FEE_PERCENTAGE = 0.25

CHANGELLY_FIAT_URL = 'https://fiat-api.changelly.com/v1'
CHANGELLY_FIAT_API_KEY = "454178e034b3c87a76511090819bfca36c96390304a4a9dcad11b00c36694822"
CHANGELLY_FIAT_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2Z0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktnd2dnU2tBZ0VBQW9JQkFRQ3dFOVpHY25lb1RXTU8KOHFkeDF6b0t1MlhFMkFmdjA2czFiVkE4V3VSVlg2Q1RnZFhpU3JydzV2cktlU2hibWMxRlQyZ1Y0U2hYemprbAo0QklFcndJeE51WWNkSGNLRFV0ODFsQkxqTHFvWm5MRCtGajJQa2dwMU43S0wvRXpVVHM4bzlHdnRPNDVwUFo4CmFQTCtyL1lzQ3VoY2pGTWZWYmZUTkMxUFV0UzRtd1ZFUzVJalJ3OU1rT2w4T0ZtSGc2VE1qRnVsUE5tNFlPYUgKbGFKT0FOTDk5QkFJMEl5cFFXUEsxQ0NGa1BnWExpeWFWeVZaekw0Tk52ZjZyNDVhZ0UzaHIza1VIQ090a3JKUgpMUDh2WnRxQUVuODk4VkpGZTFrbUJVSytnbFVWSVRYbjlXRFFON2VlcUx0MVY0eU9qa3g0T2ZQTXA3eldTSXhSCm5vd0hodTJUQWdNQkFBRUNnZ0VBRG5sQVRWL1R4SWdXb3ZWcnNlTnRHQ2NVWHF4d0VUK1hNaGZ2YkZsVkEwdzQKNFF5Si9pL1hhR2hoa3RXSHd1a3ZJdlNSTnBuZ3NrQmlRK0h2TStjR1BwdTlLYUgzTm1KN3VJek9EVHAwWTRCYwpZYmlKNk4vd3d2amJ3WEgvR1R2NFZjRS9sM3BxSDE5QjRGM1RlbFVRM3NqeUZjZ2hLR1pvUUcrOXVSTmRmTGtrCjY4NTJVNC9Pa0tBSXNLMGI1TnBFeUphK2I0N0lncU9KQ0VTVHVQeVBudlFwcGFySmovTjB5OXF1YStUb3U0bVUKeCs2ZTh0Y1B6Qk9YVkdxY01LZWhYRGJ6MmNpQnY4eVBHM2xFcU1BcHBiTjZ3a2NCczIxOUVTcWVTWVpXdWlpTwppc1JUZEJrRFM4eXpnTEFiKzV0NTY2aUdhMXlWQk0zeUdRMzNVWVREdFFLQmdRQzV4SDVscmZjRURHWXFOVjluCkpaQW9WTDRib2x1UWgzWTZHOGJEZDl4ZS9uSXFWSURCaUNXeG5NbEMzZkwyQ0ZTb1pTMnlRd3dlZkZtay81RysKaWJVSEtJZitTdHdkS1NJOWN3YWMvS1pDcG5uRG1uTGlLd0ZtemdUTTNTNEp2aDFxNVpUVkRLZk1uRytxNnNqSwo5ajAwVi91TVZvZmd2TFdUcExDbWRNR0FId0tCZ1FEeXBYMmFPcWFBVGUxbU5yRXhWVU5zdnRydHkyM2hLQ3U0CmdqRmhiV0xicWJwR2Z0cTdaNVI1R2VFSTZ4NjRBZzFDUmNaaUhERnFDeUc3NyttVTlQMUVWcm1Id1lMVVlIT2wKRTFyWS80cXhzUkpTMWc4TEdCbG95ZXhLVUNZTmprQnJZQU9xTmxWVW1aRkJoQ2NsVm5xeWJSQWZvY09PbzZOaQo2a1pteWk4VURRS0JnUUNKK3Q3L1d6WE1kZ0UwZkt3K0N2S0dZbHRLWDArdmpFNU9YdTlGcExPMGd6MzlId0w3CnZNcHlvRWdGT0tJTUNLZ0k1QTRMQ0MzcVB1YSszVzA5bno4czcvZ0M4MHVIQlZSL1cvNmZnREZsOUEwaE1vaisKWUg4TUF4NGhwRzlib1RCc2c5WUdZUDRKeG5CUy9VempJLzdWOER2UlF6eHR1djBMaXhvQ3FWcElkUUtCZ1FEWQpNajNVWW5laUVFejY2clk4aDRUWTZzQzBhYkpRa0hOTUpheUw2MlBPNXM2VEswb0crb1plMUlFZWFpZm51ZVJJCmJWVVNhNTVYcHUxNnY0dTI3Z2FQa2xvaXJIZStkT1gxYW1aaXZHVytaMUExUUljTTBuOHBUK2phV2NsZUFLWkQKUmJ4ZU42VVdDUEpVbHNRdVQzeHBhQ1dhbVk1ZGxFM3F2MlRWQjBhbExRS0JnSFptbGJaemxyTithamlHZDU1MAo1akp6SkdZOE5NN3ZBcE5zZGZTUmhUY3FqQUk3Q3RUcWwvbjhydEF5bnBZVG5qYjFzUDY5dzZZVHlkcThtT2xSCm5zd0paYTRoVU1rKzR6YU9UemVpemxnSTc0M096TDVUL0tQSGJESXRTdXU2SFkweFN0Vk9HTm9ZRWVIOEFlamIKWCtlVXkrcjBLcjJEMURreWlGUmFtMk9lCi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0K
-----END PRIVATE KEY-----"""

TRANSAK_API_KEY = "98ddbeda-799f-4de5-bb06-dcd6d729306d"
TRANSAK_REDIRECT_URL = ''

STELLAR_PLATFORM_SECRET = "SC34UKYKGMAUFWRZNB7ELZDKHJILDMR4SYSKD3B2MEM5YDMGF7US2M3L"
PLATFORM_CUSTODY_STELLAR_ACCOUNT = "GCA3RMKZWC7ZHFRBXAPKCWSP3FOWNRRX2NR5K4QZDOKSZVJSA3FSIZKQ"
USDC_ISSUER_PUBLIC_KEY = "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"

ALPACA_API_KEY = "CKDM5K9AMJN8N7PJ66F7"
ALPACA_SECRET_KEY = "UOSzfXuV8hnpmhIn9m5JfK0vxW0ZPGsQOkPnxmjj"

LINK_API_KEY = "ngnc_s_lk_d770850270259aa81a4ac216016f490f39515da7330b83dd380e3c17a1e348fa"

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

CELERY_BROKER_URL = 'redis://localhost:6379/0'  # Or your chosen broker
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

CELERY_BEAT_SCHEDULE = {
    'reconcile_every_day': {
        'task': 'app.tasks.auto_run_reconciliation',
        'schedule': 86400.0,  # 24 hours in seconds
    },
}

SERVER_JWT_KEY = '0fteaFpuDHH3J07b5BiYh8suLU_u1Sw67soOOjzgMIY'

RELOADLY_CLIENT_ID = 'Fp32qpekGJ88LYcVzreoGtMVAId8c0Jh'
RELOADLY_CLIENT_SECRET = '39B9TYHsmD-oKEKD8Vo5fRTNpJDXXZ-GrXOhzubqo7hVAd85WqyQFCvALpunCEi'
RELOADLY_BASE_URL = 'https://auth.reloadly.com'
