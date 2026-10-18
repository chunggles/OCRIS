# Installation and Setup

This guide sets OCRIS up on one computer for development or demonstration. Commands are for Windows PowerShell; differences for macOS and Linux are noted.

## 1. Prerequisites

| Software | Version | Purpose |
|---|---|---|
| Python | 3.10 to 3.12 (developed on 3.12) | Runs the backend |
| Node.js | 18 or later (developed on 24) | Builds and serves the frontend |
| MongoDB Community Server | 6 or later | Stores records, scans and the audit log |
| Tesseract OCR | 5.x (developed on 5.5) | Reads text from the scans |
| Git | any | Gets the source code |

### Installing Tesseract

- **Windows:** install the UB Mannheim build. The default location is `C:\Program Files\Tesseract-OCR\tesseract.exe`. Either add that folder to `PATH`, or set `TESSERACT_CMD` in `backend/.env` (see section 3).
- **macOS:** `brew install tesseract`
- **Ubuntu / Debian:** `sudo apt install tesseract-ocr`

Check it works:

```powershell
tesseract --version
```

### Installing MongoDB

Install MongoDB Community Server and make sure the service is running. By default it listens on `mongodb://localhost:27017`. OCRIS creates its database and collections automatically the first time it writes to them, so there is nothing to create by hand.

## 2. Get the code

```powershell
git clone <repository-url> OCRIS_v3
cd OCRIS_v3
```

## 3. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

On macOS or Linux, use `source venv/bin/activate` and `cp .env.example .env`.

