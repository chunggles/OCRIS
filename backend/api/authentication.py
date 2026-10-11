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


def session_expired(session):
    return timezone.now() - session.created > timedelta(hours=settings.TOKEN_TTL_HOURS)


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
    Authenticates the sign-in cookie. A cookie that is unknown or expired counts as no sign-in,
    so the request gets 401 and the app returns to the login screen.
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
        if user.must_change_password:
            match = getattr(request._request, 'resolver_match', None)
            if not match or match.url_name not in ALLOWED_BEFORE_PASSWORD_CHANGE:
                raise PermissionDenied({'detail': 'Change your temporary password before continuing.', 'code': PASSWORD_CHANGE_REQUIRED})
        return user, session

    def authenticate_header(self, request):
        return 'Cookie'
