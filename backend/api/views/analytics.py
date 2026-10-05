from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import PASSING_GRADE
from ..utils.http import no_class_assigned, query_param


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_dashboard(request):
    if request.user.missing_class:
        return no_class_assigned()
    scope = request.user.class_scope()  # a teacher's own class overrides the grade filter
    filters = {
        'school_year': query_param(request, 'school_year'),
        'grade_level': query_param(request, 'grade'),
        **scope,
    }
    data = db.get_analytics(filters)
    flags = [
        {'subject': subject, 'mean': mean, 'grade_level': filters['grade_level'] or 'All'}
        for subject, mean in data.get('subject_means', {}).items()
        if mean < PASSING_GRADE
    ]
    return Response({**data, 'intervention_flags': flags, 'pending_scans': db.count_pending_scans(scope)})
