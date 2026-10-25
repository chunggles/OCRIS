"""
Runs `maintenance` once a day for as long as the server runs. The cloud container starts it next to
the web server (backend/start.sh), because a host's scheduled jobs cannot reach the server's disk.
On a school server, schedule `maintenance` with Task Scheduler or cron instead.
"""
import time
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from api.services import maintenance

CHECK_EVERY_MINUTES = 10


class Command(BaseCommand):
    help = ('Run the daily upkeep (`maintenance`) at MAINTENANCE_HOUR, Manila time, and keep checking. '
            'Started by the cloud container; not needed where `maintenance` is scheduled.')

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Check once, run the upkeep if it is due, and stop.')

    def handle(self, *args, once, **options):
        if not once:
            self.stdout.write(f'Daily upkeep at {settings.MAINTENANCE_HOUR:02d}:00 (Manila); backups go to {settings.BACKUP_DIR}')
        while True:
            newest = maintenance.newest_backup_time(settings.BACKUP_DIR)
            if maintenance.upkeep_due(datetime.now(), newest, settings.MAINTENANCE_HOUR):
                try:
                    call_command('maintenance', stdout=self.stdout, stderr=self.stderr)
                except Exception as e:   # tried again at the next check; the web server is not affected
                    self.stderr.write(f'WARNING: the daily upkeep failed: {e}')
            if once:
                return
            time.sleep(CHECK_EVERY_MINUTES * 60)
