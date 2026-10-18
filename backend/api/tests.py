"""
API tests. Run with: python manage.py test

They need MongoDB running and use a throwaway database (ocris_test_...) that is dropped
after every test, so the real database is never touched. Without MongoDB they are skipped.
"""
import tempfile
import uuid
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api import db
from api.models import AuthAttempt, LoginSession, OCRISUser
from api.services import audit_chain, crypto, grading, maintenance, storage

TEST_DB = f'ocris_test_{uuid.uuid4().hex[:8]}'
PASSWORD = 'test-pass-123'


def _mongo_available():
    try:
        db.get_client().admin.command('ping')
        return True
    except Exception:
        return False


def tiny_png():
    from PIL import Image
    out = BytesIO()
    Image.new('RGB', (20, 20), 'white').save(out, 'PNG')
    return out.getvalue()


def _grades(**finals):
    return {subject: {'Q1': 'N/A', 'Q2': 'N/A', 'Q3': 'N/A', 'Q4': 'N/A', 'final': final} for subject, final in finals.items()}


class GradingTests(SimpleTestCase):
    def remarks(self, **finals):
        grades = _grades(**finals)
        return grading.remarks_for(grading.compute_general_average(grades), grades)

    def test_remarks_rules(self):
        self.assertEqual(self.remarks(English='88', Math='80'), 'Promoted')
        self.assertEqual(self.remarks(English='88', Math='74'), 'Retained')
        self.assertEqual(self.remarks(English='88', Math='?'), 'Incomplete')
        self.assertEqual(self.remarks(English='70', Math='?'), 'Retained')
        self.assertEqual(self.remarks(English='88', Math='N/A'), 'Promoted')
        self.assertEqual(self.remarks(English='N/A'), 'Incomplete')

    def test_general_average_skips_blank_grades(self):
        self.assertEqual(grading.compute_general_average(_grades(English='90', Math='N/A', Science='80')), '85.0')


class YearBlockTests(SimpleTestCase):
    def field(self, name, value):
        return {'field': name, 'value': value}

    def sf10_fields(self):
        return [
            self.field('Filipino Grade 1 Q1', '80'), self.field('Filipino Grade 1 Final', '81'),
            self.field('Filipino Grade 2 Q1', '90'), self.field('Filipino Grade 2 Final', '91'),
            self.field('EPP Grade 2 Final', '85'), self.field('Unread learning area Grade 2 Final', '70'),
            self.field('Pupil Name', 'SANTOS, MARIA'),
        ]

    def test_labels_are_split_into_subject_and_year_block(self):
        self.assertEqual(grading.split_label('Filipino Grade 2'), ('Filipino', 'Grade 2'))
        self.assertEqual(grading.split_label('English II #2'), ('English #2', 'II'))
        self.assertEqual(grading.split_label('Araling Panlipunan Block 3'), ('Araling Panlipunan', 'Block 3'))
        self.assertEqual(grading.split_label('Mathematics'), ('Mathematics', None))
        self.assertEqual((grading.block_number('Grade 4'), grading.block_number('III'), grading.block_number('Block 1')), (4, 3, None))

    def test_subject_names_have_one_spelling(self):
        for name in ('EPP', 'TLE', 'EPP / TLE', 'Technology and Livelihood Education'):
            self.assertEqual(grading.normalize_subject(name), 'EPP / TLE')
        self.assertEqual(grading.normalize_subject('GMRC (Good Manners and Right Conduct)'), 'GMRC')
        self.assertEqual(grading.normalize_subject('*Arabic Language'), 'Arabic Language')
        self.assertEqual(grading.normalize_subject('  Unread   learning area '), 'Unread learning area')
        merged = grading.clean_subjects({'EPP': {'Q1': '80', 'final': 'N/A'}, 'TLE': {'Q1': '99', 'final': '82'}})
        self.assertEqual(merged, {'EPP / TLE': {'Q1': '80', 'final': '82'}})

    def test_a_form_with_several_years_is_filed_as_one_year(self):
        blocks = grading.build_year_blocks(self.sf10_fields(), {'Filipino Grade 1 Final': '83'}, {'Unread learning area Grade 2': 'Science'})
        self.assertEqual([label for label, _ in blocks], ['Grade 1', 'Grade 2'])
        grades, others = grading.choose_year_block(blocks, 'Grade 2')
        self.assertEqual(sorted(grades), ['EPP / TLE', 'Filipino', 'Science'])
        self.assertEqual(grades['Filipino']['final'], '91')
        self.assertEqual([o['label'] for o in others], ['Grade 1'])
        self.assertEqual(others[0]['grades']['Filipino']['final'], '83')   # the correction applied to its own year
        # a grade level that matches no block takes the last one
        self.assertEqual(grading.choose_year_block(blocks, 'Grade 6')[0], grades)
        grades, others = grading.choose_year_block(blocks, 'Grade 1')
        self.assertEqual((sorted(grades), others[0]['label']), (['Filipino'], 'Grade 2'))

    def test_a_form_with_one_year_has_nothing_left_over(self):
        blocks = grading.build_year_blocks([self.field('English Final', '88')], {})
        self.assertEqual(grading.choose_year_block(blocks, 'Grade 3'), ({'English': {'final': '88'}}, []))


class YearBlockLabelTests(SimpleTestCase):
    """How year blocks are named after their "Classified as Grade", and how extra PDF pages are added."""

    def numbers(self, *reads):
        from api.ocr.table import _consistent_grades
        return _consistent_grades([(n, 90) if n else None for n in reads])

    def test_grades_read_in_order_are_kept(self):
        self.assertEqual(self.numbers(1, 2, 3, 4), ([1, 2, 3, 4], []))
        self.assertEqual(self.numbers(1, 3, 4), ([1, 3, 4], []))             # in order: taken as read
        self.assertEqual(self.numbers(None, None, 3, None), ([None, None, 3, None], []))   # one read is not enough to fill in

    def test_blocks_that_could_not_be_read_follow_the_sequence(self):
        self.assertEqual(self.numbers(None, 2, 3, None), ([1, 2, 3, 4], []))
        self.assertEqual(self.numbers(None, None), ([None, None], []))

    def test_a_misread_grade_follows_the_other_blocks_and_is_reported(self):
        numbers, notes = self.numbers(1, 2, 5, 4)
        self.assertEqual(numbers, [1, 2, 3, 4])
        self.assertEqual(len(notes), 1)
        self.assertIn('Block 3 reads as Grade 5 but was filed as Grade 3', notes[0])
        # no clear majority, or a sequence that would leave Grade 1 to 6: no block is named after its grade
        self.assertEqual(self.numbers(2, 1, 4, 3), ([None] * 4, []))
        self.assertEqual(self.numbers(5, 6, 5, 6)[0], [None] * 4)

    def test_later_pages_of_a_pdf_are_added_once(self):
        from unittest import mock
        from api.ocr import engine

        def field(name):
            return {'field': name, 'value': '85', 'raw': '85', 'conf': 95, 'status': 'ok', 'flagged': False}

        first = [field('Filipino Grade 1 Q1'), field('Filipino Grade 2 Q1')]
        later = [([field('Filipino Grade 5 Q1')], [('Grade 5', 90)], []),   # page 2: new grades
                 None,                                                       # page 3: no grade table
                 ([field('Filipino Grade 1 Q1')], [], [])]                   # page 4: repeats page 1
        with mock.patch.object(engine, 'load_page', return_value=(None, 300, 4)),                 mock.patch.object(engine, 'parse_grade_table', side_effect=later):
            grades, levels, notes = engine._add_later_pages('x.pdf', 4, first, [('Grade 1', 90)], [])
        self.assertEqual([f['field'] for f in grades], ['Filipino Grade 1 Q1', 'Filipino Grade 2 Q1', 'Filipino Grade 5 Q1'])
        self.assertEqual(levels, [('Grade 1', 90), ('Grade 5', 90)])
        self.assertEqual(len(notes), 3)
        self.assertIn('Page 3 has no grade table', ' '.join(notes))
        self.assertIn('Page 4 repeats learning areas', ' '.join(notes))


class PdfScanTests(SimpleTestCase):
    """A PDF is turned into an image of its first page, so the OCR pipeline can read it."""

    def pdf(self, pages=1):
        from PIL import Image
        page = Image.new('RGB', (850, 1300), 'white')
        page.paste((0, 0, 0), (100, 100, 750, 110))  # a ruled line, so the page isn't blank
        buffer = BytesIO()
        page.save(buffer, 'PDF', resolution=100, save_all=True, append_images=[page] * (pages - 1))
        buffer.seek(0)
        return buffer

    def test_pdf_page_is_rendered_at_scan_resolution(self):
        from api.ocr.pdf import open_scan
        image, pages = open_scan(self.pdf(pages=3))
        self.assertEqual(pages, 3)
        self.assertEqual(image.info['dpi'], (300, 300))
        self.assertEqual(image.width, 2550)  # 8.5" x 13" at 300 DPI; the renderer may round up a pixel
        self.assertAlmostEqual(image.height, 3900, delta=2)
        self.assertLess(image.getpixel((1200, 315))[0], 50)    # the line is there...
        self.assertGreater(image.getpixel((1200, 600))[0], 200)  # ...on a white page

    def test_quality_check_reads_a_pdf(self):
        from api.ocr.quality import analyze_image
        result = analyze_image(self.pdf(pages=2))
        self.assertEqual(result['pages'], 2)
        self.assertIn('300 DPI', result['metrics'][0]['value'])

    def pdf_with_text_box(self, box):
        """A blank one-page PDF with a text box that has no appearance of its own, as some PDF tools write them."""
        objects = [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 936] /Annots [4 0 R] >>',
            b'<< /Type /Annot /Subtype /FreeText /Rect [100 800 300 830] /Contents (88) '
            b'/DS (font: normal normal 20pt Arial;text-align:left;color:#000000) /DA () >>' if box else b'<< /Type /Annot /Subtype /Text /Rect [0 0 1 1] >>',
        ]
        out, offsets = b'%PDF-1.4\n', []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += b'%d 0 obj\n' % number + body + b'\nendobj\n'
        xref = len(out)
        out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offsets)
        out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
        return BytesIO(out)

    def test_text_boxes_typed_onto_a_pdf_are_drawn(self):
        """Grades filled in with a PDF tool sit in text boxes over the page; without them the form reads as blank."""
        from api.ocr.pdf import open_scan

        def darkest(image):
            # the box's rectangle, 100-300 pt across and 800-830 pt up a 936 pt page, at 300 DPI
            return image.convert('L').crop((417, 442, 1250, 567)).getextrema()[0]

        filled, _ = open_scan(self.pdf_with_text_box(True))
        blank, _ = open_scan(self.pdf_with_text_box(False))
        self.assertLess(darkest(filled), 60)
        self.assertGreater(darkest(blank), 240)

    def test_unreadable_files_give_a_clear_message(self):
        from api.ocr.quality import analyze_image
        self.assertIn('damaged or password-protected', analyze_image(BytesIO(b'%PDF-1.4 not a real pdf'))['error'])
        self.assertIn('JPG, PNG or PDF', analyze_image(BytesIO(b'just some text'))['error'])


