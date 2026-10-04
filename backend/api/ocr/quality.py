"""
Measures how suitable a scanned Form 137 image is for OCR.

Every number here is computed from the actual image:
  resolution  pixels per inch, from file metadata or estimated from the page width
  contrast    spread between dark ink and light paper (5th–95th percentile of grey levels)
  brightness  average grey level
  sharpness   variance of a Laplacian edge filter (low = blurry)
  skew        page rotation found by testing small angles for the sharpest row profile
  content     share of dark pixels (catches blank or very dark/shadowed scans)
"""
from PIL import Image, ImageFilter, ImageStat

FORM_WIDTH_IN = 8.5          # Form 137 is printed on 8.5" × 13" long bond paper
ANALYSIS_WIDTH = 1000        # images are downscaled to this width before analysis
SKEW_RANGE_DEG = 5.0
SKEW_STEP_DEG = 0.25

GOOD, FAIR, POOR = 'good', 'fair', 'poor'
STATUS_RANK = {GOOD: 0, FAIR: 1, POOR: 2}


def _resize_to_width(img, width):
    if img.width <= width:
        return img
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def _percentile(histogram, pct):
    target = sum(histogram) * pct / 100
    running = 0
    for level, count in enumerate(histogram):
        running += count
        if running >= target:
            return level
    return 255


def _metric(key, label, value, status, score, tip=''):
    return {'key': key, 'label': label, 'value': value, 'status': status,
            'score': max(0, min(100, round(score))), 'tip': tip}


# ── Individual measurements ──────────────────────────────────────────────────

def effective_dpi(img):
    """DPI from metadata when present, otherwise estimated from the page width."""
    dpi = img.info.get('dpi')
    if dpi:
        value = dpi[0] if isinstance(dpi, tuple) else dpi
        if value and int(value) > 72:  # 72 is a common placeholder, not a real scan DPI
            return int(value), False
    return round(img.width / FORM_WIDTH_IN), True


def ink_threshold(grey):
    """Grey level separating ink from paper, halfway between the darkest and lightest 5%."""
    hist = grey.histogram()
    return (_percentile(hist, 5) + _percentile(hist, 95)) / 2


def estimate_skew(grey):
    """
    Angle in degrees the page is rotated by (positive = counter-clockwise), or None
    if there's too little ink to tell. Text rows produce the sharpest horizontal ink
    profile when the page is level, so the angle with the highest row-sum variance wins.
    """
    small = _resize_to_width(grey, 600)
    threshold = ink_threshold(small)
    ink = small.point(lambda p: 255 if p < threshold else 0)
    if ImageStat.Stat(ink).mean[0] < 255 * 0.005:
        return None
    best_angle, best_score = 0.0, -1.0
    steps = int(SKEW_RANGE_DEG / SKEW_STEP_DEG)
    for i in range(-steps, steps + 1):
        angle = i * SKEW_STEP_DEG
        rotated = ink.rotate(angle, resample=Image.BILINEAR, fillcolor=0)
        row_profile = rotated.resize((1, rotated.height), Image.BOX)
        score = ImageStat.Stat(row_profile).var[0]
        if score > best_score:
            best_angle, best_score = angle, score
    return -best_angle


def sharpness(grey):
    laplacian = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
    return ImageStat.Stat(_resize_to_width(grey, ANALYSIS_WIDTH).filter(laplacian)).var[0]


# ── Grading each measurement ─────────────────────────────────────────────────

def _grade_resolution(img, grey):
    dpi, estimated = effective_dpi(img)
    status = GOOD if dpi >= 250 else FAIR if dpi >= 150 else POOR
    value = f"{'≈' if estimated else ''}{dpi} DPI ({img.width} × {img.height} px)"
    tip = '' if status == GOOD else 'Rescan at 300 DPI for best results.'
    return _metric('resolution', 'Resolution', value, status, dpi / 300 * 100, tip)


