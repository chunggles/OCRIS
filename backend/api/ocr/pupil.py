"""
Reads the pupil's details from the page: name, LRN, grade level, section and school year.

Handles both layouts:
  - elementary Form 137 / SF10:  "Name: SANTOS, MARIA", "Grade 6", "S.Y. 2024-2025"
  - secondary Form 137-A:        the name sits on a line above "(Surname)  (Given Name)"
                                 labels, and each year block has "School Year 20_09_ - 20_10_"

Fields are for display and for comparing against what was typed on the upload form;
the saved record uses the typed details.
"""
import re
from datetime import date

from ..constants import NA
from .parser import make_field

NAME_LABEL_RE = re.compile(r'Name[:\s]+([A-Z][A-Z,.\s]+?)(?:\s{2,}|Grade|LRN|$)', re.IGNORECASE | re.MULTILINE)
NAME_STOP_RE = re.compile(r'^(date|birth|sex|lrn)', re.IGNORECASE)
LRN_RE = re.compile(r'LRN[:\s]+(\d{10,12})', re.IGNORECASE)
GRADE_RE = re.compile(r'\bGrade\s*(?:Level)?[:\s]*(\d{1,2})\b', re.IGNORECASE)
SECTION_RE = re.compile(r'\bSection[\s:_]+([A-Za-z][A-Za-z\-]*)')

# A year digit as Tesseract may misread it on forms with underlined blanks
YEAR_DIGIT = r'[0-9OoQDIl|]'
# "School Year 20_09_ - 20_10_", "S.Y. 2024-2025". The end year is optional because it is
# often misread ("20 _II" for 2011); a school year always runs start → start + 1.
SCHOOL_YEAR_RE = re.compile(
    rf'(?:School\s*Year|\bS\.\s*Y\.?)[\s:_]*'
    rf'({YEAR_DIGIT}{{2}}(?:[\s_]*{YEAR_DIGIT}{{2}})?)[\s_]*[-–]'
    rf'(?:[\s_]*({YEAR_DIGIT}{{2}}(?:[\s_]*{YEAR_DIGIT}{{2}})?))?',
    re.IGNORECASE,
)
DIGIT_FIXES = str.maketrans({'O': '0', 'o': '0', 'Q': '0', 'D': '0', 'I': '1', 'l': '1', '|': '1'})
EARLIEST_SCHOOL_YEAR = 1950


class Page:
    """
    The page's words as text lines, with each word's position in the joined text so a
    regex match can be traced back to the Tesseract confidence of the words it used.
    """

    def __init__(self, data):
        self.lines = []          # [[{'text', 'left', 'right', 'conf'}]]
        keys = {}
        for i, text in enumerate(data['text']):
            if not text.strip():
                continue
            key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            if key not in keys:
                keys[key] = len(self.lines)
                self.lines.append([])
            self.lines[keys[key]].append({
                'text': text.strip(),
                'left': data['left'][i],
                'right': data['left'][i] + data['width'][i],
                'conf': max(round(float(data['conf'][i])), 0),
            })

        parts, self.spans, offset = [], [], 0   # spans: (start, end, conf) per word
        for line in self.lines:
            for k, word in enumerate(line):
                if k:
                    parts.append(' '); offset += 1
                parts.append(word['text'])
                self.spans.append((offset, offset + len(word['text']), word['conf']))
                offset += len(word['text'])
            parts.append('\n'); offset += 1
        self.text = ''.join(parts)

    def conf(self, start, end):
        """Mean confidence of the words overlapping text[start:end]."""
        confs = [c for s, e, c in self.spans if s < end and e > start]
        return round(sum(confs) / len(confs)) if confs else 0


# ── Individual fields: each returns (value, confidence) or None ──────────────

