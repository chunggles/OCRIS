from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import db
from ..constants import PUPIL_KEYS
from ..ocr.engine import OCRError, compute_confidence_summary, get_image_quality, run_ocr
from ..serializers import ValidationSubmitSerializer
from ..services import grading, storage
from ..utils.http import detail, no_class_assigned, not_found, page_param


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_quality(request):
    """Analyse an image before OCR. Nothing is saved."""
    file = request.FILES.get('file')
    if not file:
        return detail('No file provided.', 400)
    return Response(get_image_quality(file))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_upload(request):
    file = request.FILES.get('file')
    if not file:
        return detail('No file provided.', 400)

    stored_name, path = storage.save_upload(file)
    try:
        fields = run_ocr(str(path))
    except OCRError as e:
        storage.discard(path)  # nothing was extracted, so don't keep the file
        return detail(str(e), 422)
    quality = get_image_quality(str(path))
    summary = compute_confidence_summary(fields)
    pupil = {key: request.data.get(key, '') for key in PUPIL_KEYS}

    scan_id = db.create_scan({
        **pupil,
        'filename': stored_name,
        'original_name': file.name,
        'file_size_bytes': file.size,
        'uploaded_by': request.user.username,
        'ocr_fields': fields,
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
    return Response({'scan_id': scan_id, 'quality': quality, 'fields': fields, 'summary': summary})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ocr_validate(request):
    s = ValidationSubmitSerializer(data=request.data)
    if not s.is_valid():
        return Response(s.errors, status=400)
    data = s.validated_data
    scan_id = data['scan_id']

    scan = db.get_scan(scan_id)
    if not scan:
        return not_found('Scan not found. Upload the form again.')
    if scan.get('outcome') == 'saved':
        # Saving the same scan twice would create a duplicate record
        return detail(f"This scan was already saved as record {scan.get('record_id')}.", 409)

    corrections = {c['field']: c['corrected_val'] for c in data.get('corrections', [])}
    grades = grading.build_grades(scan.get('ocr_fields', []), corrections)
    general_average = grading.compute_general_average(grades)
    remarks = grading.remarks_for(general_average, grades)

    record_id = db.create_record({
        'pupil_name': data['pupil_name'],
        'lrn': data.get('lrn', ''),
        'grade_level': data['grade_level'],
        'section': data['section'],
        'school_year': data['school_year'],
        'grades': grades,
        'general_average': general_average,
        'remarks': remarks,
        'uploaded_by': request.user.username,
        'scan_id': scan_id,
        'corrections': corrections,
    })
    db.mark_scan_saved(scan_id, record_id, len(corrections))
    db.log_action('VALIDATE', request.user.username, {
        'scan_id': scan_id,
        'record_id': record_id,
        'corrections': len(corrections),
        'pupil': data['pupil_name'],
        'grade': data['grade_level'],
    })
    return Response({'record_id': record_id, 'general_average': general_average, 'remarks': remarks})


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
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=download_name)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_history(request):
    if request.user.missing_class:
        return no_class_assigned()
    return Response(db.list_scans(request.user.class_scope(), page=page_param(request)))
