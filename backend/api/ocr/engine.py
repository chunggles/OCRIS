"""
OCR entry points used by the views: run Tesseract on a scan, check image quality,
and summarise confidence. Failures raise OCRError with a message safe to show users.

Grades are read cell by cell from the ruled grade table (see table.py). Scans without
a detectable table fall back to parsing the page's free text line by line.
"""
import logging

from django.conf import settings
from PIL import UnidentifiedImageError

from .parser import parse_grade_lines
from .pupil import Page, extract_pupil_info

try:
    import pytesseract
    from .preprocess import get_image_quality, load_page, prepare_for_text
    from .table import parse_grade_table
    TESSERACT_AVAILABLE = True
    if getattr(settings, 'TESSERACT_CMD', ''):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
except ImportError:
    TESSERACT_AVAILABLE = False

    def get_image_quality(image_path):
        return {'error': 'Tesseract/Pillow is not installed.', 'overall_ok': False, 'metrics': []}

logger = logging.getLogger(__name__)

TESSERACT_CONFIG = '--psm 6 --oem 1'
RETRY_BELOW_CONF = 60  # re-run with aggressive preprocessing when average confidence is this low


class OCRError(Exception):
    """OCR could not produce a usable result. The message is shown to the user."""


def run_ocr(image_path):
    if not TESSERACT_AVAILABLE:
        raise OCRError('The OCR engine is not installed on the server.')
    try:
        page, dpi = load_page(image_path)
        words = Page(pytesseract.image_to_data(
            prepare_for_text(page, dpi), lang=_lang(), config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT))
        table = parse_grade_table(page)
        grades, year_levels = table if table else (_grades_from_text(page, dpi), [])
    except UnidentifiedImageError:
        raise OCRError("This file couldn't be read as an image. Upload the scan as a JPG or PNG.")
    except pytesseract.TesseractNotFoundError:
        raise OCRError('The OCR engine (Tesseract) was not found on the server. Set TESSERACT_CMD in the backend .env.')
    except Exception as e:
        logger.exception(f'OCR failed: {e}')
        raise OCRError('OCR failed on this scan. Try rescanning it.')

    if not grades:
        raise OCRError('No grade rows were found on this scan. Check that the whole grade table is visible and try rescanning.')
    return extract_pupil_info(words, year_levels) + grades


def _lang():
    return getattr(settings, 'OCR_LANG', 'eng')


def _page_text(img):
    return pytesseract.image_to_string(img, lang=_lang(), config=TESSERACT_CONFIG)


def _grades_from_text(page, dpi):
    """Fallback for scans without a detectable grade table: parse subject lines from free text."""
    threshold = getattr(settings, 'OCR_CONFIDENCE_THRESHOLD', 90)
    grades = []
    for aggressive in (False, True):
        img = prepare_for_text(page, dpi, aggressive)
        text = _page_text(img)
        word_data = pytesseract.image_to_data(img, lang=_lang(), config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT)
        grades = parse_grade_lines(text, _word_confidences(word_data), threshold)
        if average_confidence(grades) >= RETRY_BELOW_CONF:
            break
    return grades


def _word_confidences(word_data):
    """Best confidence Tesseract reported for each distinct word."""
    confidences = {}
    for word, conf in zip(word_data['text'], word_data['conf']):
        word = word.strip()
        if word:
            conf = max(int(float(conf)), 0)
            confidences[word] = max(confidences.get(word, 0), conf)
    return confidences


def average_confidence(fields):
    confs = [f['conf'] for f in fields if f['conf'] > 0]
    return round(sum(confs) / len(confs), 1) if confs else 0


def compute_confidence_summary(fields):
    def count(status):
        return sum(1 for f in fields if f['status'] == status)
    return {
        'total': len(fields),
        'auto_approved': count('ok'),
        'flagged': count('warn'),
        'null_count': count('null'),
        'overall_conf': average_confidence(fields),
    }