def _name_from_labels(page):
    """
    "SURNAME, GIVEN NAMES" from a line sitting above "(Surname)" and "(Given Name)" labels.
    Each word is assigned to the label it sits above, so multi-word surnames work.
    """
    lines = page.lines
    for i in range(1, len(lines)):
        surname_label = next((w for w in lines[i] if 'surname' in w['text'].lower()), None)
        given_label = next((w for w in lines[i] if 'given' in w['text'].lower()), None)
        if not (surname_label and given_label):
            continue
        split_x = (surname_label['right'] + given_label['left']) / 2
        surname, given, confs = [], [], []
        stop = False
        for word in lines[i - 1]:
            centre = (word['left'] + word['right']) / 2
            for part in (p for p in re.split(r'_+', word['text']) if p):
                if NAME_STOP_RE.match(part):
                    stop = True
                    break
                clean = re.sub(r"[^A-Za-zÑñ.'\-]", '', part)
                if clean and clean != '.':
                    (surname if centre < split_x else given).append(clean.upper())
                    confs.append(word['conf'])
            if stop:
                break
        if surname and given:
            return f"{' '.join(surname)}, {' '.join(given)}", round(sum(confs) / len(confs))
    return None


def _name(page):
    labelled = _name_from_labels(page)
    if labelled:
        return labelled
    m = NAME_LABEL_RE.search(page.text)
    return (m.group(1).strip(), page.conf(*m.span(1))) if m else None


def _lrn(page):
    m = LRN_RE.search(page.text)
    return (m.group(1), page.conf(*m.span(1))) if m else None


def _year(digits, century_hint=None):
    digits = re.sub(r'[\s_]', '', digits).translate(DIGIT_FIXES)
    if not digits.isdigit():
        return None
    if len(digits) == 2:
        return int(f'{century_hint or 20}{digits}')
    return int(digits) if len(digits) == 4 else None


def _school_years(page):
    """
    All school years in page order, e.g. ('2009-2010, 2010-2011', conf). The start year
    decides the value; a readable end year must equal start + 1, otherwise the match is
    treated as a misread and skipped. An unreadable end year is allowed.
    """
    found, confs = [], []
    for m in SCHOOL_YEAR_RE.finditer(page.text):
        start = _year(m.group(1))
        if not start or not EARLIEST_SCHOOL_YEAR <= start <= date.today().year + 1:
            continue
        end = _year(m.group(2), century_hint=str(start)[:2]) if m.group(2) else None
        if end is not None and end != start + 1 and len(re.sub(r'[\s_]', '', m.group(2))) == 4:
            continue  # a full, readable end year that contradicts the start
        value = f'{start}-{start + 1}'
        if value not in found:
            found.append(value)
            confs.append(page.conf(*m.span(1)))
    return (', '.join(found), round(sum(confs) / len(confs))) if found else None


def _sections(page):
    found, confs = [], []
    for m in SECTION_RE.finditer(page.text):
        section = m.group(1).upper()
        if section not in found:
            found.append(section)
            confs.append(page.conf(*m.span(1)))
    return (', '.join(found), min(confs)) if found else None


def _grade_level(page, year_levels):
    m = GRADE_RE.search(page.text)
    if m:
        return f'Grade {int(m.group(1))}', page.conf(*m.span(1))
    if year_levels:
        # Secondary forms have no grade printed; use the grade table's year blocks
        return ', '.join(f'Year {level}' for level, _ in year_levels), min(conf for _, conf in year_levels)
    return None


# ── Entry point ──────────────────────────────────────────────────────────────

def extract_pupil_info(page, year_levels=()):
    """
    Pupil fields read from the page. year_levels are the grade table's year blocks as
    (level, confidence) pairs, e.g. [('I', 95), ('II', 91)], used as the grade level when
    no "Grade N" is printed.
    """
    found = {
        'Pupil Name':  _name(page),
        'LRN':         _lrn(page),
        'Grade Level': _grade_level(page, year_levels),
        'Section':     _sections(page),
        'School Year': _school_years(page),
    }
    fields = []
    for name, result in found.items():
        if result:
            value, conf = result
            fields.append(make_field(name, value, value, conf, 'ok'))
        else:
            fields.append(make_field(name, NA, NA, 0, 'null'))
    return fields
