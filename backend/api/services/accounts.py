"""Sign-in limits and password rules."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import AuthAttempt


def client_ip(request):
    """
    The caller's address. Behind a proxy the real address is in X-Forwarded-For; set
    TRUSTED_PROXY_COUNT to the number of proxies in front of the server (0 = none) so a
    caller cannot choose their own address by sending the header.
    """
    hops = settings.TRUSTED_PROXY_COUNT
    forwarded = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops][:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def _window():
    return timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def _seconds_left(attempts, limit):
    """Seconds until the oldest attempt that still counts leaves the window, or 0 if under the limit."""
    times = list(attempts.order_by('-at').values_list('at', flat=True)[:limit])
    if len(times) < limit:
        return 0
    return max(int((times[-1] + _window() - timezone.now()).total_seconds()), 0)


def lockout_seconds(kind, username, ip):
    """How long this username or address must wait before trying again; 0 when free to try."""
    since = timezone.now() - _window()
    recent = AuthAttempt.objects.filter(kind=kind, at__gte=since)
    if kind == AuthAttempt.RESET:
        return _seconds_left(recent.filter(ip=ip), settings.RESET_MAX_REQUESTS)
    return max(
        _seconds_left(recent.filter(username=username.lower()), settings.LOGIN_MAX_ATTEMPTS),
        _seconds_left(recent.filter(ip=ip), settings.LOGIN_MAX_ATTEMPTS_PER_IP),
    )


def record_attempt(kind, username, ip):
    AuthAttempt.objects.create(kind=kind, username=(username or '').lower()[:150], ip=ip)
    AuthAttempt.objects.filter(at__lt=timezone.now() - timedelta(days=1)).delete()


def clear_failures(username):
    AuthAttempt.objects.filter(kind=AuthAttempt.LOGIN, username=username.lower()).delete()


def wait_message(seconds):
    minutes = max((seconds + 59) // 60, 1)
    return f'Too many attempts. Try again in {minutes} minute{"s" if minutes != 1 else ""}.'


def password_problems(password, user=None):
    """Messages describing why a password is not acceptable; empty when it is fine."""
    try:
        validate_password(password, user)
    except ValidationError as e:
        return list(e.messages)
    return []