class Sf10LayoutTests(SimpleTestCase):
    """The parts of reading an SF10-ES that don't need the OCR engine."""

    def page(self, tables):
        """A white page with ruled boxes at the given (left, right) x-ranges, from 35% to 90% of its height."""
        from PIL import Image, ImageDraw
        page = Image.new('L', (1000, 1500), 255)
        draw = ImageDraw.Draw(page)
        for left, right in tables:
            for y in range(525, 1351, 25):
                draw.line((left, y, right, y), fill=0, width=2)
            for x in (left, (left + right) // 2, right):
                draw.line((x, 525, x, 1350), fill=0, width=2)
        return page

    def test_gutter_is_found_only_between_side_by_side_tables(self):
        from api.ocr.table import find_gutter
        left, right = find_gutter(self.page([(40, 492), (508, 960)]))
        self.assertTrue(492 < left <= right < 508)
        self.assertIsNone(find_gutter(self.page([(40, 960)])))   # one table across the page: Form 137-A
        self.assertIsNone(find_gutter(self.page([])))            # a page with no clear strip to speak of is not split

    def test_sf10_learning_areas_are_recognised(self):
        from api.ocr.parser import match_subject
        for text, subject in (
            ('Language', 'Language'), ('*Arabic Language', 'Arabic Language'), ('Reading and Literacy', 'Reading and Literacy'),
            ('GMRC (Good Manners and Right Conduct)', 'GMRC'), ('Makabansa', 'Makabansa'), ('Music & Arts', 'Music & Arts'),
            ('Physical Education & Health', 'Physical Education & Health'), ('*Islamic Values Education', 'Islamic Values Education'),
            ('EPP', 'EPP / TLE'), ('Araling Panlipunan', 'Araling Panlipunan'),
        ):
            self.assertEqual(match_subject(text), subject, text)
        for text in ('General Average', 'LEARNING AREAS', 'Remedial Classes'):
            self.assertIsNone(match_subject(text), text)

    def test_sf10_learner_details_are_read_from_the_page_text(self):
        from api.ocr.pupil import Page, extract_pupil_info
        lines = [
            'LAST NAME: DELA CRUZ FIRST NAME: JANELLE MAE NAME EXTN. (Jr,I,II) ____ MIDDLE NAME: ANTONIO',
            'Learner Reference Number (LRN): 104567890123 Birthdate (mm/dd/yyyy): 07/28/2016 Sex: F',
            'Credential Presented for Grade 1: Kinder Progress Report ECCD Checklist',
            'Classified as Grade: 4 Section: Athena School Year: 2025-2026',
            'Classified as Grade: ___ Section: ______ School Year: ______',
        ]
        words = [(word, n) for n, line in enumerate(lines) for word in line.split()]
        page = Page({
            'text': [w for w, _ in words], 'conf': [90] * len(words), 'block_num': [1] * len(words), 'par_num': [1] * len(words),
            'line_num': [n for _, n in words], 'left': list(range(len(words))), 'width': [1] * len(words),
        })
        read = {f['field']: f['value'] for f in extract_pupil_info(page, [('Grade 4', 90)])}
        self.assertEqual(read['Pupil Name'], 'DELA CRUZ, JANELLE MAE')
        self.assertEqual(read['LRN'], '104567890123')
        self.assertEqual(read['Grade Level'], 'Grade 4')   # not the "for Grade 1" of the credential line
        self.assertEqual(read['Section'], 'ATHENA')        # a blank section isn't read as "SCHOOL"
        self.assertEqual(read['School Year'], '2025-2026')

    def page_of(self, lines, conf=90):
        from api.ocr.pupil import Page
        words = [(word, n) for n, line in enumerate(lines) for word in line.split()]
        return Page({
            'text': [w for w, _ in words], 'conf': [conf] * len(words), 'block_num': [1] * len(words), 'par_num': [1] * len(words),
            'line_num': [n for _, n in words], 'left': list(range(len(words))), 'width': [1] * len(words),
        })

    def test_learner_details_survive_common_misreads(self):
        from api.ocr.pupil import extract_pupil_info
        # ";" and "." read for ":", "!!" for a capital I, and the label after the first name cut short
        misread = self.page_of([
            'LAST NAME; DELA CRUZ FIRST NAME: JUAN MIGUEL NAME EX DEL MIDDLE NAME: SANTOS',
            'Leamer Reference Number (LRN). 123456789012 Birthdate (mmidd/yyyy); 03/19/2016',
            'Classified as Grade: 3 Section. !!ang-llang School Year: 2024-2025',
        ], conf=60)
        read = {f['field']: f['value'] for f in extract_pupil_info(misread, known_sections=['Ilang-Ilang', 'Rosal'])}
        self.assertEqual(read['Pupil Name'], 'DELA CRUZ, JUAN MIGUEL')
        self.assertEqual(read['LRN'], '123456789012')
        self.assertEqual(read['Section'], 'ILANG-ILANG')   # corrected to the section set up in the system

        # A second reading of the page fills in what the first one missed
        partial = self.page_of(['Classified as Grade: 3 Section: Rosal School Year: 2024-2025'], conf=95)
        both = {f['field']: f['value'] for f in extract_pupil_info(partial, other_pages=[misread])}
        self.assertEqual(both['Pupil Name'], 'DELA CRUZ, JUAN MIGUEL')
        self.assertEqual(both['Section'], 'ROSAL')         # the more confident of two single readings


@skipUnless(_mongo_available(), 'MongoDB is not running')
@override_settings(MONGO_DB_NAME=TEST_DB, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # fast hashing for tests only
class ApiTestCase(TestCase):
    def setUp(self):
        self.media = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=self.media))
        self.addCleanup(self._drop_test_database)

        self.oic = self.make_user('oic', OCRISUser.OIC)
        self.admin = self.make_user('admin', OCRISUser.ADMIN)
        self.teacher = self.make_user('teacher', OCRISUser.TEACHER, 'Grade 6', 'Sampaguita')
        self.unassigned = self.make_user('newteacher', OCRISUser.TEACHER)

    def _drop_test_database(self):
        assert settings.MONGO_DB_NAME.startswith('ocris_test_')
        db.get_client().drop_database(settings.MONGO_DB_NAME)

    def make_user(self, username, role, grade=None, section=None):
        return OCRISUser.objects.create_user(
            username=username, password=PASSWORD, role=role, assigned_grade=grade, assigned_section=section)

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make_scan(self, grade='Grade 6', section='Sampaguita', with_file=False, **extra):
        filename = ''
        if with_file:
            directory = storage.scans_dir()
            directory.mkdir(parents=True, exist_ok=True)
            filename = f'{uuid.uuid4().hex[:8]}_form.png'
            (directory / filename).write_bytes(b'image')
        return db.create_scan({
            'filename': filename, 'original_name': 'form.png', 'pupil_name': 'Santos, Maria',
            'grade_level': grade, 'section': section, 'school_year': '2024-2025',
            'ocr_fields': [
                {'field': 'English Final', 'value': '88', 'raw': '88', 'conf': 90, 'status': 'ok'},
                {'field': 'Mathematics Final', 'value': '?', 'raw': '?', 'conf': 0, 'status': 'warn'},
            ],
            **extra,
        })

    def make_record(self, grade='Grade 6', section='Sampaguita', name='Santos, Maria', **extra):
        return db.create_record({
            'pupil_name': name, 'grade_level': grade, 'section': section, 'school_year': '2024-2025',
            'grades': _grades(English='88'), 'general_average': '88.0', 'remarks': 'Promoted', **extra,
        })

    def validate_payload(self, scan_id, **overrides):
        return {
            'scan_id': scan_id, 'pupil_name': 'Santos, Maria', 'grade_level': 'Grade 6', 'section': 'Sampaguita',
            'school_year': '2024-2025', 'corrections': [{'field': 'Mathematics Final', 'corrected_val': '80'}],
            'confirmed': True, **overrides,
        }


class ClassAccessTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.own = self.make_record()
        self.other = self.make_record(grade='Grade 5', section='Orchid', name='Reyes, Ana')

    def test_teacher_lists_only_own_class(self):
        data = self.as_user(self.teacher).get('/api/records/').data
        self.assertEqual([r['record_id'] for r in data['results']], [self.own])
        self.assertEqual(self.as_user(self.admin).get('/api/records/').data['total'], 2)

    def test_section_match_ignores_case(self):
        self.make_record(section='SAMPAGUITA', name='Cruz, Jose')
        self.assertEqual(self.as_user(self.teacher).get('/api/records/').data['total'], 2)
        self.assertEqual(self.as_user(self.oic).get('/api/records/?section=sampaguita').data['total'], 2)

    def test_teacher_cannot_open_record_of_another_class(self):
        client = self.as_user(self.teacher)
        self.assertEqual(client.get(f'/api/records/{self.own}/').status_code, 200)
        self.assertEqual(client.get(f'/api/records/{self.other}/').status_code, 403)
        self.assertEqual(self.as_user(self.admin).get(f'/api/records/{self.other}/').status_code, 200)

    def test_teacher_analytics_and_history_are_limited_to_own_class(self):
        self.make_scan()
        self.make_scan(grade='Grade 5', section='Orchid')
        client = self.as_user(self.teacher)
        self.assertEqual(client.get('/api/analytics/').data['total_records'], 1)
        self.assertEqual(client.get('/api/analytics/?grade=Grade 5').data['total_records'], 1)  # can't widen
        self.assertEqual(client.get('/api/ocr/history/').data['total'], 1)
        self.assertEqual(self.as_user(self.oic).get('/api/analytics/').data['total_records'], 2)
        self.assertEqual(self.as_user(self.oic).get('/api/ocr/history/').data['total'], 2)

    def test_teacher_without_a_class_sees_nothing(self):
        client = self.as_user(self.unassigned)
        for url in ('/api/records/', '/api/records/search/?q=a', '/api/records/options/',
                    '/api/analytics/', '/api/ocr/history/', f'/api/records/{self.own}/'):
            self.assertEqual(client.get(url).status_code, 403, url)

    def test_teacher_download_is_limited_to_own_class(self):
        own_scan = self.make_scan(with_file=True)
        other_scan = self.make_scan(grade='Grade 5', section='Orchid', with_file=True)
        client = self.as_user(self.teacher)
        download = client.get(f'/api/ocr/scans/{own_scan}/file/')
        self.assertEqual(download.status_code, 200)
        download.close()  # release the file so the temp folder can be removed on Windows
        self.assertEqual(client.get(f'/api/ocr/scans/{other_scan}/file/').status_code, 403)

    def test_media_folder_is_not_served_directly(self):
        scan_id = self.make_scan(with_file=True)
        filename = db.get_scan(scan_id)['filename']
        self.assertEqual(self.as_user(self.oic).get(f'/media/scans/{filename}').status_code, 404)

    def test_options_list_values_in_use(self):
        data = self.as_user(self.oic).get('/api/records/options/').data
        self.assertEqual(data['sections'], ['Orchid', 'Sampaguita'])
        self.assertEqual(data['grade_levels'], ['Grade 5', 'Grade 6'])
        self.assertEqual(self.as_user(self.teacher).get('/api/records/options/').data['sections'], ['Sampaguita'])


