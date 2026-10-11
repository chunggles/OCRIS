import mimetypes

from django.http import FileResponse
from django.utils.http import content_disposition_header
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import PUPIL_KEYS, is_na
from ..ocr.engine import OCRError, compute_confidence_summary, get_image_quality, read_scan
from ..serializers import ValidationSubmitSerializer
from ..services import crypto, grading, identity, maintenance, storage, uploads
from ..utils.http import detail, no_class_assigned, not_found, outside_own_class, page_param


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_quality(request):
    """Analyse an image before OCR. Nothing is saved."""
    try:
        uploads.check_request_size(request)
        file = request.FILES.get('file')
        if not file:
            return detail('No file provided.', 400)
        uploads.check_upload(file)
    except uploads.UploadRefused as e:
        return detail(e.message, e.status)
    return Response(get_image_quality(file))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_upload(request):
    try:
        uploads.check_request_size(request)
        file = request.FILES.get('file')
        if not file:
            return detail('No file provided.', 400)
        uploads.check_upload(file)
    except uploads.UploadRefused as e:
        return detail(e.message, e.status)
    pupil = {key: request.data.get(key, '') for key in PUPIL_KEYS}
    pupil['lrn'] = identity.clean_lrn(pupil['lrn'])
    refusal = outside_own_class(request.user, pupil)
    if refusal:
        return refusal
    problem = identity.lrn_problem(pupil['lrn'])
    if problem:
        return detail(problem, 400)

    maintenance.cleanup_if_due()
    stored_name, path = storage.save_upload(file)
    try:
        known_sections = [section['name'] for node in db.section_tree() for section in node['sections']]
        with storage.plain_copy(path) as readable:
            fields, page_text, notes = read_scan(str(readable), known_sections)
            quality = get_image_quality(str(readable))
    except OCRError as e:
        storage.discard(path)  # nothing was extracted, so do not keep the file
        return detail(str(e), 422)
    except crypto.CryptoError as e:
        storage.discard(path)
        return detail(str(e), 500)
    summary = compute_confidence_summary(fields)

    scan_id = db.create_scan({
        **pupil,
        'filename': stored_name,
        'original_name': file.name,
        'file_size_bytes': file.size,
        'uploaded_by': request.user.username,
        'ocr_fields': fields,
        'ocr_text': page_text,
        'notes': notes,
        'overall_conf': summary['overall_conf'],
        'flags_count': summary['flagged'],
        'null_count': summary['null_count'],
    })
    db.log_action('UPLOAD', request.user.username, {
        'scan_id': scan_id,
        'filename': file.name,
        'confidence': summary['overall_conf'],
        'pupil': pupil['pupil_name'],
    })
    return Response({'scan_id': scan_id, 'quality': quality, 'fields': fields, 'summary': summary, 'notes': notes})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_validate(request):
    s = ValidationSubmitSerializer(data=request.data)
    if not s.is_valid():
        return Response(s.errors, status=400)
    data = s.validated_data
    scan_id = data['scan_id']
    refusal = outside_own_class(request.user, data)
    if refusal:
        return refusal

    scan = db.get_scan(scan_id)
    if not scan:
        return not_found('Scan not found. Upload the form again.')
    if scan.get('outcome') == 'saved':
        # Saving the same scan twice would create a duplicate record
        return detail(f"This scan was already saved as record {scan.get('record_id')}.", 409)

    corrections = {c['field']: c['corrected_val'] for c in data.get('corrections', [])}
    bad = next(((f, v) for f, v in corrections.items() if f not in grading.PUPIL_FIELDS and not grading.is_valid_grade(v)), None)
    if bad:
        return detail(f'{bad[0]}: "{bad[1]}" is not a grade from 0 to 100.', 400)

    scan_name = next((f.get('value') for f in scan.get('ocr_fields', []) if f.get('field') == 'Pupil Name'), '')
    pupil_name = (data.get('pupil_name') or '').strip() or ('' if is_na(scan_name) else scan_name)
    if not pupil_name:
        return detail("The pupil's name is needed: type it, or check that it can be read from the form.", 400)
    lrn = identity.clean_lrn(data.get('lrn'))
    problem = identity.lrn_problem(lrn)
    if problem:
        return detail(problem, 400)
    problem = identity.identity_problem({**data, 'pupil_name': pupil_name, 'lrn': lrn})
    if problem:
        return detail(problem, 409)

    blocks = grading.build_year_blocks(scan.get('ocr_fields', []), corrections, data.get('renames'))
    grades, other_years = grading.choose_year_block(blocks, data['grade_level'])
    general_average = grading.compute_general_average(grades)
    remarks = grading.remarks_for(general_average, grades)

    record_id = db.create_record({
        'pupil_name': pupil_name,
        'lrn': lrn,
        'grade_level': data['grade_level'],
        'section': data['section'],
        'school_year': data['school_year'],
        'grades': grades,
        'general_average': general_average,
        'remarks': remarks,
        'uploaded_by': request.user.username,
        'scan_id': scan_id,
        'corrections': corrections,
        'details': {'other_years': other_years} if other_years else {},
    })
    db.mark_scan_saved(scan_id, record_id, len(corrections))
    db.log_action('VALIDATE', request.user.username, {
        'scan_id': scan_id,
        'record_id': record_id,
        'corrections': len(corrections),
        'corrected': _corrected_values(scan.get('ocr_fields', []), corrections),
        'pupil': pupil_name,
        'grade': data['grade_level'],
    })
    return Response({'record_id': record_id, 'pupil_name': pupil_name, 'general_average': general_average, 'remarks': remarks})


