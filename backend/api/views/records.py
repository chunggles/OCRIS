from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import NA
from ..permissions import IsOICOrAdmin
from ..services import grading, storage
from ..utils.http import detail, no_class_assigned, not_found, outside_own_class, page_param, query_param

# Fields that may be changed on a saved record. The average and remarks are never set
# directly; they are recalculated whenever the grades change.
REQUIRED_TEXT_FIELDS = ('pupil_name', 'grade_level', 'section', 'school_year')
OPTIONAL_TEXT_FIELDS = ('lrn', 'class_adviser')
GRADE_KEYS = ('Q1', 'Q2', 'Q3', 'Q4', 'final')

# Parts of a filled-out SF10-ES stored under the record's "details" (see frontend
# pages/form137/sheet.jsx). "blocks" holds the four year blocks of the sheet.
DETAIL_FIELDS = ('name_ext', 'middle_name', 'birthdate', 'sex', 'eligibility', 'blocks')
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
    return cleaned


def _record_updates(data):
    """(updates, error message) from an edit request."""
    updates = {}
    for field in REQUIRED_TEXT_FIELDS + OPTIONAL_TEXT_FIELDS:
        if field in data:
            value = str(data[field] or '').strip()
            if not value and field in REQUIRED_TEXT_FIELDS:
                return None, f'{field} cannot be blank.'
            updates[field] = value
    if 'grades' in data:
        grades = _clean_grades(data['grades'])
        if grades is None:
            return None, 'grades must map each subject to its Q1, Q2, Q3, Q4 and final values.'
        updates['grades'] = grades
        updates['general_average'] = grading.compute_general_average(grades)
        updates['remarks'] = grading.remarks_for(updates['general_average'], grades)
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


def _bad_grade(grades):
    """The first typed grade that isn't a number from 0 to 100, as (subject, value), or None."""
    for subject, values in grades.items():
        for value in values.values():
            if value == NA:
                continue
            try:
                valid = 0 <= float(value) <= 100
            except ValueError:
                valid = False
            if not valid:
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
    refusal = outside_own_class(request.user, record)
    if refusal:
        return refusal

    record_id = db.create_record({
        **record, 'details': _clean_details(data.get('details')), 'uploaded_by': request.user.username,
    })
    db.log_action('ENCODE', request.user.username, {
        'record_id': record_id, 'pupil': record['pupil_name'], 'grade': record['grade_level'],
    })
    return Response(db.get_record(record_id), status=201)


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
    if 'grades' in updates and _is_typed(record):
        if not updates['grades']:
            return detail('Enter at least one subject with its grades.', 400)
        bad = _bad_grade(updates['grades'])
        if bad:
            return detail(f'{bad[0]}: "{bad[1]}" is not a grade from 0 to 100.', 400)
    if user.is_teacher:
        refusal = outside_own_class(user, {**record, **updates})
        if refusal:
            return refusal
    db.update_record(record_id, updates)
    db.log_action('EDIT', request.user.username, {'record_id': record_id, 'fields': sorted(updates)})
    return Response(db.get_record(record_id))


@api_view(['DELETE'])
@permission_classes([IsOICOrAdmin])
def record_delete(request, record_id):
    record = db.get_record(record_id)
    if not record:
        return not_found()
    if not db.delete_record(record_id):
        return detail('Delete failed.', 500)
    _delete_scan_of(record)
    db.log_action('DELETE', request.user.username, {'record_id': record_id, 'pupil': record.get('pupil_name')})
    return Response(status=204)


def _delete_scan_of(record):
    """Remove the record's scan and its image too, so no copy of the pupil's form is left behind."""
    scan_id = record.get('scan_id')
    scan = db.get_scan(scan_id, fields=['filename']) if scan_id else None
    if not scan:
        return
    path = storage.find_scan_file(scan.get('filename') or '')
    if path:
        storage.discard(path)
    db.delete_scan(scan_id)
