"""Remove scans from uploads that were never saved as a record, and, if asked, scans kept after their record was deleted."""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from api import db
from api.services import maintenance


class Command(BaseCommand):
    help = 'Delete pending scans (and their image files) older than --days days. The server also does this by itself (PENDING_SCAN_DAYS). Add --deleted-days to also purge scans kept after their record was deleted.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Keep pending scans newer than this (default 7).')
        parser.add_argument('--deleted-days', type=int, default=None,
                            help='Also delete scans whose record was deleted more than this many days ago. Off by default: they are kept as an audit trail.')
        parser.add_argument('--dry-run', action='store_true', help='List what would be deleted without deleting.')

    def handle(self, *args, days, dry_run, deleted_days=None, **options):
        scans = db.pending_scans_before(datetime.utcnow() - timedelta(days=days))
        verb = 'Would delete' if dry_run else 'Deleted'
        self._remove(scans, dry_run)
        self.stdout.write(f'{verb} {len(scans)} pending scan(s) older than {days} day(s).')
        if deleted_days is not None:
            kept = db.deleted_record_scans_before(datetime.utcnow() - timedelta(days=deleted_days))
            self._remove(kept, dry_run)
            self.stdout.write(f'{verb} {len(kept)} scan(s) whose record was deleted over {deleted_days} day(s) ago.')

    def _remove(self, scans, dry_run):
        for scan in scans:
            self.stdout.write(f"  {scan['scan_id']}  {scan.get('pupil_name', '')}  {scan.get('original_name', '')}")
            if not dry_run:
                maintenance.remove_scans([scan])
