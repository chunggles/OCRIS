"""Copy everything OCRIS stores into one dated zip file, encrypted when DATA_ENCRYPTION_KEY is set."""
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from bson import json_util
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api import db
from api.services import crypto, storage

COLLECTIONS = ('records', 'scans', 'audit_log', 'users', 'grade_levels')


class Command(BaseCommand):
    help = 'Back up the accounts database, the MongoDB collections and the uploaded scans into a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(settings.BACKUP_DIR), help='Folder to write the zip into.')
        parser.add_argument('--keep', type=int, default=None,
                            help='Afterwards delete all but the newest N backup files in that folder (default: keep all).')

    def handle(self, *args, out, keep=None, **options):
        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        name = f"ocris-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / name
            staging.mkdir()

            # Accounts and tokens: sqlite's own backup gives a consistent copy even while the server runs
            source = sqlite3.connect(settings.DATABASES['default']['NAME'])
            target = sqlite3.connect(staging / 'db.sqlite3')
            with target:
                source.backup(target)
            source.close()
            target.close()

            # MongoDB: one Extended JSON file per collection (restorable with mongoimport --jsonArray)
            mongo_dir = staging / 'mongo'
            mongo_dir.mkdir()
            for collection in COLLECTIONS:
                docs = list(db.get_db()[collection].find({}))
                text = json_util.dumps(docs, json_options=json_util.RELAXED_JSON_OPTIONS, indent=1)
                (mongo_dir / f'{collection}.json').write_text(text, encoding='utf-8')
                self.stdout.write(f'  {collection}: {len(docs)} document(s)')

            # Uploaded scan images
            scans = storage.scans_dir()
            count = 0
            if scans.is_dir():
                shutil.copytree(scans, staging / 'scans')
                count = sum(1 for f in (staging / 'scans').iterdir() if f.is_file())
            self.stdout.write(f'  scans: {count} file(s)')

            archive = Path(shutil.make_archive(str(out_dir / name), 'zip', root_dir=tmp, base_dir=name))
        if crypto.enabled():
            # The zip holds names, grades and password hashes, so it is encrypted as a whole
            crypto.encrypt_file(archive)
            archive = archive.rename(archive.with_name(archive.name + '.enc'))
            self.stdout.write('  encrypted with DATA_ENCRYPTION_KEY (read it back with: manage.py decrypt_backup <file>)')
        else:
            self.stdout.write(self.style.WARNING('  NOT encrypted: DATA_ENCRYPTION_KEY is not set.'))
        self.stdout.write(f'Backup written to {archive}')
        if keep is not None:
            self.prune(out_dir, keep)

    def prune(self, folder, keep):
        '''Delete the oldest backups so that only the newest `keep` remain (the names sort by date).'''
        if keep < 1:
            raise CommandError('--keep must be at least 1.')
        found = sorted(f for f in folder.iterdir()
                       if f.is_file() and f.name.startswith('ocris-backup-') and f.name.endswith(('.zip', '.zip.enc')))
        for old in found[:-keep]:
            old.unlink()
            self.stdout.write(f'  removed old backup {old.name}')
