"""Checks on an uploaded file before anything is stored or read."""
from django.conf import settings
from PIL import Image, UnidentifiedImageError

# Which file types are taken, by their first bytes, and the extensions each may carry
SIGNATURES = (
    (b'\xff\xd8\xff', 'JPEG', ('.jpg', '.jpeg')),
    (b'\x89PNG\r\n\x1a\n', 'PNG', ('.png',)),
    (b'%PDF-', 'PDF', ('.pdf',)),
)
MAX_IMAGE_PIXELS = 120_000_000
MAX_BODY_OVERHEAD = 1024 * 1024   # form fields and multipart framing around the file


class UploadRefused(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def max_upload_bytes():
    return int(settings.MAX_UPLOAD_MB * 1024 * 1024)


def check_request_size(request):
    """Refuse an oversized request from its declared length, before the body is read."""
    try:
        declared = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        declared = 0
    if declared > max_upload_bytes() + MAX_BODY_OVERHEAD:
        raise UploadRefused(f'The file is too large. The limit is {settings.MAX_UPLOAD_MB:g} MB.', 413)


def check_upload(file):
    """
    Raise UploadRefused unless the file is a JPG, PNG or PDF of a sane size whose content matches
    its name. The type is decided by the file's first bytes, never by what the browser says.
    """
    if file.size == 0:
        raise UploadRefused('The file is empty.')
    if file.size > max_upload_bytes():
        raise UploadRefused(f'The file is too large. The limit is {settings.MAX_UPLOAD_MB:g} MB.', 413)

    head = file.read(16)
    file.seek(0)
    kind = next((name for magic, name, _ in SIGNATURES if head.startswith(magic)), None)
    if kind is None:
        raise UploadRefused('Only JPG, PNG and PDF files are accepted.', 415)
    allowed = next(exts for _, n, exts in SIGNATURES if n == kind)
    if not (file.name or '').lower().endswith(allowed):
        raise UploadRefused(f"The file's name does not match its content. It is a {kind} file.", 415)

    if kind != 'PDF':
        try:
            with Image.open(file) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise UploadRefused('The image is too large to process. Scan at 300 DPI or lower.')
                image.verify()
        except UploadRefused:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
            raise UploadRefused('The image could not be opened. It may be damaged.', 415)
        finally:
            file.seek(0)
