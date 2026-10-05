# OCRIS v3

**Optical Character Recognition Information System** for Bayombong Central School, Nueva Vizcaya.

OCRIS turns scanned paper **Form 137** permanent records into searchable digital records. A staff member uploads a scan, the system reads the pupil details and the grade table, a person checks every value the system was not sure about, and the result is saved as a record that can be searched, analysed and audited.

## Project information

| | |
|---|---|
| Project title | OCRIS: Optical Character Recognition Information System |
| Client | Bayombong Central School, Nueva Vizcaya |
| Project team | _to be filled in_ |
| Adviser | _to be filled in_ |
| Institution / program | _to be filled in_ |
| Version | 3 |

## What the system does

- **Digitizes Form 137.** Reads a scanned JPG or PNG with the Tesseract OCR engine. Grades are read cell by cell from the ruled grade table.
- **Checks the scan first.** Measures resolution, contrast, brightness, sharpness, page tilt and ink coverage before OCR runs, and warns when a rescan is needed.
- **Keeps a person in the loop.** A grade is accepted automatically only when repeated readings agree. Everything else is flagged, and the record cannot be saved until a person has confirmed each flagged value against the paper form.
- **Computes results.** Works out the general average and a remark of Promoted, Retained or Incomplete.
- **Stores and finds records.** Records can be listed, filtered, searched and opened, and the original scan can be downloaded.
- **Reports on grades.** Shows class means by subject, pass rates by grade level, and flags subjects whose mean falls below 75.
- **Controls access.** Three roles (Officer in Charge, Admin Staff, Teacher) with different permissions. Teachers are limited to their assigned class.
- **Keeps an audit trail.** Logins, uploads, validations, edits, deletions and downloads are logged.

## Technology

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, plain CSS |
| Backend | Python, Django 4.2, Django REST Framework 3.15 |
| OCR | Tesseract 5 through `pytesseract`, image processing with Pillow |
| Record storage | MongoDB (records, scans, audit log) through `pymongo` |
| Account storage | SQLite (user accounts and login tokens) |
| Authentication | Token authentication (DRF `authtoken`) |

## Quick start

Prerequisites: Python 3.10 to 3.12, Node.js 18+, MongoDB running locally, and Tesseract OCR 5 installed. Full instructions are in [docs/INSTALLATION.md](docs/INSTALLATION.md).

**Backend** (first terminal):

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit .env: set SECRET_KEY and SEED_PASSWORD
python manage.py migrate
python seed.py
python manage.py runserver
```

**Frontend** (second terminal):

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

The app opens at <http://localhost:3000>. Sign in as `k.saquing` with the `SEED_PASSWORD` you set in `backend/.env`.

## Documentation

| Document | Contents |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Prerequisites, setup, configuration, default accounts, troubleshooting |
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | How to use every screen, written for school staff |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, components, data flow, project structure |
| [docs/OCR_PIPELINE.md](docs/OCR_PIPELINE.md) | How a scan becomes a record: quality check, table reading, grading rules |
| [docs/API.md](docs/API.md) | Every REST endpoint with parameters, responses and permissions |
| [docs/DATABASE.md](docs/DATABASE.md) | Data dictionary for the MongoDB collections and SQLite tables |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, roles and permissions, audit log, data privacy |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Testing done so far, known limitations, recommendations |
| [docs/FIXES_2026-10-04.md](docs/FIXES_2026-10-04.md) | The limitations fixed on October 4, 2026: before and after, and what remains |
| [CHANGELOG.md](CHANGELOG.md) | Detailed history of changes and fixes |

## Repository layout

```
OCRIS_v3/
  backend/            Django REST API, OCR engine, database access
    api/              the application: views, OCR, services, models
    ocris_backend/    Django project settings and root URLs
    seed.py           creates the default user accounts
  frontend/           React single-page application
    src/pages/        one file per screen
    src/components/   shared layout and UI components
    src/utils/        API client and helpers
  docs/               project documentation
  CHANGELOG.md
```
