"""Saving uploaded Form 137 files and finding them again for download."""
import uuid
from pathlib import Path

from django.conf import settings


def scans_dir():
    return (Path(settings.MEDIA_ROOT) / 'scans').resolve()


def _safe_name(filename):
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)


def save_upload(file):
    """
    Write an uploaded file to MEDIA_ROOT/scans and return (stored_name, path).
    The random prefix stops two uploads named e.g. "scan.jpg" overwriting each other.
    """
    directory = scans_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f'{uuid.uuid4().hex[:8]}_{_safe_name(file.name)}'
    path = directory / stored_name
    with open(path, 'wb') as out:
        for chunk in file.chunks():
            out.write(chunk)
    return stored_name, path


def find_scan_file(stored_name):
    """Path of a stored scan, or None if it's missing or would resolve outside the scans folder."""
    directory = scans_dir()
    path = (directory / Path(stored_name).name).resolve()
    if path.parent != directory or not path.is_file():
        return None
    return path


def discard(path):
    """Remove a just-saved upload that won't be kept (e.g. OCR failed)."""
    try:
        path.unlink()
    except OSError:
        pass
