"""Remove scans from uploads that were started but never saved as a record."""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from api import db
from api.services import storage


class Command(BaseCommand):
    help = 'Delete pending scans (and their image files) older than --days days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Keep pending scans newer than this (default 7).')
        parser.add_argument('--dry-run', action='store_true', help='List what would be deleted without deleting.')

    def handle(self, *args, days, dry_run, **options):
        cutoff = datetime.utcnow() - timedelta(days=days)
        scans = db.pending_scans_before(cutoff)
        for scan in scans:
            self.stdout.write(f"  {scan['scan_id']}  {scan.get('pupil_name', '')}  {scan.get('original_name', '')}")
            if dry_run:
                continue
            path = storage.find_scan_file(scan.get('filename') or '')
            if path:
                storage.discard(path)
            db.delete_scan(scan['scan_id'])
        verb = 'Would delete' if dry_run else 'Deleted'
        self.stdout.write(f'{verb} {len(scans)} pending scan(s) older than {days} day(s).')
