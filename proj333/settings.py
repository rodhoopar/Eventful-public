"""
Django settings for proj333 project.

Generated by 'django-admin startproject' using Django 1.10.6.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
import dj_database_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '1#44yqe_@d59muoeb6bdjj@q3v&3y_u)h%3^eqb2to!zq$t6hb'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*',
]

# Application definition

INSTALLED_APPS = [
    'eventful.apps.EventfulConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_twilio',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proj333.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'proj333.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=dj_database_url.config('postgres://whgameamlflffn:e14b06fab4fd2ff55915f5082f421f17104dc1a122a186061bd74142ed9ab365@ec2-54-243-107-66.compute-1.amazonaws.com:5432/d25ltkv240jo5b')
    )
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    # }
}


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_L10N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'

LOGIN_REDIRECT_URL = '/create'

LOGIN_URL = '/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'extras')

MEDIA_URL = '/extras/'

TWILIO_ACCOUNT_SID = 'AC2b20e8c26d6e98cf7872983c99ae1d63'

TWILIO_AUTH_TOKEN = 'bc37aa6722f8ca74a651da1e59f2f60b'

BROKER_URL = 'redis://h:p7274852ab2900509c6ae507f971e50a00bbe0e9217f1463ac7e6a08ff5961cd5@ec2-34-205-102-223.compute-1.amazonaws.com:13129'
# BROKER_URL = 'redis://localhost:6379/0'

BROKER_POOL_LIMIT = 0

CELERY_RESULT_BACKEND = 'redis://h:p7274852ab2900509c6ae507f971e50a00bbe0e9217f1463ac7e6a08ff5961cd5@ec2-34-205-102-223.compute-1.amazonaws.com:13129'
# CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

CELERY_ACCEPT_CONTENT = ['application/json']


CELERY_TASK_SERIALIZER = 'json'

CELERY_RESULT_SERIALIZER = 'json'

CELERY_TIMEZONE = 'US/Eastern'

CELERY_IMPORTS = ['eventful.tasks']

TWILIO_NUMBER = "+14152003573"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'staticfiles')

STATIC_URL = '/static/'

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(PROJECT_ROOT, 'static'),
)

PSIF_MAX = 32767