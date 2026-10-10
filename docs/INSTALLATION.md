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
| `TOKEN_TTL_HOURS` | No | `12` | Hours a sign-in stays valid |
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

- Each user changes their own password with **Change password** at the top right of the app.
- The OIC sets a new password for another user from **User Management → Edit**.
- If the only OIC is locked out, reset the password from the backend:

```powershell
python manage.py changepassword <username>
```

## 7. Other commands

| Command | Where | What it does |
|---|---|---|
| `python manage.py check` | `backend/` | Checks the Django configuration |
| `python manage.py test` | `backend/` | Runs the automated tests. Needs MongoDB; uses a temporary database. |
| `python manage.py backup` | `backend/` | Writes a dated zip of the accounts, MongoDB data and scans into `backend/backups/` |
| `python manage.py cleanup_scans` | `backend/` | Deletes uploads never saved as a record and older than 7 days (`--days N`, `--dry-run`) |
| `python manage.py recompute_remarks` | `backend/` | Recalculates every record's average and remarks (`--dry-run` to preview) |
| `npm run build` | `frontend/` | Builds the production frontend into `frontend/dist/` |
| `npm run preview` | `frontend/` | Serves the built frontend locally |

## 8. Where data is kept

| Data | Location | In Git? |
|---|---|---|
| User accounts and login tokens | `backend/db.sqlite3` | No |
| Records, scans, audit log | MongoDB database named by `MONGO_DB_NAME` | No |
| Uploaded scan images | `backend/media/scans/` | No |

To back the system up, run `python manage.py backup`, which copies all three into one dated zip file in `backend/backups/`. Keep the zip somewhere other than this computer. Restoring is done by hand: put `db.sqlite3` and the `scans` folder back in place, and load each file in the zip's `mongo` folder with `mongoimport --jsonArray`.

To start over with an empty system, delete `db.sqlite3` and `media/scans/`, drop the MongoDB database, then run `migrate` and `seed.py` again.

## 9. Troubleshooting

| Problem | Cause and fix |
|---|---|
| Login says "Can't reach the server" | The backend is not running, or `VITE_API_URL` points to the wrong address. Start `python manage.py runserver`. |
| Login pauses for about 5 seconds and then says "Invalid username or password" even with the right password | MongoDB is probably not running. Login writes to the audit log in MongoDB, waits about 5 seconds for it, and then fails. Check the backend terminal for a `ServerSelectionTimeoutError` and start the MongoDB service. |
| Upload fails with "The OCR engine (Tesseract) was not found on the server" | Tesseract is not installed or not on `PATH`. Set `TESSERACT_CMD` in `backend/.env` and restart the backend. |
| Upload fails with "No grade rows were found on this scan" | The grade table is cropped, the wrong page was scanned, or the image is blank. Rescan with the whole table visible. |
| `seed.py` stops with "SEED_PASSWORD is not set" | Add `SEED_PASSWORD=...` to `backend/.env`. |
| Browser console shows a CORS error | The frontend is not on port 3000. Use `npm run dev` as configured, or add the origin to `CORS_ALLOWED_ORIGINS`. |
| Records exist in MongoDB but the app shows none | `MONGO_DB_NAME` in `backend/.env` differs from the database the records were saved in. Older copies of `.env.example` used `ocris`; the default is `ocris_bcs`. |
| The backend will not start: "Set a real SECRET_KEY…" | `DEBUG` is not `True` and `SECRET_KEY` is missing or still `change-me`. For development, put `DEBUG=True` in `backend/.env`. |
| Every request fails with "Bad Request (400)" | The address used to reach the backend is not in `ALLOWED_HOSTS`. Add it in `backend/.env`. |
| A teacher sees "Your account has no class assigned yet" | The OIC must assign a grade and section in User Management → Edit. |

## 10. Deploying beyond one computer

The configuration in this repository is for development. Before putting OCRIS on a shared or public server, read the deployment items in [LIMITATIONS.md](LIMITATIONS.md) and [SECURITY.md](SECURITY.md). At minimum: set `DEBUG=False` and a strong `SECRET_KEY`, set `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` to the real addresses, turn on MongoDB authentication, serve over HTTPS, run Django behind a production server instead of `runserver`, and schedule `python manage.py backup`.
