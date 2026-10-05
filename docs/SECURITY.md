# Security and Access Control

OCRIS stores pupils' personal information and academic records, which are personal data under the Data Privacy Act of 2012 (RA 10173). This document describes how access is controlled and recorded. Known weaknesses are listed in [LIMITATIONS.md](LIMITATIONS.md).

## 1. Authentication

- Users sign in with a username and password (`POST /api/auth/login/`).
- Passwords are hashed by Django (PBKDF2 with SHA-256) and are never stored or logged in plain text. New passwords must be at least 8 characters.
- A successful login returns a **token**. The browser keeps it in `localStorage` and sends it with every request in the `Authorization: Token …` header.
- A token **expires 12 hours after the last login** (`TOKEN_TTL_HOURS`). Signing in again restarts the clock.
- Signing out deletes the token on the server, so a copied token stops working.
- Any request with a missing, invalid or expired token gets `401`, and the app returns to the login screen.
- Users change their own password from **Change password**, which requires the current password. The OIC can set a new password for any user; doing so deletes that user's token, signing them out everywhere.
- A deactivated account (`is_active = false`) cannot log in.

## 2. Roles

| Role | Code | Intended for |
|---|---|---|
| Officer in Charge | `OIC` | The school head or records officer; full control including user accounts |
| Admin Staff | `ADMIN` | Office staff who manage records |
| Teacher | `TEACHER` | Class advisers; limited to their assigned grade and section |

## 3. What each role can do

This table shows what the **backend enforces**, taken from the permission class on each view.

| Action | OIC | Admin Staff | Teacher |
|---|---|---|---|
| Upload a Form 137 and run OCR | Yes | Yes | Yes |
| Validate and save a record | Yes | Yes | Yes |
| List and search records | All | All | Own class only |
| Open a record by its ID | All | All | Own class only |
| Download an original scan | All | All | Own class only |
| View scan history | All | All | Own class only |
| View analytics | All | All | Own class only |
| Change own password | Yes | Yes | Yes |
| Edit or delete a record | Yes | Yes | No |
| View the audit log | Yes | Yes | No |
| View the user list | Yes | Yes | No |
| Create, edit, deactivate or delete users | Yes | No | No |

"Own class" means records whose grade level and section equal the teacher's `assigned_grade` and `assigned_section` (`OCRISUser.class_scope()`).

### How it is enforced

- `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`, so an endpoint is closed to anonymous users unless it explicitly opts out. Only login does.
- Role checks use two permission classes in `backend/api/permissions.py`: `IsOIC` and `IsOICOrAdmin`.
- The class limit for teachers is applied in the view by merging `class_scope()` into the database filter.
- A teacher with no grade or section assigned gets `403` on every class-limited endpoint, so an incompletely set-up account sees nothing.
- The frontend hides menu items and buttons a role cannot use, but this is for convenience only. The server makes the decision on every request.
- Uploaded scans are not served as static files. The only way to fetch one is the download endpoint, which applies the class limit.

### Safeguards on user management

- A user cannot delete their own account.
- The last active OIC cannot be deleted, deactivated or given another role, so there is always someone who can manage users.
- Deleting a user removes the account and its token but keeps the records, scans and audit entries they produced.

## 4. Audit log

The following actions are written to the `audit_log` collection with the username and time:

| Action | Meaning |
|---|---|
| `LOGIN` | A user logged in |
| `UPLOAD` | A scan was uploaded and read |
| `VALIDATE` | A record was saved |
| `EDIT` | A record was changed |
| `DELETE` | A record was deleted |
| `DOWNLOAD` | An original scan was downloaded |
| `CREATE_USER` | A user account was created |
| `DELETE_USER` | A user account was deleted |
| `EDIT_USER` | A user account was changed (including deactivation) |
| `RESET_PASSWORD` | The OIC set a new password for a user |
| `CHANGE_PASSWORD` | A user changed their own password |

The log is visible to OIC and Admin Staff on the Audit Log page. The application has no function to edit or delete log entries.

Not logged: failed logins, sign-outs, and views of records.

## 5. File handling

- Only JPG and PNG are accepted in the upload screen, up to 20 MB (also limited by `DATA_UPLOAD_MAX_MEMORY_SIZE`).
- The stored filename is built by the server from a random prefix and a sanitized copy of the original name; characters other than letters, digits, `.`, `_` and `-` are replaced.
- The download endpoint resolves the path and refuses anything outside `media/scans/`, so a stored filename cannot be used to read other files on the server.
- When OCR fails, the uploaded file is deleted.

## 6. Data integrity

- **No silent OCR output.** A value is accepted automatically only when repeated readings agree. Anything else must be confirmed by a person before the record can be saved. If OCR fails, the user sees an error; the system never substitutes sample data.
- **Traceability.** Each record keeps the ID of its scan and the corrections entered by hand. The scan keeps the original OCR output and the original image. Together they show what the machine read, what a person changed, and who saved it.
- **Blank is not zero.** A blank grade is stored as `N/A` and is excluded from averages and analytics.

## 7. Secrets and configuration

- Secrets (`SECRET_KEY`, `SEED_PASSWORD`, the MongoDB URI) are read from `backend/.env`, which is excluded from Git. `.env.example` contains only placeholders.
- The seed script reads the default password from `SEED_PASSWORD` and does not print it.
- The SQLite database and the uploaded scans are also excluded from Git.

## 8. Data privacy notes

| Principle | How OCRIS addresses it |
|---|---|
| Access limited to authorized personnel | Login is required for everything; the login screen states that access is monitored under RA 10173 |
| Least privilege | Three roles; teachers are limited to their own class in lists, search and downloads |
| Accountability | Audit log of logins, uploads, validations, edits, deletions and downloads |
| Accuracy | Human validation of every uncertain value |

The data kept about each pupil is: name, LRN, grade level, section, school year, grades, and the scanned image of the form. Retention periods, consent, and breach procedures are organisational policies for the school to define; the software does not implement them.

## 9. Before real deployment

The repository is configured for development. The items that must change before the system holds real pupil data on a shared server are listed under "Deployment" in [LIMITATIONS.md](LIMITATIONS.md).
