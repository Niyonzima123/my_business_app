# business_manager/settings.py

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# Import the cloudinary and cloudinary_storage packages
import cloudinary
import cloudinary_storage

# Load environment variables from a .env file (for local development)
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-local-secret-key-for-development')

# The `if` statement correctly sets DEBUG to False on Render
DEBUG = os.environ.get('RENDER', 'False') == 'False'

ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
else:
    # Set this for local development
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic', 
    'django.contrib.humanize', # Added for Whitenoise to handle static files in dev

    # Add Cloudinary apps
    'cloudinary_storage',
    'cloudinary',

    # My custom apps
    'inventory',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'business_manager.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'business_manager.wsgi.application'

# Database
# Use PostgreSQL with a DATABASE_URL environment variable if available
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600
        )
    }
else:
    # Fallback to local PostgreSQL for development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'business_db',
            'USER': 'business_user',
            'PASSWORD': 'ABC123',
            'HOST': 'localhost',
            'PORT': '5432',
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
TIME_ZONE = 'Africa/Kigali'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (user-uploaded content like product images)
MEDIA_URL = '/media/'
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Configure Cloudinary using the CLOUDINARY_URL environment variable
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
if CLOUDINARY_URL:
    cloudinary.config(
        secure=True,
        cloudinary_url=CLOUDINARY_URL
    )

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login/Logout Redirect URLs
LOGIN_REDIRECT_URL = '/pos/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Email Configuration for Notifications
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'