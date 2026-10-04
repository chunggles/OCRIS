from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import PASSING_GRADE
from ..utils.http import query_param


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_dashboard(request):
    school_year = query_param(request, 'school_year') or None
    grade_level = query_param(request, 'grade') or None
    data = db.get_analytics(school_year, grade_level)
    flags = [
        {'subject': subject, 'mean': mean, 'grade_level': grade_level or 'All'}
        for subject, mean in data.get('subject_means', {}).items()
        if mean < PASSING_GRADE
    ]
    return Response({**data, 'intervention_flags': flags})
