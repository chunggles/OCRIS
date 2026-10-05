"""MongoDB access for records, scans, the audit log, and the users mirror."""
import logging
import re
import uuid
from datetime import datetime

from django.conf import settings
from pymongo import DESCENDING, MongoClient

from .constants import PASSING_GRADE, is_na

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
DATE_FIELDS = ('created_at', 'updated_at', 'timestamp', 'synced_at')

_client = None


# ── Connection ───────────────────────────────────────────────────────────────

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    return get_client()[settings.MONGO_DB_NAME]


def records_col():
    return get_db()['records']


def scans_col():
    return get_db()['scans']


def audit_col():
    return get_db()['audit_log']


def users_col():
    return get_db()['users']


# ── Helpers ──────────────────────────────────────────────────────────────────

def _short_id():
    return str(uuid.uuid4())[:8].upper()


def _serialize(docs):
    """
    Convert datetimes to ISO strings so documents are JSON-ready. Dates are stored in UTC
    without a zone; the "Z" tells the browser so, and it then shows local (Philippine) time.
    """
    for doc in docs:
        for key in DATE_FIELDS:
            if isinstance(doc.get(key), datetime):
                doc[key] = doc[key].isoformat() + 'Z'
    return docs


def _paginate(collection, query, sort_field, page, size=PAGE_SIZE, projection=None):
    projection = {'_id': 0, **(projection or {})}
    total = collection.count_documents(query)
    cursor = (collection.find(query, projection)
              .sort(sort_field, DESCENDING)
              .skip((page - 1) * size)
              .limit(size))
    return {'total': total, 'page': page, 'results': _serialize(list(cursor))}


def _drop_empty(filters):
    return {k: v for k, v in (filters or {}).items() if v}


def _exact_ignoring_case(text):
    return {'$regex': f'^{re.escape(text)}$', '$options': 'i'}


def _query(filters):
    """Mongo query for exact-match filters. Sections are typed by hand, so their case is ignored."""
    query = _drop_empty(filters)
    if 'section' in query:
        query['section'] = _exact_ignoring_case(query['section'])
    return query


# ── Records ──────────────────────────────────────────────────────────────────

def create_record(data):
    record_id = f"REC-{datetime.now().strftime('%Y')}-{_short_id()}"
    now = datetime.utcnow()
    records_col().insert_one({
        'record_id':       record_id,
        'pupil_name':      data.get('pupil_name', ''),
        'lrn':             data.get('lrn', ''),
        'grade_level':     data.get('grade_level', ''),
        'section':         data.get('section', ''),
        'school_year':     data.get('school_year', ''),
        'class_adviser':   data.get('class_adviser', ''),
        'grades':          data.get('grades', {}),
        'general_average': data.get('general_average'),
        'remarks':         data.get('remarks', ''),
        'status':          'validated',
        'uploaded_by':     data.get('uploaded_by', ''),
        'scan_id':         data.get('scan_id', ''),
        'corrections':     data.get('corrections', {}),
        'created_at':      now,
        'updated_at':      now,
    })
    return record_id


def get_record(record_id):
    record = records_col().find_one({'record_id': record_id}, {'_id': 0})
    return _serialize([record])[0] if record else None


def list_records(filters=None, page=1, size=PAGE_SIZE):
    return _paginate(records_col(), _query(filters), 'created_at', page, size)


def search_records(q, filters=None, limit=50):
    query = _query(filters)
    # The search text is matched literally, so characters like "(" can't break the query
    query['$or'] = [
        {field: {'$regex': re.escape(q), '$options': 'i'}}
        for field in ('pupil_name', 'lrn', 'section', 'grade_level')
    ]
    return _serialize(list(records_col().find(query, {'_id': 0}).limit(limit)))


def record_options(filters=None):
    """The grade levels, sections and school years that saved records actually use."""
    query = _query(filters)

    def values(field):
        return sorted(v for v in records_col().distinct(field, query) if v)

    return {
        'grade_levels': values('grade_level'),
        'sections': values('section'),
        'school_years': sorted(values('school_year'), reverse=True),
    }


def all_records():
    return list(records_col().find({}, {'_id': 0}))


def update_record(record_id, updates):
    updates = {k: v for k, v in updates.items() if k != '_id'}
    updates['updated_at'] = datetime.utcnow()
    return records_col().update_one({'record_id': record_id}, {'$set': updates}).modified_count > 0


def delete_record(record_id):
    return records_col().delete_one({'record_id': record_id}).deleted_count > 0


# ── Scans ────────────────────────────────────────────────────────────────────

