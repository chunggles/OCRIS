"""Values shared across the API: grade rules and how blank values are represented."""

NA = 'N/A'
NA_VALUES = (None, '', NA)

PASSING_GRADE = 75

PROMOTED = 'Promoted'
RETAINED = 'Retained'
INCOMPLETE = 'Incomplete'  # no numeric finals, or a final that isn't a number

GRADE_LEVELS = tuple(f'Grade {n}' for n in range(1, 7))

# How a record's school year is divided: four quarters (older forms, and every scan), or three
# terms (the SF10-ES typed on the Fill Out form). Terms are stored under Q1 to Q3, with Q4 N/A.
QUARTER = 'quarter'
TERM = 'term'
PERIOD_KEYS = {QUARTER: ('Q1', 'Q2', 'Q3', 'Q4'), TERM: ('Q1', 'Q2', 'Q3')}

# Pupil fields sent with an upload and stored on the scan document
PUPIL_KEYS = ('pupil_name', 'grade_level', 'section', 'school_year', 'lrn')


def is_na(value):
    """True for values the system treats as blank (missing, empty, or 'N/A')."""
    return value in NA_VALUES


def grading_period_of(record):
    """'term' or 'quarter'. Records saved before the field existed all use quarters."""
    return TERM if record.get('grading_period') == TERM else QUARTER


def is_archived(record):
    """True for a form stored with Archive only: it was never read, keeps no grades and has no remarks."""
    return bool((record.get('details') or {}).get('archive_only'))
