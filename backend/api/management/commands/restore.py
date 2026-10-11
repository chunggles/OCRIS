"""Put a backup written by the backup command back: accounts, MongoDB collections and scans."""
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from bson import json_util
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from api import db
from api.management.commands.backup import COLLECTIONS
from api.services import crypto, storage


class Command(BaseCommand):
    help = ('Restore a backup (.zip, or .zip.enc made with DATA_ENCRYPTION_KEY). Replaces the accounts, the records, scans, '
            'audit log and sections with the backup, and adds its scan files. Stop the server first.')

    def add_arguments(self, parser):
        parser.add_argument('file', help='The backup file.')
        parser.add_argument('--yes', action='store_true', help='Really replace the current data. Without it, only shows what the backup holds.')
        parser.add_argument('--skip-safety-backup', action='store_true',
                            help='Do not back up the current data first (it is saved in backups/before-restore otherwise).')

    def handle(self, *args, file, yes, skip_safety_backup, **options):
        source = Path(file)
        if not source.is_file():
            raise CommandError(f'{source} does not exist.')
        with tempfile.TemporaryDirectory() as tmp:
            root = self._unpack(source, Path(tmp))
            contents = self._describe(root)
            if not yes:
                self.stdout.write(self.style.WARNING('Nothing was changed. Restoring replaces the current data with the above; run again with --yes.'))
                return
            if not skip_safety_backup:
                call_command('backup', out=str(Path(settings.BASE_DIR) / 'backups' / 'before-restore'), stdout=self.stdout)
            self._restore_accounts(root / 'db.sqlite3')
            for name, docs in contents.items():
                collection = db.get_db()[name]
                collection.delete_many({})
                if docs:
                    collection.insert_many(docs)
            db.ensure_indexes()
            copied = self._restore_scans(root / 'scans')
        total = sum(len(d) for d in contents.values())
        self.stdout.write(self.style.SUCCESS(
            f'Restored {total} MongoDB document(s), the accounts and {copied} scan file(s). Restart the server.'))

    def _unpack(self, source, tmp):
        archive = source
        if crypto.is_encrypted(source):
            archive = tmp / 'backup.zip'
            try:
                crypto.decrypt_to(source, archive)
            except crypto.CryptoError as e:
                raise CommandError(str(e))
        if not zipfile.is_zipfile(archive):
            raise CommandError('That file is not a backup zip.')
        folder = tmp / 'unpacked'
        with zipfile.ZipFile(archive) as z:
            z.extractall(folder)   # refuses names that would land outside the folder
        roots = [d for d in folder.iterdir() if d.is_dir()]
        if len(roots) != 1 or not (roots[0] / 'db.sqlite3').is_file() or not (roots[0] / 'mongo').is_dir():
            raise CommandError('That zip does not look like an OCRIS backup (no db.sqlite3 and mongo folder).')
        return roots[0]

    def _describe(self, root):
        """{collection: documents} of the backup, printed."""
        contents = {}
        for name in COLLECTIONS:
            path = root / 'mongo' / f'{name}.json'
            docs = json_util.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
            contents[name] = docs
            self.stdout.write(f'  {name}: {len(docs)} document(s)')
        scans = root / 'scans'
        files = sum(1 for f in scans.iterdir() if f.is_file()) if scans.is_dir() else 0
        self.stdout.write(f'  scans: {files} file(s)')
        return contents

    def _restore_accounts(self, backup_file):
        connections.close_all()
        source = sqlite3.connect(backup_file)
        target = sqlite3.connect(settings.DATABASES['default']['NAME'])
        try:
            with target:
                source.backup(target)
        finally:
            source.close()
            target.close()

    def _restore_scans(self, folder):
        if not folder.is_dir():
            return 0
        target = storage.scans_dir()
        target.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in folder.iterdir():
            if f.is_file():
                shutil.copy2(f, target / f.name)
                count += 1
        return count
