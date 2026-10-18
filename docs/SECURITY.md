# Security and Access Control

OCRIS stores pupils' personal information and academic records, which are personal data under the Data Privacy Act of 2012 (RA 10173). This document describes how access is controlled and recorded. Known weaknesses are listed in [LIMITATIONS.md](LIMITATIONS.md); the list this version works from is [WEAKNESSES_2026-10-10.md](WEAKNESSES_2026-10-10.md), section D.

## 1. Authentication

### Signing in

- Users sign in with a username and password (`POST /api/auth/login/`).
- Passwords are hashed by Django (PBKDF2 with SHA-256) and are never stored or logged in plain text.
- A deactivated account (`is_active = false`) cannot log in.

### Limits on guessing

- After **5 wrong passwords for one username** within 15 minutes, sign-in for that username is refused with `429` and a wait time, even for the right password. After 20 failures from one address, that address is refused. The lock frees itself as the failures age out.
- Usernames that do not exist are counted the same way, so the limit and the error message do not reveal which accounts exist.
- Failures are stored in the `ocris_auth_attempts` table (not in memory), so the limit holds across restarts and several server processes. Behind a proxy or a cloud host's load balancer, set `TRUSTED_PROXY_COUNT` so the caller's real address is used and cannot be faked with the `X-Forwarded-For` header.
- `LOGIN_FAILED` and `LOGIN_LOCKED` are written to the audit log. The numbers are settings: `LOGIN_MAX_ATTEMPTS`, `LOGIN_MAX_ATTEMPTS_PER_IP`, `LOGIN_LOCKOUT_MINUTES`.

### Password rules

- At least **10 characters**, with **letters and numbers**; not entirely numeric; not on a list of common passwords; not similar to the username or name. The rules (`AUTH_PASSWORD_VALIDATORS` in `settings.py`) apply when a user changes their own password and when the OIC creates an account or sets a password.
- A password typed by the OIC is **temporary**: the account is marked `must_change_password`. Until it is replaced, the server answers `403` with `"code": "password_change_required"` to everything except `/auth/me/`, `/auth/change-password/` and the sign-out routes, and the app shows a window that cannot be closed. The check is made in the authentication class, so no endpoint can forget it. The OIC setting their own password is not temporary.
- Changing your own password requires the current one and signs you out of your other devices.

### Forgotten passwords

- The login screen has **Forgot your password?**. OCRIS sends no email. The request marks the account (`password_reset_requested_at`) and the OIC sees "Password reset asked" on User Management; setting a new temporary password clears it.
- The answer is the same for an existing and a missing username, and at most 5 requests per address are accepted per 15 minutes, so the form cannot be used to list accounts or to flood the OIC.
- If the only OIC cannot sign in, the person who maintains the server runs `python manage.py changepassword <username>`.

### Sessions

- A successful login creates a **session** (`ocris_login_sessions`) whose random key is sent in the **`ocris_session` cookie**: `HttpOnly` (scripts on the page cannot read it, so a malicious script cannot steal it), `Secure` whenever HTTPS is required, and `SameSite` set by `AUTH_COOKIE_SAMESITE` (`None` with HTTPS so a site and a server on different domains can talk, `Lax` for local development). The browser holds no token in `localStorage`.
- The key is not returned in any response body.
- **One session per sign-in.** A user may be signed in on several devices. **Sign out** ends only that device; **Sign out of every device** on the Profile page (`POST /api/auth/logout-all/`) ends all of them, and the other devices return to the login screen at their next check. Changing your password ends the other devices; the OIC setting a user's password ends all of theirs.
- A session **expires 12 hours after sign-in** (`TOKEN_TTL_HOURS`). Any request with a missing, unknown or expired cookie gets `401`, and the app returns to the login screen.
- A session also **ends after 30 minutes without use** (`IDLE_TIMEOUT_MINUTES`; `0` turns it off), so a computer left signed in does not stay open. Use means typing, clicking, scrolling or touching anywhere in the app, not only requests: someone typing a long form makes no requests, so the app's own check of the signed-in user (every few minutes, sooner for a short limit) tells the server whether there was any use since the last one, and a check with no use (`?background=1`) does not extend the session. When the limit has passed without use the app asks the server at once and shows the login screen with "You were signed out after 30 minutes without use". In practice the session ends 30 to about 34 minutes after the last use.

### Forged requests

Because the browser sends the cookie by itself, a hostile website could try to make a visitor's browser send a request to OCRIS. Two things stop it:

1. Every request that changes data, and login itself, must carry the custom header `X-OCRIS-Request`. A page on another site cannot add a custom header to a request without a CORS pre-flight, and the server allows pre-flights only from `CORS_ALLOWED_ORIGINS`.
2. The server answers `403` to such requests without the header.

