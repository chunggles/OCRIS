"""Copy everything OCRIS stores into one dated zip file."""
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from bson import json_util
from django.conf import settings
from django.core.management.base import BaseCommand

from api import db
from api.services import storage

COLLECTIONS = ('records', 'scans', 'audit_log', 'users')


class Command(BaseCommand):
    help = 'Back up the accounts database, the MongoDB collections and the uploaded scans into a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(Path(settings.BASE_DIR) / 'backups'), help='Folder to write the zip into.')

    def handle(self, *args, out, **options):
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

            archive = shutil.make_archive(str(out_dir / name), 'zip', root_dir=tmp, base_dir=name)
        self.stdout.write(f'Backup written to {archive}')
