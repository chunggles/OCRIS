"""Bring records saved before the year-block and subject-name rules into line with them."""
from django.core.management.base import BaseCommand

from api import db
from api.services import grading


def _split_by_year(grades):
    """[(year block or None, grades)] from a sheet whose subject names carry their year block."""
    blocks = {}
    for label, values in grades.items():
        subject, block = grading.split_label(label)
        blocks.setdefault(block, {})[subject] = values
    return [(block, grading.clean_subjects(subjects)) for block, subjects in blocks.items()]


class Command(BaseCommand):
    help = (
        'Give every record one spelling per learning area, and file a scanned form that holds several '
        'school years under the year of its grade level (the other years are kept in its details). '
        'Averages and remarks are recalculated. Only records that change are written.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would change without changing it.')

    def handle(self, *args, dry_run, **options):
        changed = 0
        records = db.all_records()
        for record in records:
            old = record.get('grades') or {}
            blocks = _split_by_year(old)
            grades, other_years = grading.choose_year_block(blocks, record.get('grade_level')) if blocks else ({}, [])
            if grades == old and not other_years:
                continue
            updates = {'grades': grades}
            if other_years:
                updates['details'] = {**(record.get('details') or {}), 'other_years': other_years}
            updates['general_average'] = grading.compute_general_average(grades)
            updates['remarks'] = grading.remarks_for(updates['general_average'], grades)
            changed += 1
            self.stdout.write(
                f"  {record['record_id']}  {record.get('pupil_name', '')}: {len(old)} -> {len(grades)} subjects"
                + (f", {len(other_years)} other year(s) kept" if other_years else '')
                + f", average {record.get('general_average')} -> {updates['general_average']}")
            if not dry_run:
                db.update_record(record['record_id'], updates)
        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(f'{verb} {changed} of {len(records)} record(s).')
