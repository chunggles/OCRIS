from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..serializers import LoginSerializer, UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    s = LoginSerializer(data=request.data)
    if not s.is_valid():
        return Response(s.errors, status=400)
    user = s.validated_data['user']
    token, _ = Token.objects.get_or_create(user=user)
    db.log_action('LOGIN', user.username, {'role': user.role})
    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'role': user.role,
            'assigned_grade': user.assigned_grade,
            'assigned_section': user.assigned_section,
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)
