"""Encrypt the scans that were uploaded before encryption was switched on."""
from django.core.management.base import BaseCommand, CommandError

from api.services import crypto, storage


class Command(BaseCommand):
    help = 'Encrypt every plain file in the scans folder with DATA_ENCRYPTION_KEY. Safe to run again.'

    def handle(self, *args, **options):
        if not crypto.enabled():
            raise CommandError('Set DATA_ENCRYPTION_KEY in backend/.env first.')
        folder = storage.scans_dir()
        files = [f for f in folder.iterdir() if f.is_file()] if folder.is_dir() else []
        done = sum(1 for f in files if crypto.encrypt_file(f))
        self.stdout.write(f'Encrypted {done} file(s); {len(files) - done} were already encrypted.')
