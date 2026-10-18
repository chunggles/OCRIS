from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..authentication import require_request_header, start_session
from ..models import AuthAttempt, LoginSession, OCRISUser
from ..serializers import LoginSerializer, UserSerializer
from ..services import accounts
from ..utils.http import detail

RESET_ACKNOWLEDGED = 'If that account exists, the OIC has been told and will give you a new temporary password.'


def _too_many(seconds):
    response = detail(accounts.wait_message(seconds), 429)
    response['Retry-After'] = str(seconds)
    return response


def _cookie_args():
    return {'secure': settings.REQUIRE_HTTPS, 'samesite': settings.AUTH_COOKIE_SAMESITE}


@api_view(['POST'])
@authentication_classes([])   # signing in never depends on an earlier cookie, which may be stale
@permission_classes([AllowAny])
def login_view(request):
    require_request_header(request)
    username = str(request.data.get('username') or '').strip()[:150]
    ip = accounts.client_ip(request)
    wait = accounts.lockout_seconds(AuthAttempt.LOGIN, username, ip)
    if wait:
        return _too_many(wait)

    s = LoginSerializer(data=request.data)
    if not s.is_valid():
        accounts.record_attempt(AuthAttempt.LOGIN, username, ip)
        db.log_action('LOGIN_FAILED', username or '(blank)', {'ip': ip})
        if accounts.lockout_seconds(AuthAttempt.LOGIN, username, ip):
            db.log_action('LOGIN_LOCKED', username or '(blank)', {'ip': ip, 'minutes': settings.LOGIN_LOCKOUT_MINUTES})
        return Response(s.errors, status=400)

    user = s.validated_data['user']
    accounts.clear_failures(user.username)
    _, cookie = start_session(user, request)
    update_last_login(None, user)  # shown as "Last login" in User Management
    db.log_action('LOGIN', user.username, {'role': user.role, 'ip': ip})
    response = Response({'user': _own_account(user)})
    response.set_cookie(settings.AUTH_COOKIE_NAME, cookie, max_age=int(settings.TOKEN_TTL_HOURS * 3600),
                        httponly=True, **_cookie_args())
    return response


def _own_account(user):
    """The signed-in user, with the minutes a session may go unused (the app signs out after them)."""
    return {**UserSerializer(user).data, 'idle_timeout_minutes': settings.IDLE_TIMEOUT_MINUTES}


def _signed_out(message):
    response = Response({'detail': message})
    response.delete_cookie(settings.AUTH_COOKIE_NAME, samesite=settings.AUTH_COOKIE_SAMESITE)
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Sign out of this device only; the other devices of the user stay signed in."""
    if request.auth:
        LoginSession.objects.filter(pk=request.auth.pk).delete()
    db.log_action('LOGOUT', request.user.username)
    return _signed_out('Logged out.')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_all_view(request):
    """Sign out of every device."""
    LoginSession.objects.filter(user=request.user).delete()
    db.log_action('LOGOUT', request.user.username, {'all_devices': True})
    return _signed_out('Logged out of every device.')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(_own_account(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change your own password. The current password is required. Your other devices are signed out."""
    current = request.data.get('current_password') or ''
    new = request.data.get('new_password') or ''
    if not request.user.check_password(current):
        return detail('Your current password is incorrect.', 400)
    if new == current:
        return detail('The new password must be different from the current one.', 400)
    problems = accounts.password_problems(new, request.user)
    if problems:
        return Response({'detail': ' '.join(problems), 'problems': problems}, status=400)
    request.user.set_password(new)
    request.user.must_change_password = False
    request.user.save(update_fields=['password', 'must_change_password'])
    LoginSession.objects.filter(user=request.user).exclude(pk=getattr(request.auth, 'pk', None)).delete()
    db.log_action('CHANGE_PASSWORD', request.user.username)
    return Response({'detail': 'Password changed.', 'user': _own_account(request.user)})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """
    A user who cannot sign in asks for a new temporary password. OCRIS sends no email: the
    request shows up on the User Management page of the OIC. The answer is the same whether or
    not the account exists, so the form cannot be used to find out who has an account.
    """
    require_request_header(request)
    username = str(request.data.get('username') or '').strip()[:150]
    ip = accounts.client_ip(request)
    wait = accounts.lockout_seconds(AuthAttempt.RESET, username, ip)
    if wait:
        return _too_many(wait)
    accounts.record_attempt(AuthAttempt.RESET, username, ip)
    user = OCRISUser.objects.filter(username__iexact=username, is_active=True).first() if username else None
    if user:
        user.password_reset_requested_at = timezone.now()
        user.save(update_fields=['password_reset_requested_at'])
        db.log_action('PASSWORD_RESET_REQUEST', user.username, {'ip': ip})
    return Response({'detail': RESET_ACKNOWLEDGED})