def _grade_contrast(img, grey):
    hist = grey.histogram()
    spread = _percentile(hist, 95) - _percentile(hist, 5)
    status = GOOD if spread >= 150 else FAIR if spread >= 100 else POOR
    tip = '' if status == GOOD else 'Ink is faint or the background is grey. Try grayscale/black-and-white mode.'
    return _metric('contrast', 'Contrast', f'{spread} / 255', status, spread / 200 * 100, tip)


def _grade_brightness(img, grey):
    mean = ImageStat.Stat(grey).mean[0]
    if 150 <= mean <= 245:
        status, tip = GOOD, ''
    elif mean > 245:
        status, tip = FAIR, 'Very bright — the scan may be washed out.'
    elif mean >= 110:
        status, tip = FAIR, 'Slightly dark — check for shadows.'
    else:
        status, tip = POOR, 'Too dark — rescan with more light or a scanner.'
    score = 100 - abs(mean - 210) / 210 * 100
    return _metric('brightness', 'Brightness', f'{round(mean)} / 255', status, score, tip)


def _grade_sharpness(img, grey):
    value = sharpness(grey)
    # Calibrated on a 1000px-wide page: crisp scans score ~3500, a slight blur ~1300, clearly blurry < 300
    status = GOOD if value >= 1000 else FAIR if value >= 300 else POOR
    label = 'Sharp' if status == GOOD else 'Slightly soft' if status == FAIR else 'Blurry'
    tip = '' if status == GOOD else 'Keep the document flat and still while scanning.'
    return _metric('sharpness', 'Sharpness', label, status, value / 1500 * 100, tip)


def _grade_skew(img, grey):
    angle = estimate_skew(grey)
    if angle is None:
        return _metric('skew', 'Page tilt', 'Not measurable — no text found', POOR, 0)
    tilt = abs(angle)
    if tilt >= SKEW_RANGE_DEG:
        return _metric('skew', 'Page tilt', f'Over {SKEW_RANGE_DEG:.0f}°', POOR, 0,
                       'Page is badly tilted. Align it with the scanner edge and rescan.')
    status = GOOD if tilt <= 1 else FAIR
    note = ' — corrected automatically' if tilt >= 0.5 else ''
    tip = 'Tilt is corrected before OCR, but a straight scan reads more reliably.' if status == FAIR else ''
    return _metric('skew', 'Page tilt', f'{tilt:.1f}°{note}', status, 100 - tilt / SKEW_RANGE_DEG * 100, tip)


def _grade_content(img, grey):
    small = _resize_to_width(grey, ANALYSIS_WIDTH)
    hist = small.histogram()
    threshold = int(ink_threshold(small))
    dark_ratio = sum(hist[:threshold]) / max(sum(hist), 1) * 100
    if dark_ratio < 0.5:
        status, tip = POOR, 'Page looks blank. Check that the right side was scanned.'
    elif dark_ratio > 40:
        status, tip = POOR, 'Large dark areas — likely shadows or a dark background.'
    elif dark_ratio > 25:
        status, tip = FAIR, 'More dark area than a typical form — check for shadows.'
    else:
        status, tip = GOOD, ''
    score = 100 if status == GOOD else 60 if status == FAIR else 20
    return _metric('content', 'Ink coverage', f'{dark_ratio:.1f}% of page', status, score, tip)


GRADERS = [_grade_resolution, _grade_contrast, _grade_brightness, _grade_sharpness, _grade_skew, _grade_content]


def analyze_image(source):
    """source: a file path or file-like object. Returns per-metric results and an overall verdict."""
    try:
        img = Image.open(source)
        img.load()
    except Exception:
        return {'error': 'Quality check is only available for JPG and PNG images.', 'overall_ok': False, 'metrics': []}

    grey = img.convert('L')
    metrics = [grade(img, grey) for grade in GRADERS]
    worst = max(metrics, key=lambda m: STATUS_RANK[m['status']])['status']
    assessment = {GOOD: 'Good', FAIR: 'Acceptable', POOR: 'Poor — rescan recommended'}[worst]
    return {
        'metrics': metrics,
        'assessment': assessment,
        'status': worst,
        'overall_ok': worst != POOR,
        'width': img.width,
        'height': img.height,
    }
