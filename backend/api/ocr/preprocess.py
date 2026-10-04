"""Image clean-up before OCR."""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .quality import analyze_image, effective_dpi, estimate_skew

MIN_DPI = 250
TARGET_DPI = 300
MIN_SKEW_TO_FIX = 0.5  # degrees

get_image_quality = analyze_image


def load_page(image_path):
    """(greyscale page straightened to level, effective DPI). Raises if the file isn't an image."""
    original = Image.open(image_path)
    dpi, _ = effective_dpi(original)
    grey = original.convert('RGB').convert('L')
    skew = estimate_skew(grey)
    if skew is not None and abs(skew) >= MIN_SKEW_TO_FIX:
        grey = grey.rotate(-skew, resample=Image.BICUBIC, expand=True, fillcolor=255)
    return grey, dpi


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
