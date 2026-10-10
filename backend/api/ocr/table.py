"""
Reads the grade table of a Form 137 by its grid instead of as free text.

Tesseract reads ruled tables badly: grid lines turn into junk characters and digits
get mangled. Instead we:
  1. find the table's horizontal and vertical rules from ink-density profiles,
  2. identify subject rows by reading only their first cell,
  3. read each grade cell on its own, cropped inside its borders, as digits only,
     several times at different scales. A grade is auto-approved only when the
     readings agree; anything else is flagged for a person to check.

Expected column order (Form 137 / SF10 and Form 137-A):
  Subject | Q1 | Q2 | Q3 | Q4 | Final | (remarks / units / ...)

parse_grade_table() returns None when no ruled grade table is found, so the caller
can fall back to free-text parsing.
"""
import difflib
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from typing import NamedTuple, Optional

import pytesseract
from django.conf import settings
from PIL import Image, ImageOps

from ..constants import NA
from .parser import GRADE_COLUMNS, make_field, match_subject_span
from .quality import _percentile, ink_threshold

# Grid detection
H_LINE_MIN_COVERAGE = 0.45   # a horizontal rule spans at least this share of the page width
V_LINE_MIN_COVERAGE = 0.90   # a vertical rule is inked over at least this share of the full row height
MIN_ROW_HEIGHT = 12          # px; thinner gaps between rules are double lines, not rows
RULE_MARGIN = 2              # px skipped next to each horizontal rule
RULE_X_TOLERANCE = 3         # px; rules in neighbouring rows this close are the same rule
RULE_SUPPORT_WINDOW = 3      # rows above/below checked when confirming a vertical rule
RULE_MIN_SUPPORT = 3         # rows (including itself) that must share a vertical rule
MIN_SUBJECT_CELL_SHARE = 0.15  # the subject column is at least this share of the page width
LAYOUT_MIN_SHARE = 0.5       # a column rule must appear in at least this share of a block's rows
# Horizontal rules are found on a looser "darker than paper" mask than ink: on low-resolution
# scans thin rules are antialiased to grey and would otherwise be missed, merging two rows.
# Vertical rules use the normal ink mask, where letter strokes are less likely to pass as rules.
RULE_DARKNESS = 0.25         # share of the paper-to-ink range a pixel must darken to count as rule
MERGED_ROW_FACTOR = 1.6      # a table row this many times taller than usual is two rows merged
MIN_SPLIT_COVERAGE = 0.2     # weakest rule coverage accepted when splitting a merged row

# Two tables side by side (SF10-ES)
GUTTER_ZONE = (0.30, 0.96)   # share of the page height holding the grade tables, below the header boxes
GUTTER_SEARCH = (0.42, 0.58)  # share of the page width where the strip between the tables can be
GUTTER_MAX_INK = 0.006       # a strip column may be inked over at most this share of the zone (specks)
GUTTER_MIN_WIDTH = 4         # px
BLOCK_BAND_TOLERANCE = 0.05  # blocks starting within this share of the page height sit side by side
CLASS_LINE_ABOVE = (6.2, 1.2)  # the school/class lines lie this many row heights above a block's first subject
CLASS_GRADE_RE = re.compile(r'^[:_\s]*([1-6])[_.\s]*$')

# Cell reading
CELL_INSET = 3               # px trimmed inside each cell so borders don't reach the OCR
CELL_PADDING = 16            # px of white added around each crop
MIN_CELL_INK = 0.006         # share of dark pixels below which a cell counts as blank
SUBJECT_HEIGHT = 64          # px; subject cells are scaled to this height before reading
SUBJECT_RETRY_HEIGHTS = (48, 96)  # tried in turn when a grade-table row's first cell matches no subject
# Each grade cell is read at all of these heights. It is auto-approved only if at least
# MIN_AGREEMENT readings give the same valid grade, none gives a different valid grade, and
# their mean Tesseract confidence is above settings.OCR_CONFIDENCE_THRESHOLD (90 by default:
# "high-confidence extractions (>90%) are auto-approved"). MIN_MEAN_CONF is used if that
# setting is missing. Calibrated on the Form 137-A
# mockup in 12 variants (94–294 DPI, tilted, blurred, JPEG q25–60, noisy; 1,080 cells):
# 788 correct grades auto-approved, 0 wrong ones; everything else was flagged for review.
VOTE_HEIGHTS = (48, 40, 56, 32)
MIN_AGREEMENT = 3
MIN_MEAN_CONF = 50
MIN_GRADE, MAX_GRADE = 60, 100
WORKERS = min(8, os.cpu_count() or 4)

