"""Subject matching and the free-text grade parser (used when no table grid is found)."""
import re

from ..constants import NA

GRADE_RE = re.compile(r'\b([6-9][0-9]|100)\b')
NULL_RE = re.compile(r'\b(N/?A|NIA|n/a)\b', re.IGNORECASE)
# Grade level written after the subject on secondary forms ("English I", "English II", ...)
LEVEL_RE = re.compile(r'\b(IV|V?I{1,3}|VI)\b')

# Common Tesseract misreads of handwritten grades
OCR_FIXES = {
    'ae': '88', 'as': '85', 'a0': '80', 'a1': '81', 'al': '81', 'a2': '82', 'a3': '83',
    'a4': '84', 'a6': '86', 'a7': '87', 'a8': '88', 'a9': '89',
    '7s': '75', '8s': '85', '9s': '95',
    'Bs': '85', 'B2': '82', 'B3': '83', 'B4': '84', 'B5': '85', 'B6': '86', 'B7': '87', 'B8': '88', 'B9': '89',
    'S2': '82', 'S3': '83', 'S5': '85', 'S6': '86',
    'NIA': NA, 'Nia': NA, 'nia': NA,
}

# (pattern, canonical name) — checked in order, first match wins. Word boundaries keep
# short aliases like "TLE"/"AP" from matching inside other words; "Edu\w*" tolerates
# typos on real forms (e.g. "Technology and Livelihood Eduation").
SUBJECT_ALIASES = [(re.compile(pattern, re.IGNORECASE), name) for pattern, name in [
    # Learning areas of the SF10-ES. The longer names come first: "Arabic Language" must not
    # match as "Language", nor "Physical Education & Health" as something shorter.
    (r'\bArabic\s+Language\b',                                            'Arabic Language'),
    (r'\bIslamic\s+Values(?:\s+Edu\w*)?\b',                               'Islamic Values Education'),
    (r'\bReading\s+and\s+Literacy\b',                                     'Reading and Literacy'),
    (r'\bPhysical\s+Edu\w*(?:\s*(?:&|and)\s*Health)?\b',                  'Physical Education & Health'),
    (r'\bMusic\s*(?:&|and)\s*Arts?\b',                                    'Music & Arts'),
    (r'\bGMRC\b|\bGood\s+Manners\b',                                      'GMRC'),
    (r'\bMakabansa\b',                                                    'Makabansa'),
    (r'\bMother\s+Tongue\b',                                              'Mother Tongue'),
    (r'\bFilipino\b',                                                     'Filipino'),
    (r'\bEnglish\b',                                                      'English'),
    (r'\bMath(?:ematics)?\b',                                             'Mathematics'),
    (r'\bScience\b',                                                      'Science'),
    (r'\bAraling\s+Panlipunan\b|\bAP\b',                                  'Araling Panlipunan'),
    (r'\bEdukasyon\s+sa\s+Pagpapakatao\b|\bEsP\b',                        'Edukasyon sa Pagpapakatao'),
    (r'\bTechnology\s+and\s+Livelihood(?:\s+Edu\w*)?\b|\bTLE\b|\bEPP\b',  'EPP / TLE'),
    (r'\bMAPEH\b',                                                        'MAPEH'),
    (r'\bMAKABAYAN\b',                                                    'MAKABAYAN'),
    (r'\bLanguage\b',                                                     'Language'),
]]

GRADE_COLUMNS = ('Q1', 'Q2', 'Q3', 'Q4', 'Final')
DEFAULT_WORD_CONF = 80
FIXED_WORD_CONF = 72  # confidence given to a value repaired via OCR_FIXES


def make_field(name, raw, value, conf, status):
    return {'field': name, 'raw': raw, 'value': value, 'conf': conf, 'status': status, 'flagged': status == 'warn'}


def match_subject_span(text):
    """(canonical subject, index just past the match) for the first alias found, else None."""
    for rx, name in SUBJECT_ALIASES:
        m = rx.search(text)
        if m:
            return name, m.end()
    return None


def match_subject(line):
    span = match_subject_span(line)
    return span[0] if span else None


def _subject_label(line, subject, seen):
    """
    Form 137 has one block per school year (e.g. "English I", "English II"),
    so field names must carry the level or they collide across blocks.
    """
    level = LEVEL_RE.search(line)
    label = f'{subject} {level.group(1)}' if level else subject
    seen[label] = seen.get(label, 0) + 1
    return f'{label} #{seen[label]}' if seen[label] > 1 else label


def _grade_tokens(line, word_conf):
    """Up to five (value, raw_token, confidence) tuples found on a subject line."""
    numbers = []
    for token in line.split():
        cleaned = OCR_FIXES.get(token, token)
        if NULL_RE.match(cleaned):
            numbers.append((NA, token, 0))
        elif GRADE_RE.match(cleaned):
            conf = word_conf.get(token, DEFAULT_WORD_CONF) if token == cleaned else FIXED_WORD_CONF
            numbers.append((cleaned, token, conf))
        if len(numbers) == len(GRADE_COLUMNS):
            break
    return numbers


def parse_grade_lines(text, word_conf, threshold):
    fields = []
    seen = {}
    for line in text.split('\n'):
        line = line.strip()
        subject = match_subject(line)
        if not subject:
            continue
        label = _subject_label(line, subject, seen)
        numbers = _grade_tokens(line, word_conf)
        for i, column in enumerate(GRADE_COLUMNS):
            value, raw, conf = numbers[i] if i < len(numbers) else (NA, '', 0)
            if value == NA or conf == 0:
                status = 'null'
            elif conf < threshold:
                status = 'warn'
            else:
                status = 'ok'
            fields.append(make_field(f'{label} {column}', raw, value, conf, status))
    return fields
