# API Reference

Base URL: `http://localhost:8000/api`

All routes are defined in `backend/api/urls.py`.

## Conventions

**Authentication.** `POST /auth/login/` sets an **HttpOnly cookie** (`ocris_session`). Every other endpoint except `/auth/forgot-password/` needs that cookie, which the browser sends by itself; scripts on the page cannot read it. The cookie is not returned in the response body.

**Request header.** Every request that changes data (`POST`, `PUT`, `PATCH`, `DELETE`), including login, must carry `X-OCRIS-Request: 1`. A request without it gets `403`. Another website cannot add a custom header to a request it sends for the user, so this stops forged requests. A browser client must also send credentials (`fetch(..., { credentials: 'include' })`) and be served from an origin listed in `CORS_ALLOWED_ORIGINS`.

**Format.** Requests and responses are JSON, except file uploads (`multipart/form-data`) and the file download.

**Errors.** Errors written by OCRIS have the form `{"detail": "message"}`. Validation errors from a serializer have the form `{"field_name": ["message"]}`.

| Status | Meaning |
|---|---|
| 400 | Missing or invalid input |
| 401 | No sign-in cookie, an unknown one, or one older than 12 hours |
| 403 | Logged in, but the role is not allowed, the item belongs to another class, a teacher has no class assigned, or the `X-OCRIS-Request` header is missing. A user who still has a temporary password gets `403` with `"code": "password_change_required"` on everything except `/auth/me/`, `/auth/change-password/` and the sign-out routes |
| 404 | Not found |
| 409 | The scan was already saved as a record |
| 413 | An uploaded file is larger than `MAX_UPLOAD_MB` (20) |
| 415 | An uploaded file is not a JPG, PNG or PDF, its name does not match its content, or it is damaged |
| 422 | The upload was received but OCR could not read it |
| 429 | Too many sign-in attempts or reset requests; the `Retry-After` header and the message say how long to wait |

**Pagination.** Paginated lists take `?page=N` (default 1; an invalid value is treated as 1), return 20 items per page, newest first, in this shape:

```json
{ "total": 57, "page": 1, "results": [ ... ] }
```

**Roles.** `Any` means any logged-in user. Where noted, teachers are limited to their assigned grade and section (the section match ignores capital letters). A teacher with no grade or section assigned gets `403` on those endpoints.

**Dates** are UTC in ISO 8601 form with a `Z` suffix.

