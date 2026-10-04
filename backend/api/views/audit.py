from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .. import db
from ..permissions import IsOICOrAdmin
from ..utils.http import page_param


@api_view(['GET'])
@permission_classes([IsOICOrAdmin])
def audit_log(request):
    return Response(db.list_audit(page=page_param(request)))
