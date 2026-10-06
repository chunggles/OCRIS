"""
API tests. Run with: python manage.py test

They need MongoDB running and use a throwaway database (ocris_test_...) that is dropped
after every test, so the real database is never touched. Without MongoDB they are skipped.
"""
import tempfile
import uuid
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from api import db
from api.models import OCRISUser
from api.services import grading, storage

TEST_DB = f'ocris_test_{uuid.uuid4().hex[:8]}'
PASSWORD = 'test-pass-123'


def _mongo_available():
    try:
        db.get_client().admin.command('ping')
        return True
    except Exception:
        return False


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
        upload = {'file': SimpleUploadedFile('form.png', b'image', 'image/png'), 'grade_level': 'Grade 5', 'section': 'Orchid'}
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

    def test_edit_recalculates_average_and_remarks(self):
        record_id = self.make_record()
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

    def test_delete_removes_the_scan_and_its_file(self):
        scan_id = self.make_scan(with_file=True)
        path = storage.find_scan_file(db.get_scan(scan_id)['filename'])
        record_id = self.make_record(scan_id=scan_id)
        self.assertEqual(self.as_user(self.teacher).delete(f'/api/records/{record_id}/delete/').status_code, 403)
        self.assertEqual(self.as_user(self.admin).delete(f'/api/records/{record_id}/delete/').status_code, 204)
        self.assertIsNone(db.get_record(record_id))
        self.assertIsNone(db.get_scan(scan_id))
        self.assertFalse(path.exists())

    def test_pending_scans_are_counted(self):
        self.make_scan()
        saved = self.make_scan()
        db.mark_scan_saved(saved, 'REC-X', 0)
        self.assertEqual(self.as_user(self.oic).get('/api/analytics/').data['pending_scans'], 1)


class AccountTests(ApiTestCase):
    def login(self, username, password=PASSWORD):
        return APIClient().post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def with_token(self, key):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {key}')
        return client

    def test_login_returns_user_and_records_last_login(self):
        response = self.login('teacher')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['role'], 'TEACHER')
        self.assertEqual(response.data['user']['assigned_section'], 'Sampaguita')
        self.teacher.refresh_from_db()
        self.assertIsNotNone(self.teacher.last_login)

    def test_token_expires(self):
        key = self.login('teacher').data['token']
        self.assertEqual(self.with_token(key).get('/api/auth/me/').status_code, 200)
        Token.objects.filter(key=key).update(created=timezone.now() - timedelta(hours=settings.TOKEN_TTL_HOURS + 1))
        self.assertEqual(self.with_token(key).get('/api/auth/me/').status_code, 401)
        # Signing in again gives a working session
        self.assertEqual(self.with_token(self.login('teacher').data['token']).get('/api/auth/me/').status_code, 200)

    def test_change_own_password(self):
        client = self.as_user(self.teacher)
        url = '/api/auth/change-password/'
        self.assertEqual(client.post(url, {'current_password': 'wrong', 'new_password': 'new-pass-456'}, format='json').status_code, 400)
        self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': 'short'}, format='json').status_code, 400)
        self.assertEqual(client.post(url, {'current_password': PASSWORD, 'new_password': 'new-pass-456'}, format='json').status_code, 200)
        self.assertEqual(self.login('teacher').status_code, 400)
        self.assertEqual(self.login('teacher', 'new-pass-456').status_code, 200)

    def test_oic_resets_password_and_edits_user(self):
        key = self.login('teacher').data['token']
        body = {'first_name': 'Gloria', 'assigned_section': 'Rosal', 'password': 'reset-pass-789'}
        self.assertEqual(self.as_user(self.admin).patch(f'/api/users/{self.teacher.pk}/', body, format='json').status_code, 403)
        response = self.as_user(self.oic).patch(f'/api/users/{self.teacher.pk}/', body, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Gloria')
        self.assertEqual(response.data['assigned_section'], 'Rosal')
        self.assertEqual(self.with_token(key).get('/api/auth/me/').status_code, 401)  # signed out everywhere
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

    def test_recompute_remarks_fixes_old_records(self):
        stale = self.make_record(grades=_grades(English='88', Math='?'), general_average='88.0', remarks='Retained')
        fine = self.make_record()
        call_command('recompute_remarks', stdout=StringIO())
        self.assertEqual(db.get_record(stale)['remarks'], 'Incomplete')
        self.assertEqual(db.get_record(fine)['remarks'], 'Promoted')

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
