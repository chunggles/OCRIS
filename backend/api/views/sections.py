from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..models import OCRISUser
from ..serializers import UserSerializer
from ..constants import GRADE_LEVELS
from ..permissions import IsOICOrAdmin
from ..utils.http import detail, not_found

MAX_NAME_LENGTH = 50


def _teachers_of(grade_level, name):
    """Teacher accounts assigned to this class. Sections are matched by name, ignoring case."""
    return OCRISUser.objects.filter(role=OCRISUser.TEACHER, assigned_grade=grade_level, assigned_section__iexact=name)


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
    """The section tree: each grade level with the sections under it, and how many records and teachers use each."""
    tree = db.section_tree()
    record_counts = db.section_record_counts()
    for node in tree:
        for section in node['sections']:
            section['records'] = record_counts.get((node['grade_level'], section['name'].casefold()), 0)
            section['teachers'] = _teachers_of(node['grade_level'], section['name']).count()
    return Response(tree)


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
    """
    Rename a section or move it to another grade level. Records and teacher accounts are matched
    to a section by its name, so they are changed with it and stay linked.
    """
    name, grade_level, error = _section_fields(request.data, current=section)
    if error:
        return detail(error, 400)
    old_grade, old_name = section['grade_level'], section['name']
    moved_records, moved_teachers = 0, 0
    if (grade_level, name) != (old_grade, old_name):
        moved_records = db.move_records_of_section(old_grade, old_name, grade_level, name)
        for teacher in _teachers_of(old_grade, old_name):
            teacher.assigned_grade, teacher.assigned_section = grade_level, name
            teacher.save(update_fields=['assigned_grade', 'assigned_section'])
            db.upsert_user_in_mongo(UserSerializer(teacher).data)
            moved_teachers += 1
    db.update_section(section['section_id'], name, grade_level)
    db.log_action('EDIT_SECTION', request.user.username, {
        'section': name, 'grade': grade_level, 'was': f'{old_grade} — {old_name}',
        'records_moved': moved_records, 'teachers_moved': moved_teachers,
    })
    return Response({**db.get_section(section['section_id']), 'records': moved_records, 'teachers': moved_teachers})


def _delete_section(request, section):
    """
    Remove a section from the list. A section with teachers assigned can't be removed, or they
    would lose their class. Records keep the section as plain text, so they stay intact.
    """
    teachers = list(_teachers_of(section['grade_level'], section['name']))
    if teachers:
        names = ', '.join(t.get_full_name() or t.username for t in teachers)
        return detail(f"{section['name']} is the class of {names}. Assign them to another section first.", 409)
    db.delete_section(section['section_id'])
    db.log_action('DELETE_SECTION', request.user.username, {
        'section': section['name'], 'grade': section['grade_level'],
        'records_kept': db.count_records_in_section(section['grade_level'], section['name']),
    })
    return Response(status=204)
