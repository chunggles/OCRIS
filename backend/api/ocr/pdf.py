"""
Opening an uploaded scan as an image, whether it is an image file or a PDF.

A PDF's first page is rendered to an image, so the rest of the OCR pipeline treats it like
any other scan. The form is expected to be on page 1; other pages are not read.
"""
import ctypes
import logging
import re
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

try:
    import pypdfium2
    import pypdfium2.raw as pdfium_raw
except ImportError:  # the system then reads image files only
    pypdfium2 = pdfium_raw = None

logger = logging.getLogger(__name__)

# PDFium must never be used by two threads at once, even on different files: doing so corrupts
# it or crashes the server. The web server handles requests in parallel, so every use is serialised.
_pdfium_lock = threading.Lock()

RENDER_DPI = 300
PDF_POINTS_PER_INCH = 72
MAX_RENDER_PIXELS = 4500  # longest side; keeps an oversized page from using too much memory
PDF_MAGIC = b'%PDF-'


def _is_pdf(source):
    """True if the file (a path or an open binary file) starts like a PDF."""
    if hasattr(source, 'read'):
        start = source.read(len(PDF_MAGIC))
        source.seek(0)
        return start == PDF_MAGIC
    with open(source, 'rb') as f:
        return f.read(len(PDF_MAGIC)) == PDF_MAGIC


def _render_first_page(source):
    """(image of page 1, number of pages). The image carries the DPI it was rendered at."""
    if pypdfium2 is None:
        raise UnidentifiedImageError('PDF support is not installed on the server.')
    # The file is read into memory first, so the PDF library never holds the stored file open
    # (an open handle stops a failed upload from being deleted on Windows).
    data = source.read() if hasattr(source, 'read') else Path(source).read_bytes()
    with _pdfium_lock:
        try:
            document = pypdfium2.PdfDocument(data)
        except pypdfium2.PdfiumError as e:
            logger.warning(f'PDF could not be opened: {e}')
            raise UnidentifiedImageError("This PDF couldn't be opened. It may be damaged or password-protected.")
        try:
            if len(document) == 0:
                raise UnidentifiedImageError('This PDF has no pages.')
            # A form filled in on a computer keeps its entries apart from the printed page: as
            # form fields, or as text boxes added on top. Both have to be drawn, or the page
            # comes out as the blank form.
            try:
                document.init_forms()   # must come before the page is loaded
                fields = True
            except Exception as e:      # a damaged form definition shouldn't stop the page being read
                logger.warning(f'PDF form fields could not be set up: {e}')
                fields = False
            page = document[0]
            scale = min(RENDER_DPI / PDF_POINTS_PER_INCH, MAX_RENDER_PIXELS / max(page.get_size()))
            image = page.render(scale=scale, may_draw_forms=fields).to_pil().convert('RGB')
            _draw_plain_text_boxes(page, image)
            image.info['dpi'] = (round(scale * PDF_POINTS_PER_INCH),) * 2
            return image, len(document)
        finally:
            document.close()


# ── Text boxes the PDF library doesn't draw ──────────────────────────────────
#
# A "FreeText" annotation is a text box laid over the page. Normally it carries a ready-made
# picture of itself (its appearance), which PDFium draws. Some tools write only the text, its
# rectangle and a style, and leave drawing to the viewer; PDFium skips those, so they are
# drawn here.

FONT_SIZE_RE = re.compile(r'(\d+(?:\.\d+)?)\s*pt|(\d+(?:\.\d+)?)\s+Tf')   # "6.5pt" in a style, "/Helv 6.5 Tf" in a DA
ALIGN_RE = re.compile(r'text-align\s*:\s*(left|center|right)', re.IGNORECASE)
COLOUR_RE = re.compile(r'color\s*:\s*#([0-9a-f]{6})', re.IGNORECASE)
DEFAULT_FONT_PT = 9
TEXT_BOX_PADDING_PT = 1
FONT_FILES = ('arial.ttf', 'Arial.ttf', 'LiberationSans-Regular.ttf', 'DejaVuSans.ttf')


