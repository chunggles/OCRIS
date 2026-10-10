"""Image clean-up before OCR."""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .pdf import open_scan
from .quality import analyze_image, effective_dpi, estimate_skew

MIN_DPI = 250
TARGET_DPI = 300
MIN_SKEW_TO_FIX = 0.5  # degrees
SMOOTH_DPI_PER_PIXEL = 250   # blur radius of smoothed(): 1 px per this many DPI...
SMOOTH_MIN_RADIUS, SMOOTH_MAX_RADIUS = 0.6, 1.2   # ...kept within these

get_image_quality = analyze_image


def load_page(image_path):
    """(greyscale page straightened to level, effective DPI). Raises if the file isn't an image or a PDF."""
    original, _ = open_scan(image_path)
    dpi, _ = effective_dpi(original)
    grey = original.convert('RGB').convert('L')
    skew = estimate_skew(grey)
    if skew is not None and abs(skew) >= MIN_SKEW_TO_FIX:
        grey = grey.rotate(-skew, resample=Image.BICUBIC, expand=True, fillcolor=255)
    return grey, dpi


def smoothed(grey, dpi):
    """
    A copy of the page for grainy or faded scans: lightly blurred, so specks stop breaking up
    the table rules and letters, then stretched back to full contrast.
    """
    radius = min(max(dpi / SMOOTH_DPI_PER_PIXEL, SMOOTH_MIN_RADIUS), SMOOTH_MAX_RADIUS)
    return ImageOps.autocontrast(grey.filter(ImageFilter.GaussianBlur(radius)), cutoff=1)


def prepare_grey_for_text(grey, dpi):
    """
    The page for full-page OCR without binarising it: contrast stretched, low-resolution scans
    upscaled. Small print that the hard threshold of prepare_for_text() erases survives here.
    """
    img = ImageOps.autocontrast(grey, cutoff=1)
    if dpi < MIN_DPI:
        scale = TARGET_DPI / dpi
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    return img


def prepare_for_text(grey, dpi, aggressive=False):
    """Sharpen, upscale low-resolution scans, then binarise and denoise for full-page OCR."""
    img = ImageOps.autocontrast(grey, cutoff=2)
    img = ImageEnhance.Sharpness(img).enhance(2.0 if aggressive else 1.5)
    if dpi < MIN_DPI:
        scale = TARGET_DPI / dpi
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    threshold = 145 if aggressive else 160
    img = img.point(lambda p: 255 if p > threshold else 0, '1').convert('L')
    return img.filter(ImageFilter.MedianFilter(size=3))