class RecordTests(ApiTestCase):
    def test_search_with_special_characters(self):
        self.make_record(name='Dela Cruz (Jr), Juan')
        client = self.as_user(self.oic)
        for q in ('(', '[', 'Cruz (Jr', '*', '\\'):
            response = client.get('/api/records/search/', {'q': q})
            self.assertEqual(response.status_code, 200, q)
        self.assertEqual(client.get('/api/records/search/', {'q': 'Cruz (Jr'}).data['count'], 1)
        self.assertEqual(client.get('/api/records/search/', {'q': '.*'}).data['count'], 0)

    def test_search_covers_subjects_school_year_and_scanned_text(self):
        scan_id = self.make_scan(ocr_text='Republic of the Philippines ... Transferred from Solano North')
        scanned = self.make_record(name='Reyes, Ana', scan_id=scan_id, grades=_grades(Science='90'))
        self.make_record(name='Cruz, Jose', grade='Grade 5', section='Orchid', school_year='2019-2020', grades=_grades(MAPEH='85'))
        client = self.as_user(self.oic)

        def found(q, **params):
            data = client.get('/api/records/search/', {'q': q, **params}).data
            return {r['pupil_name']: r['matched_in'] for r in data['results']}

        self.assertEqual(found('mapeh'), {'Cruz, Jose': ['subject']})
        self.assertEqual(found('2019'), {'Cruz, Jose': ['school year']})
        self.assertEqual(found('solano north'), {'Reyes, Ana': ['scanned text']})   # only written on the scanned form
        self.assertEqual(found('e'), {'Cruz, Jose': ['name', 'grade level', 'subject'],
                                      'Reyes, Ana': ['name', 'grade level', 'subject', 'scanned text']})
        self.assertEqual(list(found('e', grade='Grade 5')), ['Cruz, Jose'])   # filters narrow the search
        self.assertEqual(found('e', school_year='1999-2000'), {})
        # a teacher's search stays inside their class whatever filter is sent
        teacher = self.as_user(self.teacher).get('/api/records/search/', {'q': 'e', 'grade': 'Grade 5'}).data
        self.assertEqual([r['record_id'] for r in teacher['results']], [scanned])

    def test_search_says_when_there_are_more_matches_than_it_returns(self):
        for n in range(db.SEARCH_LIMIT + 3):
            self.make_record(name=f'Santos, Pupil {n:02d}')
        data = self.as_user(self.oic).get('/api/records/search/', {'q': 'santos'}).data
        self.assertEqual((data['count'], data['total'], data['limit']), (db.SEARCH_LIMIT, db.SEARCH_LIMIT + 3, db.SEARCH_LIMIT))

    def test_analytics_per_grading_period_and_subject(self):
        def sheet(**subjects):   # subject="Q1 Q2 Q3 Q4 final"
            return {s: dict(zip(('Q1', 'Q2', 'Q3', 'Q4', 'final'), v.split())) for s, v in subjects.items()}
        self.make_record(grades=sheet(English='80 82 84 86 83', Math='70 72 N/A ? 71'))
        self.make_record(grades=sheet(English='90 88 86 84 87', Math='80 80 80 80 80'))
        self.make_record(grade='Grade 5', section='Orchid', grades=sheet(English='60 60 60 60 60'))
        data = self.as_user(self.oic).get('/api/analytics/', {'grade': 'Grade 6'}).data

        by_subject = {s['subject']: s for s in data['subjects']}
        self.assertEqual(by_subject['English']['means'], {'Q1': 85.0, 'Q2': 85.0, 'Q3': 85.0, 'Q4': 85.0, 'final': 85.0})
        # blank and unreadable grades are left out, not counted as zero
        self.assertEqual(by_subject['Math']['means'], {'Q1': 75.0, 'Q2': 76.0, 'Q3': 80.0, 'Q4': 80.0, 'final': 75.5})
        self.assertEqual((by_subject['Math']['graded'], by_subject['Math']['passed'], by_subject['Math']['failed']), (2, 1, 1))
        self.assertEqual(by_subject['Math']['pass_rate'], 50.0)
        self.assertEqual(by_subject['English']['pass_rate'], 100.0)
        self.assertEqual([s['subject'] for s in data['subjects']], ['Math', 'English'])   # most failing grades first
        self.assertEqual(data['period_means']['Q1'], 80.0)   # (80 + 90 + 70 + 80) / 4
        self.assertEqual(data['subject_means'], {'Math': 75.5, 'English': 85.0})
        # the section filter narrows it further
        self.assertEqual(self.as_user(self.oic).get('/api/analytics/', {'section': 'Orchid'}).data['subject_means'], {'English': 60.0})

    def test_analytics_never_averages_terms_with_quarters(self):
        self.make_record(grades={'English': {'Q1': '80', 'Q2': '80', 'Q3': '80', 'Q4': '80', 'final': '80'}})
        for name, q in (('Reyes, Ana', '90'), ('Cruz, Jose', '94')):
            self.make_record(name=name, grading_period='term', grades={'English': {'Q1': q, 'Q2': q, 'Q3': q, 'Q4': 'N/A', 'final': q}})
        client = self.as_user(self.oic)
        data = client.get('/api/analytics/').data   # most records use terms
        self.assertEqual((data['grading_period'], data['period_counts']), ('term', {'quarter': 1, 'term': 2}))
        self.assertEqual(data['subjects'][0]['means'], {'Q1': 92.0, 'Q2': 92.0, 'Q3': 92.0, 'final': 88.0})   # final: all three
        self.assertEqual(data['period_means'], {'Q1': 92.0, 'Q2': 92.0, 'Q3': 92.0, 'final': 88.0})
        quarters = client.get('/api/analytics/', {'period': 'quarter'}).data
        self.assertEqual(quarters['grading_period'], 'quarter')
        self.assertEqual(quarters['subjects'][0]['means'], {'Q1': 80.0, 'Q2': 80.0, 'Q3': 80.0, 'Q4': 80.0, 'final': 88.0})
        self.assertEqual(quarters['total_records'], 3)

    def test_archived_forms_are_left_out_of_analytics(self):
        self.make_record()
        for n in range(3):
            self.make_record(name=f'Reyes, Pupil {n}', grades={}, general_average=None, remarks='', details={'archive_only': True})
        data = self.as_user(self.oic).get('/api/analytics/', {'grade': 'Grade 6'}).data
        self.assertEqual(data['total_records'], 1)
        self.assertEqual(data['pass_rates'], {'Grade 6': 100.0})   # not 25.0
        self.assertEqual(self.as_user(self.oic).get('/api/records/').data['total'], 4)   # still listed as records

    def test_archive_only_upload_stores_the_form_without_reading_it(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        def upload(**fields):
            data = {'file': SimpleUploadedFile('form.png', tiny_png(), 'image/png'), 'archive_only': 'true',
                    'grade_level': 'Grade 6', 'section': 'Sampaguita', 'school_year': '1998-1999', **fields}
            return self.as_user(self.teacher).post('/api/ocr/upload/', data, format='multipart')

        with patch('api.views.ocr.read_scan', side_effect=AssertionError('OCR must not run')):
            self.assertEqual(upload(pupil_name='  ').status_code, 400)   # the name cannot be read from the form
            self.assertEqual(db.scans_col().count_documents({}), 0)
            response = upload(pupil_name='Pulonan, Ellen Joy')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['archived'])
        record = db.get_record(response.data['record_id'])
        self.assertEqual((record['grades'], record['general_average'], record['remarks']), ({}, None, ''))
        self.assertEqual(record['details'], {'archive_only': True})
        scan = db.get_scan(response.data['scan_id'])
        self.assertEqual((scan['outcome'], scan['record_id'], scan['archive_only']), ('saved', record['record_id'], True))
        self.assertIsNotNone(storage.find_scan_file(scan['filename']))
        entry = db.audit_col().find_one({'action': 'UPLOAD'})
        self.assertTrue(entry['details']['archive_only'])
        self.assertEqual(self.as_user(self.teacher).get('/api/ocr/pending/').data['results'], [])   # nothing left to finish

    def test_archived_record_stays_without_grades_when_edited(self):
        record_id = self.make_record(scan_id=self.make_scan(), grades={}, general_average=None, remarks='',
                                     details={'archive_only': True})
        url = f'/api/records/{record_id}/update/'
        client = self.as_user(self.oic)
        # Record Detail sends the (empty) grade sheet with every edit: the remarks must not become Incomplete
        response = client.patch(url, {'pupil_name': 'Pulonan, Ellen Joy', 'grades': {}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['pupil_name'], response.data['general_average'], response.data['remarks']),
                         ('Pulonan, Ellen Joy', None, ''))
        self.assertEqual(client.patch(url, {'grades': _grades(English='88')}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'grades': {}}, format='json').status_code, 400)   # nothing left to change
        client.patch(url, {'details': {'sex': 'F'}}, format='json')
        self.assertEqual(db.get_record(record_id)['details'], {'sex': 'F', 'archive_only': True})
        self.assertEqual(db.get_record(record_id)['grades'], {})

    def test_dates_are_marked_as_utc(self):
        record_id = self.make_record()
        client = self.as_user(self.oic)
        self.assertTrue(client.get(f'/api/records/{record_id}/').data['created_at'].endswith('Z'))
        self.assertTrue(client.get('/api/records/').data['results'][0]['created_at'].endswith('Z'))

    def test_validate_creates_a_record_once(self):
        scan_id = self.make_scan()
        client = self.as_user(self.teacher)
        first = client.post('/api/ocr/validate/', self.validate_payload(scan_id), format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['general_average'], '84.0')
        self.assertEqual(first.data['remarks'], 'Promoted')
        self.assertEqual(db.get_record(first.data['record_id'])['grading_period'], 'quarter')
        second = client.post('/api/ocr/validate/', self.validate_payload(scan_id), format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(db.records_col().count_documents({}), 1)

    def test_teacher_can_only_file_forms_under_own_class(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client = self.as_user(self.teacher)
        other_class = self.validate_payload(self.make_scan(), grade_level='Grade 5', section='Orchid')
        self.assertEqual(client.post('/api/ocr/validate/', other_class, format='json').status_code, 403)
        own_class = self.validate_payload(self.make_scan(), section='SAMPAGUITA')  # case is ignored
        self.assertEqual(client.post('/api/ocr/validate/', own_class, format='json').status_code, 200)
        self.assertEqual(self.as_user(self.admin).post('/api/ocr/validate/', other_class, format='json').status_code, 200)
        self.assertEqual(self.as_user(self.unassigned).post('/api/ocr/validate/', other_class, format='json').status_code, 403)

        # An upload for another class is refused before the file is stored or read
        upload = {'file': SimpleUploadedFile('form.png', tiny_png(), 'image/png'), 'grade_level': 'Grade 5', 'section': 'Orchid'}
        self.assertEqual(client.post('/api/ocr/upload/', upload, format='multipart').status_code, 403)
        self.assertEqual(db.scans_col().count_documents({}), 2)
        self.assertFalse(storage.scans_dir().exists() and any(storage.scans_dir().iterdir()))

    def test_validate_rejects_unknown_scan_and_unconfirmed(self):
        client = self.as_user(self.teacher)
        missing = client.post('/api/ocr/validate/', self.validate_payload('SCAN-NOPE'), format='json')
        self.assertEqual(missing.status_code, 404)
        unconfirmed = client.post('/api/ocr/validate/', self.validate_payload(self.make_scan(), confirmed=False), format='json')
        self.assertEqual(unconfirmed.status_code, 400)
        self.assertEqual(db.records_col().count_documents({}), 0)

    def filled_form(self, **overrides):
        return {
            'pupil_name': 'Santos, Maria', 'lrn': '123456789012', 'grade_level': 'Grade 6', 'section': 'Sampaguita',
            'school_year': '2024-2025', 'grades': {'English': {'Q1': '88', 'final': '90'}, 'Math': {'final': '80'}},
            'details': {
                'sex': ' F ', 'middle_name': 'x' * 500, 'junk': 'x',
                'blocks': [{'grade_level': 'Grade 6', 'rows': [{'subject': 'English', 'Q1': '88'}] * 100}],
            },
            **overrides,
        }

    def test_filled_out_form_is_saved_as_a_record(self):
        response = self.as_user(self.teacher).post('/api/records/create/', self.filled_form(), format='json')
        self.assertEqual(response.status_code, 201)
        record = db.get_record(response.data['record_id'])
        self.assertEqual((record['general_average'], record['remarks']), ('85.0', 'Promoted'))
        self.assertEqual(record['grades']['English'], {'Q1': '88', 'Q2': 'N/A', 'Q3': 'N/A', 'Q4': 'N/A', 'final': '90'})
        self.assertEqual((record['uploaded_by'], record['scan_id'], record['grading_period']), ('teacher', '', 'quarter'))
        # The sheet's other details are kept, trimmed and cut to a bounded size; unknown keys are dropped
        self.assertEqual(record['details']['sex'], 'F')
        self.assertEqual(len(record['details']['middle_name']), 100)
        self.assertEqual(record['details']['blocks'][0]['grade_level'], 'Grade 6')
        self.assertEqual(len(record['details']['blocks'][0]['rows']), 40)
        self.assertEqual(record['details']['blocks'][0]['rows'][0], {'subject': 'English', 'Q1': '88'})
        self.assertNotIn('junk', record['details'])
        self.assertEqual(self.as_user(self.teacher).get('/api/records/').data['total'], 1)  # the teacher sees it

    def test_record_kept_in_terms_has_no_q4(self):
        client = self.as_user(self.oic)
        terms = {'English': {'Q1': '88', 'Q2': '90', 'Q3': '92', 'final': '90'}}
        self.assertEqual(client.post('/api/records/create/', self.filled_form(grading_period='trimester'), format='json').status_code, 400)
        with_q4 = {'English': {**terms['English'], 'Q4': '91'}}
        refused = client.post('/api/records/create/', self.filled_form(grading_period='term', grades=with_q4), format='json')
        self.assertEqual((refused.status_code, refused.data['detail']), (400, 'English: a record kept in terms has no Q4 grade.'))
        created = client.post('/api/records/create/', self.filled_form(grading_period='term', grades=terms), format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual((created.data['grading_period'], created.data['grades']['English']['Q4']), ('term', 'N/A'))
        url = f"/api/records/{created.data['record_id']}/update/"
        self.assertEqual(client.patch(url, {'grades': with_q4}, format='json').status_code, 400)
        # a quarterly record keeps its Q4, and cannot become a term record while it has one
        quarterly = self.make_record(name='Reyes, Ana', grades=_grades(English='88') | {'Math': {'Q4': '80', 'final': '80'}})
        url = f'/api/records/{quarterly}/update/'
        self.assertEqual(client.patch(url, {'grading_period': 'term'}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'grading_period': 'term', 'grades': terms}, format='json').status_code, 200)
        self.assertEqual(db.get_record(quarterly)['grading_period'], 'term')

    def test_filled_out_form_rejects_bad_input(self):
        client = self.as_user(self.teacher)
        for bad in ({'pupil_name': ' '}, {'grades': {}}, {'grades': {'English': {'final': 'abc'}}},
                    {'grades': {'English': {'final': '101'}}}):
            self.assertEqual(client.post('/api/records/create/', self.filled_form(**bad), format='json').status_code, 400, bad)
        other_class = self.filled_form(grade_level='Grade 5', section='Orchid')
        self.assertEqual(client.post('/api/records/create/', other_class, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.unassigned).post('/api/records/create/', other_class, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.admin).post('/api/records/create/', other_class, format='json').status_code, 201)
        self.assertEqual(db.records_col().count_documents({}), 1)

    def test_teacher_edits_typed_forms_of_own_class_only(self):
        teacher = self.as_user(self.teacher)
        typed = teacher.post('/api/records/create/', self.filled_form(), format='json').data['record_id']
        url = f'/api/records/{typed}/update/'
        body = {'pupil_name': 'Santos, Maria Joy', 'grades': {'English': {'final': '70'}}, 'details': {'sex': 'M'}}
        response = teacher.patch(url, body, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['pupil_name'], response.data['remarks']), ('Santos, Maria Joy', 'Retained'))
        self.assertEqual(list(response.data['grades']), ['English'])  # the sheet replaces the old grades
        self.assertEqual(response.data['details']['sex'], 'M')

        self.assertEqual(teacher.patch(url, {'section': 'Orchid'}, format='json').status_code, 403)  # can't move it away
        self.assertEqual(teacher.patch(url, {'grades': {'English': {'final': 'x'}}}, format='json').status_code, 400)
        self.assertEqual(teacher.patch(url, {'grades': {}}, format='json').status_code, 400)
        self.assertEqual(db.get_record(typed)['section'], 'Sampaguita')

        scanned = self.make_record(scan_id='SCAN-X')
        other_class = self.make_record(grade='Grade 5', section='Orchid')
        for record_id in (scanned, other_class):
            self.assertEqual(teacher.patch(f'/api/records/{record_id}/update/', body, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.unassigned).patch(url, body, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.admin).patch(f'/api/records/{other_class}/update/', body, format='json').status_code, 200)

    def sf10_scan(self):
        names = ['Filipino', 'English']
        fields = [{'field': f'{n} Grade {g} {col}', 'value': str(80 + g), 'raw': '', 'conf': 95, 'status': 'ok'}
                  for g in (5, 6) for n in names for col in ('Q1', 'Final')]
        fields.append({'field': 'Unread learning area Grade 6 Final', 'value': '?', 'raw': '?', 'conf': 0, 'status': 'warn'})
        return self.make_scan(ocr_fields=fields)

    def test_scanned_form_with_two_years_is_one_record_of_the_pupils_grade(self):
        client = self.as_user(self.admin)
        payload = self.validate_payload(
            self.sf10_scan(), corrections=[{'field': 'Unread learning area Grade 6 Final', 'corrected_val': '79'}],
            renames={'Unread learning area Grade 6': 'Science'})
        response = client.post('/api/ocr/validate/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        record = db.get_record(response.data['record_id'])
        self.assertEqual(sorted(record['grades']), ['English', 'Filipino', 'Science'])   # Grade 6 only, no year suffix
        self.assertEqual(record['grades']['English']['final'], '86')
        self.assertEqual(record['general_average'], '83.7')
        self.assertEqual(record['details']['other_years'][0]['label'], 'Grade 5')
        self.assertEqual(record['details']['other_years'][0]['grades']['Filipino']['final'], '85')

    def test_corrections_must_be_grades(self):
        scan_id = self.make_scan()
        for bad in ('abc', '101', '-1'):
            payload = self.validate_payload(scan_id, corrections=[{'field': 'Mathematics Final', 'corrected_val': bad}])
            self.assertEqual(self.as_user(self.oic).post('/api/ocr/validate/', payload, format='json').status_code, 400, bad)
        self.assertEqual(db.records_col().count_documents({}), 0)
        payload = self.validate_payload(scan_id, corrections=[{'field': 'Mathematics Final', 'corrected_val': 'N/A'}])
        self.assertEqual(self.as_user(self.oic).post('/api/ocr/validate/', payload, format='json').status_code, 200)

    def test_name_is_read_from_the_form_when_left_blank(self):
        fields = [{'field': 'Pupil Name', 'value': 'SANTOS, MARIA', 'raw': '', 'conf': 90, 'status': 'ok'},
                  {'field': 'English Final', 'value': '88', 'raw': '88', 'conf': 95, 'status': 'ok'}]
        client = self.as_user(self.oic)
        payload = {**self.validate_payload(self.make_scan(ocr_fields=fields), corrections=[]), 'pupil_name': ''}
        response = client.post('/api/ocr/validate/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.get_record(response.data['record_id'])['pupil_name'], 'SANTOS, MARIA')
        # nothing typed and nothing read: it can't be saved
        response = client.post('/api/ocr/validate/', {**self.validate_payload(self.make_scan()), 'pupil_name': ''}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_lrn_must_be_12_digits_and_belong_to_one_pupil(self):
        client = self.as_user(self.oic)
        for bad in ('12345', '12345678901x', '1234567890123'):
            payload = self.validate_payload(self.make_scan(), lrn=bad)
            self.assertEqual(client.post('/api/ocr/validate/', payload, format='json').status_code, 400, bad)
            self.assertEqual(client.post('/api/records/create/', self.filled_form(lrn=bad), format='json').status_code, 400, bad)
        spaced = client.post('/api/ocr/validate/', self.validate_payload(self.make_scan(), lrn='1234 5678-9012'), format='json')
        self.assertEqual(db.get_record(spaced.data['record_id'])['lrn'], '123456789012')
        # the same LRN under another surname is refused; under the same pupil's name, in another year, it is fine
        other = self.filled_form(pupil_name='Reyes, Ana', school_year='2023-2024')
        self.assertEqual(client.post('/api/records/create/', other, format='json').status_code, 409)
        again = self.filled_form(school_year='2023-2024')
        self.assertEqual(client.post('/api/records/create/', again, format='json').status_code, 201)

    def test_a_pupil_has_one_record_per_school_year(self):
        client = self.as_user(self.oic)
        self.assertEqual(client.post('/api/records/create/', self.filled_form(), format='json').status_code, 201)
        for body in (self.filled_form(pupil_name='Santos, M.'),      # same LRN
                     self.filled_form(pupil_name='SANTOS, MARIA', lrn='')):   # same name and grade, no LRN
            response = client.post('/api/records/create/', body, format='json')
            self.assertEqual(response.status_code, 409, body)
            self.assertIn('already has record', response.data['detail'])
        scan_id = self.make_scan()
        self.assertEqual(client.post('/api/ocr/validate/', self.validate_payload(scan_id, lrn='123456789012'), format='json').status_code, 409)
        self.assertEqual(db.get_scan(scan_id).get('outcome'), 'pending')   # the scan stays open to be fixed
        # another school year, or another pupil with a different LRN, is fine
        self.assertEqual(client.post('/api/records/create/', self.filled_form(school_year='2023-2024'), format='json').status_code, 201)
        self.assertEqual(client.post('/api/records/create/', self.filled_form(lrn='999999999999'), format='json').status_code, 201)
        self.assertEqual(db.records_col().count_documents({}), 3)

    def test_editing_into_a_duplicate_is_refused(self):
        first = self.make_record(name='Santos, Maria')
        second = self.make_record(name='Reyes, Ana')
        client = self.as_user(self.admin)
        response = client.patch(f'/api/records/{second}/update/', {'pupil_name': 'Santos, Maria'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(client.patch(f'/api/records/{first}/update/', {'pupil_name': 'Santos, Maria'}, format='json').status_code, 200)
        self.assertEqual(client.patch(f'/api/records/{first}/update/', {'lrn': '12'}, format='json').status_code, 400)

    def test_scanned_records_accept_only_grades_and_subjects_can_be_renamed(self):
        grades = {'Unread learning area Grade 6': {'final': '80'}, **_grades(English='88')}
        record_id = self.make_record(scan_id='SCAN-X', grades=grades)
        client = self.as_user(self.admin)
        url = f'/api/records/{record_id}/update/'
        self.assertEqual(client.patch(url, {'grades': {'English': {'final': 'abc'}}}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'grades': {'English': {'final': '101'}}}, format='json').status_code, 400)
        renamed = client.patch(url, {'grades': {'Science': {'final': '80'}, 'EPP': {'final': '90'}}}, format='json')
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(sorted(renamed.data['grades']), ['EPP / TLE', 'Science'])   # names are tidied as they are saved
        # a value saved earlier that is not a grade does not stop other edits
        db.update_record(record_id, {'grades': {'English': {'Q1': '?', 'final': '88'}}})
        ok = client.patch(url, {'grades': {'English': {'Q1': '?', 'final': '90'}}}, format='json')
        self.assertEqual(ok.status_code, 200)

    def test_edit_recalculates_average_and_remarks(self):
        record_id = self.make_record(scan_id='SCAN-X')
        body = {'pupil_name': 'Santos, Maria Joy', 'grades': {'English': {'Q1': '80', 'final': '70'}}}
        self.assertEqual(self.as_user(self.teacher).patch(f'/api/records/{record_id}/update/', body, format='json').status_code, 403)
        response = self.as_user(self.admin).patch(f'/api/records/{record_id}/update/', body, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['pupil_name'], 'Santos, Maria Joy')
        self.assertEqual(response.data['general_average'], '70.0')
        self.assertEqual(response.data['remarks'], 'Retained')
        self.assertEqual(response.data['grades']['English'], {'Q1': '80', 'Q2': 'N/A', 'Q3': 'N/A', 'Q4': 'N/A', 'final': '70'})

    def test_edit_rejects_bad_input(self):
        record_id = self.make_record()
        client = self.as_user(self.admin)
        url = f'/api/records/{record_id}/update/'
        self.assertEqual(client.patch(url, {'remarks': 'Promoted', 'record_id': 'X'}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'pupil_name': '  '}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'grades': {'English': {'Q9': '80'}}}, format='json').status_code, 400)
        self.assertEqual(db.get_record(record_id)['remarks'], 'Promoted')

    def test_delete_keeps_the_scan_as_an_audit_trail(self):
        scan_id = self.make_scan(with_file=True)
        path = storage.find_scan_file(db.get_scan(scan_id)['filename'])
        record_id = self.make_record(scan_id=scan_id)
        self.assertEqual(self.as_user(self.teacher).delete(f'/api/records/{record_id}/delete/').status_code, 403)
        self.assertEqual(self.as_user(self.admin).delete(f'/api/records/{record_id}/delete/').status_code, 204)
        self.assertIsNone(db.get_record(record_id))
        scan = db.get_scan(scan_id)
        self.assertEqual((scan['outcome'], scan['record_deleted_by']), ('record deleted', 'admin'))
        self.assertTrue(path.exists())
        entry = db.audit_col().find_one({'action': 'DELETE'})
        self.assertEqual(entry['details']['record']['grades'], _grades(English='88'))   # what was deleted can be restored by hand
        # The scan is purged only on request, once old enough
        call_command('cleanup_scans', '--deleted-days', '30', stdout=StringIO())
        self.assertTrue(path.exists())
        db.scans_col().update_one({'scan_id': scan_id}, {'$set': {'record_deleted_at': datetime.utcnow() - timedelta(days=31)}})
        call_command('cleanup_scans', '--deleted-days', '30', stdout=StringIO())
        self.assertFalse(path.exists())
        self.assertIsNone(db.get_scan(scan_id))

    def test_pending_scans_are_counted(self):
        self.make_scan()
        saved = self.make_scan()
        db.mark_scan_saved(saved, 'REC-X', 0)
        self.assertEqual(self.as_user(self.oic).get('/api/analytics/').data['pending_scans'], 1)


class AccountTests(ApiTestCase):
    def login(self, username, password=PASSWORD, client=None):
        return (client or self.browser()).post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def browser(self):
        """A client that behaves like the OCRIS site: it keeps cookies and sends the request header."""
        return APIClient(HTTP_X_OCRIS_REQUEST='1')

    def signed_in(self, username, password=PASSWORD):
        client = self.browser()
        self.assertEqual(self.login(username, password, client).status_code, 200)
        return client

    def test_login_returns_user_and_records_last_login(self):
        response = self.login('teacher')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['role'], 'TEACHER')
        self.assertEqual(response.data['user']['assigned_section'], 'Sampaguita')
        self.assertNotIn('token', response.data)   # the sign-in lives in a cookie scripts cannot read
        cookie = response.cookies[settings.AUTH_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.teacher.refresh_from_db()
        self.assertIsNotNone(self.teacher.last_login)

    def test_session_expires(self):
        client = self.signed_in('teacher')
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)
        LoginSession.objects.update(created=timezone.now() - timedelta(hours=settings.TOKEN_TTL_HOURS + 1))
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        # Signing in again gives a working session
        self.assertEqual(self.signed_in('teacher').get('/api/auth/me/').status_code, 200)

    def test_only_a_hash_of_the_session_cookie_is_stored(self):
        import hashlib
        cookie = self.login('teacher').cookies[settings.AUTH_COOKIE_NAME].value
        stored = LoginSession.objects.get().key
        self.assertEqual(stored, hashlib.sha256(cookie.encode()).hexdigest())
        thief = self.browser()   # someone with a copy of the database
        thief.cookies[settings.AUTH_COOKIE_NAME] = stored
        self.assertEqual(thief.get('/api/auth/me/').status_code, 401)

    def test_sessions_left_behind_are_cleared_at_the_next_sign_in(self):
        self.signed_in('teacher')
        self.signed_in('admin')
        LoginSession.objects.filter(user=self.teacher).update(created=timezone.now() - timedelta(hours=settings.TOKEN_TTL_HOURS + 1))
        LoginSession.objects.filter(user=self.admin).update(last_active=timezone.now() - timedelta(minutes=settings.IDLE_TIMEOUT_MINUTES + 1))
        self.signed_in('oic')
        self.assertEqual(list(LoginSession.objects.values_list('user__username', flat=True)), ['oic'])

    def test_upgrade_keeps_existing_sessions(self):
        import importlib
        from django.apps import apps
        LoginSession.objects.create(key='cookie-from-before', user=self.teacher)   # stored as it was
        importlib.import_module('api.migrations.0004_hash_session_keys').hash_keys(apps, None)
        client = self.browser()
        client.cookies[settings.AUTH_COOKIE_NAME] = 'cookie-from-before'
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)

    def test_change_own_password(self):
        client = self.signed_in('teacher')
        url = '/api/auth/change-password/'
        self.assertEqual(client.post(url, {'current_password': 'wrong', 'new_password': 'new-pass-456'}, format='json').status_code, 400)
        self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': 'short'}, format='json').status_code, 400)
        self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': 'new-pass-456'}, format='json').status_code, 200)
        self.assertEqual(self.login('teacher').status_code, 400)
        self.assertEqual(self.login('teacher', 'new-pass-456').status_code, 200)

    def test_oic_resets_password_and_edits_user(self):
        client = self.signed_in('teacher')
        body = {'first_name': 'Gloria', 'assigned_section': 'Rosal', 'password': 'reset-pass-789'}
        self.assertEqual(self.as_user(self.admin).patch(f'/api/users/{self.teacher.pk}/', body, format='json').status_code, 403)
        response = self.as_user(self.oic).patch(f'/api/users/{self.teacher.pk}/', body, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Gloria')
        self.assertEqual(response.data['assigned_section'], 'Rosal')
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)  # signed out everywhere
        self.assertEqual(self.login('teacher', 'reset-pass-789').status_code, 200)
        short = self.as_user(self.oic).patch(f'/api/users/{self.teacher.pk}/', {'password': 'short'}, format='json')
        self.assertEqual(short.status_code, 400)

    def test_last_oic_cannot_be_demoted_or_deactivated(self):
        client = self.as_user(self.oic)
        url = f'/api/users/{self.oic.pk}/'
        self.assertEqual(client.patch(url, {'role': 'ADMIN'}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'is_active': False}, format='json').status_code, 400)
        self.make_user('oic2', OCRISUser.OIC)
        self.assertEqual(client.patch(url, {'role': 'ADMIN'}, format='json').status_code, 200)