DIGITS_CONFIG = '--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789'
TEXT_CONFIG = '--psm 7 --oem 1'

# Subject matching when the exact patterns fail because of a misread letter ("Filipina")
FUZZY_SUBJECTS = [
    ('Filipino', 'Filipino'),
    ('English', 'English'),
    ('Mathematics', 'Mathematics'),
    ('Science', 'Science'),
    ('Araling Panlipunan', 'Araling Panlipunan'),
    ('Edukasyon sa Pagpapakatao', 'Edukasyon sa Pagpapakatao'),
    ('Technology and Livelihood Education', 'EPP / TLE'),
    ('MAPEH', 'MAPEH'),
    ('MAKABAYAN', 'MAKABAYAN'),
    ('Makabansa', 'Makabansa'),
    ('Reading and Literacy', 'Reading and Literacy'),
    ('Language', 'Language'),
    ('GMRC', 'GMRC'),
    ('Music & Arts', 'Music & Arts'),
    ('Physical Education & Health', 'Physical Education & Health'),
    ('Arabic Language', 'Arabic Language'),
    ('Islamic Values Education', 'Islamic Values Education'),
]
FUZZY_MIN_RATIO = 0.8
UNREAD_SUBJECT = 'Unread learning area'   # name given to a row with grades whose learning area couldn't be read
UNREAD_MIN_HEIGHT_SHARE = 0.85   # an unread row is about as tall as the block's recognised rows
UNREAD_MIN_LETTERS = 3      # letters read in a first cell for it to count as an unreadable name...
UNREAD_MIN_INK = 0.03       # ...or this share of the cell inked, when no letters could be read
NOT_A_SUBJECT_RATIO = 0.6   # a first cell this much like "General Average" is that row, not a learning area
FUZZY_MIN_RATIO_IN_TABLE = 0.7   # for the first cell of a row that has the grade columns

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI']
# Year level written after the subject, optionally after "(AP)"-style abbreviations.
# Tesseract often reads "I" as "l", "|" or "1".
LEVEL_TOKEN_RE = re.compile(r'^\s*(?:\([^)]*\)\s*)?([IVl|1]{1,4})(?![A-Za-z0-9])')
LEVEL_FIXES = str.maketrans({'l': 'I', '|': 'I', '1': 'I'})


# ── Grid detection ───────────────────────────────────────────────────────────

def _runs(values, threshold):
    """(start, end) index ranges where values stay at or above threshold."""
    runs, start = [], None
    for i, v in enumerate(values):
        if v >= threshold and start is None:
            start = i
        elif v < threshold and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(values) - 1))
    return runs


def _row_coverage(ink):
    return [v / 255 for v in ink.resize((1, ink.height), Image.BOX).getdata()]


def _column_coverage(ink, top, bottom):
    band = ink.crop((0, top, ink.width, bottom))
    return [v / 255 for v in band.resize((ink.width, 1), Image.BOX).getdata()]


def rule_mask(grey):
    hist = grey.histogram()
    paper, dark = _percentile(hist, 95), _percentile(hist, 5)
    cutoff = paper - RULE_DARKNESS * (paper - dark)
    return grey.point(lambda p: 255 if p < cutoff else 0)


