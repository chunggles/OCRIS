"""Checks on who a record is for: the LRN, and whether the record is already on file."""
import re

from .. import db

LRN_LENGTH = 12
LRN_RE = re.compile(rf'^\d{{{LRN_LENGTH}}}$')


def clean_lrn(lrn):
    """The LRN without spaces or dashes, as people often type or print it."""
    return re.sub(r'[\s-]', '', str(lrn or ''))


def lrn_problem(lrn):
    """Message if a typed LRN is not 12 digits. A blank LRN is allowed; it is optional."""
    if lrn and not LRN_RE.match(lrn):
        return f'The LRN must be {LRN_LENGTH} digits.'
    return None


def _surname(name):
    return str(name or '').split(',')[0].strip().casefold()


def identity_problem(record, exclude_id=None):
    """
    Message if this record can't be saved because it clashes with one already on file, else None.
    A pupil has one record per school year, and an LRN belongs to one pupil.
    `record` needs pupil_name, lrn, grade_level and school_year.
    """
    lrn = record.get('lrn') or ''
    twin = db.find_record_of_year(
        record.get('pupil_name', ''), lrn, record.get('grade_level', ''), record.get('school_year', ''), exclude_id)
    if twin:
        return (f"{twin['pupil_name']} already has record {twin['record_id']} for school year "
                f"{twin['school_year']}. Edit that record instead of saving another.")
    if lrn:
        owner = db.find_record_by_lrn(lrn, exclude_id)
        if owner and _surname(owner['pupil_name']) != _surname(record.get('pupil_name')):
            return f"LRN {lrn} already belongs to {owner['pupil_name']} (record {owner['record_id']})."
    return None