class SectionTests(ApiTestCase):
    def add(self, name, grade='Grade 1', user=None):
        body = {'name': name, 'grade_level': grade}
        return self.as_user(user or self.oic).post('/api/sections/create/', body, format='json')

    def tree(self, user=None):
        """The section tree as {grade level: [section names]}."""
        nodes = self.as_user(user or self.oic).get('/api/sections/').data
        return {node['grade_level']: [s['name'] for s in node['sections']] for node in nodes}

    def test_add_and_list_sections(self):
        self.assertEqual(self.add('Rosal', 'Grade 2').status_code, 201)
        self.assertEqual(self.add('  Sampaguita ', user=self.admin).data['name'], 'Sampaguita')
        self.add('Orchid')
        self.assertEqual(self.tree(self.teacher), {
            'Grade 1': ['Orchid', 'Sampaguita'], 'Grade 2': ['Rosal'],
            'Grade 3': [], 'Grade 4': [], 'Grade 5': [], 'Grade 6': [],
        })

    def test_add_rejects_bad_input(self):
        self.add('Rosal')
        self.assertEqual(self.add('').status_code, 400)
        self.assertEqual(self.add('Rosal', 'Grade 7').status_code, 400)
        self.assertEqual(self.add('ROSAL').status_code, 400)  # same name in the same grade
        self.assertEqual(self.add('Rosal', 'Grade 2').status_code, 201)  # other grades may reuse a name
        self.assertEqual(self.add('Jasmine', user=self.teacher).status_code, 403)
        self.assertEqual((self.tree()['Grade 1'], self.tree()['Grade 2']), (['Rosal'], ['Rosal']))

    def test_edit_section(self):
        self.add('Orchid')
        url = f"/api/sections/{self.add('Rosal').data['section_id']}/"
        self.assertEqual(self.as_user(self.teacher).patch(url, {'name': 'Jasmine'}, format='json').status_code, 403)
        self.assertEqual(self.as_user(self.oic).patch(url, {'name': 'orchid'}, format='json').status_code, 400)
        self.assertEqual(self.as_user(self.oic).patch(url, {'name': 'rosal'}, format='json').data['name'], 'rosal')
        moved = self.as_user(self.admin).patch(url, {'name': 'Jasmine', 'grade_level': 'Grade 3'}, format='json')
        self.assertEqual((moved.data['name'], moved.data['grade_level']), ('Jasmine', 'Grade 3'))
        self.assertEqual((self.tree()['Grade 1'], self.tree()['Grade 3']), (['Orchid'], ['Jasmine']))  # moved to the new parent
        self.assertEqual(self.as_user(self.oic).patch('/api/sections/SEC-NOPE/', {'name': 'X'}, format='json').status_code, 404)

    def test_delete_section_keeps_records(self):
        record_id = self.make_record(grade='Grade 1', section='Rosal')
        url = f"/api/sections/{self.add('Rosal').data['section_id']}/"
        self.assertEqual(self.as_user(self.teacher).delete(url).status_code, 403)
        self.assertEqual(self.as_user(self.admin).delete(url).status_code, 204)
        self.assertEqual(self.as_user(self.admin).delete(url).status_code, 404)
        self.assertEqual(self.tree()['Grade 1'], [])
        self.assertEqual(db.get_record(record_id)['section'], 'Rosal')

    def test_renaming_a_section_moves_its_records_and_teachers(self):
        section_id = self.add('Sampaguita', 'Grade 6').data['section_id']
        record_id = self.make_record(grade='Grade 6', section='sampaguita')   # case differs, still the same section
        other = self.make_record(grade='Grade 5', section='Sampaguita', name='Reyes, Ana')   # another grade's section of that name
        nodes = self.as_user(self.oic).get('/api/sections/').data
        counts = {(n['grade_level'], s['name']): (s['records'], s['teachers']) for n in nodes for s in n['sections']}
        self.assertEqual(counts[('Grade 6', 'Sampaguita')], (1, 1))

        response = self.as_user(self.oic).patch(f'/api/sections/{section_id}/', {'name': 'Dahlia'}, format='json')
        self.assertEqual((response.data['records'], response.data['teachers']), (1, 1))
        self.assertEqual(db.get_record(record_id)['section'], 'Dahlia')
        self.assertEqual(db.get_record(other)['section'], 'Sampaguita')
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.assigned_section, 'Dahlia')
        self.assertEqual(self.as_user(self.teacher).get('/api/records/').data['total'], 1)   # still sees the class

    def test_a_section_with_teachers_cannot_be_deleted(self):
        section_id = self.add('Sampaguita', 'Grade 6').data['section_id']
        response = self.as_user(self.oic).delete(f'/api/sections/{section_id}/')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Assign them', response.data['detail'])
        self.assertEqual(self.tree()['Grade 6'], ['Sampaguita'])
        self.teacher.assigned_section = 'Orchid'
        self.teacher.save()
        self.assertEqual(self.as_user(self.oic).delete(f'/api/sections/{section_id}/').status_code, 204)


