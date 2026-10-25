"""Checks of the running server, for the host and for setting it up."""
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..permissions import IsOIC
from ..services import accounts


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """For the host's health check: the server is up and answering. It does not touch the databases."""
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([IsOIC])
def client_address(request):
    """
    What the server sees of the caller's address, to set TRUSTED_PROXY_COUNT on a new host. Open it
    signed in as the OIC: `address_used` must be your own public address. If it is not, set
    TRUSTED_PROXY_COUNT to the number of `x_forwarded_for` entries from your address to the end.
    Behind Cloudflare (as on Render) that number is worked out in `suggested_trusted_proxy_count`.
    """
    forwarded = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    edge = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
    suggested = None
    if edge in forwarded:
        suggested = len(forwarded) - max(i for i, hop in enumerate(forwarded) if hop == edge)
    return Response({
        'address_used': accounts.client_ip(request),
        'trusted_proxy_count': settings.TRUSTED_PROXY_COUNT,
        'x_forwarded_for': forwarded,
        'remote_addr': request.META.get('REMOTE_ADDR', ''),
        'cf_connecting_ip': edge or None,
        'suggested_trusted_proxy_count': suggested,
    })
