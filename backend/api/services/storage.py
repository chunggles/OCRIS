"""Saving uploaded Form 137 files and finding them again for download."""
import logging
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

from . import crypto

logger = logging.getLogger(__name__)


def scans_dir():
    return (Path(settings.MEDIA_ROOT) / 'scans').resolve()


def _safe_name(filename):
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)


def save_upload(file):
    """
    Write an uploaded file to MEDIA_ROOT/scans and return (stored_name, path). It is encrypted
    when DATA_ENCRYPTION_KEY is set. The random prefix stops two uploads named e.g. "scan.jpg"
    overwriting each other.
    """
    directory = scans_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f'{uuid.uuid4().hex[:8]}_{_safe_name(file.name)}'
    path = directory / stored_name
    with open(path, 'wb') as out:
        if crypto.enabled():
            crypto.encrypt_chunks(file.chunks(), out)
        else:
            for chunk in file.chunks():
                out.write(chunk)
    return stored_name, path


@contextmanager
def plain_copy(path):
    """
    A path to the readable content of a stored scan, for the OCR. An encrypted scan is decrypted
    into a temporary folder that is removed afterwards; a plain one is used where it lies.
    """
    if not crypto.is_encrypted(path):
        yield path
        return
    folder = Path(tempfile.mkdtemp(prefix='ocris-'))
    try:
        target = folder / path.name
        crypto.decrypt_to(path, target)
        yield target
    finally:
        shutil.rmtree(folder, ignore_errors=True)


class _Stream:
    """Byte strings of a stored scan for a response. Closing it releases the file."""

    def __init__(self, chunks, first):
        self._chunks, self._first = chunks, first

    def __iter__(self):
        yield self._first
        yield from self._chunks

    def close(self):
        self._chunks.close()


def open_stream(path):
    """
    The content of a stored scan, decrypted if need be, ready to send. The first piece is read
    here, so a wrong key or a damaged file raises CryptoError before a response is started.
    """
    chunks = crypto.iter_plain(path)
    try:
        return _Stream(chunks, next(chunks, b''))
    except Exception:
        chunks.close()
        raise


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
    except OSError as e:
        logger.warning(f'Could not remove {path.name}; it is left in the scans folder: {e}')
