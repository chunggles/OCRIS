from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .. import db
from ..models import OCRISUser
from ..permissions import IsOIC, IsOICOrAdmin
from ..serializers import CreateUserSerializer, UserSerializer
from ..utils.http import detail, not_found


@api_view(['GET'])
@permission_classes([IsOICOrAdmin])
def users_list(request):
    users = OCRISUser.objects.all().order_by('last_name', 'first_name')
    data = UserSerializer(users, many=True).data
    db.sync_users_to_mongo(list(data))
    return Response(data)


@api_view(['POST'])
@permission_classes([IsOIC])
def users_create(request):
    s = CreateUserSerializer(data=request.data)
    if not s.is_valid():
        return Response(s.errors, status=400)
    user = s.save()
    user_data = UserSerializer(user).data
    db.log_action('CREATE_USER', request.user.username, {'new_user': user.username, 'role': user.role})
    db.upsert_user_in_mongo(user_data)
    return Response(user_data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsOIC])
def user_detail(request, user_id):
    user = OCRISUser.objects.filter(pk=user_id).first()
    if not user:
        return not_found()
    if request.method == 'GET':
        return Response(UserSerializer(user).data)
    if request.method == 'DELETE':
        return _delete_user(request, user)

    s = UserSerializer(user, data=request.data, partial=True)
    if not s.is_valid():
        return Response(s.errors, status=400)
    s.save()
    db.upsert_user_in_mongo(UserSerializer(user).data)
    return Response(s.data)


def _delete_user(request, user):
    """
    Permanently remove an account. Records, scans and audit entries keep the username as
    plain text, so they stay intact. You can't delete yourself or the last active OIC.
    """
    if user.pk == request.user.pk:
        return detail("You can't delete your own account.", 400)
    other_oics = OCRISUser.objects.filter(role=OCRISUser.OIC, is_active=True).exclude(pk=user.pk)
    if user.role == OCRISUser.OIC and not other_oics.exists():
        return detail("You can't delete the only active OIC account.", 400)

    username, role = user.username, user.role
    user.delete()
    db.delete_user_in_mongo(username)
    db.log_action('DELETE_USER', request.user.username, {'deleted_user': username, 'role': role})
    return Response(status=204)
