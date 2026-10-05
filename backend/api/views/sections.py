from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import GRADE_LEVELS
from ..permissions import IsOICOrAdmin
from ..utils.http import detail, not_found

MAX_NAME_LENGTH = 50


def _section_fields(data, current=None):
    """(name, grade level, error message) from an add or edit request. An edit keeps what it doesn't send."""
    current = current or {}
    name = ' '.join(str(data.get('name', current.get('name')) or '').split())
    grade_level = str(data.get('grade_level', current.get('grade_level')) or '').strip()
    if not name:
        return None, None, 'Enter a section name.'
    if len(name) > MAX_NAME_LENGTH:
        return None, None, f'The section name must be {MAX_NAME_LENGTH} characters or fewer.'
    if grade_level not in GRADE_LEVELS:
        return None, None, f'Choose a grade level from {GRADE_LEVELS[0]} to {GRADE_LEVELS[-1]}.'
    if db.find_section(name, grade_level, exclude_id=current.get('section_id')):
        return None, None, f'{grade_level} already has a section named {name}.'
    return name, grade_level, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sections_list(request):
    return Response(db.list_sections())


@api_view(['POST'])
@permission_classes([IsOICOrAdmin])
def sections_create(request):
    name, grade_level, error = _section_fields(request.data)
    if error:
        return detail(error, 400)
    section_id = db.create_section(name, grade_level)
    db.log_action('ADD_SECTION', request.user.username, {'section': name, 'grade': grade_level})
    return Response(db.get_section(section_id), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsOICOrAdmin])
def section_detail(request, section_id):
    section = db.get_section(section_id)
    if not section:
        return not_found()
    if request.method == 'DELETE':
        return _delete_section(request, section)
    return _update_section(request, section)


def _update_section(request, section):
    """Rename a section or move it to another grade level. Records and teacher accounts are not changed."""
    name, grade_level, error = _section_fields(request.data, current=section)
    if error:
        return detail(error, 400)
    db.update_section(section['section_id'], name, grade_level)
    db.log_action('EDIT_SECTION', request.user.username, {
        'section': name, 'grade': grade_level,
        'was': f"{section['grade_level']} — {section['name']}",
    })
    return Response(db.get_section(section['section_id']))


def _delete_section(request, section):
    """Remove a section from the list. Records keep the section as plain text, so they stay intact."""
    db.delete_section(section['section_id'])
    db.log_action('DELETE_SECTION', request.user.username, {'section': section['name'], 'grade': section['grade_level']})
    return Response(status=204)