class CommandTests(ApiTestCase):
    def test_cleanup_scans_removes_only_old_pending_scans(self):
        old = self.make_scan(with_file=True)
        old_saved = self.make_scan()
        recent = self.make_scan()
        long_ago = datetime.utcnow() - timedelta(days=30)
        db.scans_col().update_many({'scan_id': {'$in': [old, old_saved]}}, {'$set': {'created_at': long_ago}})
        db.mark_scan_saved(old_saved, 'REC-X', 0)
        path = storage.find_scan_file(db.get_scan(old)['filename'])

        call_command('cleanup_scans', '--dry-run', stdout=StringIO())
        self.assertIsNotNone(db.get_scan(old))
        call_command('cleanup_scans', stdout=StringIO())
        self.assertIsNone(db.get_scan(old))
        self.assertFalse(path.exists())
        self.assertIsNotNone(db.get_scan(old_saved))
        self.assertIsNotNone(db.get_scan(recent))

    def test_tidy_records_splits_old_scanned_year_blocks(self):
        grades = {'Filipino Grade 1': {'final': '80'}, 'Filipino Grade 2': {'final': '90'}, 'EPP Grade 2': {'final': '70'}}
        record_id = self.make_record(grade='Grade 2', grades=grades, general_average='80.0')
        clean = self.make_record(name='Reyes, Ana', grades=_grades(English='88'))
        call_command('tidy_records', '--dry-run', stdout=StringIO())
        self.assertEqual(len(db.get_record(record_id)['grades']), 3)
        call_command('tidy_records', stdout=StringIO())
        record = db.get_record(record_id)
        self.assertEqual(sorted(record['grades']), ['EPP / TLE', 'Filipino'])
        self.assertEqual((record['general_average'], record['remarks']), ('80.0', 'Retained'))
        self.assertEqual(record['details']['other_years'][0]['label'], 'Grade 1')
        self.assertEqual(db.get_record(clean)['grades'], _grades(English='88'))

    def test_recompute_remarks_fixes_old_records(self):
        stale = self.make_record(grades=_grades(English='88', Math='?'), general_average='88.0', remarks='Retained')
        fine = self.make_record()
        call_command('recompute_remarks', stdout=StringIO())
        self.assertEqual(db.get_record(stale)['remarks'], 'Incomplete')
        self.assertEqual(db.get_record(fine)['remarks'], 'Promoted')

    def test_repair_commands_leave_archived_records_alone(self):
        old_scan = self.make_scan()   # archived before scans carried the flag
        archived = self.make_record(scan_id=old_scan, grades={}, general_average=None, remarks='', details={'archive_only': True})
        read_scan = self.make_scan()
        self.make_record(name='Reyes, Ana', scan_id=read_scan)
        call_command('recompute_remarks', stdout=StringIO())
        self.assertEqual((db.get_record(archived)['remarks'], db.get_record(archived)['general_average']), ('', None))
        call_command('tidy_records', '--dry-run', stdout=StringIO())
        self.assertFalse(db.get_scan(old_scan)['archive_only'])
        out = StringIO()
        call_command('tidy_records', stdout=out)
        self.assertIn('Marked 1 archived scan(s).', out.getvalue())
        self.assertTrue(db.get_scan(old_scan)['archive_only'])
        self.assertFalse(db.get_scan(read_scan)['archive_only'])
        self.assertEqual(db.get_record(archived)['remarks'], '')

    def test_tidy_records_marks_forms_typed_in_terms(self):
        typed = {'grades': _grades(English='88'), 'details': {'certifications': [{}], 'blocks': []}}
        two_page = self.make_record(**typed)
        older = self.make_record(name='Reyes, Ana', details={'sex': 'F'})
        scanned = self.make_record(name='Cruz, Jose', scan_id=self.make_scan(), **typed)
        for record_id in (two_page, older, scanned):   # saved before records carried grading_period
            db.records_col().update_one({'record_id': record_id}, {'$unset': {'grading_period': ''}})
        call_command('tidy_records', '--dry-run', stdout=StringIO())
        self.assertNotIn('grading_period', db.get_record(two_page))
        out = StringIO()
        call_command('tidy_records', stdout=out)
        self.assertIn('Marked 1 typed record(s) as kept in terms.', out.getvalue())
        self.assertEqual(db.get_record(two_page)['grading_period'], 'term')
        self.assertNotIn('grading_period', db.get_record(older))
        self.assertNotIn('grading_period', db.get_record(scanned))

    @override_settings(DATA_ENCRYPTION_KEYS=[])   # a key in .env would make the backup .zip.enc
    def test_backup_writes_a_zip(self):
        self.make_record()
        self.make_scan(with_file=True)
        out = Path(self.media) / 'backups'
        call_command('backup', '--out', str(out), stdout=StringIO())
        archives = list(out.glob('ocris-backup-*.zip'))
        self.assertEqual(len(archives), 1)
        import zipfile
        names = zipfile.ZipFile(archives[0]).namelist()
        self.assertTrue(any(n.endswith('mongo/records.json') for n in names))
        self.assertTrue(any(n.endswith('db.sqlite3') for n in names))
        self.assertTrue(any('/scans/' in n and n.endswith('_form.png') for n in names))


