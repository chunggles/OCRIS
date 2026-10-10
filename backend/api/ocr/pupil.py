"""
Reads the pupil's details from the page: name, LRN, grade level, section and school year.

Handles both layouts:
  - elementary Form 137:         "Name: SANTOS, MARIA", "Grade 6", "S.Y. 2024-2025"
  - SF10-ES:                     "LAST NAME: … FIRST NAME: …", and each year block has
                                 "Classified as Grade: 4  Section: …  School Year: 2025-2026"
  - secondary Form 137-A:        the name sits on a line above "(Surname)  (Given Name)"
                                 labels, and each year block has "School Year 20_09_ - 20_10_"

Fields are for display and for comparing against what was typed on the upload form;
the saved record uses the typed details.
"""
import difflib
import re
from datetime import date

from ..constants import NA
from .parser import make_field

NAME_LABEL_RE = re.compile(r'Name[:\s]+([A-Z][A-Z,.\s]+?)(?:\s{2,}|Grade|LRN|$)', re.IGNORECASE | re.MULTILINE)
NAME_STOP_RE = re.compile(r'^(date|birth|sex|lrn)', re.IGNORECASE)
# SF10-ES: "LAST NAME: DELA CRUZ FIRST NAME: JANELLE MAE NAME EXTN. (Jr,I,II) ___ MIDDLE NAME: ANTONIO"
# The colon after a label is often read as ";" or "." (or dropped), so any of these may follow one
SEP = r'[:;.,\s_]'
SF10_NAME_RE = re.compile(
    rf'LAST\s+NAME{SEP}+(?P<last>[^:;\n]*?)[\s_]*FIRST\s+NAME{SEP}+(?P<first>[^:;\n]*?)[\s_]*(?:NAME\s+EX|MIDDLE\s+NAME|$)',
    re.IGNORECASE | re.MULTILINE)
# "LRN: 1234…" and the SF10-ES "Learner Reference Number (LRN): 1234…"
LRN_RE = re.compile(rf'LRN\)?{SEP}+(\d{{10,12}})', re.IGNORECASE)
# Not the SF10-ES line "Credential Presented for Grade 1:", which is printed on every form
GRADE_RE = re.compile(r'(?<!for )\bGrade\s*(?:Level)?[:\s]*(\d{1,2})\b', re.IGNORECASE)
# On an SF10-ES a blank section is followed by the next label ("Section: ____ School Year:").
# A capital I at the start of a name is often read as "!" or "|" ("!!ang-llang" for Ilang-Ilang).
SECTION_RE = re.compile(rf'\bSection{SEP}+(?!School\b)([A-Za-z!|](?:[A-Za-z!|\-]*[A-Za-z])?)')
SECTION_FIXES = str.maketrans({'!': 'I', '|': 'I'})
LIST_FIELDS = ('Grade Level', 'Section', 'School Year')
KNOWN_SECTION_MIN_RATIO = 0.7   # how alike a read section and one on the Sections page must be to be taken as it

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


def _name_from_sf10(page):
    """ "SURNAME, GIVEN NAMES" from the SF10-ES line "LAST NAME: … FIRST NAME: …". """
    m = SF10_NAME_RE.search(page.text)
    if not m:
        return None
    last, first = (re.sub(r"[^A-Za-zÑñ.'\- ]", '', m.group(g)).strip().upper() for g in ('last', 'first'))
    if not (last and first):
        return None
    return f'{last}, {first}', round((page.conf(*m.span('last')) + page.conf(*m.span('first'))) / 2)


def _name(page):
    labelled = _name_from_sf10(page) or _name_from_labels(page)
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


def _known_section(text, known_sections):
    """
    The section on the Sections page that a read section most resembles, in capitals, or the
    text as read if none is close. Letter shapes are compared loosely, since I and l are read
    for each other ("IIANG-LLANG" for ILANG-ILANG).
    """
    def shape(name):
        return name.upper().replace('L', 'I')

    best = max(known_sections, key=lambda name: difflib.SequenceMatcher(None, shape(text), shape(name)).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, shape(text), shape(best)).ratio() >= KNOWN_SECTION_MIN_RATIO:
        return best.upper()
    return text


def _sections(page, known_sections=()):
    found, confs = [], []
    for m in SECTION_RE.finditer(page.text):
        section = _known_section(m.group(1).translate(SECTION_FIXES).upper(), known_sections)
        if section not in found:
            found.append(section)
            confs.append(page.conf(*m.span(1)))
    return (', '.join(found), min(confs)) if found else None


def _grade_level(page, year_levels):
    # An SF10-ES has a "Classified as Grade" per year block, read with the grade table
    classified = [(level, conf) for level, conf in year_levels if level.startswith('Grade')]
    if classified:
        return ', '.join(dict.fromkeys(level for level, _ in classified)), min(conf for _, conf in classified)
    m = GRADE_RE.search(page.text)
    if m:
        return f'Grade {int(m.group(1))}', page.conf(*m.span(1))
    if year_levels:
        # Secondary forms have no grade printed; use the grade table's year blocks
        return ', '.join(f'Year {level}' for level, _ in year_levels), min(conf for _, conf in year_levels)
    return None


# ── Entry point ──────────────────────────────────────────────────────────────

def _read_details(page, year_levels, known_sections):
    return {
        'Pupil Name':  _name(page),
        'LRN':         _lrn(page),
        'Grade Level': _grade_level(page, year_levels),
        'Section':     _sections(page, known_sections),
        'School Year': _school_years(page),
    }


def _better(name, a, b):
    """The better of two readings of a field, each (value, conf) or None."""
    if not (a and b):
        return a or b
    if name in LIST_FIELDS:
        # one value per year block: the reading that found more of them is the more complete
        count_a, count_b = len(a[0].split(', ')), len(b[0].split(', '))
        if count_a != count_b:
            return a if count_a > count_b else b
    return a if a[1] >= b[1] else b


def extract_pupil_info(page, year_levels=(), known_sections=(), other_pages=()):
    """
    Pupil fields read from the page. year_levels are the grade table's year blocks as
    (level, confidence) pairs, e.g. [('I', 95), ('II', 91)], used as the grade level when
    no "Grade N" is printed. known_sections are the section names set up in the system; a
    section read from the page is corrected to the one it most resembles. other_pages are
    further readings of the same page; for each field the better reading is kept.
    """
    found = _read_details(page, year_levels, known_sections)
    # A second reading of the same page (see engine.run_ocr) fills in what the first missed
    for other in other_pages:
        for name, result in _read_details(other, year_levels, known_sections).items():
            found[name] = _better(name, found[name], result)
    fields = []
    for name, result in found.items():
        if result:
            value, conf = result
            fields.append(make_field(name, value, value, conf, 'ok'))
        else:
            fields.append(make_field(name, NA, NA, 0, 'null'))
    return fields