## Summary

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/login/` | Public | Log in; sets the sign-in cookie |
| POST | `/auth/logout/` | Any | Sign out of this device |
| POST | `/auth/logout-all/` | Any | Sign out of every device |
| GET | `/auth/me/` | Any | Current user |
| POST | `/auth/change-password/` | Any | Change your own password |
| POST | `/auth/forgot-password/` | Public | Ask the OIC for a new temporary password |
| GET | `/records/` | Any (teachers: own class) | List records |
| POST | `/records/create/` | Any (teachers: own class) | Save a record typed into the on-screen Form 137 |
| GET | `/records/search/` | Any (teachers: own class) | Search records |
| GET | `/records/options/` | Any (teachers: own class) | Values for the filter dropdowns |
| GET | `/records/<record_id>/` | Any (teachers: own class) | One record |
| PUT, PATCH | `/records/<record_id>/update/` | OIC, Admin; teachers: typed forms of own class | Edit a record |
| DELETE | `/records/<record_id>/delete/` | OIC, Admin | Delete a record |
| POST | `/ocr/quality/` | Any | Check image quality |
| POST | `/ocr/upload/` | Any (teachers: own class) | Upload a scan and run OCR |
| POST | `/ocr/validate/` | Any (teachers: own class) | Save a validated record |
| GET | `/ocr/scans/<scan_id>/file/` | Any (teachers: own class) | Download the original scan |
| GET | `/ocr/history/` | Any (teachers: own class) | List scans |
| GET | `/ocr/pending/` | Any | Your uploads that were read but not saved yet |
| GET | `/ocr/scans/<scan_id>/` | Any (teachers: own uploads) | One unsaved upload with what was read, to carry on from step 4 |
| GET | `/analytics/` | Any (teachers: own class) | Grade analytics |
| GET | `/sections/` | Any | The section tree (grade levels and their sections) |
| POST | `/sections/create/` | OIC, Admin | Add a section |
| PATCH, DELETE | `/sections/<section_id>/` | OIC, Admin | Edit or delete a section |
| GET | `/users/` | OIC, Admin | List users |
| POST | `/users/create/` | OIC | Create a user |
| GET, PATCH, DELETE | `/users/<id>/` | OIC | View, edit or delete a user |
| GET | `/audit/` | OIC, Admin | Audit log |

---

## Authentication

### POST `/auth/login/`

Request:

```json
{ "username": "k.saquing", "password": "..." }
```

Response `200`, with the cookie in `Set-Cookie` (`HttpOnly`; `Secure` when HTTPS is required; valid 12 hours):

```json
{ "user": { "...": "a user object, see Users below" } }
```

Each sign-in is its own session, so a user can be signed in on several devices at once.

Response `400`: `{"non_field_errors": ["Invalid username or password."]}`

**Limit.** After `LOGIN_MAX_ATTEMPTS` (5) wrong passwords for one username, or `LOGIN_MAX_ATTEMPTS_PER_IP` (20) from one address, within `LOGIN_LOCKOUT_MINUTES` (15), the answer is `429` with `Retry-After` until the oldest of those attempts is more than 15 minutes old. While locked, even the right password is refused. A successful sign-in clears the username's failures. Usernames that do not exist are limited in the same way, so the answer does not reveal which accounts exist.

Writes `LOGIN` on success; `LOGIN_FAILED` for each wrong password and `LOGIN_LOCKED` when a lock starts. A success also records the user's last login time.

### POST `/auth/logout/`

Ends only the session of the cookie used and removes the cookie; the user stays signed in on other devices. Response `200`: `{"detail": "Logged out."}`. Writes `LOGOUT`.

### POST `/auth/logout-all/`

Ends every session of the user. Response `200`. Writes `LOGOUT` with `all_devices: true`.

### GET `/auth/me/`

Returns the current user as a [user object](#user-object). The frontend calls this when the page opens to restore the session; `401` means nobody is signed in.

### POST `/auth/forgot-password/`

Public. Body: `{ "username": "g.ramos" }`. OCRIS sends no email: the request marks the account, and the OIC sees "Password reset asked" beside it on User Management and sets a new temporary password. The answer is always `200` with the same message, whether or not the account exists. At most `RESET_MAX_REQUESTS` (5) requests per address per 15 minutes, then `429`. Writes `PASSWORD_RESET_REQUEST` for a real, active account.

### POST `/auth/change-password/`

```json
{ "current_password": "...", "new_password": "see the password rules" }
```

**Password rules** (also for passwords set by the OIC): at least 10 characters; letters and numbers; not entirely numeric; not a common password; not similar to the username or name.

Response `200`: `{"detail": "Password changed.", "user": {...}}`. This clears `must_change_password` and signs the user out of every other device. Response `400` if the current password is wrong, the new one breaks a rule (the messages are in `detail` and `problems`), or it is the same as the current one. Writes a `CHANGE_PASSWORD` audit entry.

---

## Records

A record object is described in [DATABASE.md](DATABASE.md#records).

### GET `/records/`

| Query parameter | Meaning |
|---|---|
| `grade` | Exact grade level, e.g. `Grade 5` |
| `section` | Section; capital letters are ignored |
| `school_year` | Exact school year, e.g. `2024-2025` |
| `page` | Page number |

For a teacher, the grade and section are replaced by the teacher's assigned class. Returns a paginated list of records.

### GET `/records/search/?q=<text>`

Finds records whose pupil name, LRN, grade level, section or school year contains the text, or that have a subject whose name contains it, or whose scanned form has it written anywhere on the page. The text is matched literally, ignoring case.

Optional filters: `grade`, `section`, `school_year`. A teacher is always limited to their own class.

```json
{
  "query": "santos",
  "count": 50,
  "total": 128,
  "limit": 50,
  "results": [ { "record_id": "REC-2026-7C1E4A90", "pupil_name": "Santos, Maria", "matched_in": ["name"] } ]
}
```

`count` is how many records are returned and `total` how many match; at most `limit` are returned, ordered by pupil name. `matched_in` lists where each record matched: `name`, `LRN`, `grade level`, `section`, `school year`, `subject`, `scanned text`. Response `400` if `q` is missing.

### GET `/records/<record_id>/`

Returns the record, `404` if it does not exist, or `403` if a teacher requests a record outside their class.

### GET `/records/options/`

The values that saved records actually use, for filter dropdowns. Teachers get the values of their own class.

```json
{ "grade_levels": ["Grade 5", "Grade 6"], "sections": ["Orchid", "Sampaguita"], "school_years": ["2024-2025", "2023-2024"] }
```

### POST `/records/create/`

Saves a record typed into the on-screen SF10-ES. No scan is involved, so the record's `scan_id` is empty.

```json
{
  "pupil_name": "Dela Cruz, Janelle Mae",
  "lrn": "104567890123",
  "grade_level": "Grade 4",
  "section": "Athena",
  "school_year": "2025-2026",
  "class_adviser": "Gloria D. Ramos",
  "grades": { "English": { "Q1": "88", "Q2": "90", "Q3": "92", "Q4": "94", "final": "91" } },
  "details": {
    "name_ext": "", "middle_name": "Antonio", "birthdate": "07/28/2016", "sex": "F",
    "eligibility": { "kinder_progress_report": true, "school_name": "…" },
    "blocks": [ { "grade_level": "Grade 1", "section": "Rizal", "school_year": "2022-2023", "rows": [ { "subject": "Language", "Q1": "86" } ], "remedial": {} } ]
  }
}
```

`pupil_name`, `grade_level`, `section`, `school_year` and at least one subject in `grades` are required. Each grade is a number from 0 to 100 or left out. The general average and remarks are calculated by the server. A teacher may only send their assigned class.

The top-level class and `grades` are those of the last year block that has grades on the sheet. `details` is optional and holds the rest of the sheet, including all eight year blocks as typed (`blocks`), the three certification boxes (`certifications`) and `total_pages`, so the form can be shown again. A typed form sends its three terms as `Q1` to `Q3`; `Q4` is stored as `N/A`. Only the keys shown are kept; text is cut to 100 characters, lists and objects to 40 entries.

Response `201` with the record, `400` for invalid input, `403` for a teacher filing under another class. Writes an `ENCODE` audit entry.

### PUT or PATCH `/records/<record_id>/update/`

Access: OIC and Admin for any record. A teacher may edit only a typed-in form (a record with no `scan_id`) of their own class, and cannot change its grade level or section to another class; anything else gets `403`.

The body holds the fields to change. Only these are accepted; anything else is ignored.

| Field | Rule |
|---|---|
| `pupil_name`, `grade_level`, `section`, `school_year` | Text; cannot be blank |
| `lrn`, `class_adviser` | Text; may be blank |
| `grades` | The whole grade sheet: `{subject: {Q1, Q2, Q3, Q4, final}}`. A missing or empty value is stored as `N/A`. On a typed-in form, each grade must be a number from 0 to 100 and at least one subject is required. |
| `details` | The whole details object, as in `POST /records/create/`. |

When `grades` is sent, `general_average` and `remarks` are recalculated; they cannot be set directly. Response `200`: the updated record. Response `400` if nothing valid was sent or a value breaks a rule. Writes an `EDIT` audit entry.

### DELETE `/records/<record_id>/delete/`

Access: OIC, Admin. Response `204` with no body. The record is removed, but **its scan and image file are kept**: the original form is part of the audit trail. The scan is marked `outcome: "record deleted"`. Writes a `DELETE` audit entry holding the record ID, pupil and a snapshot of what the record contained (details and grades), so it can be restored by hand. Kept scans are purged only by `manage.py cleanup_scans --deleted-days N`.

---

## OCR

### POST `/ocr/quality/`

Analyses an image without saving anything. Body: `multipart/form-data` with `file`.

Response `200`:

```json
{
  "metrics": [
    { "key": "resolution", "label": "Resolution", "value": "≈141 DPI (1200 × 1835 px)",
      "status": "poor", "score": 47, "tip": "Rescan at 300 DPI for best results." },
    { "key": "contrast", "label": "Contrast", "value": "212 / 255", "status": "good", "score": 100, "tip": "" }
  ],
  "assessment": "Poor — rescan recommended",
  "status": "poor",
  "overall_ok": false,
  "width": 1200,
  "height": 1835
}
```

`metrics` has six entries with the keys `resolution`, `contrast`, `brightness`, `sharpness`, `skew`, `content`. `status` is `good`, `fair` or `poor`; the overall `status` is the worst of the six.

If the file is not a readable image, the response is still `200`:

```json
{ "error": "Quality check is only available for JPG and PNG images.", "overall_ok": false, "metrics": [] }
```

Response `400` if no file is sent. The file is checked as for `/ocr/upload/` below (`413`, `415`).

### POST `/ocr/upload/`

Saves the image, runs OCR and creates a scan. Body: `multipart/form-data`.

A teacher may only send their assigned `grade_level` and `section` (section case is ignored). Anything else gets `403` here and on `/ocr/validate/`, before the file is stored.

| Field | Required | Meaning |
|---|---|---|
| `file` | Yes | JPG, PNG or PDF, up to `MAX_UPLOAD_MB` (20). For a PDF, up to 4 pages are read. |
| `pupil_name` | No | Stored on the scan |
| `grade_level` | No | Stored on the scan |
| `section` | No | Stored on the scan |
| `school_year` | No | Stored on the scan |
| `lrn` | No | Stored on the scan |
| `archive_only` | No | `true` or `1`: store the file without running OCR (see below) |

**Archive only.** With `archive_only`, no OCR is run. `pupil_name` is then required (`400` if blank). The file is stored, a scan is created, and a record is created straight away with empty `grades`, a `null` `general_average`, empty `remarks` and `details.archive_only` set to `true`. The scan is marked `saved`, so `/ocr/validate/` is not called. The audit log gets an `UPLOAD` entry with `archive_only: true` and the `record_id`. Response `200`:

```json
{ "archived": true, "scan_id": "SCAN-3F9A1C2B", "record_id": "REC-2026-7C1E4A90", "pupil_name": "Pulonan, Ellen Joy A.", "general_average": null, "remarks": "" }
```

Without `archive_only`, response `200`:

```json
{
  "scan_id": "SCAN-3F9A1C2B",
  "quality": { "...": "same shape as /ocr/quality/" },
  "fields": [
    { "field": "Pupil Name", "raw": "PULONAN, ELLEN JOY A.", "value": "PULONAN, ELLEN JOY A.", "conf": 93, "status": "ok", "flagged": false },
    { "field": "English I Q1", "raw": "87", "value": "87", "conf": 91, "status": "ok", "flagged": false },
    { "field": "English I Q2", "raw": "88 / 83", "value": "88", "conf": 0, "status": "warn", "flagged": true },
    { "field": "English I Q3", "raw": "", "value": "N/A", "conf": 0, "status": "null", "flagged": false }
  ],
  "summary": { "total": 95, "auto_approved": 78, "flagged": 14, "null_count": 3, "overall_conf": 88.4 },
  "notes": ["Page 2 has no grade table, so it was not read."]
}
```

The meaning of each field key is in [OCR_PIPELINE.md](OCR_PIPELINE.md#7-output-format).

Response `422`: `{"detail": "<reason OCR failed>"}`. No scan is created and the file is removed. The possible messages are listed in [OCR_PIPELINE.md](OCR_PIPELINE.md#8-failures).

**File checks, before anything is stored.** The type is decided by the first bytes of the file, never by the name or the type the browser reports; the name must agree with it (`.jpg` or `.jpeg` for a JPEG, `.png`, `.pdf`). An image is opened to check that it is not damaged and is at most 120 megapixels. Responses: `400` no file or an empty file, `413` too large (also refused from the declared request size, before the body is read), `415` wrong or damaged type. When `DATA_ENCRYPTION_KEY` is set, the file is stored encrypted and decrypted only into a temporary folder while the OCR reads it.

Response `400` if no file is sent. Writes an `UPLOAD` audit entry on success.

### POST `/ocr/validate/`

Turns a scan into a saved record.

Request:

```json
{
  "scan_id": "SCAN-3F9A1C2B",
  "pupil_name": "Pulonan, Ellen Joy A.",
  "lrn": "",
  "grade_level": "Grade 6",
  "section": "Bonifacio",
  "school_year": "2024-2025",
  "corrections": [
    { "field": "English I Q2", "corrected_val": "88" },
    { "field": "Science I Final", "corrected_val": "N/A" }
  ],
  "confirmed": true
}
```

`scan_id`, `grade_level`, `section`, `school_year` and `confirmed` are required. `pupil_name` may be blank, and then the name read from the form is used (`400` if none was read). `lrn` (12 digits, optional), `corrections` and `renames` are optional. `renames` maps a subject label as read (`"Unread learning area Grade 2"`) to the name a person gave it.

Every correction must be a number from 0 to 100 or `N/A`, otherwise `400`. A record for the same pupil (same LRN, or same name and grade level) and school year already on file gives `409`, and so does an LRN that belongs to another pupil; the scan stays unsaved.

The server reads the scan's OCR fields, applies the corrections over them, computes the general average and remarks, creates the record, and marks the scan as saved. When the form holds several school years (an SF10-ES, or year levels I to VI on a Form 137-A) the record takes the block of its `grade_level`, or the last block when none matches; the other blocks are kept in `details.other_years` as `[{"label": "Grade 5", "grades": {...}}]` and take no part in the average. Subject names are normalised ("EPP", "TLE" and "EPP / TLE" are one subject). The response is `{record_id, pupil_name, general_average, remarks}`.

Response `200`:

```json
{ "record_id": "REC-2026-7C1E4A90", "general_average": "86.4", "remarks": "Promoted" }
```

`general_average` is `null` when there are no numeric Final grades. `remarks` is `Promoted`, `Retained` or `Incomplete`. Writes a `VALIDATE` audit entry.

| Response | When |
|---|---|
| `400` | A required field is missing, or `confirmed` is not `true` |
| `404` | No scan has this `scan_id` |
| `409` | The scan was already saved as a record |

### GET `/ocr/scans/<scan_id>/file/`

Downloads the original uploaded file as an attachment under its original filename (`Content-Disposition`). An encrypted file is decrypted on the way out. The scan can still be downloaded after its record was deleted (see `outcome` in [DATABASE.md](DATABASE.md)).

| Response | When |
|---|---|
| `200` | The file |
| `403` | A teacher requested a scan outside their assigned class |
| `404` | Unknown scan, or the file is no longer on the server |

Writes a `DOWNLOAD` audit entry.

### GET `/ocr/history/`

Paginated list of scans, without their `ocr_fields`. Teachers get the scans of their own class. The scan object is described in [DATABASE.md](DATABASE.md#scans).

### GET `/ocr/pending/`

The signed-in user's scans whose outcome is still `pending`, newest first, without `ocr_fields`, `ocr_text` and `notes`: `{"results": [scan, ...]}`. The Upload page lists them as "Unfinished uploads", so a refresh or a closed tab does not lose a form that was already read. Pending scans older than `PENDING_SCAN_DAYS` (7) are deleted by the server, so they do not stay here for long.

### GET `/ocr/scans/<scan_id>/`

What the reader found on an unsaved upload: `scan_id`, `original_name`, `pupil_name`, `lrn`, `grade_level`, `section`, `school_year`, `ocr_fields`, `notes` and `summary` (the same figures `POST /ocr/upload/` returns). The original file is fetched with `/ocr/scans/<scan_id>/file/`.

| Status | Meaning |
|---|---|
| `403` | A teacher asking for a scan of another class, or one that someone else uploaded |
| `404` | Unknown scan |
| `409` | The upload was already saved as a record (or its record was deleted) |

---

## Analytics

### GET `/analytics/`

Descriptive figures for the saved records. Optional filters: `school_year`, `grade`, `section`. A teacher is always limited to their own class. Blank and unreadable grades are left out of every figure.

```json
{
  "total_records": 40,
  "subject_means": { "Mathematics": 74.0, "English": 84.0 },
  "pass_rates": { "Grade 6": 95.0 },
  "subjects": [
    {
      "subject": "Mathematics",
      "means": { "Q1": 76.0, "Q2": 74.0, "Q3": 73.0, "Q4": 72.0, "final": 74.0 },
      "graded": 40, "passed": 23, "failed": 17, "pass_rate": 57.5
    }
  ],
  "period_means": { "Q1": 83.5, "Q2": 84.0, "Q3": 84.4, "Q4": 85.5, "final": 84.5 },
  "intervention_flags": [ { "subject": "Mathematics", "mean": 74.0, "grade_level": "All" } ],
  "pending_scans": 2
}
```

| Field | Meaning |
|---|---|
| `subject_means` | Mean final rating per subject |
| `pass_rates` | Per grade level, the share of records whose general average is 75 or higher |
| `subjects` | Per subject: its mean for each grading period and the final rating, how many final ratings there are (`graded`), and how many pass and fail. The subjects with the most failing final ratings come first. |
| `period_means` | Mean over every subject for each grading period |
| `intervention_flags` | Subjects whose mean final rating is below 75 |
| `pending_scans` | Scans uploaded but never saved as a record |

---

## Users

### User object

```json
{
  "id": 3,
  "username": "g.ramos",
  "full_name": "Gloria Ramos",
  "first_name": "Gloria",
  "last_name": "Ramos",
  "email": "",
  "role": "TEACHER",
  "employee_id": "BCS-TCH-001",
  "assigned_grade": "Grade 6",
  "assigned_section": "Sampaguita",
  "is_active": true,
  "last_login": "2026-10-04T01:15:00Z",
  "must_change_password": false,
  "password_reset_requested_at": null
}
```

`role` is `OIC`, `ADMIN` or `TEACHER`. `must_change_password` is `true` after the OIC created the account or set a new password: the user must replace the temporary password before using anything else. `password_reset_requested_at` is the time of an unanswered "forgot password" request. Both are read-only.

### GET `/users/`

Access: OIC, Admin. Returns an array of all users (not paginated), ordered by last name then first name.

### POST `/users/create/`

Access: OIC.

```json
{
  "username": "a.reyes",
  "password": "a temporary password that follows the password rules",
  "first_name": "Ana",
  "last_name": "Reyes",
  "email": "",
  "role": "TEACHER",
  "employee_id": "a.reyes",
  "assigned_grade": "Grade 4",
  "assigned_section": "Rosal"
}
```

`username` and `password` are required. `username` and `employee_id` must be unique. The password must follow the password rules (`400` with `{"password": [...]}` otherwise). The new user must change it at first sign-in. Response `201` with the user object. Writes a `CREATE_USER` audit entry.

### GET `/users/<id>/`

Access: OIC. Returns the user object.

### PATCH `/users/<id>/`

Access: OIC. Changes any of `username`, `first_name`, `last_name`, `email`, `role`, `employee_id`, `assigned_grade`, `assigned_section`, `is_active`. Setting `is_active` to `false` deactivates the account. Returns the updated user object.

Sending `password` sets a new temporary password (the password rules apply): the user is signed out everywhere, must change it at next sign-in, and any pending reset request is cleared. When the OIC sets their own password, it is not temporary.

Response `400` if the change would leave the system without an active OIC, or the password breaks a rule. Writes `EDIT_USER` (with the old and new value of every field changed) and, when a password is set, `RESET_PASSWORD` audit entries.

### DELETE `/users/<id>/`

Access: OIC. Permanently deletes the account and its sessions. Records, scans and audit entries are kept.

| Response | When |
|---|---|
| `204` | Deleted |
| `400` | Trying to delete your own account, or the only active OIC |
| `404` | No such user |

Writes a `DELETE_USER` audit entry.

---

## Sections

Sections are a tree, managed on the Sections page: each grade level is a parent node and its sections are the child nodes. It is stored in the `grade_levels` collection, one document per grade level with its sections in a `sections` array. Records and teacher accounts store their section as plain text, matched to a section by its name (case ignored). Renaming or moving a section therefore also updates its records and teacher accounts, and a section with teachers assigned cannot be deleted. The records of a deleted section keep its name.

### GET `/sections/`

Access: any. Returns the whole tree: all six grade levels in order, including those with no sections, each with its sections ordered by name. Each section also has `records` and `teachers`, how many records and teacher accounts are filed under it.

```json
[
  {
    "grade_level": "Grade 1",
    "sections": [
      { "section_id": "SEC-3F9A1C2B", "name": "Sampaguita", "created_at": "2026-10-05T02:10:00Z", "updated_at": "2026-10-05T02:10:00Z" }
    ]
  },
  { "grade_level": "Grade 2", "sections": [] }
]
```

The add and edit endpoints below return a single section, with the grade level it sits under:

```json
{
  "section_id": "SEC-3F9A1C2B",
  "name": "Sampaguita",
  "grade_level": "Grade 1",
  "created_at": "2026-10-05T02:10:00Z",
  "updated_at": "2026-10-05T02:10:00Z"
}
```

### POST `/sections/create/`

Access: OIC, Admin.

```json
{ "name": "Sampaguita", "grade_level": "Grade 1" }
```

`name` is required, at most 50 characters. `grade_level` is `Grade 1` to `Grade 6`. Response `201` with the section object, or `400` if a field is invalid or that grade level already has a section with the same name (case is ignored). Writes an `ADD_SECTION` audit entry.

### PATCH `/sections/<section_id>/`

Access: OIC, Admin. Changes `name`, `grade_level` or both, with the same rules as adding. Changing `grade_level` moves the section under that grade level. Returns the updated section object, with `records` and `teachers` giving how many were moved with it. Writes an `EDIT_SECTION` audit entry.

### DELETE `/sections/<section_id>/`

Access: OIC, Admin. Response `204`; `404` if there is no such section; `409` if teachers are assigned to it (the message names them). Writes a `DELETE_SECTION` audit entry.

---

## Audit

### GET `/audit/`

Access: OIC, Admin. Paginated list, newest first.

```json
{
  "action": "VALIDATE",
  "user": "g.ramos",
  "details": { "scan_id": "SCAN-3F9A1C2B", "record_id": "REC-2026-7C1E4A90", "corrections": 14, "pupil": "Pulonan, Ellen Joy A.", "grade": "Grade 6" },
  "timestamp": "2026-10-01T05:12:44.118000Z"
}
```

The actions and their details are listed in [DATABASE.md](DATABASE.md#audit_log).