class SecurityTests(ApiTestCase):
    """Weaknesses 30 to 38: sign-in limits, passwords, sessions, encryption, audit trail, uploads."""

    def browser(self):
        return APIClient(HTTP_X_OCRIS_REQUEST='1')

    def login(self, username, password=PASSWORD, client=None):
        return (client or self.browser()).post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def signed_in(self, username, password=PASSWORD):
        client = self.browser()
        self.assertEqual(self.login(username, password, client).status_code, 200)
        return client

    # 30. login attempts
    def test_repeated_wrong_passwords_lock_the_username(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            self.assertEqual(self.login('teacher', 'wrong-pass-1').status_code, 400)
        locked = self.login('teacher')   # even the right password is refused while locked
        self.assertEqual(locked.status_code, 429)
        self.assertIn('Retry-After', locked)
        self.assertEqual(self.login('admin').status_code, 200)   # other accounts are unaffected
        self.assertEqual(db.audit_col().count_documents({'action': 'LOGIN_FAILED'}), settings.LOGIN_MAX_ATTEMPTS)
        self.assertEqual(db.audit_col().count_documents({'action': 'LOGIN_LOCKED'}), 1)
        AuthAttempt.objects.update(at=timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES + 1))
        self.assertEqual(self.login('teacher').status_code, 200)   # the lock ages out

    def test_a_good_login_clears_earlier_failures(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
            self.login('teacher', 'wrong-pass-1')
        self.assertEqual(self.login('teacher').status_code, 200)
        self.assertEqual(AuthAttempt.objects.filter(username='teacher').count(), 0)

    def test_unknown_usernames_are_limited_too(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            self.login('nobody', 'wrong-pass-1')
        self.assertEqual(self.login('nobody').status_code, 429)

    # 31. password rules and temporary passwords
    def test_weak_passwords_are_refused(self):
        client = self.signed_in('teacher')
        url = '/api/auth/change-password/'
        for weak in ('short1', '1234567890', 'onlyletterspassword', 'password123', 'teacher12345'):
            self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': weak}, format='json').status_code, 400, weak)
        self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': 'Good-pass-2468'}, format='json').status_code, 200)

    def test_a_temporary_password_must_be_changed_before_anything_else(self):
        oic = self.as_user(self.oic)
        body = {'username': 'newhire', 'password': 'abc', 'role': 'ADMIN', 'first_name': 'New', 'last_name': 'Hire'}
        self.assertEqual(oic.post('/api/users/create/', body, format='json').status_code, 400)
        body['password'] = 'Temp-pass-9021'
        self.assertEqual(oic.post('/api/users/create/', body, format='json').status_code, 201)

        client = self.signed_in('newhire', 'Temp-pass-9021')
        me = client.get('/api/auth/me/')
        self.assertEqual((me.status_code, me.data['must_change_password']), (200, True))
        blocked = client.get('/api/records/')
        self.assertEqual((blocked.status_code, blocked.data['code']), (403, 'password_change_required'))
        self.assertEqual(client.post('/api/ocr/validate/', {}, format='json').status_code, 403)
        done = client.post('/api/auth/change-password/', {'current_password': 'Temp-pass-9021', 'new_password': 'My-own-pass-77'}, format='json')
        self.assertEqual((done.status_code, done.data['user']['must_change_password']), (200, False))
        self.assertEqual(client.get('/api/records/').status_code, 200)

    def test_a_password_set_by_the_oic_is_temporary_unless_it_is_their_own(self):
        oic = self.as_user(self.oic)
        oic.patch(f'/api/users/{self.teacher.pk}/', {'password': 'Reset-pass-5531'}, format='json')
        oic.patch(f'/api/users/{self.oic.pk}/', {'password': 'Oic-own-pass-5531'}, format='json')
        self.teacher.refresh_from_db()
        self.oic.refresh_from_db()
        self.assertEqual((self.teacher.must_change_password, self.oic.must_change_password), (True, False))
        weak = oic.patch(f'/api/users/{self.teacher.pk}/', {'password': '12345678'}, format='json')
        self.assertEqual(weak.status_code, 400)

    # 32. cookie sign-in
    def test_requests_that_change_data_need_the_site_header(self):
        client = self.signed_in('admin')
        forged = APIClient()
        forged.cookies = client.cookies
        self.assertEqual(forged.get('/api/auth/me/').status_code, 200)   # reading is harmless
        self.assertEqual(forged.post('/api/auth/logout/').status_code, 403)
        self.assertEqual(self.login('admin', client=forged).status_code, 403)   # nor can a site sign someone in
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)

    def test_a_bad_cookie_is_just_signed_out(self):
        client = self.browser()
        client.cookies[settings.AUTH_COOKIE_NAME] = 'not-a-session'
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.login('admin', client=client).status_code, 200)   # a stale cookie never blocks signing in

    # 33. several devices
    def test_signing_out_ends_only_this_device(self):
        phone, desktop = self.signed_in('teacher'), self.signed_in('teacher')
        self.assertEqual(phone.post('/api/auth/logout/').status_code, 200)
        self.assertEqual(phone.get('/api/auth/me/').status_code, 401)
        self.assertEqual(desktop.get('/api/auth/me/').status_code, 200)

    def test_sign_out_everywhere_and_password_change(self):
        phone, desktop = self.signed_in('teacher'), self.signed_in('teacher')
        change = {'current_password': PASSWORD, 'new_password': 'Fresh-pass-3141'}
        self.assertEqual(desktop.post('/api/auth/change-password/', change, format='json').status_code, 200)
        self.assertEqual(phone.get('/api/auth/me/').status_code, 401)   # other devices are signed out
        self.assertEqual(desktop.get('/api/auth/me/').status_code, 200)  # this one stays
        self.assertEqual(desktop.post('/api/auth/logout-all/').status_code, 200)
        self.assertEqual(desktop.get('/api/auth/me/').status_code, 401)
        self.assertEqual(LoginSession.objects.filter(user=self.teacher).count(), 0)

    # 38. forgotten password
    def test_forgotten_password_request_reaches_the_oic(self):
        client = self.browser()
        known = client.post('/api/auth/forgot-password/', {'username': 'teacher'}, format='json')
        unknown = client.post('/api/auth/forgot-password/', {'username': 'nobody'}, format='json')
        self.assertEqual((known.status_code, unknown.status_code), (200, 200))
        self.assertEqual(known.data, unknown.data)   # the answer does not reveal who has an account
        self.teacher.refresh_from_db()
        self.assertIsNotNone(self.teacher.password_reset_requested_at)
        listed = {u['username']: u for u in self.as_user(self.oic).get('/api/users/').data}
        self.assertIsNotNone(listed['teacher']['password_reset_requested_at'])
        self.assertIsNone(listed['admin']['password_reset_requested_at'])
        self.assertEqual(db.audit_col().count_documents({'action': 'PASSWORD_RESET_REQUEST'}), 1)

        self.as_user(self.oic).patch(f'/api/users/{self.teacher.pk}/', {'password': 'Reset-pass-5531'}, format='json')
        self.teacher.refresh_from_db()
        self.assertIsNone(self.teacher.password_reset_requested_at)

    def test_reset_requests_are_limited(self):
        client = self.browser()
        for _ in range(settings.RESET_MAX_REQUESTS):
            self.assertEqual(client.post('/api/auth/forgot-password/', {'username': 'teacher'}, format='json').status_code, 200)
        self.assertEqual(client.post('/api/auth/forgot-password/', {'username': 'teacher'}, format='json').status_code, 429)

    # 34. encryption at rest
    def test_scans_are_encrypted_on_disk_and_readable_through_the_app(self):
        from cryptography.fernet import Fernet
        from django.core.files.uploadedfile import SimpleUploadedFile
        content = tiny_png()
        with self.settings(DATA_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            name, path = storage.save_upload(SimpleUploadedFile('form.png', content, 'image/png'))
            self.assertTrue(path.read_bytes().startswith(crypto.MAGIC))
            self.assertNotIn(content[:16], path.read_bytes())
            with storage.plain_copy(path) as readable:
                self.assertEqual(Path(readable).read_bytes(), content)
            self.assertFalse(Path(readable).exists())   # the temporary readable copy is gone

            scan_id = db.create_scan({'filename': name, 'original_name': 'form.png', 'grade_level': 'Grade 6', 'section': 'Sampaguita'})
            response = self.as_user(self.oic).get(f'/api/ocr/scans/{scan_id}/file/')
            self.assertEqual(b''.join(response.streaming_content), content)
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertIn('attachment; filename="form.png"', response['Content-Disposition'])
            response.close()

            legacy = storage.scans_dir() / 'old_form.png'
            legacy.write_bytes(content)   # written before encryption was switched on
            self.assertEqual(crypto.read_plain(legacy), content)
            out = StringIO()
            call_command('encrypt_scans', stdout=out)
            self.assertTrue(crypto.is_encrypted(legacy))
            self.assertEqual(crypto.read_plain(legacy), content)
            self.assertIn('Encrypted 1 file(s)', out.getvalue())

        with self.settings(DATA_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):   # a different key cannot read it
            with self.assertRaises(crypto.CryptoError):
                crypto.read_plain(path)

    def test_a_large_file_is_encrypted_in_pieces(self):
        from cryptography.fernet import Fernet
        data = bytes(range(256)) * (crypto.CHUNK_SIZE // 256 * 2 + 5)
        with self.settings(DATA_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            path = Path(self.media) / 'big.bin'
            path.write_bytes(data)
            crypto.encrypt_file(path)
            self.assertEqual(crypto.read_plain(path), data)
            empty = Path(self.media) / 'empty.bin'
            empty.write_bytes(b'')
            crypto.encrypt_file(empty)
            self.assertEqual(crypto.read_plain(empty), b'')

    def test_keys_can_be_rotated(self):
        from cryptography.fernet import Fernet
        old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        path = Path(self.media) / 'rotate.bin'
        path.write_bytes(b'secret')
        with self.settings(DATA_ENCRYPTION_KEYS=[old]):
            crypto.encrypt_file(path)
        with self.settings(DATA_ENCRYPTION_KEYS=[new, old]):   # the new key writes, the old one still reads
            self.assertEqual(crypto.read_plain(path), b'secret')

    def test_backup_is_encrypted_and_can_be_decrypted(self):
        from cryptography.fernet import Fernet
        self.make_record()
        out = Path(self.media) / 'backups'
        with self.settings(DATA_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            call_command('backup', '--out', str(out), stdout=StringIO())
            archives = list(out.glob('ocris-backup-*.zip.enc'))
            self.assertEqual((len(archives), len(list(out.glob('*.zip')))), (1, 0))
            self.assertTrue(crypto.is_encrypted(archives[0]))
            call_command('decrypt_backup', str(archives[0]), stdout=StringIO())
            import zipfile
            names = zipfile.ZipFile(archives[0].with_suffix('')).namelist()
            self.assertTrue(any(n.endswith('mongo/records.json') for n in names))

    # 35. audit trail
    def test_edits_record_old_and_new_values(self):
        record_id = self.make_record()
        body = {'pupil_name': 'Santos, Maria Joy', 'grades': {'English': {'Q1': '80', 'final': '70'}}}
        self.as_user(self.admin).patch(f'/api/records/{record_id}/update/', body, format='json')
        entry = db.audit_col().find_one({'action': 'EDIT'})['details']
        self.assertEqual(entry['changes']['pupil_name'], {'old': 'Santos, Maria', 'new': 'Santos, Maria Joy'})
        self.assertIn({'subject': 'English', 'period': 'final', 'old': '88', 'new': '70'}, entry['grade_changes'])
        self.assertIn({'subject': 'English', 'period': 'Q1', 'old': 'N/A', 'new': '80'}, entry['grade_changes'])

    def test_validation_records_what_the_ocr_read_and_what_replaced_it(self):
        scan_id = self.make_scan()
        self.as_user(self.teacher).post('/api/ocr/validate/', self.validate_payload(scan_id), format='json')
        entry = db.audit_col().find_one({'action': 'VALIDATE'})['details']
        self.assertEqual(entry['corrected'], [{'field': 'Mathematics Final', 'read': '?', 'new': '80'}])

    def test_user_edits_record_old_and_new_values(self):
        self.as_user(self.oic).patch(f'/api/users/{self.teacher.pk}/', {'assigned_section': 'Rosal'}, format='json')
        entry = db.audit_col().find_one({'action': 'EDIT_USER'})['details']
        self.assertEqual(entry['changes']['assigned_section'], {'old': 'Sampaguita', 'new': 'Rosal'})

    def audit_file(self):
        path = Path(self.media) / 'audit.jsonl'
        self.enterContext(self.settings(AUDIT_LOG_FILE=path))
        return path

    def check_audit(self):
        """(passed, report text) of manage.py verify_audit."""
        out = StringIO()
        try:
            call_command('verify_audit', stdout=out)
            return True, out.getvalue()
        except CommandError as e:
            return False, out.getvalue() + str(e)

    def test_every_audit_entry_is_also_written_to_a_file(self):
        import json
        path = self.audit_file()
        db.log_action('LOGIN', 'teacher', {'role': 'TEACHER'})
        db.log_action('LOGOUT', 'teacher')
        first, second = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual((first['action'], first['user'], first['details']), ('LOGIN', 'teacher', {'role': 'TEACHER'}))
        self.assertTrue(first['timestamp'].endswith('Z'))
        self.assertEqual((first['prev'], second['prev']), ('', first['hash']))   # each line holds the one before
        self.assertEqual(db.audit_col().find_one({'action': 'LOGOUT'})['hash'], second['hash'])
        self.assertNotIn('hash', self.as_user(self.oic).get('/api/audit/').data['results'][0])
        self.assertEqual(self.check_audit()[0], True)
        db.audit_col().delete_many({})   # the database is wiped...
        passed, report = self.check_audit()   # ...the file still has the entries, and says they are not in the database
        self.assertTrue(passed)
        self.assertIn('2 entries are in the file but not in the database', report)

    def test_verify_audit_finds_changed_removed_and_added_lines(self):
        import json
        path = self.audit_file()
        path.write_text('{"action": "LOGIN", "user": "old", "details": {}}\n', encoding='utf-8')   # written before the chain
        for n in range(4):
            db.log_action('EDIT', 'admin', {'record_id': f'REC-{n}'})
        passed, report = self.check_audit()
        self.assertTrue(passed, report)
        self.assertIn('4 entries checked; 1 older line(s)', report)
        good = path.read_text(encoding='utf-8')
        lines = good.splitlines()

        def check_with(text):
            path.write_text(text, encoding='utf-8')
            return self.check_audit()

        edited = json.loads(lines[2])
        edited['details']['record_id'] = 'REC-X'
        passed, report = check_with('\n'.join(lines[:2] + [json.dumps(edited)] + lines[3:]) + '\n')
        self.assertFalse(passed)
        self.assertIn('Line 3 was changed after it was written.', report)
        passed, report = check_with('\n'.join(lines[:2] + lines[3:]) + '\n')   # a line removed from the middle
        self.assertIn('Line 3 does not follow the line before it', report)
        passed, report = check_with('\n'.join(lines[:-1]) + '\n')   # the end cut off
        self.assertFalse(passed)
        self.assertIn('1 entry in the database is not in the file', report)
        passed, report = check_with(good + '{"action": "LOGIN", "user": "intruder", "details": {}}\n')
        self.assertIn('Line 6 has no hash', report)
        self.assertFalse(check_with('')[0])   # the file replaced by an empty one
        path.write_text(good, encoding='utf-8')
        self.assertTrue(self.check_audit()[0])

    def test_audit_chain_holds_with_writers_at_once(self):
        from concurrent.futures import ThreadPoolExecutor
        path = Path(self.media) / 'chain.jsonl'
        with ThreadPoolExecutor(8) as pool:
            hashes = list(pool.map(lambda n: audit_chain.append(path, {'action': 'TEST', 'n': n}), range(40)))
        report = audit_chain.verify(path, hashes)
        self.assertEqual((report['entries'], report['problems'], report['missing']), (40, [], []))

    def test_audit_chain_survives_a_line_cut_off_by_a_crash(self):
        path = Path(self.media) / 'chain.jsonl'
        hashes = [audit_chain.append(path, {'action': 'A'})]
        with open(path, 'ab') as f:
            f.write('{"action": "B", "user": "é'.encode('utf-8')[:-1])   # the server stopped mid-line, mid-letter
        report = audit_chain.verify(path, hashes)
        self.assertEqual((report['problems'], report['cut_off']), ([], [2]))   # nothing written after it yet
        hashes += [audit_chain.append(path, {'action': 'C'}), audit_chain.append(path, {'action': 'D'})]
        self.assertEqual(path.read_bytes().count(b'\n'), 4)   # C is on a line of its own
        report = audit_chain.verify(path, hashes)
        self.assertEqual((report['entries'], report['problems'], report['cut_off']), (3, [], [2]))
        # the half line changed or removed afterwards still shows
        lines = path.read_bytes().split(b'\n')
        path.write_bytes(b'\n'.join(lines[:1] + [b'{"action": "X"'] + lines[2:]))
        self.assertEqual(audit_chain.verify(path, hashes)['problems'], [(2, 'cannot be read as an entry')])
        path.write_bytes(b'\n'.join(lines[:1] + lines[2:]))
        self.assertIn('was removed or changed', audit_chain.verify(path, hashes)['problems'][0][1])
        # an unreadable last line that was finished is not a crash
        path.write_bytes(b'\n'.join(lines) + b'garbage\n')
        self.assertEqual(audit_chain.verify(path, hashes)['problems'], [(5, 'cannot be read as an entry')])

    # idle sessions
    def test_a_session_unused_for_too_long_ends(self):
        from api.models import LoginSession
        client = self.signed_in('teacher')
        me = client.get('/api/auth/me/')
        self.assertEqual(me.data['idle_timeout_minutes'], settings.IDLE_TIMEOUT_MINUTES)
        idle = timedelta(minutes=settings.IDLE_TIMEOUT_MINUTES)
        LoginSession.objects.update(last_active=timezone.now() - idle + timedelta(minutes=2))
        # the app's own refresh does not count as use...
        self.assertEqual(client.get('/api/auth/me/', {'background': '1'}).status_code, 200)
        self.assertLess(LoginSession.objects.get().last_active, timezone.now() - idle + timedelta(minutes=3))
        # ...a request the user made does
        self.assertEqual(client.get('/api/records/').status_code, 200)
        self.assertGreater(LoginSession.objects.get().last_active, timezone.now() - timedelta(minutes=1))
        LoginSession.objects.update(last_active=timezone.now() - idle - timedelta(minutes=1))
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        self.assertFalse(LoginSession.objects.exists())   # the session is gone, not just refused
        with self.settings(IDLE_TIMEOUT_MINUTES=0):   # 0 turns the limit off
            client = self.signed_in('teacher')
            LoginSession.objects.update(last_active=timezone.now() - timedelta(hours=5))
            self.assertEqual(client.get('/api/auth/me/').status_code, 200)

    def test_login_response_tells_the_app_the_idle_limit(self):
        self.assertEqual(self.login('teacher').data['user']['idle_timeout_minutes'], settings.IDLE_TIMEOUT_MINUTES)

    # 37. uploads
    def post_file(self, name, content, url='/api/ocr/upload/'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = {'file': SimpleUploadedFile(name, content), 'grade_level': 'Grade 6', 'section': 'Sampaguita'}
        return self.as_user(self.teacher).post(url, data, format='multipart')

    def test_uploads_are_checked_by_content_not_by_name(self):
        for url in ('/api/ocr/upload/', '/api/ocr/quality/'):
            self.assertEqual(self.post_file('form.png', b'', url).status_code, 400)                 # empty
            self.assertEqual(self.post_file('form.png', b'<?php echo 1;', url).status_code, 415)    # not an image
            self.assertEqual(self.post_file('form.jpg', tiny_png(), url).status_code, 415)          # a PNG named .jpg
            self.assertEqual(self.post_file('form.exe', tiny_png(), url).status_code, 415)
            self.assertEqual(self.post_file('form.png', tiny_png()[:40], url).status_code, 415)     # cut off
        self.assertEqual(db.scans_col().count_documents({}), 0)
        self.assertFalse(storage.scans_dir().exists() and any(storage.scans_dir().iterdir()))

    @override_settings(MAX_UPLOAD_MB=0.0001)
    def test_oversized_uploads_are_refused(self):
        for url in ('/api/ocr/upload/', '/api/ocr/quality/'):
            self.assertEqual(self.post_file('form.png', tiny_png() + b'\0' * 500, url).status_code, 413)
        self.assertFalse(storage.scans_dir().exists() and any(storage.scans_dir().iterdir()))


class ReliabilityTests(ApiTestCase):
    """Weaknesses 39 to 43: restore, automatic cleanup, resuming an upload, class changes, indexes."""

    def backup_file(self):
        out = Path(self.media) / 'backups'
        with self.settings(DATA_ENCRYPTION_KEYS=[]):
            call_command('backup', '--out', str(out), stdout=StringIO())
        return next(out.glob('ocris-backup-*.zip'))

    def test_backup_keep_removes_the_oldest(self):
        out = Path(self.media) / 'backups'
        out.mkdir()
        for stamp in ('20240101-000000', '20240102-000000', '20240103-000000'):
            (out / f'ocris-backup-{stamp}.zip').write_bytes(b'x')
        (out / 'notes.txt').write_text('keep me')
        with self.settings(DATA_ENCRYPTION_KEYS=[]):
            call_command('backup', '--out', str(out), '--keep', '2', stdout=StringIO())
        names = sorted(f.name for f in out.iterdir())
        self.assertEqual(len(names), 3)   # the newest two backups and the unrelated file
        self.assertIn('notes.txt', names)
        self.assertNotIn('ocris-backup-20240101-000000.zip', names)
        self.assertNotIn('ocris-backup-20240102-000000.zip', names)

    def test_restore_brings_back_what_was_lost(self):
        record_id = self.make_record()
        scan_id = self.make_scan(with_file=True)
        scan_path = storage.find_scan_file(db.get_scan(scan_id)['filename'])
        archive = self.backup_file()
        db.delete_record(record_id)
        db.delete_scan(scan_id)
        scan_path.unlink()

        with patch('api.management.commands.restore.Command._restore_accounts') as accounts:
            call_command('restore', str(archive), stdout=StringIO())   # without --yes it only looks
            self.assertIsNone(db.get_record(record_id))
            accounts.assert_not_called()
            call_command('restore', str(archive), '--yes', '--skip-safety-backup', stdout=StringIO())
            accounts.assert_called_once()
        self.assertEqual(db.get_record(record_id)['pupil_name'], 'Santos, Maria')
        self.assertIsInstance(db.get_record(record_id)['created_at'], str)
        self.assertIsNotNone(db.get_scan(scan_id))
        self.assertTrue(scan_path.is_file())

    def test_restore_refuses_a_file_that_is_not_a_backup(self):
        junk = Path(self.media) / 'junk.zip'
        junk.write_bytes(b'not a zip')
        with self.assertRaises(CommandError):
            call_command('restore', str(junk), '--yes', stdout=StringIO())

    def test_restore_reads_an_encrypted_backup(self):
        record_id = self.make_record()
        out = Path(self.media) / 'backups'
        with self.settings(DATA_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            call_command('backup', '--out', str(out), stdout=StringIO())
            archive = next(out.glob('*.zip.enc'))
            db.delete_record(record_id)
            with patch('api.management.commands.restore.Command._restore_accounts'):
                call_command('restore', str(archive), '--yes', '--skip-safety-backup', stdout=StringIO())
        self.assertIsNotNone(db.get_record(record_id))

    def test_abandoned_uploads_are_removed_by_themselves_once_an_hour(self):
        old = self.make_scan(with_file=True)
        db.scans_col().update_one({'scan_id': old}, {'$set': {'created_at': datetime.utcnow() - timedelta(days=30)}})
        path = storage.find_scan_file(db.get_scan(old)['filename'])
        fresh = self.make_scan()
        maintenance.reset_schedule()
        self.assertEqual(maintenance.cleanup_if_due(), 1)
        self.assertIsNone(db.get_scan(old))
        self.assertFalse(path.exists())
        self.assertIsNotNone(db.get_scan(fresh))
        # a second old upload is left alone until the hour is up
        other = self.make_scan()
        db.scans_col().update_one({'scan_id': other}, {'$set': {'created_at': datetime.utcnow() - timedelta(days=30)}})
        self.assertEqual(maintenance.cleanup_if_due(), 0)
        self.assertIsNotNone(db.get_scan(other))

    @override_settings(PENDING_SCAN_DAYS=0)
    def test_automatic_cleanup_can_be_switched_off(self):
        old = self.make_scan()
        db.scans_col().update_one({'scan_id': old}, {'$set': {'created_at': datetime.utcnow() - timedelta(days=300)}})
        maintenance.reset_schedule()
        self.assertEqual(maintenance.cleanup_if_due(), 0)
        self.assertIsNotNone(db.get_scan(old))

    def test_maintenance_runs_backup_cleanup_and_indexes(self):
        out = Path(self.media) / 'backups'
        with self.settings(DATA_ENCRYPTION_KEYS=[]):
            call_command('maintenance', '--out', str(out), '--keep', '3', stdout=StringIO())
        self.assertEqual(len(list(out.glob('ocris-backup-*.zip'))), 1)

    def test_unsaved_uploads_can_be_listed_and_reopened(self):
        mine = self.make_scan(uploaded_by='teacher', notes=['Page 2 was skipped.'])
        saved = self.make_scan(uploaded_by='teacher')
        db.mark_scan_saved(saved, 'REC-X', 0)
        self.make_scan(uploaded_by='oic')
        teacher = self.as_user(self.teacher)
        listed = teacher.get('/api/ocr/pending/').data['results']
        self.assertEqual([s['scan_id'] for s in listed], [mine])
        scan = teacher.get(f'/api/ocr/scans/{mine}/').data
        self.assertEqual(scan['notes'], ['Page 2 was skipped.'])
        self.assertEqual(len(scan['ocr_fields']), 2)
        self.assertEqual(scan['summary']['flagged'], 1)
        self.assertEqual(teacher.get(f'/api/ocr/scans/{saved}/').status_code, 409)
        self.assertEqual(teacher.get('/api/ocr/scans/SCAN-NONE/').status_code, 404)

    def test_a_teacher_cannot_reopen_someone_elses_upload(self):
        theirs = self.make_scan(uploaded_by='oic')
        elsewhere = self.make_scan(grade='Grade 5', section='Rose', uploaded_by='teacher')
        teacher = self.as_user(self.teacher)
        self.assertEqual(teacher.get(f'/api/ocr/scans/{theirs}/').status_code, 403)
        self.assertEqual(teacher.get(f'/api/ocr/scans/{elsewhere}/').status_code, 403)
        self.assertEqual(self.as_user(self.oic).get(f'/api/ocr/scans/{theirs}/').status_code, 200)

    def test_a_class_change_shows_on_the_next_request(self):
        self.make_record(section='Orchid')
        teacher = self.as_user(self.teacher)
        self.assertEqual(teacher.get('/api/records/').data['total'], 0)
        self.assertEqual(teacher.get('/api/auth/me/').data['assigned_section'], 'Sampaguita')
        self.teacher.assigned_section = 'Orchid'
        self.teacher.save()
        self.assertEqual(teacher.get('/api/auth/me/').data['assigned_section'], 'Orchid')
        self.assertEqual(teacher.get('/api/records/').data['total'], 1)

    def test_indexes_are_created_and_repeatable(self):
        self.assertTrue(db.ensure_indexes())
        self.assertTrue(db.ensure_indexes())
        records = db.get_db()['records'].index_information()
        self.assertTrue(records['record_id_1']['unique'])
        self.assertIn('lrn_1', records)
        self.assertIn('outcome_1_created_at_1', db.get_db()['scans'].index_information())
        out = StringIO()
        call_command('create_indexes', stdout=out)
        self.assertIn('records:', out.getvalue())
