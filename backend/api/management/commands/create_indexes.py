"""Create the MongoDB indexes. The server also does this by itself the first time it connects."""
from django.core.management.base import BaseCommand, CommandError

from api import db


class Command(BaseCommand):
    help = 'Create the MongoDB indexes that are missing (safe to run at any time).'

    def handle(self, *args, **options):
        if not db.ensure_indexes():
            raise CommandError('MongoDB could not be reached.')
        for name in db.INDEXES:
            names = sorted(i for i in db.get_db()[name].index_information() if i != '_id_')
            self.stdout.write(f'  {name}: {", ".join(names)}')