### Configure `backend/.env`

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `SECRET_KEY` | Yes | `ocris-dev-key` | Django secret key. Use a long random value. |
| `DEBUG` | For development | `False` | Django debug mode. `.env.example` sets it to `True` for development. When it is `False`, the server will not start unless `SECRET_KEY` is a real value. |
| `MONGO_URI` | No | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | No | `ocris_bcs` | MongoDB database name |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Host names the backend answers to, separated by commas. Add the server's name or IP address when others connect to it. |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:3000,http://127.0.0.1:3000` | Addresses the frontend may be opened from, separated by commas |
| `DATA_ENCRYPTION_KEY` | Yes when `DEBUG` is `False` | none | Key that encrypts uploaded scans and backups. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Several keys separated by commas allow rotation: the first encrypts, all can decrypt. **Keep a copy outside the server: without the key, encrypted scans and backups cannot be read.** |
| `PENDING_SCAN_DAYS` | No | `7` | Days an upload that was read but not saved is kept before the server deletes it (`0` keeps them) |
| `BACKUP_KEEP` | No | `14` | Backup files `manage.py maintenance` leaves in `backend/backups/` |
| `TOKEN_TTL_HOURS` | No | `12` | Hours a sign-in stays valid |
| `IDLE_TIMEOUT_MINUTES` | No | `30` | Minutes a sign-in may go without use before it ends; `0` turns this off |
| `LOGIN_MAX_ATTEMPTS` | No | `5` | Wrong passwords for one username before sign-in is refused |
| `LOGIN_MAX_ATTEMPTS_PER_IP` | No | `20` | The same, counted per address |
| `LOGIN_LOCKOUT_MINUTES` | No | `15` | How long failures count, and so how long a lock lasts |
| `RESET_MAX_REQUESTS` | No | `5` | "Forgot password" requests per address per window |
| `TRUSTED_PROXY_COUNT` | No | `1` when HTTPS is required, else `0` | Proxies in front of the server (a cloud host's load balancer is one). Needed so the real address of a caller is used for the limits above. |
| `AUTH_COOKIE_SAMESITE` | No | `None` with HTTPS, else `Lax` | Use `None` (needs HTTPS) when the site and the server are on different domains; `Lax` or `Strict` when they share one |
| `MAX_UPLOAD_MB` | No | `20` | Largest scan accepted |
| `AUDIT_LOG_FILE` | No | `backend/logs/audit.jsonl` | File every audit entry is also appended to |
| `OCR_CONFIDENCE_THRESHOLD` | No | `90` | A grade read from a scan is auto-approved only above this confidence (%). Lower it to review fewer grades by hand, at more risk of a wrong one. |
| `REQUIRE_HTTPS` | No | `True` when `DEBUG` is `False` | Redirects plain HTTP to HTTPS and sends cookies over HTTPS only |
| `SEED_PASSWORD` | Yes, for seeding | none | Password given to the default accounts by `seed.py` |
| `TESSERACT_CMD` | Only if Tesseract is not on `PATH` | empty | Full path to the Tesseract executable, e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe` |

`.env` is ignored by Git. Never commit it.

### Create the database and default accounts

```powershell
python manage.py migrate
python seed.py
```

`migrate` creates `db.sqlite3` with the user and token tables. `seed.py` creates the accounts below, all with the password from `SEED_PASSWORD`. Accounts that already exist are skipped, so it is safe to run again.

| Username | Role | Assigned class | Employee ID |
|---|---|---|---|
| `k.saquing` | OIC | none (full access) | BCS-OIC-001 |
| `j.aquino` | Admin Staff | none (full access) | BCS-ADM-001 |
| `g.ramos` | Teacher | Grade 6, Sampaguita | BCS-TCH-001 |
| `m.delacruz` | Teacher | Grade 5, Orchid | BCS-TCH-002 |
| `r.santos` | Teacher | Grade 4, Rosal | BCS-TCH-003 |

Change these passwords before real use (see section 6).

### Run the backend

```powershell
python manage.py runserver
```

The API is served at <http://localhost:8000/api/>.

## 4. Frontend

In a second terminal:

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

| Variable (`frontend/.env`) | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL of the backend API |

The development server runs on port 3000 and opens <http://localhost:3000> in the browser. The port matters: by default the backend only accepts browser requests from `http://localhost:3000` and `http://127.0.0.1:3000`. Other addresses are added with `CORS_ALLOWED_ORIGINS` in `backend/.env`.

## 5. First login

1. Open <http://localhost:3000>.
2. Sign in as `k.saquing` with the `SEED_PASSWORD`.
3. Go to **Upload Form 137** and try a scan. See the [User Manual](USER_MANUAL.md).

## 6. Managing passwords

- A password needs at least 10 characters, with letters and numbers, and must not be a common password or resemble the username or name.
- Each user changes their own password with **Change password** at the top right of the app. Their other devices are signed out.
- A password the OIC types when creating an account or in **User Management → Edit** is **temporary**: the user must replace it at the next sign-in, before they can do anything else.
- A user who forgot their password uses **Forgot your password?** on the login screen. The OIC then sees "Password reset asked" beside that account and sets a new temporary password. No email is sent.
- After 5 wrong passwords a username is locked for up to 15 minutes. It frees itself; the OIC need do nothing.
- If the only OIC is locked out or forgot their own password, reset it from the backend:

```powershell
python manage.py changepassword <username>
```

## 7. Other commands

| Command | Where | What it does |
|---|---|---|
| `python manage.py check` | `backend/` | Checks the Django configuration |
| `python manage.py test` | `backend/` | Runs the automated tests. Needs MongoDB; uses a temporary database. |
| `python manage.py backup` | `backend/` | Writes a dated zip of the accounts, MongoDB data and scans into `backend/backups/`. `--keep N` then deletes all but the newest N backups |
| `python manage.py restore <file>` | `backend/` | Puts a backup back (accounts, MongoDB, scans). Without `--yes` it only lists what the backup holds. Takes a safety backup of the current data first |
| `python manage.py maintenance` | `backend/` | The routine upkeep for a schedule: a backup (keeping `BACKUP_KEEP`, 14), removal of old unsaved uploads, the MongoDB indexes, and the audit file check |
| `python manage.py verify_audit` | `backend/` | Checks that no line of the audit file was changed, added, moved or removed, and that it holds every entry the database holds; exit code 1 when it finds a change (see SECURITY.md) |
| `python manage.py create_indexes` | `backend/` | Creates the MongoDB indexes that are missing (the server also does it by itself) |
| `python manage.py cleanup_scans` | `backend/` | Deletes uploads never saved as a record and older than 7 days (`--days N`, `--dry-run`). The server also does this by itself (see below). With `--deleted-days N` it also purges scans kept after their record was deleted more than N days ago |
| `python manage.py encrypt_scans` | `backend/` | Encrypts scans uploaded before `DATA_ENCRYPTION_KEY` was set. Run once after setting the key; safe to repeat |
| `python manage.py decrypt_backup <file>` | `backend/` | Turns an encrypted backup (`.zip.enc`) back into a zip |
| `python manage.py tidy_records` | `backend/` | One-off repair of older records: one spelling per subject, one school year per scanned form, marks the scans of forms archived before 2026-10-18, and marks forms typed in with three terms before then (`--dry-run` to preview) |
| `python manage.py recompute_remarks` | `backend/` | Recalculates every record's average and remarks, except archived forms, which have none (`--dry-run` to preview) |
| `npm run build` | `frontend/` | Builds the production frontend into `frontend/dist/` |
| `npm run preview` | `frontend/` | Serves the built frontend locally |

## 8. Where data is kept

| Data | Location | In Git? |
|---|---|---|
| User accounts, login sessions, sign-in attempts | `backend/db.sqlite3` | No |
| Records, scans, audit log | MongoDB database named by `MONGO_DB_NAME` | No |
| Uploaded scan images (encrypted when `DATA_ENCRYPTION_KEY` is set) | `backend/media/scans/` | No |
| A second copy of the audit log, one JSON line per entry | `backend/logs/audit.jsonl` | No |

To back the system up, run `python manage.py backup`, which copies the first three into one dated zip file in `backend/backups/`. With `DATA_ENCRYPTION_KEY` set the zip is encrypted as a whole (`.zip.enc`); without it the command warns that the backup is not encrypted. Copy `backend/logs/audit.jsonl` too. Keep the backups somewhere other than this computer, and keep the encryption key somewhere else again. To restore, stop the server and run `python manage.py restore backups/<file>` to see what the backup holds, then again with `--yes` to replace the current accounts, records, scans, audit log and sections with it (an encrypted backup needs the same `DATA_ENCRYPTION_KEY`). The current data is backed up into `backups/before-restore/` first unless you add `--skip-safety-backup`. Scan files in the backup are added to the scans folder; files that are only on the server are left alone. Start the server again afterwards, and sign-in cookies of the old sessions that are not in the backup stop working. **Rehearse a restore on a copy before you need it.**

### Scheduled backups

`python manage.py maintenance` backs up, keeps the newest `BACKUP_KEEP` (default 14) backups, removes old unsaved uploads, checks the indexes and checks the audit file (a WARNING line means `verify_audit` found a change). OCRIS has no scheduler of its own, so ask the operating system to run it every night.

- **Windows (Task Scheduler):** `schtasks /Create /SC DAILY /ST 22:00 /TN "OCRIS maintenance" /TR "cmd /c cd /d C:\path\to\OCRIS_v3\backend && venv\Scripts\python manage.py maintenance >> logs\maintenance.log 2>&1"`
- **Linux (cron):** `0 22 * * * cd /srv/ocris/backend && venv/bin/python manage.py maintenance >> logs/maintenance.log 2>&1`

A backup that stays on the same disk does not protect against that disk failing: copy `backend/backups/` and `backend/logs/audit.jsonl` somewhere else as well.

### Unsaved uploads

A form that was read but never saved is kept for `PENDING_SCAN_DAYS` (default 7) so that its user can carry on from the Upload page. After that the server deletes it, with its file, by itself: whenever someone uploads, at most once an hour. Set `PENDING_SCAN_DAYS=0` to keep them until `cleanup_scans` is run.

**Switching encryption on for an existing system:** add `DATA_ENCRYPTION_KEY` to `.env`, restart the server, then run `python manage.py encrypt_scans` once. After upgrading to this version, run `python manage.py migrate` once; everyone is signed out and signs in again (the old token table is no longer used).

**Upgrading to the 2026-10-18 version:** run `python manage.py migrate` once (it adds the sessions' last-use time and replaces each stored session key by its hash; until then signed-in requests fail). Sessions stay signed in.

To start over with an empty system, delete `db.sqlite3` and `media/scans/`, drop the MongoDB database, then run `migrate` and `seed.py` again.

## 9. Troubleshooting

| Problem | Cause and fix |
|---|---|
| Login says "Can't reach the server" | The backend is not running, or `VITE_API_URL` points to the wrong address. Start `python manage.py runserver`. |
| Login pauses for about 5 seconds and then says "Invalid username or password" even with the right password | MongoDB is probably not running. Login writes to the audit log in MongoDB, waits about 5 seconds for it, and then fails. Check the backend terminal for a `ServerSelectionTimeoutError` and start the MongoDB service. |
| Upload fails with "The OCR engine (Tesseract) was not found on the server" | Tesseract is not installed or not on `PATH`. Set `TESSERACT_CMD` in `backend/.env` and restart the backend. |
| Upload fails with "No grade rows were found on this scan" | The grade table is cropped, the wrong page was scanned, or the image is blank. Rescan with the whole table visible. |
| Login succeeds but the next screen returns to the login page | The browser is not sending the sign-in cookie. In development, open the site and the API with the **same host name**: `http://localhost:3000` with `VITE_API_URL=http://localhost:8000/api` (not `127.0.0.1` for one and `localhost` for the other), and make sure the address in the browser is listed in `CORS_ALLOWED_ORIGINS`. On a real server use HTTPS and `AUTH_COOKIE_SAMESITE=None` when the site and the API are on different domains. |
| `seed.py` stops with "SEED_PASSWORD is not set" | Add `SEED_PASSWORD=...` to `backend/.env`. |
| Browser console shows a CORS error | The frontend is not on port 3000. Use `npm run dev` as configured, or add the origin to `CORS_ALLOWED_ORIGINS`. |
| Records exist in MongoDB but the app shows none | `MONGO_DB_NAME` in `backend/.env` differs from the database the records were saved in. Older copies of `.env.example` used `ocris`; the default is `ocris_bcs`. |
| The backend will not start: "Set a real SECRET_KEY…" | `DEBUG` is not `True` and `SECRET_KEY` is missing or still `change-me`. For development, put `DEBUG=True` in `backend/.env`. |
| Every request fails with "Bad Request (400)" | The address used to reach the backend is not in `ALLOWED_HOSTS`. Add it in `backend/.env`. |
| A teacher sees "Your account has no class assigned yet" | The OIC must assign a grade and section in User Management → Edit. |

## 10. Deploying beyond one computer

The configuration in this repository is for development. Before putting OCRIS on a shared or public server, read the deployment items in [LIMITATIONS.md](LIMITATIONS.md) and [SECURITY.md](SECURITY.md). At minimum: set `DEBUG=False` and a strong `SECRET_KEY`, set `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` to the real addresses, turn on MongoDB authentication, serve over HTTPS, run Django behind a production server instead of `runserver`, and schedule `python manage.py maintenance` (see "Scheduled backups" above).