Django's own CSRF protection remains on for the admin site. Only the origins in `CORS_ALLOWED_ORIGINS` may call the API with credentials; list nothing else.

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
| Create, edit, deactivate or delete users, set passwords | Yes | No | No |

"Own class" means records whose grade level and section equal the teacher's `assigned_grade` and `assigned_section` (`OCRISUser.class_scope()`).

### How it is enforced

- `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`, so an endpoint is closed to anonymous users unless it explicitly opts out. Only login and "forgot password" do.
- Role checks use two permission classes in `backend/api/permissions.py`: `IsOIC` and `IsOICOrAdmin`.
- The class limit for teachers is applied in the view by merging `class_scope()` into the database filter.
- A teacher with no grade or section assigned gets `403` on every class-limited endpoint, so an incompletely set-up account sees nothing.
- The frontend hides menu items and buttons a role cannot use, but this is for convenience only. The server makes the decision on every request.
- Uploaded scans are not served as static files. The only way to fetch one is the download endpoint, which applies the class limit.

### Safeguards on user management

- A user cannot delete their own account.
- The last active OIC cannot be deleted, deactivated or given another role, so there is always someone who can manage users.
- Deleting a user removes the account and its sessions but keeps the records, scans and audit entries they produced.

## 4. Audit log

The following actions are written to the `audit_log` collection with the username and time:

| Action | Meaning |
|---|---|
| `LOGIN` | A user logged in (with the address they came from) |
| `LOGIN_FAILED` | A wrong username or password; the name typed and the address are kept |
| `LOGIN_LOCKED` | Repeated failures locked a username |
| `LOGOUT` | A user signed out (one device or all) |
| `PASSWORD_RESET_REQUEST` | A user asked for a new password from the login screen |
| `UPLOAD` | A scan was uploaded and read |
| `VALIDATE` | A record was saved; every value a person entered in place of what the OCR read is kept (`read` and `new`) |
| `ENCODE` | A record was typed in on the Fill Out Form 137 page |
| `EDIT` | A record was changed; the **old and new value** of every changed field, and of every grade, are kept |
| `DELETE` | A record was deleted; a **snapshot** of what it held (identity, average, remarks and all grades) is kept, and the scan is retained |
| `DOWNLOAD` | An original scan was downloaded |
| `CREATE_USER`, `DELETE_USER` | A user account was created or deleted |
| `EDIT_USER` | A user account was changed; old and new values are kept (passwords never) |
| `RESET_PASSWORD` | The OIC set a new password for a user |
| `CHANGE_PASSWORD` | A user changed their own password |
| `ADD_SECTION`, `EDIT_SECTION`, `DELETE_SECTION` | The section tree was changed |

The log is visible to OIC and Admin Staff on the Audit Log page. The application has no function to edit or delete log entries.

**A second copy outside the database.** Every entry is first appended as one JSON line to `backend/logs/audit.jsonl` (`AUDIT_LOG_FILE`), then stored in MongoDB. If the database is wiped or replaced, the file still holds the trail. It must be kept on storage that a deploy does not wipe, and copied with each backup.

**Changes to the file show.** The file is a hash chain: each line holds the hash of the line before it (`prev`) and its own (`hash`, SHA-256 of the line). The same hash is stored with the entry in MongoDB. `python manage.py verify_audit` (also run by `maintenance`) reports a line that was changed, a line removed, added or moved, a line without a hash after the chain began, and entries the database holds that the file has lost (the end cut off, or the file replaced); it exits with code 1 when it finds any. Entries in the file but not in the database are listed as a note: they were deleted from the database, or the database was restored from an older backup. Lines written before this version are counted but cannot be checked. Writers take a lock, so two server processes never break the chain.

This makes a change **visible, not impossible**: someone with access to the server who rewrites both the file and the database, recomputing every hash, is not detected. For that, copy the file regularly to a computer or log service the server cannot write to.

Not logged: record views.

## 5. File handling

### Uploads

- Only **JPG, PNG and PDF** are accepted, up to `MAX_UPLOAD_MB` (default 20).
- The server checks, before the file is stored or read: the declared request size (refused with `413` before the body is read), the real size, the **type from the file's first bytes** (never the browser's claim), that the name's extension matches that type, and for images that the file opens, is not damaged and is at most 120 megapixels. Refusals are `400` (empty), `413` (too large), `415` (wrong or damaged type).
- The stored filename is built by the server from a random prefix and a sanitized copy of the original name; characters other than letters, digits, `.`, `_` and `-` are replaced.
- The download endpoint resolves the path and refuses anything outside `media/scans/`, so a stored filename cannot be used to read other files on the server.
- When OCR fails, the uploaded file is deleted.

### Encryption at rest

