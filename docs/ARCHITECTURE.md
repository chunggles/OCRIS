# System Architecture

## 1. Overview

OCRIS is a three-tier web application:

1. A **React single-page application** in the browser.
2. A **Django REST API** that holds the business logic and the OCR engine.
3. **Two data stores**: SQLite for user accounts, MongoDB for records, scans and the audit log. Uploaded images are kept on the server's disk.

```mermaid
flowchart LR
    subgraph Browser
        UI[React SPA<br/>Vite, port 3000]
    end
    subgraph Server["Django backend, port 8000"]
        API[REST API<br/>Django REST Framework]
        OCR[OCR engine<br/>Pillow + pytesseract]
        SVC[Services<br/>grading, storage]
    end
    TESS[Tesseract 5<br/>executable]
    SQL[(SQLite<br/>users, tokens)]
    MONGO[(MongoDB<br/>records, scans,<br/>audit_log, users)]
    DISK["media/scans<br/>uploaded images"]

    UI -- "JSON over HTTP<br/>Authorization: Token" --> API
    API --> OCR
    API --> SVC
    OCR --> TESS
    API --> SQL
    API --> MONGO
    SVC --> DISK
```

### Why two databases

- **SQLite** holds what Django's authentication system manages: user accounts, hashed passwords and login tokens. Using Django's built-in user model gives password hashing, the admin site and token authentication without extra code.
- **MongoDB** holds the school data. A Form 137 record is a natural document: the set of subjects differs between forms and year levels, and each record carries a nested grade sheet. Storing it as one document avoids a fixed schema of subject columns.

SQLite is the source of truth for users. A copy of each user (without the password) is mirrored to a MongoDB `users` collection for reference.

## 2. Backend

Location: `backend/`. Framework: Django 4.2 with Django REST Framework.

```
backend/
  manage.py
  seed.py                   creates the default accounts
  requirements.txt
  ocris_backend/
    settings.py             configuration (reads .env)
    urls.py                 /admin/ and /api/
  api/
    models.py               OCRISUser: roles, class assignment, class access check
    authentication.py       token authentication with expiry
    permissions.py          IsOIC, IsOICOrAdmin
    tests.py                automated tests
    management/commands/    backup, cleanup_scans, recompute_remarks
    serializers.py          login, user, and validation payloads
    urls.py                 all /api/ routes
    constants.py            passing grade, N/A handling, remark names
    db.py                   every MongoDB read and write
    views/
      auth.py               login, logout, current user, change password
      records.py            list, search, filter options, detail, create (typed-in forms), update, delete
      ocr.py                quality check, upload, validate, download, history
      analytics.py          grade analytics
      sections.py           the section tree: list, add, edit, delete
      users.py              user management
      audit.py              audit log
    services/
      grading.py            builds the grade sheet, average, and remarks
      storage.py            saves and finds uploaded files
    ocr/
      engine.py             read_scan / run_ocr entry points, error handling, retry on a smoothed copy
      pdf.py                opens a scan as an image; renders page 1 of a PDF
      quality.py            image quality measurements
      preprocess.py         straightening and clean-up before OCR
      table.py              reads the grade table cell by cell; one or two table columns (SF10-ES)
      parser.py             subject names; free-text fallback parser
      pupil.py              reads name, LRN, grade, section, school year
    utils/http.py           small request and response helpers; the teacher's-own-class check
```

### Layering

| Layer | Modules | Responsibility |
|---|---|---|
| Routing | `api/urls.py` | Maps URLs to view functions |
| Views | `api/views/*` | Check permissions, read the request, call the layers below, write the audit log, shape the response |
| Services | `api/services/*` | Business rules that do not depend on HTTP: grading and file storage |
| OCR | `api/ocr/*` | Everything about turning an image into fields |
| Data access | `api/db.py`, `api/models.py` | MongoDB queries and the Django user model |

Views are function-based (`@api_view`). Each declares its allowed methods and its permission class directly above the function, so the access rule for an endpoint can be read in one place.

## 3. Frontend

Location: `frontend/`. React 18 built with Vite. No router library and no state library are used.

```
frontend/src/
  main.jsx                  entry point
  App.jsx                   maps page names to page components
  context/AppContext.jsx    login state, current page, nav()
  data/constants.js         sidebar items, option lists, role labels
  utils/
    api.js                  HTTP client for the backend
    useFetch.js             load-data hook (data, loading, error, refetch)
    useObjectUrl.js         image previews
    useRecordOptions.js     filter choices taken from saved records
    useClassPicker.js       grade and section choices from the section tree; locked for teachers
    format.js               dates, N/A checks, error messages
    compare.js              tolerant text comparison
  components/
    layout/Sidebar.jsx      navigation
    layout/Topbar.jsx       page title, menu button on narrow screens, change password, sign out
    layout/ChangePasswordModal.jsx
    ui/index.jsx            Card, Btn, Badge, Pager, EmptyState, ...
    ui/DownloadScanBtn.jsx  download button for the original scan
    ui/ScanPreview.jsx      shows an uploaded scan (image or PDF)
    ui/Chart.jsx            Chart.js charts for Grade Analytics
  assets/                   DepEd seal and logo for the SF10-ES sheet
  pages/
    LoginPage, DashboardPage, UploadPage, RecordsPage, RecordDetailPage,
    SearchPage, AnalyticsPage, HistoryPage, UsersPage, AuditPage,
    SectionsPage, FillFormPage
    upload/                 one component per upload step
    users/                  add form, edit dialog, permission matrix
    sections/               add/edit and delete-confirmation windows
    form137/                the SF10-ES sheet (sheet.jsx) and the print button
  styles/                   global.css, components.css, pages.css
```

