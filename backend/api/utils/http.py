"""Request parsing and response shortcuts shared by the views."""
from rest_framework.response import Response

NO_CLASS_MESSAGE = 'Your account has no class assigned yet. Ask the OIC to assign your grade and section.'


def query_param(request, name):
    return request.query_params.get(name, '').strip()


def page_param(request):
    """The ?page= number, falling back to 1 when missing or invalid."""
    try:
        return max(int(request.query_params.get('page', 1)), 1)
    except (TypeError, ValueError):
        return 1


def detail(message, status):
    return Response({'detail': message}, status=status)


def not_found(message='Not found.'):
    return detail(message, 404)


def no_class_assigned():
    return detail(NO_CLASS_MESSAGE, 403)