def _corrected_values(ocr_fields, corrections):
    """[{field, read, new}]: what the OCR read and what a person entered instead, for the audit log."""
    read = {f.get('field'): f.get('value') for f in ocr_fields}
    return [{'field': field, 'read': read.get(field), 'new': value} for field, value in list(corrections.items())[:200]]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_file(request, scan_id):
    scan = db.get_scan(scan_id, fields=['filename', 'original_name', 'grade_level', 'section', 'pupil_name'])
    if not scan or not scan.get('filename'):
        return not_found('Scan not found.')

    if not request.user.can_access(scan):
        return detail('You can only download forms for your assigned class.', 403)

    path = storage.find_scan_file(scan['filename'])
    if not path:
        return not_found('The uploaded file is no longer on the server.')

    download_name = scan.get('original_name') or path.name
    db.log_action('DOWNLOAD', request.user.username, {
        'scan_id': scan_id,
        'filename': download_name,
        'pupil': scan.get('pupil_name', ''),
    })
    try:
        stream = storage.open_stream(path)
    except crypto.CryptoError as e:
        return detail(str(e), 500)
    # A streamed object carries no name, so Django would not set these headers itself
    response = FileResponse(stream)
    response['Content-Type'] = mimetypes.guess_type(download_name)[0] or 'application/octet-stream'
    response['Content-Disposition'] = content_disposition_header(True, download_name)
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_history(request):
    if request.user.missing_class:
        return no_class_assigned()
    return Response(db.list_scans(request.user.class_scope(), page=page_param(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_scans(request):
    """The signed-in user's uploads that were read but not saved yet, so a refresh does not lose them."""
    return Response({'results': db.pending_scans_of(request.user.username)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_detail(request, scan_id):
    """What the reader found on an unsaved upload, to carry on from the extraction step."""
    scan = db.get_scan(scan_id, fields=[
        'scan_id', 'original_name', 'pupil_name', 'lrn', 'grade_level', 'section', 'school_year',
        'ocr_fields', 'notes', 'outcome', 'uploaded_by', 'filename'])
    if not scan:
        return not_found('Scan not found.')
    if not request.user.can_access(scan) or (request.user.is_teacher and scan.get('uploaded_by') != request.user.username):
        return detail('You can only open your own uploads.', 403)
    if scan.get('outcome') != 'pending':
        return detail('This upload was already finished.', 409)
    scan['summary'] = compute_confidence_summary(scan.get('ocr_fields', []))
    scan['notes'] = scan.get('notes', [])
    return Response(scan)