def create_scan(data):
    scan_id = f'SCAN-{_short_id()}'
    scans_col().insert_one({
        'scan_id':           scan_id,
        'filename':          data.get('filename', ''),
        'original_name':     data.get('original_name', ''),
        'file_size_bytes':   data.get('file_size_bytes', 0),
        'uploaded_by':       data.get('uploaded_by', ''),
        'pupil_name':        data.get('pupil_name', ''),
        'grade_level':       data.get('grade_level', ''),
        'section':           data.get('section', ''),
        'school_year':       data.get('school_year', ''),
        'lrn':               data.get('lrn', ''),
        'ocr_fields':        data.get('ocr_fields', []),
        'overall_conf':      data.get('overall_conf', 0),
        'flags_count':       data.get('flags_count', 0),
        'corrections_count': 0,
        'null_count':        data.get('null_count', 0),
        'outcome':           'pending',
        'record_id':         None,
        'created_at':        datetime.utcnow(),
    })
    return scan_id


def get_scan(scan_id, fields=None):
    projection = {'_id': 0, **{f: 1 for f in (fields or [])}}
    return scans_col().find_one({'scan_id': scan_id}, projection)


def mark_scan_saved(scan_id, record_id, corrections_count):
    scans_col().update_one({'scan_id': scan_id}, {'$set': {
        'outcome': 'saved',
        'record_id': record_id,
        'corrections_count': corrections_count,
    }})


def list_scans(filters=None, page=1, size=PAGE_SIZE):
    return _paginate(scans_col(), _query(filters), 'created_at', page, size, projection={'ocr_fields': 0})


def count_pending_scans(filters=None):
    return scans_col().count_documents({**_query(filters), 'outcome': 'pending'})


def pending_scans_before(cutoff):
    """Scans uploaded before cutoff that were never saved as a record."""
    return list(scans_col().find({'outcome': 'pending', 'created_at': {'$lt': cutoff}}, {'_id': 0, 'ocr_fields': 0}))


def delete_scan(scan_id):
    return scans_col().delete_one({'scan_id': scan_id}).deleted_count > 0


# ── Audit log ────────────────────────────────────────────────────────────────

def log_action(action, user, details=None):
    audit_col().insert_one({
        'action': action,
        'user': user,
        'details': details or {},
        'timestamp': datetime.utcnow(),
    })


def list_audit(page=1, size=PAGE_SIZE):
    return _paginate(audit_col(), {}, 'timestamp', page, size)


# ── Users mirror (Django/SQLite is the source of truth) ──────────────────────

def upsert_user_in_mongo(user_data):
    users_col().update_one({'username': user_data['username']}, {'$set': {
        'username':         user_data.get('username'),
        'full_name':        user_data.get('full_name'),
        'email':            user_data.get('email', ''),
        'role':             user_data.get('role'),
        'employee_id':      user_data.get('employee_id', ''),
        'assigned_grade':   user_data.get('assigned_grade'),
        'assigned_section': user_data.get('assigned_section'),
        'is_active':        user_data.get('is_active', True),
        'synced_at':        datetime.utcnow(),
    }}, upsert=True)


def delete_user_in_mongo(username):
    users_col().delete_one({'username': username})


def sync_users_to_mongo(users):
    for user in users:
        try:
            upsert_user_in_mongo(user)
        except Exception as e:
            logger.warning(f"User sync failed: {user.get('username')}: {e}")


# ── Analytics ────────────────────────────────────────────────────────────────

def _to_float(value):
    if is_na(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_analytics(filters=None):
    records = list(records_col().find(_query(filters), {'_id': 0}))

    subject_totals, subject_counts = {}, {}
    pass_counts, total_counts = {}, {}

    for record in records:
        grade = record.get('grade_level', 'Unknown')
        total_counts[grade] = total_counts.get(grade, 0) + 1

        average = _to_float(record.get('general_average'))
        if average is not None and average >= PASSING_GRADE:
            pass_counts[grade] = pass_counts.get(grade, 0) + 1

        for subject, grades in record.get('grades', {}).items():
            final = _to_float(grades.get('final'))
            if final is not None:
                subject_totals[subject] = subject_totals.get(subject, 0) + final
                subject_counts[subject] = subject_counts.get(subject, 0) + 1

    return {
        'total_records': len(records),
        'subject_means': {s: round(subject_totals[s] / subject_counts[s], 1) for s in subject_totals},
        'pass_rates': {g: round(pass_counts.get(g, 0) / total_counts[g] * 100, 1) for g in total_counts},
    }