def find_rows(ink):
    """Bands between consecutive horizontal rules, as (top, bottom) bounds excluding the rules."""
    rules = _runs(_row_coverage(ink), H_LINE_MIN_COVERAGE)
    rows = []
    for (_, above_end), (below_start, _) in zip(rules, rules[1:]):
        top, bottom = above_end + 1 + RULE_MARGIN, below_start - RULE_MARGIN
        if bottom - top >= MIN_ROW_HEIGHT - 2 * RULE_MARGIN:
            rows.append((top, bottom))
    return rows


def find_columns(ink, top, bottom):
    """
    (start, end) x-ranges of vertical rules running through a row. Coverage is measured
    over the full height between the horizontal rules: a real rule touches both, while
    letters leave a gap above and below, which matters on small, low-resolution rows.
    """
    return _runs(_column_coverage(ink, top - RULE_MARGIN, bottom + RULE_MARGIN), V_LINE_MIN_COVERAGE)


def _centre(rule):
    return (rule[0] + rule[1]) / 2


def confirmed_columns(ink, rows):
    """
    Vertical rules per row, keeping only rules shared with nearby rows. Tall glyphs such
    as "(" or a large "1" can look like a rule within one row, but real rules continue
    through the rows above and below at the same x-position.
    """
    raw = [find_columns(ink, top, bottom) for top, bottom in rows]
    confirmed = []
    for i, rules in enumerate(raw):
        window = raw[max(0, i - RULE_SUPPORT_WINDOW): i + RULE_SUPPORT_WINDOW + 1]
        confirmed.append([
            rule for rule in rules
            if sum(any(abs(_centre(rule) - _centre(o)) <= RULE_X_TOLERANCE for o in row) for row in window) >= RULE_MIN_SUPPORT
        ])
    return confirmed


