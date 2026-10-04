from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..permissions import IsOICOrAdmin
from ..utils.http import detail, not_found, page_param, query_param


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def records_list(request):
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
    q = query_param(request, 'q')
    if not q:
        return detail('q parameter required.', 400)
    results = db.search_records(q, request.user.class_scope())
    return Response({'query': q, 'count': len(results), 'results': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def record_detail(request, record_id):
    record = db.get_record(record_id)
    if not record:
        return not_found()
    return Response(record)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsOICOrAdmin])
def record_update(request, record_id):
    if not db.get_record(record_id):
        return not_found()
    if not db.update_record(record_id, dict(request.data)):
        return detail('Update failed.', 500)
    db.log_action('EDIT', request.user.username, {'record_id': record_id})
    return Response({'detail': 'Updated.'})


@api_view(['DELETE'])
@permission_classes([IsOICOrAdmin])
def record_delete(request, record_id):
    record = db.get_record(record_id)
    if not record:
        return not_found()
    if not db.delete_record(record_id):
        return detail('Delete failed.', 500)
    db.log_action('DELETE', request.user.username, {'record_id': record_id, 'pupil': record.get('pupil_name')})
    return Response(status=204)
