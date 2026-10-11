"""Old and new values for the audit log."""

GRADE_KEYS = ('Q1', 'Q2', 'Q3', 'Q4', 'final')
MAX_GRADE_CHANGES = 200
MAX_VALUE_LENGTH = 200


def _show(value):
    return value if isinstance(value, (int, float, bool)) or value is None else str(value)[:MAX_VALUE_LENGTH]


def field_changes(old, new, fields):
    """{field: {'old': ..., 'new': ...}} for the listed fields whose value differs."""
    return {
        field: {'old': _show(old.get(field)), 'new': _show(new.get(field))}
        for field in fields if field in new and old.get(field) != new.get(field)
    }


def grade_changes(old, new):
    """A list of {subject, period, old, new} for every grade that was added, changed or removed."""
    changes = []
    for subject in sorted(set(old) | set(new)):
        before, after = old.get(subject) or {}, new.get(subject) or {}
        for key in GRADE_KEYS:
            if before.get(key) != after.get(key):
                changes.append({
                    'subject': subject[:MAX_VALUE_LENGTH], 'period': key,
                    'old': _show(before.get(key)) if subject in old else None,
                    'new': _show(after.get(key)) if subject in new else None,
                })
    return changes[:MAX_GRADE_CHANGES]


def record_snapshot(record):
    """What a deleted record held, so the audit trail can restore it by hand."""
    keys = ('pupil_name', 'lrn', 'grade_level', 'section', 'school_year', 'general_average', 'remarks', 'scan_id', 'uploaded_by')
    return {**{k: _show(record.get(k)) for k in keys}, 'grades': record.get('grades', {})}
