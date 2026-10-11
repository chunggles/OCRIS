"""Turn an encrypted backup (.zip.enc) back into a normal zip file."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services import crypto


class Command(BaseCommand):
    help = 'Decrypt a backup written by the backup command, using DATA_ENCRYPTION_KEY.'

    def add_arguments(self, parser):
        parser.add_argument('file', help='The .zip.enc file.')
        parser.add_argument('--out', help='Where to write the zip (default: beside the file, without .enc).')

    def handle(self, *args, file, out=None, **options):
        source = Path(file)
        if not source.is_file():
            raise CommandError(f'{source} does not exist.')
        target = Path(out) if out else source.with_suffix('') if source.suffix == '.enc' else source.with_name(source.name + '.zip')
        if not crypto.is_encrypted(source):
            raise CommandError('That file is not encrypted.')
        try:
            crypto.decrypt_to(source, target)
        except crypto.CryptoError as e:
            target.unlink(missing_ok=True)
            raise CommandError(str(e))
        self.stdout.write(f'Decrypted to {target}')
