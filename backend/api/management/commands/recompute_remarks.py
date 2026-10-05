"""Recalculate the general average and remarks of saved records with the current rules."""
from django.core.management.base import BaseCommand

from api import db
from api.services import grading


class Command(BaseCommand):
    help = 'Recalculate general average and remarks for every record. Only records that change are written.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would change without changing it.')

    def handle(self, *args, dry_run, **options):
        changed = 0
        records = db.all_records()
        for record in records:
            grades = record.get('grades') or {}
            average = grading.compute_general_average(grades)
            remarks = grading.remarks_for(average, grades)
            if average == record.get('general_average') and remarks == record.get('remarks'):
                continue
            changed += 1
            self.stdout.write(
                f"  {record['record_id']}  {record.get('pupil_name', '')}: "
                f"{record.get('general_average')} {record.get('remarks')} -> {average} {remarks}")
            if not dry_run:
                db.update_record(record['record_id'], {'general_average': average, 'remarks': remarks})
        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(f'{verb} {changed} of {len(records)} record(s).')
