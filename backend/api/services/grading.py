"""Turns validated OCR fields into a grade sheet and decides promotion."""
from ..constants import INCOMPLETE, NA, PASSING_GRADE, PROMOTED, RETAINED, is_na

PUPIL_FIELDS = {'Pupil Name', 'LRN', 'Grade Level', 'Section', 'School Year'}
QUARTERS = {'Q1', 'Q2', 'Q3', 'Q4', 'Final'}


def build_grades(ocr_fields, corrections):
    """
    Build {subject: {'Q1': ..., 'Q4': ..., 'final': ...}} from OCR field names
    like "English I Q1". Human corrections take priority over OCR values.
    """
    grades = {}
    for field in ocr_fields:
        name = field.get('field', '')
        _add_grade(grades, name, corrections.get(name, field.get('value', NA)))
    for name, value in corrections.items():
        _add_grade(grades, name, value)
    return grades


def _add_grade(grades, field_name, value):
    if field_name in PUPIL_FIELDS:
        return
    parts = field_name.rsplit(' ', 1)
    if len(parts) != 2:
        return
    subject, quarter = parts[0].strip(), parts[1].strip()
    if quarter not in QUARTERS:
        return
    key = 'final' if quarter == 'Final' else quarter
    subject_grades = grades.setdefault(subject, {})
    # Keep the first real value; only overwrite a missing or N/A one
    if subject_grades.get(key, NA) == NA:
        subject_grades[key] = value or NA


def compute_general_average(grades):
    """Mean of all numeric final grades as a string (e.g. '86.4'), or None."""
    finals = []
    for subject_grades in grades.values():
        final = subject_grades.get('final')
        if is_na(final):
            continue
        try:
            finals.append(float(final))
        except ValueError:
            pass
    return str(round(sum(finals) / len(finals), 1)) if finals else None


def is_promoted(general_average, grades):
    """Promoted when the average and every recorded final are at least the passing grade."""
    if not general_average:
        return False
    try:
        return float(general_average) >= PASSING_GRADE and all(
            float(g['final']) >= PASSING_GRADE
            for g in grades.values()
            if not is_na(g.get('final'))
        )
    except (TypeError, ValueError):
        return False


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def has_unreadable_final(grades):
    """True if any final grade is filled in but isn't a number (e.g. '?')."""
    return any(not is_na(g.get('final')) and not _is_number(g.get('final')) for g in grades.values())


def _has_failing_final(grades):
    return any(_is_number(g.get('final')) and float(g['final']) < PASSING_GRADE for g in grades.values())


def remarks_for(general_average, grades):
    """
    Retained if any numeric final is below the passing grade — that decides it even when
    other finals are unreadable. Otherwise Incomplete when promotion can't be decided
    (no numeric finals, or a final that isn't a number). Blank (N/A) finals are skipped,
    as in the general average.
    """
    if _has_failing_final(grades):
        return RETAINED
    if general_average is None or has_unreadable_final(grades):
        return INCOMPLETE
    return PROMOTED if is_promoted(general_average, grades) else RETAINED
