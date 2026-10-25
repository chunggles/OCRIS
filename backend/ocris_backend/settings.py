import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
# Where everything OCRIS writes is kept: the accounts database, the uploaded scans, the audit file and
# the backups. On a cloud host point it at the persistent disk (Render: /var/data); the rest of the
# server's files are replaced on every deploy.
DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR)))
# The built React app (frontend/dist). When this is set, the server also serves the site, from the
# same address as the API (the cloud set-up, see Dockerfile); otherwise the Vite dev server does.
FRONTEND_DIST = Path(os.environ['FRONTEND_DIST']) if os.getenv('FRONTEND_DIST') else None


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
if os.getenv('RENDER_EXTERNAL_HOSTNAME'):   # set by Render: the service's onrender.com address
    ALLOWED_HOSTS.append(os.getenv('RENDER_EXTERNAL_HOSTNAME'))
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
# Django's admin site is off outside local development: changes made there skip the audit log and
# its sign-in has no limit on wrong passwords. ENABLE_DJANGO_ADMIN=True turns it on.
ENABLE_DJANGO_ADMIN = os.getenv('ENABLE_DJANGO_ADMIN', str(DEBUG)).lower() == 'true'

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
    SECURE_REDIRECT_EXEMPT = [r'^api/health/$']   # the host's health check comes over plain HTTP
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')   # set by the host's load balancer
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── Encryption at rest ───────────────────────────────────────────────────────
# Uploaded scans and backup files are encrypted with this key (several, comma-separated, to rotate:
# the first encrypts, all decrypt). Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Without a key, files are stored as they are; that is allowed for local development only.
DATA_ENCRYPTION_KEYS = _env_list('DATA_ENCRYPTION_KEY', '')
if DATA_ENCRYPTION_KEYS:
    try:
        for _key in DATA_ENCRYPTION_KEYS:
            Fernet(_key)
    except ValueError:
        raise ImproperlyConfigured('DATA_ENCRYPTION_KEY is not a valid key. Generate one as described in settings.py.')
elif not DEBUG:
    raise ImproperlyConfigured('Set DATA_ENCRYPTION_KEY in backend/.env (or set DEBUG=True for local development).')

# ── Databases ────────────────────────────────────────────────────────────────
# SQLite holds Django auth (users, tokens); MongoDB holds records, scans and the audit log.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': DATA_DIR / 'db.sqlite3'}}
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'ocris_bcs')

# ── Sign-in and sessions ─────────────────────────────────────────────────────
# A sign-in is kept in an HttpOnly cookie, which scripts on the page cannot read. The cookie is
# sent across sites only when the site and the server are on different domains (SameSite=None
# needs HTTPS); every request that changes data must also carry the X-OCRIS-Request header,
# which another website cannot add, so a forged request from elsewhere is refused.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['api.authentication.CookieSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
AUTH_COOKIE_NAME = 'ocris_session'
# Lax when the site and the API share one address (FRONTEND_DIST set); None only when they cannot
AUTH_COOKIE_SAMESITE = os.getenv('AUTH_COOKIE_SAMESITE', 'None' if REQUIRE_HTTPS and not FRONTEND_DIST else 'Lax')
REQUEST_HEADER = 'X-OCRIS-Request'
# Hours a login stays valid
TOKEN_TTL_HOURS = float(os.getenv('TOKEN_TTL_HOURS', '12'))
# Minutes a login may go unused (no typing, clicking or request) before it ends; 0 turns it off
IDLE_TIMEOUT_MINUTES = float(os.getenv('IDLE_TIMEOUT_MINUTES', '30'))
# After this many wrong passwords for one username (or LOGIN_MAX_ATTEMPTS_PER_IP from one address)
# within LOGIN_LOCKOUT_MINUTES, sign-in is refused until the oldest of them ages out
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_MAX_ATTEMPTS_PER_IP = int(os.getenv('LOGIN_MAX_ATTEMPTS_PER_IP', '20'))
LOGIN_LOCKOUT_MINUTES = int(os.getenv('LOGIN_LOCKOUT_MINUTES', '15'))
RESET_MAX_REQUESTS = int(os.getenv('RESET_MAX_REQUESTS', '5'))   # password-reset requests per address per window
# Number of proxies in front of the server (a cloud host's load balancer counts as one)
TRUSTED_PROXY_COUNT = int(os.getenv('TRUSTED_PROXY_COUNT', '1' if REQUIRE_HTTPS else '0'))

