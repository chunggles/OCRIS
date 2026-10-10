import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_list(name, default):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


# ── Core ─────────────────────────────────────────────────────────────────────
# Safe by default: DEBUG is off unless .env turns it on, and a real SECRET_KEY is then required.
DEV_SECRET_KEYS = ('', 'ocris-dev-key', 'change-me')
SECRET_KEY = os.getenv('SECRET_KEY', 'ocris-dev-key')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
if not DEBUG and SECRET_KEY in DEV_SECRET_KEYS:
    raise ImproperlyConfigured('Set a real SECRET_KEY in backend/.env (or set DEBUG=True for local development).')
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ROOT_URLCONF = 'ocris_backend.urls'
WSGI_APPLICATION = 'ocris_backend.wsgi.application'
AUTH_USER_MODEL = 'api.OCRISUser'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

# ── HTTPS ────────────────────────────────────────────────────────────────────
# Outside local development every request must use HTTPS: plain HTTP is redirected, browsers
# are told to keep using HTTPS, and cookies are sent over HTTPS only. Set REQUIRE_HTTPS=False
# in .env only for a server that genuinely has no HTTPS in front of it.
REQUIRE_HTTPS = os.getenv('REQUIRE_HTTPS', str(not DEBUG)).lower() == 'true'
if REQUIRE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')   # set by the host's load balancer
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── Databases ────────────────────────────────────────────────────────────────
# SQLite holds Django auth (users, tokens); MongoDB holds records, scans and the audit log.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'ocris_bcs')

# ── REST framework & CORS ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
# Hours a login stays valid; signing in again restarts the clock
TOKEN_TTL_HOURS = float(os.getenv('TOKEN_TTL_HOURS', '12'))
CORS_ALLOWED_ORIGINS = _env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Disposition']  # lets the frontend read download filenames

# ── Files ────────────────────────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# ── OCR ──────────────────────────────────────────────────────────────────────
# A grade read from a scan is auto-approved only above this confidence (%); anything else is
# flagged for a person to check. Lower it in .env to review less, at more risk of a wrong grade.
OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '90'))
OCR_LANG = 'eng'
# Full path to tesseract.exe if it isn't on PATH (Windows), e.g. C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '')

# ── Locale ───────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True
