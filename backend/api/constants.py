"""Values shared across the API: grade rules and how blank values are represented."""

NA = 'N/A'
NA_VALUES = (None, '', NA)

PASSING_GRADE = 75

PROMOTED = 'Promoted'
RETAINED = 'Retained'
INCOMPLETE = 'Incomplete'  # no numeric finals, or a final that isn't a number

# Pupil fields sent with an upload and stored on the scan document
PUPIL_KEYS = ('pupil_name', 'grade_level', 'section', 'school_year', 'lrn')


def is_na(value):
    """True for values the system treats as blank (missing, empty, or 'N/A')."""
    return value in NA_VALUES
