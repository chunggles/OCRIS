"""
OCR entry points used by the views: run Tesseract on a scan, check image quality,
and summarise confidence. Failures raise OCRError with a message safe to show users.

Grades are read cell by cell from the ruled grade table (see table.py). Scans without
a detectable table fall back to parsing the page's free text line by line.
"""
import logging
import re

from django.conf import settings
from PIL import UnidentifiedImageError

from .parser import parse_grade_lines
from .pupil import Page, extract_pupil_info

try:
    import pytesseract
    from .preprocess import get_image_quality, load_page, prepare_for_text, prepare_grey_for_text, smoothed
    from .table import MAX_GRADE, MIN_GRADE, parse_grade_table
    TESSERACT_AVAILABLE = True
    if getattr(settings, 'TESSERACT_CMD', ''):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
except ImportError:
    TESSERACT_AVAILABLE = False

    def get_image_quality(image_path):
        return {'error': 'Tesseract/Pillow is not installed.', 'overall_ok': False, 'metrics': []}

logger = logging.getLogger(__name__)

TESSERACT_CONFIG = '--psm 6 --oem 1'
RETRY_BELOW_READ_SHARE = 0.85  # read a smoothed copy as well when fewer of the table's filled-in cells than this give a grade
RETRY_BELOW_CONF = 60  # re-run with aggressive preprocessing when average confidence is this low


class OCRError(Exception):
    """OCR could not produce a usable result. The message is shown to the user."""


MAX_PAGE_TEXT = 20000   # characters of page text kept with a scan for searching
BLOCK_NAME_RE = re.compile(r'Grade [1-6]|Block \d')
MAX_PAGES = 4           # pages of a PDF that are read; an SF10-ES is a front and a back


def run_ocr(image_path, known_sections=()):
    """Fields read from a scan; see read_scan()."""
    return read_scan(image_path, known_sections)[0]


def read_scan(image_path, known_sections=()):
    """
    (fields, page text, notes). The fields are the pupil's details, then every grade. The text is
    everything read off the first page, kept so records can be found by what is written on
    their form. The notes are things the person checking the form should know, such as a page
    that was skipped. known_sections are the section names set up in the system, used to
    correct a misread section name. The pupil's details are read from the first page; the
    grade tables of the further pages of a PDF are added after it.
    """
    if not TESSERACT_AVAILABLE:
        raise OCRError('The OCR engine is not installed on the server.')
    try:
        page, dpi, page_count = load_page(image_path)
        # The page's words are read twice, binarised and as plain grey. Each way loses different
        # small print, and the pupil's details are taken from whichever reading has them.
        words, grey_words = (_page_words(img) for img in (prepare_for_text(page, dpi), prepare_grey_for_text(page, dpi)))
        table = parse_grade_table(page)
        if table and _is_hard_to_read(table[0]):
            # Grain and faded ink break up the table. Read a smoothed copy too and keep the better result.
            again = parse_grade_table(smoothed(page, dpi))
            if again and _readability(again[0]) > _readability(table[0]):
                table = again
        grades, year_levels, notes = table if table else (_grades_from_text(page, dpi), [], [])
        if table and page_count > 1:
            grades, year_levels, notes = _add_later_pages(image_path, page_count, grades, year_levels, notes)
    except UnidentifiedImageError as e:
        raise OCRError(str(e))  # open_scan words these for the user
    except pytesseract.TesseractNotFoundError:
        raise OCRError('The OCR engine (Tesseract) was not found on the server. Set TESSERACT_CMD in the backend .env.')
    except Exception as e:
        logger.exception(f'OCR failed: {e}')
        raise OCRError('OCR failed on this scan. Try rescanning it.')

    if not grades:
        raise OCRError('No grade rows were found on this scan. Check that the whole grade table is visible and try rescanning.')
    if all(field['status'] == 'null' for field in grades):
        # e.g. an unfilled template; saving it would create a record with no grades at all
        raise OCRError('Every grade box on this form is empty. Check that you chose the filled-in form, not a blank one.')
    fields = extract_pupil_info(words, year_levels, known_sections, other_pages=[grey_words]) + grades
    # the fuller of the two readings of the page
    return fields, max(words.text, grey_words.text, key=len)[:MAX_PAGE_TEXT], notes


def _add_later_pages(image_path, page_count, grades, year_levels, notes):
    """
    The grade fields, year levels and notes of the first page with the grade tables of the
    PDF's further pages added (at most MAX_PAGES pages in all). A page without a grade table,
    or one that repeats learning areas already read, is left out and a note says so.
    """
    notes = list(notes)
    if page_count > MAX_PAGES:
        notes.append(f'This PDF has {page_count} pages. Only the first {MAX_PAGES} were read.')
    for index in range(1, min(page_count, MAX_PAGES)):
        number = index + 1
        later, _, _ = load_page(image_path, index)
        blocks_so_far = len({m.group(0) for f in grades if (m := BLOCK_NAME_RE.search(f['field']))})
        table = parse_grade_table(later, block_start=blocks_so_far + 1)   # keeps unnamed "Block n" labels apart
        if not table:
            notes.append(f'Page {number} has no grade table, so it was not read.')
            continue
        fields, levels, more_notes = table
        names = {f['field'] for f in grades}
        if any(f['field'] in names for f in fields):
            notes.append(f'Page {number} repeats learning areas already read from an earlier page, so it was not added. '
                         'Upload it as a separate form if it is another school year.')
            continue
        grades = grades + fields
        year_levels = year_levels + levels
        notes += [f'Page {number}: {note}' for note in more_notes]
        notes.append(f'Page {number}: {len(fields)} grade boxes were read and added.')
    return grades, year_levels, notes


def _page_words(img):
    return Page(pytesseract.image_to_data(img, lang=_lang(), config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT))


def _is_grade(value):
    return str(value).isdigit() and MIN_GRADE <= int(value) <= MAX_GRADE


def _readability(grades):
    """How well a grade table was read: (cells that gave a grade, of those auto-approved). Bigger is better."""
    return sum(1 for f in grades if _is_grade(f['value'])), sum(1 for f in grades if f['status'] == 'ok')


def _is_hard_to_read(grades):
    """
    True when too few of the table's filled-in cells came out as a grade at all. That points to
    grain or faded ink breaking up the page, not to grades that were read but with low confidence.
    """
    filled = sum(1 for f in grades if f['status'] != 'null')
    return filled == 0 or _readability(grades)[0] / filled < RETRY_BELOW_READ_SHARE


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
