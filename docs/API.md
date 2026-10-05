# API Reference

Base URL: `http://localhost:8000/api`

All routes are defined in `backend/api/urls.py`.

## Conventions

**Authentication.** Every endpoint except login requires the header:

```
Authorization: Token <token>
```

The token is returned by `POST /auth/login/`.

**Format.** Requests and responses are JSON, except file uploads (`multipart/form-data`) and the file download.

**Errors.** Errors written by OCRIS have the form `{"detail": "message"}`. Validation errors from a serializer have the form `{"field_name": ["message"]}`.

| Status | Meaning |
|---|---|
| 400 | Missing or invalid input |
| 401 | No token, an invalid token, or a token older than 12 hours |
| 403 | Logged in, but the role is not allowed, the item belongs to another class, or a teacher has no class assigned |
| 404 | Not found |
| 409 | The scan was already saved as a record |
| 422 | The upload was received but OCR could not read it |

**Pagination.** Paginated lists take `?page=N` (default 1; an invalid value is treated as 1), return 20 items per page, newest first, in this shape:

```json
{ "total": 57, "page": 1, "results": [ ... ] }
```

**Roles.** `Any` means any logged-in user. Where noted, teachers are limited to their assigned grade and section (the section match ignores capital letters). A teacher with no grade or section assigned gets `403` on those endpoints.

**Dates** are UTC in ISO 8601 form with a `Z` suffix.

