from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import NA, PERIOD_KEYS, QUARTER, TERM, grading_period_of, is_archived, is_na
from ..permissions import IsOICOrAdmin
from ..services import audit, grading, identity
from ..utils.http import detail, no_class_assigned, not_found, outside_own_class, page_param, query_param

# Fields that may be changed on a saved record. The average and remarks are never set
# directly; they are recalculated whenever the grades change.
REQUIRED_TEXT_FIELDS = ('pupil_name', 'grade_level', 'section', 'school_year')
OPTIONAL_TEXT_FIELDS = ('lrn', 'class_adviser')
GRADE_KEYS = ('Q1', 'Q2', 'Q3', 'Q4', 'final')

# Parts of a filled-out SF10-ES stored under the record's "details" (see frontend
# pages/form137/sheet.jsx). "blocks" holds the eight year blocks of the sheet (four a page), "certifications" the boxes on its back; "other_years" holds the
# school years of a scanned form other than the one the record is filed under.
DETAIL_FIELDS = ('name_ext', 'middle_name', 'birthdate', 'sex', 'eligibility', 'blocks', 'certifications', 'total_pages', 'other_years')
DETAIL_MAX_LENGTH = 100
DETAIL_MAX_KEY = 40
DETAIL_MAX_ITEMS = 40
DETAIL_MAX_DEPTH = 5


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def records_list(request):
    if request.user.missing_class:
        return no_class_assigned()
    filters = {
        'grade_level': query_param(request, 'grade'),
        'section': query_param(request, 'section'),
        'school_year': query_param(request, 'school_year'),
        **request.user.class_scope(),
    }
    return Response(db.list_records(filters, page=page_param(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def records_search(request):
    if request.user.missing_class:
        return no_class_assigned()
    q = query_param(request, 'q')
    if not q:
        return detail('q parameter required.', 400)
    filters = {
        'grade_level': query_param(request, 'grade'),
        'section': query_param(request, 'section'),
        'school_year': query_param(request, 'school_year'),
        **request.user.class_scope(),   # a teacher's own class overrides the filters
    }
    results, total = db.search_records(q, filters)
    # "count" is how many are returned; "total" how many match, which can be more than the limit
    return Response({'query': q, 'count': len(results), 'total': total, 'limit': db.SEARCH_LIMIT, 'results': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def records_options(request):
    """Values to offer in the grade, section and school-year filters."""
    if request.user.missing_class:
        return no_class_assigned()
    return Response(db.record_options(request.user.class_scope()))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def record_detail(request, record_id):
    record = db.get_record(record_id)
    if not record:
        return not_found()
    if not request.user.can_access(record):
        return detail('You can only view records of your assigned class.', 403)
    return Response(record)


def _clean_grades(grades):
    """Validated copy of a {subject: {Q1..Q4, final}} grade sheet, or None if it's malformed."""
    if not isinstance(grades, dict):
        return None
    cleaned = {}
    for subject, values in grades.items():
        if not str(subject).strip() or not isinstance(values, dict) or set(values) - set(GRADE_KEYS):
            return None
        cleaned[str(subject).strip()] = {key: str(values.get(key) or '').strip() or NA for key in GRADE_KEYS}
    return grading.clean_subjects(cleaned)


def _record_updates(data):
    """(updates, error message) from an edit request."""
    updates = {}
    for field in REQUIRED_TEXT_FIELDS + OPTIONAL_TEXT_FIELDS:
        if field in data:
            value = str(data[field] or '').strip()
            if not value and field in REQUIRED_TEXT_FIELDS:
                return None, f'{field} cannot be blank.'
            updates[field] = identity.clean_lrn(value) if field == 'lrn' else value
    if 'grades' in data:
        grades = _clean_grades(data['grades'])
        if grades is None:
            return None, 'grades must map each subject to its Q1, Q2, Q3, Q4 and final values.'
        updates['grades'] = grades
        updates['general_average'] = grading.compute_general_average(grades)
        updates['remarks'] = grading.remarks_for(updates['general_average'], grades)
    if 'grading_period' in data:
        if data['grading_period'] not in PERIOD_KEYS:
            return None, 'grading_period must be "quarter" or "term".'
        updates['grading_period'] = data['grading_period']
    if 'details' in data:
        updates['details'] = _clean_details(data['details'])
    if not updates:
        return None, 'Nothing to update.'
    return updates, None


def _bounded(value, depth=0):
    """
    A copy of a JSON value kept to a safe size: text is trimmed and cut to DETAIL_MAX_LENGTH,
    lists and objects to DETAIL_MAX_ITEMS entries, and nesting stops at DETAIL_MAX_DEPTH.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value.strip()[:DETAIL_MAX_LENGTH]
    if depth >= DETAIL_MAX_DEPTH:
        return None
    if isinstance(value, list):
        return [_bounded(item, depth + 1) for item in value[:DETAIL_MAX_ITEMS]]
    if isinstance(value, dict):
        return {str(key)[:DETAIL_MAX_KEY]: _bounded(item, depth + 1) for key, item in list(value.items())[:DETAIL_MAX_ITEMS]}
    return str(value)[:DETAIL_MAX_LENGTH]


def _clean_details(details):
    """
    What a filled-out SF10-ES holds beside the record's own grades: the learner's other
    personal details, the eligibility section, and every year block as typed, so the sheet
    can be shown again for editing and printing. Unknown top-level keys are dropped and
    everything kept is cut to a bounded size.
    """
    details = details if isinstance(details, dict) else {}
    return {key: _bounded(details[key]) for key in DETAIL_FIELDS if key in details}


def _q4_problem(grading_period, grades):
    """A message if a record kept in terms has a Q4 grade (terms are Q1 to Q3), else None."""
    if grading_period != TERM:
        return None
    subject = next((s for s, values in (grades or {}).items() if not is_na(values.get('Q4'))), None)
    return f'{subject}: a record kept in terms has no Q4 grade.' if subject else None


def _bad_grade(grades, saved=None):
    """
    The first grade that isn't a number from 0 to 100, as (subject, value), or None. With the
    `saved` grades, values that haven't changed are passed over, so an old record with an
    odd value can still be edited elsewhere.
    """
    for subject, values in grades.items():
        for key, value in values.items():
            if value == ((saved or {}).get(subject) or {}).get(key):
                continue
            if not grading.is_valid_grade(value):
                return subject, value
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_create(request):
    """Save a record typed into the on-screen Form 137. There is no scan behind it."""
    data = request.data
    blank = [field for field in REQUIRED_TEXT_FIELDS if not str(data.get(field) or '').strip()]
    if blank:
        return detail(f'{blank[0]} cannot be blank.', 400)
    record, error = _record_updates(data)
    if error:
        return detail(error, 400)
    if not record.get('grades'):
        return detail('Enter at least one subject with its grades.', 400)
    bad = _bad_grade(record['grades'])
    if bad:
        return detail(f'{bad[0]}: "{bad[1]}" is not a grade from 0 to 100.', 400)
    record.setdefault('grading_period', QUARTER)
    problem = _q4_problem(record['grading_period'], record['grades'])
    if problem:
        return detail(problem, 400)
    refusal = outside_own_class(request.user, record)
    if refusal:
        return refusal
    problem = identity.lrn_problem(record.get('lrn'))
    if problem:
        return detail(problem, 400)
    problem = identity.identity_problem(record)
    if problem:
        return detail(problem, 409)

    record_id = db.create_record({
        **record, 'details': _clean_details(data.get('details')), 'uploaded_by': request.user.username,
    })
    db.log_action('ENCODE', request.user.username, {
        'record_id': record_id, 'pupil': record['pupil_name'], 'grade': record['grade_level'],
    })
    return Response(db.get_record(record_id), status=201)


def _identity_problem_of_edit(record, updates):
    """(message, status) if an edit gives the record an LRN or identity that clashes, else None."""
    if not any(updates.get(f, record.get(f)) != record.get(f) for f in ('pupil_name', 'lrn', 'grade_level', 'school_year')):
        return None
    merged = {**record, **updates}
    if 'lrn' in updates and updates['lrn'] != record.get('lrn'):
        problem = identity.lrn_problem(merged.get('lrn'))
        if problem:
            return problem, 400
    problem = identity.identity_problem(merged, exclude_id=record['record_id'])
    return (problem, 409) if problem else None


def _is_typed(record):
    """True for a record typed into the on-screen Form 137, which has no scan behind it."""
    return not record.get('scan_id')


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def record_update(request, record_id):
    """
    Edit a record. The OIC and Admin Staff may edit any record. A teacher may edit only the
    typed-in forms of their own class, and can't move one to another class.
    """
    record = db.get_record(record_id)
    if not record:
        return not_found()
    user = request.user
    if user.is_teacher:
        if not _is_typed(record):
            return detail('Only the OIC or Admin Staff can edit a scanned record.', 403)
        refusal = outside_own_class(user, record)
        if refusal:
            return refusal

    updates, error = _record_updates(request.data)
    if error:
        return detail(error, 400)
    if is_archived(record):
        # Only the pupil's details of an archived form can change; an empty grade sheet sent along is ignored,
        # so its average and remarks are not recalculated
        if updates.get('grades'):
            return detail('An archived form keeps no grades.', 400)
        for field in ('grades', 'general_average', 'remarks', 'grading_period'):
            updates.pop(field, None)
        if 'details' in updates:
            updates['details']['archive_only'] = True
        if not updates:
            return detail('Nothing to update.', 400)
    if 'grades' in updates:
        if _is_typed(record) and not updates['grades']:
            return detail('Enter at least one subject with its grades.', 400)
        bad = _bad_grade(updates['grades'], record.get('grades'))
        if bad:
            return detail(f'{bad[0]}: "{bad[1]}" is not a grade from 0 to 100.', 400)
    problem = _q4_problem(updates.get('grading_period', grading_period_of(record)), updates.get('grades', record.get('grades')))
    if problem:
        return detail(problem, 400)
    problem = _identity_problem_of_edit(record, updates)
    if problem:
        return detail(*problem)
    if user.is_teacher:
        refusal = outside_own_class(user, {**record, **updates})
        if refusal:
            return refusal
    db.update_record(record_id, updates)
    details = {
        'record_id': record_id, 'pupil': record.get('pupil_name'), 'fields': sorted(updates),
        'changes': audit.field_changes(record, updates, [f for f in updates if f not in ('grades', 'details')]),
    }
    if 'grades' in updates:
        details['grade_changes'] = audit.grade_changes(record.get('grades') or {}, updates['grades'])
    db.log_action('EDIT', request.user.username, details)
    return Response(db.get_record(record_id))


@api_view(['DELETE'])
@permission_classes([IsOICOrAdmin])
def record_delete(request, record_id):
    record = db.get_record(record_id)
    if not record:
        return not_found()
    if not db.delete_record(record_id):
        return detail('Delete failed.', 500)
    # The scan is kept: the original form is part of the audit trail. It can be purged later
    # with "manage.py cleanup_scans --deleted-days N".
    scan_id = record.get('scan_id')
    if scan_id:
        db.mark_scan_record_deleted(scan_id, request.user.username)
    db.log_action('DELETE', request.user.username, {
        'record_id': record_id, 'pupil': record.get('pupil_name'), 'scan_kept': bool(scan_id),
        'record': audit.record_snapshot(record),
    })
    return Response(status=204)