PASSWORD_MIN_LENGTH = 10
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': PASSWORD_MIN_LENGTH}},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'api.password_validators.LetterAndDigitValidator'},
]

# Other addresses allowed to call the API from a browser. None are needed when this server also
# serves the site; the Vite dev server's addresses are allowed in local development only.
CORS_ALLOWED_ORIGINS = _env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000' if DEBUG else '')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [*default_headers, REQUEST_HEADER.lower()]
CORS_EXPOSE_HEADERS = ['Content-Disposition']  # lets the frontend read download filenames

# ── Files ────────────────────────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'
BACKUP_DIR = DATA_DIR / 'backups'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

if FRONTEND_DIST:
    # WhiteNoise serves the built site: index.html at / (never cached, so a deploy shows at once) and
    # the files under /assets/, whose names change with their content, cached for good.
    from .frontend import add_headers, is_immutable
    MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                      'whitenoise.middleware.WhiteNoiseMiddleware')
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True
    WHITENOISE_IMMUTABLE_FILE_TEST = is_immutable
    WHITENOISE_ADD_HEADERS_FUNCTION = add_headers
# Largest scan accepted, in MB. Larger uploads are refused before they are read or stored.
MAX_UPLOAD_MB = float(os.getenv('MAX_UPLOAD_MB', '20'))
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # bigger uploads are streamed to a temporary file

# ── Housekeeping ─────────────────────────────────────────────────────────────
# Uploads that were read but never saved as a record are deleted, with their file, after this
# many days (0 keeps them forever). It happens by itself, at most once an hour, when someone uploads;
# `manage.py cleanup_scans` does it on demand.
PENDING_SCAN_DAYS = int(os.getenv('PENDING_SCAN_DAYS', '7'))
# How many backup files `manage.py maintenance` (or `backup --keep`) leaves in the backups folder.
BACKUP_KEEP = int(os.getenv('BACKUP_KEEP', '14'))
# Hour of the day (Manila time, 0-23) at which `manage.py maintenance_loop` runs the upkeep. The
# cloud container starts that loop; on a school server, schedule `maintenance` instead.
MAINTENANCE_HOUR = int(os.getenv('MAINTENANCE_HOUR', '2'))

# ── Audit trail ──────────────────────────────────────────────────────────────
# Every audit entry is also appended to this file (one JSON object per line, each holding the hash
# of the one before it; see api/services/audit_chain.py), so the trail survives if the database is
# wiped or replaced. Keep it on storage that is not wiped on deploy. The tests never write to it,
# even when .env names a file, so their entries cannot join the school's trail.
AUDIT_LOG_FILE = Path(os.devnull if 'test' in sys.argv else os.getenv('AUDIT_LOG_FILE', str(DATA_DIR / 'logs' / 'audit.jsonl')))

# ── OCR ──────────────────────────────────────────────────────────────────────
# A grade read from a scan is auto-approved only above this confidence (%); anything else is
# flagged for a person to check. Lower it in .env to review less, at more risk of a wrong grade.
OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '90'))
OCR_LANG = 'eng'
# Forms read at the same time by one server process (each takes about 300 MB); further uploads wait.
# The cloud container runs 2 processes, so 2 here means at most 4 forms at once on a 2 GB instance.
OCR_MAX_CONCURRENT = int(os.getenv('OCR_MAX_CONCURRENT', '2'))
# Full path to tesseract.exe if it isn't on PATH (Windows), e.g. C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '')

# ── Locale ───────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# ── Audit file ───────────────────────────────────────────────────────────────
# Written by api/services/audit_chain.py, one hash-chained JSON line per entry
if AUDIT_LOG_FILE != Path(os.devnull):
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
