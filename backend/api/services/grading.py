"""Turns validated OCR fields into a grade sheet and decides promotion."""
import re

from ..constants import INCOMPLETE, NA, PASSING_GRADE, PROMOTED, RETAINED, is_na
from ..ocr.parser import match_subject_span

PUPIL_FIELDS = {'Pupil Name', 'LRN', 'Grade Level', 'Section', 'School Year'}
QUARTERS = {'Q1', 'Q2', 'Q3', 'Q4', 'Final'}
# A year block's label on a scan: "Grade 3" or "Block 2" on an SF10-ES, "I" to "VI" on a Form 137-A
BLOCK_LABEL_RE = re.compile(r'^(?P<subject>.+?)\s+(?P<block>Grade [1-6]|Block \d|VI|IV|V|I{1,3})(?:\s+#(?P<n>\d+))?$')
ROMAN_LEVELS = ('I', 'II', 'III', 'IV', 'V', 'VI')


def split_label(label):
    """
    (subject, year block) from a scan's subject label such as "Filipino Grade 2" or "English II #2".
    The block is None when the label carries none. A repeated subject keeps its "#n" so rows stay apart.
    """
    m = BLOCK_LABEL_RE.match(label.strip())
    if not m:
        return label.strip(), None
    subject = m.group('subject') if not m.group('n') else f"{m.group('subject')} #{m.group('n')}"
    return subject, m.group('block')


def block_number(block):
    """The grade a year block stands for (3 for "Grade 3", 2 for "II"), or None when it can't be told."""
    if block is None:
        return None
    if block.startswith('Grade '):
        return int(block[6:])
    return ROMAN_LEVELS.index(block) + 1 if block in ROMAN_LEVELS else None


def normalize_subject(name):
    """
    One spelling per learning area, so typed and scanned forms are counted together:
    "EPP", "TLE" and "EPP / TLE" all become "EPP / TLE", "GMRC (Good Manners ...)" becomes "GMRC".
    Names that match no known learning area are only tidied.
    """
    text = ' '.join(str(name).replace('*', ' ').split())
    text = re.sub(r'\s*\(.*\)\s*$', '', text).strip()
    span = match_subject_span(text)
    if span and span[1] >= len(text):
        return span[0]
    return text


def merge_grades(into, grades):
    """Add one subject's grades to another entry of the same subject, filling only the blanks."""
    for key, value in grades.items():
        if is_na(into.get(key)):
            into[key] = value


def clean_subjects(grades):
    """The grade sheet with every subject name normalised; subjects that become one are merged."""
    cleaned = {}
    for subject, values in grades.items():
        name = normalize_subject(subject) or subject
        if name in cleaned:
            merge_grades(cleaned[name], values)
        else:
            cleaned[name] = dict(values)
    return cleaned


def build_year_blocks(ocr_fields, corrections, renames=None):
    """
    [(year block label or None, {subject: {'Q1': ..., 'Q4': ..., 'final': ...}})] in page order,
    from OCR field names like "English I Q1" or "Filipino Grade 2 Final". Human corrections take
    priority over OCR values. `renames` maps a subject label as read ("Unread learning area Grade 2")
    to the name a person gave it.
    """
    blocks = {}
    renames = renames or {}
    for field in ocr_fields:
        name = field.get('field', '')
        _add_grade(blocks, name, corrections.get(name, field.get('value', NA)), renames)
    for name, value in corrections.items():
        _add_grade(blocks, name, value, renames)
    return [(label, clean_subjects(grades)) for label, grades in blocks.items()]


def _add_grade(blocks, field_name, value, renames):
    if field_name in PUPIL_FIELDS:
        return
    parts = field_name.rsplit(' ', 1)
    if len(parts) != 2:
        return
    label, quarter = parts[0].strip(), parts[1].strip()
    if quarter not in QUARTERS:
        return
    subject, block = split_label(label)
    subject = renames.get(label) or subject
    key = 'final' if quarter == 'Final' else quarter
    subject_grades = blocks.setdefault(block, {}).setdefault(subject, {})
    # Keep the first real value; only overwrite a missing or N/A one
    if subject_grades.get(key, NA) == NA:
        subject_grades[key] = value or NA


def choose_year_block(blocks, grade_level):
    """
    (grades of the record, other years). A form that holds several school years is filed as the
    year of the record's grade level; when that can't be matched, the last block, which is the
    latest school year. The other years are kept as [{'label', 'grades'}] so nothing is lost, but
    they take no part in the record's average or in the analytics.
    """
    if len(blocks) == 1:
        return blocks[0][1], []
    wanted = int(re.sub(r'\D', '', grade_level or '') or 0)
    index = next((i for i, (label, _) in enumerate(blocks) if block_number(label) == wanted), len(blocks) - 1)
    others = [{'label': label or f'Block {i + 1}', 'grades': grades} for i, (label, grades) in enumerate(blocks) if i != index]
    return blocks[index][1], others


def is_valid_grade(value):
    """True for a blank (N/A) or a number from 0 to 100; anything else can't be saved as a grade."""
    if is_na(value):
        return True
    try:
        return 0 <= float(value) <= 100
    except (TypeError, ValueError):
        return False


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
