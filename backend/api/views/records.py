from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import NA
from ..permissions import IsOICOrAdmin
from ..services import grading, storage
from ..utils.http import detail, no_class_assigned, not_found, page_param, query_param

# Fields an OIC or Admin may change on a saved record. The average and remarks are
# never set directly; they are recalculated whenever the grades change.
REQUIRED_TEXT_FIELDS = ('pupil_name', 'grade_level', 'section', 'school_year')
OPTIONAL_TEXT_FIELDS = ('lrn', 'class_adviser')
GRADE_KEYS = ('Q1', 'Q2', 'Q3', 'Q4', 'final')


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
    results = db.search_records(q, request.user.class_scope())
    return Response({'query': q, 'count': len(results), 'results': results})


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
    if not updates:
        return None, 'Nothing to update.'
    return updates, None


@api_view(['PUT', 'PATCH'])
@permission_classes([IsOICOrAdmin])
def record_update(request, record_id):
    if not db.get_record(record_id):
        return not_found()
    updates, error = _record_updates(request.data)
    if error:
        return detail(error, 400)
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