def _font(pixels):
    for name in FONT_FILES:
        try:
            return ImageFont.truetype(name, pixels)
        except OSError:
            continue
    return ImageFont.load_default(pixels)


def _annotation_text(annotation, key):
    """The text stored under a key of an annotation ('' if there is none)."""
    size = pdfium_raw.FPDFAnnot_GetStringValue(annotation, key, None, 0)   # bytes, UTF-16 with a terminator
    if size <= 2:
        return ''
    buffer = ctypes.create_string_buffer(size)
    pdfium_raw.FPDFAnnot_GetStringValue(annotation, key, ctypes.cast(buffer, ctypes.POINTER(pdfium_raw.FPDF_WCHAR)), size)
    return buffer.raw[:size - 2].decode('utf-16-le', errors='replace')


def _has_appearance(annotation):
    mode = pdfium_raw.FPDF_ANNOT_APPEARANCEMODE_NORMAL
    return pdfium_raw.FPDFAnnot_GetAP(annotation, mode, None, 0) > 2


def _to_pixels(page, image, x, y):
    """A point of the page, in PDF units from its bottom left, as a pixel of the rendered image."""
    px, py = ctypes.c_int(), ctypes.c_int()
    pdfium_raw.FPDF_PageToDevice(page, 0, 0, image.width, image.height, 0, x, y, ctypes.byref(px), ctypes.byref(py))
    return px.value, py.value


def _draw_plain_text_boxes(page, image):
    """Draw the page's text boxes that have no appearance of their own onto its rendered image."""
    draw = None
    for index in range(pdfium_raw.FPDFPage_GetAnnotCount(page)):
        annotation = pdfium_raw.FPDFPage_GetAnnot(page, index)
        if not annotation:
            continue
        try:
            if pdfium_raw.FPDFAnnot_GetSubtype(annotation) != pdfium_raw.FPDF_ANNOT_FREETEXT or _has_appearance(annotation):
                continue
            text = _annotation_text(annotation, b'Contents').strip()
            rect = pdfium_raw.FS_RECTF()
            if not text or not pdfium_raw.FPDFAnnot_GetRect(annotation, rect):
                continue
            style = f"{_annotation_text(annotation, b'DS')} {_annotation_text(annotation, b'DA')}"
        finally:
            pdfium_raw.FPDFPage_CloseAnnot(annotation)

        left, top = _to_pixels(page, image, rect.left, rect.top)
        right, bottom = _to_pixels(page, image, rect.right, rect.bottom)
        left, right, top, bottom = min(left, right), max(left, right), min(top, bottom), max(top, bottom)
        pixels_per_point = (right - left) / max(rect.right - rect.left, 0.01)

        size = FONT_SIZE_RE.search(style)
        points = float(size.group(1) or size.group(2)) if size else DEFAULT_FONT_PT
        font = _font(max(round(points * pixels_per_point), 6))
        colour = COLOUR_RE.search(style)
        fill = tuple(int(colour.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if colour else (0, 0, 0)
        align = (ALIGN_RE.search(style).group(1).lower() if ALIGN_RE.search(style) else 'left')
        padding = TEXT_BOX_PADDING_PT * pixels_per_point

        draw = draw or ImageDraw.Draw(image)
        lines = text.splitlines()
        line_height = font.size * 1.15
        y = (top + bottom) / 2 - line_height * len(lines) / 2   # the lines sit in the middle of the box
        for line in lines:
            width = draw.textlength(line, font=font)
            x = {'left': left + padding, 'center': (left + right - width) / 2, 'right': right - padding - width}[align]
            draw.text((x, y + (line_height - font.size) / 2), line, font=font, fill=fill)
            y += line_height


def open_scan(source):
    """
    (image, number of pages) for a scan given as a path or an open binary file. An image file
    counts as one page. Raises PIL's UnidentifiedImageError, with a message for the user, when
    the file is neither an image nor a readable PDF.
    """
    if _is_pdf(source):
        return _render_first_page(source)
    try:
        image = Image.open(source)
        image.load()
    except (UnidentifiedImageError, OSError):
        raise UnidentifiedImageError("This file couldn't be read. Upload the scan as a JPG, PNG or PDF.")
    return image, 1