- When `DATA_ENCRYPTION_KEY` is set, every uploaded scan is **encrypted before it is written to disk** (Fernet: AES-128-CBC with an HMAC, in 1 MB pieces so large files are not held in memory). Backups are encrypted as a whole (`.zip.enc`), because they also hold names, grades and password hashes.
- The server decrypts a scan only (a) while it is sent to a user who is allowed to download it, and (b) into a temporary folder for the time the OCR reads it; the folder is removed straight after.
- The key is in `backend/.env`, never in the database or in Git. Several keys separated by commas allow **rotation**: the first encrypts, all of them decrypt, so a new key can be added in front without re-encrypting. When `DEBUG` is off the server will not start without a key.
- Scans uploaded before the key was set are read as they are; `python manage.py encrypt_scans` encrypts them. `python manage.py decrypt_backup <file>` turns a backup back into a zip.
- **Lose the key and the encrypted files are unrecoverable.** Keep a copy somewhere other than the server and the backups.
- Not covered: MongoDB itself (names, grades and the text read from scans are stored in it as ordinary data). Use MongoDB's encryption at rest or an encrypted disk for that.

### Deleted records and their scans

Deleting a record does **not** delete its scan. The original form is the evidence for the record, so it stays as part of the audit trail: the scan is marked `record deleted` (with who and when), still listed in Scan History and still downloadable by those allowed to see its class, and the audit entry holds a snapshot of the record's contents so it can be restored by hand. A school that wants to remove old personal data does so deliberately, with `python manage.py cleanup_scans --deleted-days N`, which purges scans whose record was deleted more than N days ago.

## 6. Data integrity

- **No silent OCR output.** A value is accepted automatically only when repeated readings agree and their confidence is above 90%. Anything else must be confirmed by a person before the record can be saved. If OCR fails, the user sees an error; the system never substitutes sample data.
- **Traceability.** Each record keeps the ID of its scan and the corrections entered by hand. The scan keeps the original OCR output and the original image. The audit log keeps what the OCR read and what replaced it, and the old and new value of every later edit. Together they show what the machine read, what a person changed, and who saved it.
- **Blank is not zero.** A blank grade is stored as `N/A` and is excluded from averages and analytics.

## 7. Secrets and configuration

- Secrets (`SECRET_KEY`, `DATA_ENCRYPTION_KEY`, `SEED_PASSWORD`, the MongoDB URI) are read from `backend/.env`, which is excluded from Git. `.env.example` contains only placeholders.
- The seed script reads the default password from `SEED_PASSWORD` and does not print it.
- The SQLite database, the uploaded scans, the backups and the audit file are also excluded from Git.
- With `DEBUG` off, the server refuses to start without a real `SECRET_KEY` and a valid `DATA_ENCRYPTION_KEY`, and HTTPS is required (plain HTTP is redirected, cookies are HTTPS-only).

## 8. Data privacy notes

| Principle | How OCRIS addresses it |
|---|---|
| Access limited to authorized personnel | Login is required for everything; the login screen states that access is monitored under RA 10173 |
| Protection against guessing and theft of credentials | Limits on wrong passwords; strong-password rule; temporary passwords must be replaced; the session key is HttpOnly |
| Least privilege | Three roles; teachers are limited to their own class in lists, search and downloads |
| Security of stored data | Scans and backups encrypted at rest; uploads validated by content; HTTPS enforced |
| Accountability | Audit log of sign-ins (including failures), uploads, validations, edits with old and new values, deletions and downloads, kept also in a file |
| Accuracy | Human validation of every uncertain value |
| Retention | Deleted records keep their scan as an audit trail; purge deliberately with `cleanup_scans --deleted-days` |

The data kept about each pupil is: name, LRN, grade level, section, school year, grades, and the scanned image of the form. Retention periods, consent, and breach procedures are organisational policies for the school to define; the software supports them (the purge command, the audit trail) but does not decide them.

## 9. Before real deployment

The repository is configured for development. Before the system holds real pupil data on a shared server:

1. Set `DEBUG=False`, a long random `SECRET_KEY` and a `DATA_ENCRYPTION_KEY`; store a copy of the key apart from the server.
2. Serve everything over HTTPS; set `CORS_ALLOWED_ORIGINS` to the site's address only, `TRUSTED_PROXY_COUNT` to the number of proxies, and `AUTH_COOKIE_SAMESITE=None` if the site and the server are on different domains.
3. Run `python manage.py migrate`, then `python manage.py encrypt_scans` if scans already exist.
4. Keep `db.sqlite3`, `media/scans/` and `logs/audit.jsonl` on storage that is not wiped on deploy, or move accounts to a database that is (see "Deployment" in [LIMITATIONS.md](LIMITATIONS.md)).
5. Enable MongoDB authentication and encryption at rest.
