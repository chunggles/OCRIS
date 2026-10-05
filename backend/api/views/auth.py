from django.contrib.auth.models import update_last_login
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..serializers import MIN_PASSWORD_LENGTH, LoginSerializer, UserSerializer
from ..utils.http import detail


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    s = LoginSerializer(data=request.data)
    if not s.is_valid():
        return Response(s.errors, status=400)
    user = s.validated_data['user']
    token, created = Token.objects.get_or_create(user=user)
    if not created:
        # Signing in restarts the session clock (see ExpiringTokenAuthentication)
        Token.objects.filter(pk=token.pk).update(created=timezone.now())
    update_last_login(None, user)  # shown as "Last login" in User Management
    db.log_action('LOGIN', user.username, {'role': user.role})
    return Response({'token': token.key, 'user': UserSerializer(user).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change your own password. The current password is required."""
    current = request.data.get('current_password') or ''
    new = request.data.get('new_password') or ''
    if not request.user.check_password(current):
        return detail('Your current password is incorrect.', 400)
    if len(new) < MIN_PASSWORD_LENGTH:
        return detail(f'The new password must be at least {MIN_PASSWORD_LENGTH} characters.', 400)
    if new == current:
        return detail('The new password must be different from the current one.', 400)
    request.user.set_password(new)
    request.user.save(update_fields=['password'])
    db.log_action('CHANGE_PASSWORD', request.user.username)
    return Response({'detail': 'Password changed.'})