## Summary

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/login/` | Public | Log in, get a token |
| POST | `/auth/logout/` | Any | Delete the token |
| GET | `/auth/me/` | Any | Current user |
| POST | `/auth/change-password/` | Any | Change your own password |
| GET | `/records/` | Any (teachers: own class) | List records |
| GET | `/records/search/` | Any (teachers: own class) | Search records |
| GET | `/records/options/` | Any (teachers: own class) | Values for the filter dropdowns |
| GET | `/records/<record_id>/` | Any (teachers: own class) | One record |
| PUT, PATCH | `/records/<record_id>/update/` | OIC, Admin | Edit a record |
| DELETE | `/records/<record_id>/delete/` | OIC, Admin | Delete a record |
| POST | `/ocr/quality/` | Any | Check image quality |
| POST | `/ocr/upload/` | Any | Upload a scan and run OCR |
| POST | `/ocr/validate/` | Any | Save a validated record |
| GET | `/ocr/scans/<scan_id>/file/` | Any (teachers: own class) | Download the original scan |
| GET | `/ocr/history/` | Any (teachers: own class) | List scans |
| GET | `/analytics/` | Any (teachers: own class) | Grade analytics |
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

Response `200`:

```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": { "...": "a user object, see Users below" }
}
```

Response `400`: `{"non_field_errors": ["Invalid username or password."]}`

Writes a `LOGIN` audit entry, records the user's last login time, and restarts the token's 12-hour clock.

### POST `/auth/logout/`

Deletes the user's token. Response `200`: `{"detail": "Logged out."}`

### GET `/auth/me/`

Returns the current user as a [user object](#user-object). The frontend calls this after a page refresh to restore the session.

### POST `/auth/change-password/`

```json
{ "current_password": "...", "new_password": "at least 8 characters" }
```

Response `200`: `{"detail": "Password changed."}`. Response `400` if the current password is wrong, the new one is shorter than 8 characters, or it is the same as the current one. Writes a `CHANGE_PASSWORD` audit entry.

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

Case-insensitive search in pupil name, LRN, section and grade level. The text is matched literally; characters such as `(` or `*` have no special meaning. Returns at most 50 records. Teachers only get results from their assigned class.

Response `200`:

```json
{ "query": "santos", "count": 2, "results": [ ... ] }
```

Response `400` if `q` is missing.

### GET `/records/<record_id>/`

Returns the record, `404` if it does not exist, or `403` if a teacher requests a record outside their class.

### GET `/records/options/`

The values that saved records actually use, for filter dropdowns. Teachers get the values of their own class.

```json
{ "grade_levels": ["Grade 5", "Grade 6"], "sections": ["Orchid", "Sampaguita"], "school_years": ["2024-2025", "2023-2024"] }
```

### PUT or PATCH `/records/<record_id>/update/`

Access: OIC, Admin. The body holds the fields to change. Only these are accepted; anything else is ignored.

| Field | Rule |
|---|---|
| `pupil_name`, `grade_level`, `section`, `school_year` | Text; cannot be blank |
| `lrn`, `class_adviser` | Text; may be blank |
| `grades` | The whole grade sheet: `{subject: {Q1, Q2, Q3, Q4, final}}`. A missing or empty value is stored as `N/A`. |

When `grades` is sent, `general_average` and `remarks` are recalculated; they cannot be set directly. Response `200`: the updated record. Response `400` if nothing valid was sent or a value breaks a rule. Writes an `EDIT` audit entry.

### DELETE `/records/<record_id>/delete/`

Access: OIC, Admin. Response `204` with no body. Writes a `DELETE` audit entry with the record ID and pupil name. The record's scan and its image file are deleted too.

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

Response `400` if no file is sent.

### POST `/ocr/upload/`

Saves the image, runs OCR and creates a scan. Body: `multipart/form-data`.

| Field | Required | Meaning |
|---|---|---|
| `file` | Yes | JPG or PNG, up to 20 MB |
| `pupil_name` | No | Stored on the scan |
| `grade_level` | No | Stored on the scan |
| `section` | No | Stored on the scan |
| `school_year` | No | Stored on the scan |
| `lrn` | No | Stored on the scan |

Response `200`:

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
  "summary": { "total": 95, "auto_approved": 78, "flagged": 14, "null_count": 3, "overall_conf": 88.4 }
}
```

The meaning of each field key is in [OCR_PIPELINE.md](OCR_PIPELINE.md#7-output-format).

Response `422`: `{"detail": "<reason OCR failed>"}`. No scan is created and the file is removed. The possible messages are listed in [OCR_PIPELINE.md](OCR_PIPELINE.md#8-failures).

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

`scan_id`, `pupil_name`, `grade_level`, `section`, `school_year` and `confirmed` are required. `lrn` and `corrections` are optional.

The server reads the scan's OCR fields, applies the corrections over them, computes the general average and remarks, creates the record, and marks the scan as saved.

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

Downloads the original uploaded image as an attachment under its original filename (`Content-Disposition`).

| Response | When |
|---|---|
| `200` | The file |
| `403` | A teacher requested a scan outside their assigned class |
| `404` | Unknown scan, or the file is no longer on the server |

Writes a `DOWNLOAD` audit entry.

### GET `/ocr/history/`

Paginated list of scans, without their `ocr_fields`. Teachers get the scans of their own class. The scan object is described in [DATABASE.md](DATABASE.md#scans).

---

## Analytics

### GET `/analytics/`

| Query parameter | Meaning |
|---|---|
| `school_year` | Limit to one school year |
| `grade` | Limit to one grade level |

Response `200`:

```json
{
  "total_records": 42,
  "subject_means": { "English I": 86.2, "Mathematics I": 73.9 },
  "pass_rates": { "Grade 5": 92.3, "Grade 6": 88.0 },
  "intervention_flags": [
    { "subject": "Mathematics I", "mean": 73.9, "grade_level": "All" }
  ],
  "pending_scans": 2
}
```

| Key | How it is computed |
|---|---|
| `subject_means` | Mean of numeric Final grades per subject, one decimal place. Blank grades are excluded. |
| `pass_rates` | Per grade level, the percentage of records whose general average is at least 75 |
| `intervention_flags` | Subjects whose mean is below 75. `grade_level` is the `grade` filter, or `All`. |
| `pending_scans` | Uploads that were read but never saved as a record (not affected by the filters) |

For a teacher, everything is limited to their own class and the `grade` filter cannot widen it.

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
  "last_login": "2026-10-04T01:15:00Z"
}
```

`role` is `OIC`, `ADMIN` or `TEACHER`.

### GET `/users/`

Access: OIC, Admin. Returns an array of all users (not paginated), ordered by last name then first name.

### POST `/users/create/`

Access: OIC.

```json
{
  "username": "a.reyes",
  "password": "at least 8 characters",
  "first_name": "Ana",
  "last_name": "Reyes",
  "email": "",
  "role": "TEACHER",
  "employee_id": "a.reyes",
  "assigned_grade": "Grade 4",
  "assigned_section": "Rosal"
}
```

`username` and `password` are required. `username` and `employee_id` must be unique. Response `201` with the user object. Writes a `CREATE_USER` audit entry.

### GET `/users/<id>/`

Access: OIC. Returns the user object.

### PATCH `/users/<id>/`

Access: OIC. Changes any of `username`, `first_name`, `last_name`, `email`, `role`, `employee_id`, `assigned_grade`, `assigned_section`, `is_active`. Setting `is_active` to `false` deactivates the account. Returns the updated user object.

Sending `password` (at least 8 characters) sets a new password and deletes the user's token, signing them out everywhere.

Response `400` if the change would leave the system without an active OIC, or the password is too short. Writes `EDIT_USER` and, when a password is set, `RESET_PASSWORD` audit entries.

### DELETE `/users/<id>/`

Access: OIC. Permanently deletes the account and its token. Records, scans and audit entries are kept.

| Response | When |
|---|---|
| `204` | Deleted |
| `400` | Trying to delete your own account, or the only active OIC |
| `404` | No such user |

Writes a `DELETE_USER` audit entry.

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