### Navigation and state

- `AppContext` holds `loggedIn`, `user`, `activePage` and `navParams`.
- Pages change screen by calling `nav('records')` or `nav('detail', { recordId })`. `App.jsx` looks the page name up in its `PAGES` table.
- The sidebar and the top-bar titles are both generated from `NAV_ITEMS` in `data/constants.js`. An item can list the roles allowed to see it; `App.jsx` applies the same rule to the page itself.
- After a page refresh, `AppContext` asks the server who the stored token belongs to (`GET /auth/me/`) and restores the session, so the user stays signed in.
- The upload wizard (`UploadPage.jsx`) keeps the data gathered so far in one object and passes it to each step.

### Talking to the backend

All requests go through `utils/api.js`, which:

- adds the `Authorization: Token <token>` header from `localStorage`;
- on a `401` response, clears the token and returns to the login screen;
- throws `{ status, data }` for HTTP errors and `{ status: 0, offline: true }` when the server cannot be reached, so pages can show a suitable message;
- downloads files by fetching them as a blob, because a plain link cannot send the token header.

## 4. Main data flow: digitizing a form

```mermaid
sequenceDiagram
    actor Staff
    participant UI as React app
    participant API as Django API
    participant OCR as OCR engine
    participant DB as MongoDB
    participant FS as Scan files

    Staff->>UI: Step 1: enter pupil details, choose image
    UI->>API: POST /ocr/quality/ (image)
    API->>OCR: analyze_image
    API-->>UI: quality metrics and verdict
    Staff->>UI: Step 2: Run OCR
    UI->>API: POST /ocr/upload/ (image + pupil details)
    API->>FS: save file
    API->>OCR: run_ocr
    alt OCR fails
        API->>FS: delete file
        API-->>UI: 422 with a message
    else OCR succeeds
        API->>DB: insert scan (outcome: pending)
        API->>DB: audit UPLOAD
        API-->>UI: scan_id, fields, summary
    end
    Staff->>UI: Steps 3-5: review, confirm each flagged field
    Staff->>UI: Step 6: tick confirmation, Save
    UI->>API: POST /ocr/validate/ (scan_id, details, corrections)
    API->>DB: read scan fields
    API->>API: build grades, average, remarks
    API->>DB: insert record
    API->>DB: mark scan saved
    API->>DB: audit VALIDATE
    API-->>UI: record_id, general_average, remarks
```

Two points in this flow are deliberate design decisions:

- **The scan and the record are separate documents.** The scan keeps what the machine read; the record keeps what a person approved. The record's `corrections` field and the scan's `ocr_fields` together show exactly what was changed by hand.
- **The pupil details on the record come from what the staff member typed, not from OCR.** The details read from the scan are only used to warn when they disagree with what was typed.

The OCR stage itself is described in [OCR_PIPELINE.md](OCR_PIPELINE.md).

## 5. Users and roles

```mermaid
flowchart TB
    OIC[Officer in Charge]
    ADM[Admin Staff]
    TCH[Teacher]

    U1([Upload and validate Form 137])
    U2([View, search and download records])
    U3([View analytics])
    U4([Edit or delete records])
    U5([View audit log])
    U6([Manage user accounts])

    TCH --> U1
    TCH -->|own class only| U2
    TCH -->|own class only| U3
    ADM --> U1
    ADM --> U2
    ADM --> U3
    ADM --> U4
    ADM --> U5
    OIC --> U1
    OIC --> U2
    OIC --> U3
    OIC --> U4
    OIC --> U5
    OIC --> U6
```

Roles are stored on the user model (`OCRISUser.role`). Permissions are enforced by the backend on every request; the exact rule for each endpoint is in [SECURITY.md](SECURITY.md) and [API.md](API.md).

## 6. Configuration

All environment-specific settings are read from `backend/.env` and `frontend/.env`; see [INSTALLATION.md](INSTALLATION.md). Settings fixed in `settings.py` that affect behaviour:

| Setting | Value | Effect |
|---|---|---|
| `TIME_ZONE` | `Asia/Manila` | Django's time zone |
| `TOKEN_TTL_HOURS` | 12 (from `.env`) | Hours a sign-in stays valid |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | 20 MB | Largest accepted upload |
| `OCR_LANG` | `eng` | Tesseract language |
| `OCR_CONFIDENCE_THRESHOLD` | 90 | Auto-approval threshold used by the free-text fallback parser |
| `PAGE_SIZE` (`api/db.py`) | 20 | Rows per page in lists |
| `PASSING_GRADE` (`api/constants.py`) | 75 | Used for remarks, pass rates and intervention flags |