def split_merged_rows(rules, ink, rows, row_columns):
    """
    Split table rows that are much taller than their neighbours at their strongest
    horizontal line. Returns new (rows, row_columns).
    """
    min_rules = len(GRADE_COLUMNS) + 2
    heights = sorted(b - t for (t, b), cols in zip(rows, row_columns) if len(cols) >= min_rules)
    if not heights:
        return rows, row_columns
    typical = heights[len(heights) // 2]
    coverage = _row_coverage(rules)
    split = []
    for (top, bottom), cols in zip(rows, row_columns):
        pieces = [(top, bottom)]
        if len(cols) >= min_rules and bottom - top > MERGED_ROW_FACTOR * typical:
            parts = max(2, round((bottom - top) / typical))
            pieces, start = [], top
            for k in range(1, parts):
                guess = top + (bottom - top) * k // parts
                lo, hi = guess - typical // 3, guess + typical // 3
                y = max(range(lo, hi + 1), key=lambda r: coverage[r])
                if coverage[y] < MIN_SPLIT_COVERAGE:
                    pieces = [(top, bottom)]
                    break
                pieces.append((start, y - 1 - RULE_MARGIN))
                start = y + 1 + RULE_MARGIN
            else:
                pieces.append((start, bottom))
        split.extend(pieces)
    if len(split) == len(rows):
        return rows, row_columns
    return split, confirmed_columns(ink, split)


def _cells(columns):
    """(left, right) bounds of the cells between consecutive vertical rules."""
    return [(left_end + 1, right_start - 1) for (_, left_end), (right_start, _) in zip(columns, columns[1:])]


def _cell_box(left, right, top, bottom):
    """Crop box for a cell; rows already exclude the horizontal rules, so only trim the sides."""
    return (left + CELL_INSET, top, right - CELL_INSET, bottom)


# ── Reading cells ────────────────────────────────────────────────────────────

def _ink_share(ink, box):
    region = ink.crop(box)
    return sum(1 for p in region.getdata() if p) / max(region.width * region.height, 1)


def _prepare_cell(grey, box, height):
    cell = ImageOps.autocontrast(grey.crop(box))
    scale = height / max(cell.height, 1)
    cell = cell.resize((max(round(cell.width * scale), 1), height), Image.LANCZOS)
    return ImageOps.expand(cell, border=CELL_PADDING, fill=255)


def _read(image, config):
    """(text, confidence) for a single-line crop."""
    lang = getattr(settings, 'OCR_LANG', 'eng')
    data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    words = [(w.strip(), float(c)) for w, c in zip(data['text'], data['conf']) if w.strip()]
    if not words:
        return '', 0
    return ' '.join(w for w, _ in words), max(round(min(c for _, c in words)), 0)


def _is_grade(text):
    return text.isdigit() and MIN_GRADE <= int(text) <= MAX_GRADE


def read_grade_cell(grey, ink, box):
    """
    (value, raw, conf, status) for one grade cell, read at every VOTE_HEIGHTS scale.
    status is 'ok' only under the agreement rule described at VOTE_HEIGHTS.
    """
    if _ink_share(ink, box) < MIN_CELL_INK:
        return NA, '', 0, 'null'

    readings = []        # every non-empty text read
    grade_confs = {}     # valid grade -> confidences of the readings that produced it
    for height in VOTE_HEIGHTS:
        text, conf = _read(_prepare_cell(grey, box, height), DIGITS_CONFIG)
        if text:
            readings.append(text)
        if _is_grade(text):
            grade_confs.setdefault(text, []).append(conf)
        if len(grade_confs) > 1:
            break  # readings conflict — a person has to decide either way

    if len(grade_confs) == 1:
        value, confs = next(iter(grade_confs.items()))
        threshold = getattr(settings, 'OCR_CONFIDENCE_THRESHOLD', None)
        confident = mean(confs) > threshold if threshold is not None else mean(confs) >= MIN_MEAN_CONF
        agreed = len(confs) >= MIN_AGREEMENT and confident
        return value, value, round(mean(confs)), 'ok' if agreed else 'warn'

    if len(grade_confs) > 1:
        # Show the most frequent candidate, but never approve it
        value = max(grade_confs, key=lambda g: len(grade_confs[g]))
        return value, ' / '.join(grade_confs), 0, 'warn'

    # Ink but no valid grade (unreadable, "N/A", out-of-range number, ...)
    raw = max(set(readings), key=readings.count) if readings else '?'
    return raw, raw, 0, 'warn'


# ── Subject rows and year blocks ─────────────────────────────────────────────

def _fuzzy_subject(text, min_ratio=None):
    """(subject, end index) when the leading words closely match a subject name."""
    min_ratio = min_ratio or FUZZY_MIN_RATIO
    words = list(re.finditer(r'\S+', text))
    best = None
    for phrase, subject in FUZZY_SUBJECTS:
        n = len(phrase.split())
        if len(words) < n:
            continue
        candidate = text[words[0].start():words[n - 1].end()]
        ratio = difflib.SequenceMatcher(None, candidate.casefold(), phrase.casefold()).ratio()
        if ratio >= min_ratio and (best is None or ratio > best[0]):
            best = (ratio, subject, words[n - 1].end())
    return (best[1], best[2]) if best else None


def _match_subject(text):
    return match_subject_span(text) or _fuzzy_subject(text)


def _level_after(text, end):
    m = LEVEL_TOKEN_RE.match(text[end:])
    if not m:
        return None
    level = m.group(1).translate(LEVEL_FIXES)
    return level if level in ROMAN else None


class SubjectRow(NamedTuple):
    index: int            # position in rows
    subject: str
    level: Optional[str]  # year level written after the subject ("I", "II", ...), if read
    conf: int             # Tesseract confidence of the subject cell's text


def _identify_subject_rows(grey, ink, rows, row_columns):
    """
    (SubjectRows for rows whose first cell names a subject, {row index: text} for the other
    rows with a name written in their first cell that couldn't be matched). Only the first two rules of a row are
    needed here; the grade columns come from the block layout.
    """
    candidates = []
    for i, ((top, bottom), columns) in enumerate(zip(rows, row_columns)):
        cells = _cells(columns)
        if not cells or cells[0][1] - cells[0][0] < MIN_SUBJECT_CELL_SHARE * ink.width:
            continue
        box = _cell_box(*cells[0], top, bottom)
        if _ink_share(ink, box) >= MIN_CELL_INK:
            candidates.append((i, box))

    def read(candidate):
        """(text, conf, match) for a subject cell. A grade-table row that matches no subject is read
        again at other sizes: on low-resolution scans a bold name can come out as "Lanquaae"."""
        i, box = candidate
        heights = (SUBJECT_HEIGHT,) + (SUBJECT_RETRY_HEIGHTS if len(row_columns[i]) >= len(GRADE_COLUMNS) + 2 else ())
        text, conf = '', 0
        in_grade_table = len(heights) > 1
        texts = []
        for height in heights:
            text, conf = _read(_prepare_cell(grey, box, height), TEXT_CONFIG)
            match = _match_subject(text)
            if match or not text:
                return text, conf, match
            texts.append((text, conf))
        if in_grade_table:
            # Still nothing: inside a grade table the first cell can only be a learning area, a
            # blank or "General Average", so a looser likeness is enough ("Lanauaae" is Language)
            for text, conf in texts:
                match = _fuzzy_subject(text, FUZZY_MIN_RATIO_IN_TABLE)
                if match:
                    return text, conf, match
        return text, conf, None

    with ThreadPoolExecutor(WORKERS) as pool:
        reads = list(pool.map(read, candidates))

    candidates_box = dict(candidates)
    subject_rows, unread = [], {}
    for (i, _), (text, conf, match) in zip(candidates, reads):
        if match:
            subject, end = match
            subject_rows.append(SubjectRow(i, subject, _level_after(text, end), conf))
        elif len(re.findall(r'[A-Za-z]', text)) >= UNREAD_MIN_LETTERS or _ink_share(ink, candidates_box[i]) >= UNREAD_MIN_INK:
            unread[i] = text
    return subject_rows, unread


def _group_blocks(subject_rows):
    """Split subject rows into year blocks: consecutive table rows with no repeated subject."""
    blocks = []
    for row in subject_rows:
        adjacent = bool(blocks) and blocks[-1][-1].index == row.index - 1
        repeated = bool(blocks) and any(row.subject == other.subject for other in blocks[-1])
        if not adjacent or repeated:
            blocks.append([])
        blocks[-1].append(row)
    return blocks


def _block_layout(block, row_columns):
    """
    Column rules shared by the block's rows, by majority vote. Every row in a block uses
    the same layout, so a rule that is faint or missed in one row can't shift its cells.
    Returns None if the block doesn't have enough columns for the grade table.
    """
    needed = max(1, math.ceil(len(block) * LAYOUT_MIN_SHARE))
    rules = sorted((rule, row.index) for row in block for rule in row_columns[row.index])
    clusters = []
    for rule, i in rules:
        if clusters and _centre(rule) - _centre(clusters[-1][-1][0]) <= RULE_X_TOLERANCE:
            clusters[-1].append((rule, i))
        else:
            clusters.append([(rule, i)])
    layout = []
    for cluster in clusters:
        if len({i for _, i in cluster}) >= needed:
            starts = sorted(r[0] for r, _ in cluster)
            ends = sorted(r[1] for r, _ in cluster)
            layout.append((starts[len(starts) // 2], ends[len(ends) // 2]))
    return layout if len(_cells(layout)) >= len(GRADE_COLUMNS) + 1 else None


def _block_level(block, block_index, block_count):
    """
    (level, conf, was_read) for a year block. The level is the majority of the levels read
    after each subject; if none could be read on a multi-block form, the block's position
    is used (was_read False) so field names stay distinct.
    """
    read = [row for row in block if row.level]
    if read:
        levels = [row.level for row in read]
        level = max(set(levels), key=levels.count)
        conf = round(mean(row.conf for row in read if row.level == level))
        return level, conf, True
    if block_count > 1:
        return (ROMAN[block_index] if block_index < len(ROMAN) else str(block_index + 1)), 0, False
    return None, 0, False  # single-table forms (elementary) have no year level


# ── Entry point ──────────────────────────────────────────────────────────────

class _Table(NamedTuple):
    """One ruled table area (the whole page, or one half of a two-column page) and its year blocks."""
    grey: Image.Image
    ink: Image.Image
    rows: list            # (top, bottom) of every band between horizontal rules
    blocks: list          # [(subject rows of the block, its grade cells or Nones)]


def _find_table(grey, join_across_blank_rows=False):
    """The subject rows of a table area, grouped into year blocks, or None if it has none."""
    cutoff = ink_threshold(grey)
    ink = grey.point(lambda p: 255 if p < cutoff else 0)
    rules = rule_mask(grey)
    rows = find_rows(rules)
    rows, row_columns = split_merged_rows(rules, ink, rows, confirmed_columns(ink, rows))
    subject_rows, unread = _identify_subject_rows(grey, ink, rows, row_columns)
    if not subject_rows:
        return None
    groups = _group_blocks(subject_rows)
    if join_across_blank_rows:
        groups = [_with_unread_rows(block, unread, rows, row_columns) for block in _join_same_grid(groups, row_columns)]
    blocks = []
    for block in groups:
        layout = _block_layout(block, row_columns)
        blocks.append((block, _cells(layout)[1:len(GRADE_COLUMNS) + 1] if layout else [None] * len(GRADE_COLUMNS)))
    return _Table(grey, ink, rows, blocks)


def _join_same_grid(groups, row_columns):
    """
    Join blocks that are parts of one printed table: every row between them has the grade
    columns, and no subject repeats. On the SF10-ES the pre-printed subjects at the top of a
    table and "*Arabic Language" near its bottom are separated only by empty rows.
    """
    joined = []
    for block in groups:
        if joined:
            previous = joined[-1]
            between = range(previous[-1].index, block[0].index + 1)
            # every row in between has the grade columns; a speck or a faint rule may add or drop one
            same_grid = all(len(row_columns[i]) >= len(GRADE_COLUMNS) + 2 for i in between)
            repeated = {row.subject for row in previous} & {row.subject for row in block}
            if same_grid and not repeated:
                previous.extend(block)
                continue
        joined.append(list(block))
    return joined


def _with_unread_rows(block, unread, rows, row_columns):
    """
    The block plus the rows inside it whose learning area couldn't be read. Such a row still
    has grades, and leaving it out would lose them without anyone noticing, so it is kept under
    the name UNREAD_SUBJECT for a person to see. The row must be a full-height row of the
    table with a name written in its first cell. Only rows between the block's first and last
    recognised subjects are taken: above them is the table's heading (whose "1 2 3 4" would
    pass for grades), below them "General Average".
    """
    def is_grade_row(i):
        return len(row_columns[i]) >= len(GRADE_COLUMNS) + 2

    def height(i):
        return rows[i][1] - rows[i][0]

    # A stray rule can cut a sliver off a row; a sliver is not a row of the table
    heights = sorted(height(row.index) for row in block)
    full_height = UNREAD_MIN_HEIGHT_SHARE * heights[len(heights) // 2]

    def is_unread_subject(i):
        text = unread.get(i)
        if text is None or not is_grade_row(i) or height(i) < full_height:
            return False
        return difflib.SequenceMatcher(None, text.casefold(), 'general average').ratio() < NOT_A_SUBJECT_RATIO

    first, last = block[0].index, block[-1].index
    known = {row.index for row in block}
    extra = [i for i in range(first, last) if i not in known and is_unread_subject(i)]
    return sorted(block + [SubjectRow(i, UNREAD_SUBJECT, None, 0) for i in extra], key=lambda row: row.index)


def _block_jobs(table, block, grade_cells, label_of):
    """(field name, table, cell box or None) for every grade cell of a block's subject rows."""
    jobs = []
    for row in block:
        top, bottom = table.rows[row.index]
        label = label_of(row)
        for column, cell in zip(GRADE_COLUMNS, grade_cells):
            jobs.append((f'{label} {column}', table, _cell_box(*cell, top, bottom) if cell else None))
    return jobs


def _read_jobs(jobs):
    """Grade fields for jobs, reading the cells in parallel."""
    def read(job):
        _, table, box = job
        # A subject whose grade columns couldn't be located is still listed, flagged for manual entry
        return read_grade_cell(table.grey, table.ink, box) if box else ('?', '?', 0, 'warn')

    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(read, jobs))
    return [make_field(name, raw, value, conf, status) for (name, _, _), (value, raw, conf, status) in zip(jobs, results)]


def _unique_labeller(suffix_of):
    """Field label for a subject row: the subject plus its block's suffix, numbered if it repeats."""
    seen = {}

    def label_of(row):
        suffix = suffix_of(row)
        label = f'{row.subject} {suffix}' if suffix else row.subject
        seen[label] = seen.get(label, 0) + 1
        return f'{label} #{seen[label]}' if seen[label] > 1 else label
    return label_of


def _parse_single(grey):
    """A page with one table column (Form 137, Form 137-A): year blocks stacked down the page."""
    table = _find_table(grey)
    if not table:
        return None
    levels, year_levels = {}, []
    for b, (block, _) in enumerate(table.blocks):
        level, level_conf, was_read = _block_level(block, b, len(table.blocks))
        if was_read:
            year_levels.append((level, level_conf))
        levels.update({row.index: level for row in block})
    label_of = _unique_labeller(lambda row: levels[row.index])
    jobs = [job for block, cells in table.blocks for job in _block_jobs(table, block, cells, label_of)]
    return _read_jobs(jobs), year_levels


# ── Two tables side by side (SF10-ES) ────────────────────────────────────────

def find_gutter(grey):
    """
    (left edge, right edge) of the blank strip between two grade tables printed side by side,
    as on the SF10-ES, or None for a page with a single table column. The strip must be clear
    of ink over the whole table area; on a single-column form every row rule crosses it.
    """
    cutoff = ink_threshold(grey)
    ink = grey.point(lambda p: 255 if p < cutoff else 0)
    width, height = ink.size
    coverage = _column_coverage(ink, round(height * GUTTER_ZONE[0]), round(height * GUTTER_ZONE[1]))
    lo, hi = round(width * GUTTER_SEARCH[0]), round(width * GUTTER_SEARCH[1])
    clear = _runs([1 if c <= GUTTER_MAX_INK else 0 for c in coverage[lo:hi]], 1)
    if not clear:
        return None
    start, end = max(clear, key=lambda run: run[1] - run[0])
    # A real gutter is a narrow strip with a table's edge on each side. A clear run reaching the
    # end of the search area is just an empty part of the page.
    bounded = start > 0 and end < hi - lo - 1
    return (lo + start, lo + end) if bounded and end - start + 1 >= GUTTER_MIN_WIDTH else None


def _classified_grade(table, block):
    """
    (grade number, conf) from the "Classified as Grade: 4" line printed above a block, or None.
    Only the strip between the previous table and this block's header is read.
    """
    first_top, first_bottom = table.rows[block[0].index]
    row_height = first_bottom - first_top
    top = max(round(first_top - CLASS_LINE_ABOVE[0] * row_height), 0)
    bottom = round(first_top - CLASS_LINE_ABOVE[1] * row_height)
    if bottom - top < row_height:
        return None
    strip = ImageOps.autocontrast(table.grey.crop((0, top, table.grey.width, bottom)))
    data = pytesseract.image_to_data(strip, lang=getattr(settings, 'OCR_LANG', 'eng'), config='--psm 6 --oem 1',
                                     output_type=pytesseract.Output.DICT)
    words = [(w.strip(), float(c)) for w, c in zip(data['text'], data['conf']) if w.strip()]
    for i, (word, _) in enumerate(words):
        if not word.lower().startswith('grade'):
            continue
        # The number follows "Grade:", sometimes glued to it or to the underline of the blank
        for text, conf in [(word[5:], words[i][1])] + words[i + 1:i + 3]:
            m = CLASS_GRADE_RE.match(text)
            if m:
                return int(m.group(1)), max(round(conf), 0)
            if text.strip(':_ ') and not text.lower().startswith('grade'):
                break  # some other word follows: the blank was left empty
    return None


def _parse_side_by_side(grey, gutter):
    """
    SF10-ES: up to four year blocks, two tables wide. Each half of the page is read as its own
    table. Blocks are named after their "Classified as Grade", or their position when that
    can't be read; blocks and subject rows left completely empty are dropped.
    """
    halves = [grey.crop((0, 0, gutter[1], grey.height)), grey.crop((gutter[0], 0, grey.width, grey.height))]
    found = []   # (top of block, half index, table, block, grade cells)
    for h, half in enumerate(halves):
        table = _find_table(half, join_across_blank_rows=True)
        for block, cells in (table.blocks if table else []):
            # A learning area typed in the Remedial Classes table sits in a table with too few
            # columns for quarterly grades; it is not a year block
            if cells[0] is not None:
                found.append((table.rows[block[0].index][0], h, table, block, cells))
    if not found:
        return None
    # Reading order: across each band of the page, then down. Blocks of one band start at about the same height.
    band = grey.height * BLOCK_BAND_TOLERANCE
    found.sort(key=lambda f: (round(f[0] / band), f[1]))

    # A block is named after its grade only when the grades read make sense together: a pupil's
    # blocks run in order, so a repeat or a step backwards means one was misread (a handwritten
    # 1 as a 2, say). The whole form then falls back to block numbers, which are never wrong.
    grades = [_classified_grade(table, block) for _, _, table, block, _ in found]
    read = [g[0] for g in grades if g]
    trusted = all(a < b for a, b in zip(read, read[1:]))
    suffixes, levels = {}, []
    for n, ((_, h, _, block, _), grade) in enumerate(zip(found, grades), start=1):
        named = bool(grade) and trusted
        if named:
            levels.append((f'Grade {grade[0]}', grade[1]))
        suffixes.update({(h, row.index): f'Grade {grade[0]}' if named else f'Block {n}' for row in block})

    fields = []
    half_of = {}   # one labeller for the page, so two blocks read as the same grade still get distinct names
    label_of = _unique_labeller(lambda row: suffixes[(half_of[id(row)], row.index)])
    for _, h, table, block, cells in found:
        half_of.update({id(row): h for row in block})
        block_fields = _read_jobs(_block_jobs(table, block, cells, label_of))
        per_row = len(GRADE_COLUMNS)
        for i in range(0, len(block_fields), per_row):
            row_fields = block_fields[i:i + per_row]
            if any(f['status'] != 'null' for f in row_fields):
                fields.extend(row_fields)
    if not fields:
        # Nothing is filled in anywhere: report the first block's rows so the caller can say so
        _, h, table, block, cells = found[0]
        fields = _read_jobs(_block_jobs(table, block, cells, _unique_labeller(lambda row: suffixes[(h, row.index)])))
        return fields, levels
    return fields, levels


# ── Entry point ──────────────────────────────────────────────────────────────

def parse_grade_table(grey):
    """
    (grade fields read cell by cell, levels read). Levels are (label, conf) pairs in page
    order: the year level written after the subjects on a Form 137-A ("I", "II"), or each
    block's "Grade N" on an SF10-ES. Returns None if no ruled grade table with subjects was found.
    """
    gutter = find_gutter(grey)
    if gutter:
        result = _parse_side_by_side(grey, gutter)
        if result:
            return result
    return _parse_single(grey)
