"""Housekeeping that keeps the server tidy without anyone having to remember to run a command."""
import logging
import threading
import time
from datetime import datetime, timedelta

from django.conf import settings

from .. import db
from . import storage

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 3600
_lock = threading.Lock()
_last_check = 0.0


def remove_scans(scans):
    """Delete these scans' image files and their database entries."""
    for scan in scans:
        path = storage.find_scan_file(scan.get('filename') or '')
        if path:
            storage.discard(path)
        db.delete_scan(scan['scan_id'])


def purge_abandoned(days, dry_run=False):
    """Scans uploaded more than `days` days ago and never saved as a record; deleted unless dry_run. Returns them."""
    scans = db.pending_scans_before(datetime.utcnow() - timedelta(days=days))
    if not dry_run:
        remove_scans(scans)
    return scans


def cleanup_if_due():
    """
    Delete abandoned uploads (PENDING_SCAN_DAYS), at most once an hour per server process, so the
    list never grows unnoticed. Called when someone uploads; never raises, because a failed
    cleanup must not stop an upload.
    """
    global _last_check
    days = settings.PENDING_SCAN_DAYS
    if days <= 0:
        return 0
    with _lock:
        if time.monotonic() - _last_check < CHECK_EVERY_SECONDS and _last_check:
            return 0
        _last_check = time.monotonic()
    try:
        removed = purge_abandoned(days)
    except Exception as e:
        logger.warning(f'Automatic cleanup of abandoned uploads failed: {e}')
        return 0
    if removed:
        logger.info(f'Removed {len(removed)} abandoned upload(s) older than {days} day(s).')
    return len(removed)


def reset_schedule():
    """Make the next cleanup_if_due() run at once (for tests)."""
    global _last_check
    _last_check = 0.0
