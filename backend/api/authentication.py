import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import PermissionDenied

from .models import LoginSession

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
# What a user who still has a temporary password may do: see who they are, change it, or sign out
ALLOWED_BEFORE_PASSWORD_CHANGE = ('me', 'change-password', 'logout', 'logout-all')
PASSWORD_CHANGE_REQUIRED = 'password_change_required'
# A request with ?background=1 was made by the app on its own (its refresh of the signed-in user),
# so it does not count as use; the app sends it without the flag when the user typed or clicked since
BACKGROUND_PARAM = 'background'
ACTIVITY_RESOLUTION = timedelta(minutes=1)   # last_active is written at most this often (sooner for a short idle limit)


def session_expired(session):
    """Past TOKEN_TTL_HOURS since sign-in, or unused for IDLE_TIMEOUT_MINUTES (0: no idle limit)."""
    now = timezone.now()
    if now - session.created > timedelta(hours=settings.TOKEN_TTL_HOURS):
        return True
    idle = settings.IDLE_TIMEOUT_MINUTES
    return bool(idle) and now - session.last_active > timedelta(minutes=idle)


def _mark_used(session, request):
    now = timezone.now()
    idle = settings.IDLE_TIMEOUT_MINUTES
    resolution = min(ACTIVITY_RESOLUTION, timedelta(minutes=idle) / 4) if idle else ACTIVITY_RESOLUTION
    if request._request.GET.get(BACKGROUND_PARAM) != '1' and now - session.last_active >= resolution:
        LoginSession.objects.filter(pk=session.pk).update(last_active=now)


def start_session(user, request):
    """A new login for the user on this device. Other devices stay signed in."""
    return LoginSession.objects.create(
        key=secrets.token_urlsafe(48), user=user, user_agent=request.META.get('HTTP_USER_AGENT', '')[:200])


def require_request_header(request):
    """Refuse a request that lacks the header only the OCRIS site can add (see settings.py)."""
    if not request.META.get('HTTP_' + settings.REQUEST_HEADER.upper().replace('-', '_')):
        raise PermissionDenied('The request was refused because it did not come from the OCRIS site.')


class CookieSessionAuthentication(BaseAuthentication):
    """
    Authenticates the sign-in cookie. A cookie that is unknown or expired (too old, or unused for too
    long) counts as no sign-in, so the request gets 401 and the app returns to the login screen.
    """

    def authenticate(self, request):
        key = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not key:
            return None
        session = LoginSession.objects.select_related('user').filter(key=key).first()
        if session is None:
            return None
        if session_expired(session):
            session.delete()
            return None
        user = session.user
        if not user.is_active:
            return None
        if request.method not in SAFE_METHODS:
            require_request_header(request)
        _mark_used(session, request)
        if user.must_change_password:
            match = getattr(request._request, 'resolver_match', None)
            if not match or match.url_name not in ALLOWED_BEFORE_PASSWORD_CHANGE:
                raise PermissionDenied({'detail': 'Change your temporary password before continuing.', 'code': PASSWORD_CHANGE_REQUIRED})
        return user, session

    def authenticate_header(self, request):
        return 'Cookie'
