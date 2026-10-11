"""The routine upkeep in one command, meant to be run on a schedule (for example every night)."""
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Back up everything, keep only the newest backups, delete abandoned uploads and make sure the '
            'MongoDB indexes exist. Schedule this daily (see docs/INSTALLATION.md).')

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(Path(settings.BASE_DIR) / 'backups'), help='Folder for the backups.')
        parser.add_argument('--keep', type=int, default=settings.BACKUP_KEEP, help='Backups to keep (default BACKUP_KEEP, 14).')
        parser.add_argument('--skip-backup', action='store_true', help='Only delete abandoned uploads.')

    def handle(self, *args, out, keep, skip_backup, **options):
        if not skip_backup:
            call_command('backup', out=out, keep=keep, stdout=self.stdout)
        call_command('cleanup_scans', days=settings.PENDING_SCAN_DAYS or 7, stdout=self.stdout)
        call_command('create_indexes', stdout=self.stdout)
