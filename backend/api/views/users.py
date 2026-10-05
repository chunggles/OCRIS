from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .. import db
from ..models import OCRISUser
from ..permissions import IsOIC, IsOICOrAdmin
from ..serializers import MIN_PASSWORD_LENGTH, CreateUserSerializer, UserSerializer
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
    return _update_user(request, user)


def _is_last_active_oic(user):
    others = OCRISUser.objects.filter(role=OCRISUser.OIC, is_active=True).exclude(pk=user.pk)
    return user.role == OCRISUser.OIC and user.is_active and not others.exists()


def _update_user(request, user):
    """Edit an account. Sending "password" sets a new one and signs the user out everywhere."""
    data = request.data.copy()
    password = data.pop('password', None)
    if isinstance(password, list):  # form-encoded requests give a list
        password = password[0] if password else None
    if password is not None and len(password) < MIN_PASSWORD_LENGTH:
        return detail(f'The password must be at least {MIN_PASSWORD_LENGTH} characters.', 400)

    s = UserSerializer(user, data=data, partial=True)
    if not s.is_valid():
        return Response(s.errors, status=400)
    changes = s.validated_data
    losing_oic = changes.get('role', user.role) != OCRISUser.OIC or changes.get('is_active', True) is False
    if losing_oic and _is_last_active_oic(user):
        return detail('This is the only active OIC account. Make another user an OIC first.', 400)

    username_before = user.username
    s.save()
    if password is not None:
        user.set_password(password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        db.log_action('RESET_PASSWORD', request.user.username, {'target_user': user.username})
    if changes:
        if user.username != username_before:
            db.delete_user_in_mongo(username_before)
        db.log_action('EDIT_USER', request.user.username, {'target_user': user.username, 'fields': sorted(changes)})
    user_data = UserSerializer(user).data
    db.upsert_user_in_mongo(user_data)
    return Response(user_data)


def _delete_user(request, user):
    """
    Permanently remove an account. Records, scans and audit entries keep the username as
    plain text, so they stay intact. You can't delete yourself or the last active OIC.
    """
    if user.pk == request.user.pk:
        return detail("You can't delete your own account.", 400)
    if _is_last_active_oic(user):
        return detail("You can't delete the only active OIC account.", 400)

    username, role = user.username, user.role
    user.delete()
    db.delete_user_in_mongo(username)
    db.log_action('DELETE_USER', request.user.username, {'deleted_user': username, 'role': role})
    return Response(status=204)
