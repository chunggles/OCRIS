"""The routine upkeep in one command, meant to be run on a schedule (for example every night)."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Back up everything, keep only the newest backups, delete abandoned uploads, make sure the '
            'MongoDB indexes exist and check the audit file. Schedule this daily (see docs/INSTALLATION.md).')

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(settings.BACKUP_DIR), help='Folder for the backups.')
        parser.add_argument('--keep', type=int, default=settings.BACKUP_KEEP, help='Backups to keep (default BACKUP_KEEP, 14).')
        parser.add_argument('--skip-backup', action='store_true', help='Only delete abandoned uploads.')

    def handle(self, *args, out, keep, skip_backup, **options):
        if not skip_backup:
            call_command('backup', out=out, keep=keep, stdout=self.stdout)
        call_command('cleanup_scans', days=settings.PENDING_SCAN_DAYS or 7, stdout=self.stdout)
        call_command('create_indexes', stdout=self.stdout)
        try:
            call_command('verify_audit', stdout=self.stdout)
        except CommandError as e:   # reported, but the rest of the upkeep has already run
            self.stderr.write(f'WARNING: {e} Run python manage.py verify_audit for the details.')
