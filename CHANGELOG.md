# OCRIS v3: Changelog

## 2026-10-01

Four changes: two bug fixes in the OCR → validation flow, a working Record Detail page, and downloads for uploaded Form 137 files.

---

### 1. Validation step showed only 8 of 10 flagged fields

**Symptom:** Step 5 (Validation) of the upload flow said "10 fields flagged", but only 8 could be reviewed. The Save button stayed disabled.

**Cause:** A Form 137-A (secondary) has one grade table per school year, so the same subject appears more than once (`English I`, `English II`, …). The OCR parser named both rows `English Q1`, `English Final`, and so on. Step 5 stored review state in objects keyed by field name and used the name as the React `key`, so the duplicate names collapsed into one entry. The counter still used the full list length (10), while only the unique keys (8) could be confirmed.

**Fix:**

| File | Change |
|---|---|
| `backend/api/ocr/engine.py` | `_parse_grade_lines` adds the grade level from the row label (`I`, `II`, `III`, `IV`, …) to the subject, giving names like `English I Q1` and `English II Q1`. If a row has no level label and its subject repeats, it adds `#2`, `#3`, … |
| `frontend/src/pages/UploadPage.jsx` (`Step5`) | Each flagged field gets a position-based key (`_k`), and all review state (`vals`, `confirmed`, React keys) uses it instead of the field name. Corrections are still sent to the backend with the real field name. |

**Note:** Scans made before this fix keep the old duplicated names. Re-upload the form to get the new names.

---

### 2. Subjects missing from Form 137-A parsing

**Symptom:** Some subject rows on the secondary Form 137-A were skipped completely.

**Cause:** Subjects were found by plain substring matching against a fixed list. `Technology and Livelihood Eduation` (misspelled on the real form) and `MAKABAYAN` matched nothing. Short names like `TLE` and `EsP` could also match inside longer words.

**Fix (`backend/api/ocr/engine.py`):** The `SUBJECTS` list is replaced by `SUBJECT_ALIASES`, a list of word-boundary regexes that each map to a standard subject name. `_match_subject(line)` returns the first one that matches.

| Text on the form | Saved as |
|---|---|
| Filipino | Filipino |
| English | English |
| Math / Mathematics | Mathematics |
| Science | Science |
| Araling Panlipunan / (AP) | Araling Panlipunan |
| Edukasyon sa Pagpapakatao / (EsP) | Edukasyon sa Pagpapakatao |
| Technology and Livelihood Edu\* / TLE / EPP | EPP / TLE |
| MAPEH | MAPEH |
| MAKABAYAN | MAKABAYAN |

**Verified:** On text typed from a two-year Form 137-A (not a real scan), all 60 grade fields were found, every name was unique, and every Final grade matched the form. Header rows and the "Days of School" row were ignored.

---

### 3. Record Detail page showed no data

**Symptom:** Clicking **View** on the Records page opened a page that always said "Select a record from the Records page".

**Cause:** `RecordDetailPage` was a placeholder that never loaded a record, and `nav('detail')` had no way to say which record was clicked.

**Fix:**

| File | Change |
|---|---|
| `frontend/src/context/AppContext.jsx` | `nav(page, params)` now takes an optional second argument, available to pages as `navParams`. Existing `nav('page')` calls work as before. |
| `frontend/src/pages/RecordsPage.jsx` | **View** calls `nav('detail', { recordId })` and is disabled when a record has no ID. |
| `frontend/src/pages/SearchPage.jsx` | **View** used to go back to the Records list. It now opens Record Detail for that record. |
| `frontend/src/pages/RecordDetailPage.jsx` | Rewritten. Loads `GET /api/records/<id>/` and shows the sections listed below. |

The rewritten Record Detail page shows:
- **Pupil information:** name, LRN, grade level, section, school year and class adviser.
- **Summary:** general average, Promoted/Retained, status, uploaded by, created and updated times, and scan ID.
- **Grades table:** Q1–Q4 and Final for each subject. Finals below 75 are highlighted in red.
- **Manual corrections:** the values entered during validation, if there were any.
- **States:** loading, error with Retry, and record not found.

No backend changes were needed, because the `record_detail` endpoint already existed.

---

### 4. Uploaded forms can be downloaded

The original uploaded Form 137 file (image or PDF) can now be downloaded from:
- **Records page:** a **Download** button on each row.
- **Record Detail page:** a **Download original form** button.
- **Scan History page:** a new **File** column.

**Backend:**

| File | Change |
|---|---|
| `backend/api/views.py` | New view `scan_file`. Uploads are now saved as `<8-char random id>_<sanitized name>`. |
| `backend/api/urls.py` | New route `GET /api/ocr/scans/<scan_id>/file/`. |
| `backend/ocris_backend/settings.py` | Added `CORS_EXPOSE_HEADERS = ['Content-Disposition']` so the browser can read the filename the server sends. |

How `scan_file` works:
- It requires login (token auth).
- Teachers can only download scans for their assigned grade and section, the same rule as the Records list.
- It only serves files from inside `MEDIA_ROOT/scans/`, so stored filenames can't point it anywhere else.
- It returns 404 with a clear message if the file no longer exists.
- Each download is written to the audit log as `DOWNLOAD`, with the scan ID, filename and pupil.
- The file is sent as an attachment under its original upload name.

Upload filenames used to be saved as-is, so a second upload called `scan.jpg` overwrote the first. The random prefix stops this.

**Frontend:**

| File | Change |
|---|---|
| `frontend/src/utils/api.js` | New `ocrAPI.downloadFile(scanId)`. The API authenticates with a header token, which a plain `<a href>` can't send, so this fetches the file as a blob with the token and saves it under the server's filename. |
| `frontend/src/components/ui/DownloadScanBtn.jsx` | New reusable button. It shows "Downloading…" while busy and an alert if the download fails. It isn't shown when there's no `scanId`. |
| `RecordsPage.jsx`, `RecordDetailPage.jsx`, `HistoryPage.jsx` | Download button added. |

**Older uploads:** Files uploaded before this change may already have been overwritten by a later upload with the same name. The download for such a scan returns the newer file, and the original can't be recovered.

---

### 5. Section is now typed in; login is no longer prefilled

| File | Change |
|---|---|
| `frontend/src/pages/UploadPage.jsx` | The **Section** dropdown in Step 1 is now a text box (placeholder "e.g. Sampaguita"). The value is trimmed, and an empty or spaces-only section is rejected. The unused `SECTIONS` import was removed. |
| `frontend/src/pages/LoginPage.jsx` | Removed the hardcoded demo login (`k.saquing`). Both fields start empty, with `autoComplete` set to discourage browser autofill. |

---

### 6. Codebase refactor

The code was reorganised so each file has one job. API URLs, request and response formats, and the screens are unchanged, apart from the small fixes listed under "Bugs fixed during the refactor". A copy of the code from before the refactor is in `Documents/OCRIS_v3_backup_before_refactor/`.

**Backend layout**

```
backend/api/
  constants.py        N/A handling, passing grade (75), Promoted/Retained
  db.py               MongoDB access (shared pagination helper, get_scan, mark_scan_saved)
  models.py           OCRISUser + role constants + class_scope() for teacher filtering
  views/              one module per area: auth, records, ocr, analytics, users, audit
  services/
    grading.py        build_grades, compute_general_average, is_promoted, remarks_for
    storage.py        save_upload, find_scan_file
  ocr/
    engine.py         run_ocr, compute_confidence_summary (entry points)
    preprocess.py     image clean-up and quality check
    parser.py         subject aliases, grade-line and pupil-info parsing
    mock.py           sample extraction used when Tesseract is unavailable
  utils/http.py       query_param, page_param, not_found, detail
```

Other backend changes:
- Bare `except:` blocks now catch specific exceptions.
- An invalid `?page=` value falls back to page 1 instead of causing a server error.
- New optional setting `TESSERACT_CMD` (read from `.env`) for Windows installs where `tesseract.exe` isn't on PATH.
- `DEBUG` is now read from `.env`. It defaults to `True`, as before.

**Frontend layout**

```
frontend/src/
  utils/api.js            HTTP client; one place for auth headers, 401 handling, offline errors
  utils/useFetch.js       simplified to useFetch(fn)
  utils/useObjectUrl.js   image previews that release their memory
  utils/format.js         dates, N/A checks, plural(), errorMessage()
  components/ui/index.jsx adds PageHeader, Pager, EmptyState, SearchInput, Notice, RemarksBadge
  pages/upload/           one file per wizard step (UploadPage.jsx is now only the wizard frame)
  pages/users/            AddUserForm, EditUserModal, PermissionMatrix, RoleSelect
```

Other frontend changes:
- Repeated code now lives in one place:
  - the pager, which had three copies;
  - empty states and error boxes;
  - the remarks badge;
  - date formatting;
  - the role and section lists.
- Styles that were written inline over and over are now CSS classes. Unused CSS and the unused `Tabs` component were removed.
- Top-bar page titles now come from the sidebar's `NAV_ITEMS`, so the two can't drift apart.

**Bugs fixed during the refactor**

| Where | Bug | Fix |
|---|---|---|
| Validation step | The confirmed badge showed the literal text `&#10003; Confirmed`. | Shows ✓ Confirmed. |
| Search | Typing a character like `(` or `[` crashed the results table, because the search term was used as a regex without escaping. | The term is escaped first. |
| Upload success screen | Remarks always showed a green "Promoted" badge, even for Retained pupils. | Shows the real remarks. |
| Confirm step | The "OCR read" value looked up the field by name, so with repeated names it could show the wrong one. | The raw value is carried with each correction. |
| Processing step | The log showed fixed fake lines (e.g. "English Q1: 61% — FLAGGED") whatever the scan contained. | The log is built from the actual result. |
| Sign out | The server token was never deleted. | Sign out now calls `/auth/logout/`. |
| Dashboard | **View** on a recent upload opened the Records list. | It opens that record's detail page. |
| Upload step | An offline "mock scan" fallback could never run: network errors weren't marked as offline. | Removed. Offline now shows a "start the backend" message. |

---

### 7. Real image-quality check; unnecessary text and UI removed

**Image quality (Upload step 2)**

Step 2 used to show fixed, made-up numbers ("310 DPI", "2.3° skew") for every file. It now sends the image to a new endpoint, `POST /api/ocr/quality/`, which analyses the actual pixels and saves nothing. The code is in `backend/api/ocr/quality.py`.

| Check | How it's measured | Good / Acceptable / Poor |
|---|---|---|
| Resolution | DPI from the file's metadata, or estimated from width ÷ 8.5" (long bond paper) | ≥ 250 / ≥ 150 / below |
| Contrast | Spread between the darkest and lightest 5% of pixels | ≥ 150 / ≥ 100 / below |
| Brightness | Average grey level | 150–245 / slightly dark or washed out / < 110 |
| Sharpness | Variance of a Laplacian edge filter on a 1000px-wide copy | ≥ 1000 / ≥ 300 / below |
| Page tilt | Rotation (±5°) giving the sharpest text-row profile | ≤ 1° / ≤ 5° / over 5° or no text |
| Ink coverage | Share of pixels darker than the ink/paper midpoint | normal / > 25% / blank or > 40% (shadows) |

How the result is used:
- The overall verdict is the worst single check.
- When the verdict is **Poor**, the main button becomes "Choose another scan", with "Run OCR anyway" still available.
- PDFs show a note that the check only works for images.

Calibration: thresholds were tuned on the Form 137-A mockup and on copies made deliberately worse (blurred, tilted, darkened, low contrast, half in shadow, low resolution, blank). Every case produced the expected verdict.

OCR preprocessing (`ocr/preprocess.py`) also changed:
- **Tilted pages are now straightened before OCR**, using the same tilt measurement, so the "corrected automatically" note is accurate. A page tilted 3° comes out level.
- **Scans without DPI metadata are no longer treated as 72 DPI.** They used to be enlarged about 4× before OCR, which made it very slow. They now use the page-width estimate.

**Removed**

- **Buttons that did nothing:** Export (Scan History), Export log (Audit Log), the OIC / Teacher tabs on the login screen, and the "Export data" row of the permission matrix.
- **Made-up data:**
  - the "Grade levels active: 6" stat;
  - the Dashboard "System status" card;
  - the Mathematics quarterly trend chart (`MATH_TREND`);
  - the fake 65% progress bar while OCR runs.
- **Duplicates:**
  - Dashboard "Quick actions", which repeated the sidebar;
  - the Filter and Apply buttons on Records and Analytics, where filters already apply as you change them;
  - the second "Proceed to validation" button;
  - the processing-log console in Upload step 3;
  - the "Status: validated" row on Record Detail;
  - the search tip and the elapsed-time display.
- **Developer wording in the UI:**
  - "from MongoDB", "Tesseract-OCR" and MongoDB Compass instructions;
  - "Start the Django backend" and "Run seed.py" messages;
  - long footnotes.
  - Connection errors now say "Can't reach the server."
- **Placeholder pages:** Performance Trends ("Coming in Sprint 3") and Batch Queue are no longer in the sidebar or the app. Their files remain; see Open items.

---

### 8. OCR failures show an error instead of sample data

**Problem:** When OCR failed, `run_ocr` silently returned built-in sample data (pupil "SANTOS, MARIA JOY L.", 40 made-up grades). Users went on to review and save a fake record. This happened for:
- every PDF upload;
- every unreadable image;
- any server without Tesseract installed.

**Fix:**

| File | Change |
|---|---|
| `backend/api/ocr/engine.py` | New `OCRError` exception. `run_ocr` raises it with a plain-language message instead of returning sample data. A scan with no grade rows found is also treated as a failure. |
| `backend/api/views/ocr.py` | `POST /api/ocr/upload/` returns **422** with the message. No scan record is created and the uploaded file is removed (`storage.discard`). |
| `frontend/src/pages/upload/StepPupilInfo.jsx` | PDFs are no longer accepted, since the OCR engine can't read them. The error message suggests exporting the PDF as an image. |
| `StepQuality.jsx`, `StepValidation.jsx`, `components.css` | Removed the PDF-only branches. |

`run_ocr` raises `OCRError` in these cases:

| Situation | Message shown to the user |
|---|---|
| File isn't an image (e.g. PDF) | "This file couldn't be read as an image. Upload the scan as a JPG or PNG." |
| Tesseract missing | "The OCR engine (Tesseract) was not found on the server. Set TESSERACT_CMD in the backend .env." |
| No grade rows found (blank, wrong page, cropped table) | "No grade rows were found on this scan. Check that the whole grade table is visible and try rescanning." |
| Any other OCR crash (details logged on the server) | "OCR failed on this scan. Try rescanning it." |

**Verified:** Uploading a fake PDF and a blank page through the API each returned 422 with the right message, and no files were left in `media/scans/`. OCR on the real mockup ran with Tesseract 5.5 (about 7 s) and returned real fields.

---

### 9. Grades are read cell by cell from the table grid

**Problem:** On the Form 137-A mockup, Tesseract read the page as free text:
- grid lines became junk characters;
- digits were misread ("87" → "@7");
- only 1 of 90 grades was auto-approved, and every Final grade came back blank.

**Fix:** a new module, `backend/api/ocr/table.py`, reads the grade table by its structure.

1. **Find the grid.** Horizontal lines are rows where at least 45% of the page width is darker than the paper. Vertical lines must cover at least 90% of the full height between two horizontal lines. Letters leave a gap above and below, so they don't qualify.
2. **Reject fake lines.** A vertical line only counts if at least 2 other rows within 3 rows either side have one at the same position. Tall glyphs such as "(" in "(AP)" otherwise split cells.
3. **Find subject rows.** Only the first cell of each row is read. It's matched against the subject patterns, with fuzzy matching for misreads ("Filipina" → Filipino). The year level ("I", "II", also read as "|" or "Il") is taken by majority vote per block.
4. **One layout per year block.** All rows in a block share one column layout, decided by majority vote. A line that is faint in one row can't shift that row's cells into the wrong column.
5. **Repair merged rows.** Any row more than 1.6× the usual height is split at its strongest line. This happens on low-resolution scans where a horizontal line fades to grey.
6. **Read each grade cell four times.** Each cell is cropped inside its borders and read digits-only at heights of 48, 40, 56 and 32px. It is **auto-approved only if all of these hold:**
   - at least 3 readings give the same grade;
   - that grade is between 60 and 100;
   - no reading gives a different valid grade;
   - the readings' mean confidence is at least 50.

   Everything else is flagged:
   - conflicting readings show "88 / 83";
   - an unreadable cell shows "?";
   - a cell with no ink at all is treated as blank (N/A).

If no ruled table is found, the previous free-text parser is used instead.

**Other changes**

| File | Change |
|---|---|
| `ocr/preprocess.py` | `load_page()` straightens the page once; both readers use the result. |
| `ocr/parser.py` | New `match_subject_span()`. Pupil-info fields that aren't found are no longer flagged. The record uses the details from the upload form, so reviewing them changed nothing; on a Form 137-A this was 5 pointless review items per upload. |
| `ocr/engine.py` | Uses the table reader, falling back to free text. |
| `frontend/.../StepExtraction.jsx` | Badges are coloured by approved/flagged status instead of a raw "≥ 90%" confidence. A flagged cell with no reading says "Unreadable" instead of "Blank". |
| `frontend/.../StepValidation.jsx` | Review cards with no reading say "Unreadable" instead of "0% conf". |

**Results**

The mockup was tested in 12 variants: original, enlarged, tilted ±, blurred, JPEG at quality 60/40/25, shrunk to 1000/900/800px, and noisy. That is 1,080 grade cells in total.

| | Before | After |
|---|---|---|
| Grades found with the correct subject and year | partial | **1,080 / 1,080** |
| Correct grades auto-approved | 1 / 90 (original image) | **788** (76 / 90 on the original) |
| **Wrong grades auto-approved** | — | **0** |
| Flagged for a person to check | — | 292 (more on poor scans: 62 / 90 at 800px) |
| Time per upload | ~7 s | ~17 s |

Also verified:
- a page with no grid still reads through the text fallback;
- blank pages and PDFs still return clear errors.

Limit: these numbers come from one form layout. Other layouts, or handwritten grades, will mostly be flagged rather than misread, because approval requires agreement. Accuracy should be re-checked on real scans.

---

### 10. Name, grade level, section and school year are read from Form 137-A

**Problem:** The pupil-detail patterns only matched an elementary layout (`Name: …`, `S.Y. 2024-2025`). On the Form 137-A mockup:
- the name, grade level and school year were never found;
- only the second of the two sections was found.

**Fix:** a new module, `backend/api/ocr/pupil.py`, replaces the old patterns in `parser.py`.

| Field | How it's read |
|---|---|
| Name | On a Form 137-A, from the line above the `(Surname)` and `(Given Name)` labels. Each word goes with the label it sits above, so multi-word surnames like "DELA CRUZ" work, and reading stops at "Date of Birth". Otherwise from `Name: …`. Output is `SURNAME, GIVEN NAMES`. |
| School year | Every `School Year …` or `S.Y. …` on the page, including underlined blanks like `20_09__ - 20_10_`. Common misreads are fixed (O/Q/D → 0, I/l/\| → 1). The start year decides the value. A readable end year must equal start + 1, or the match is rejected as a misread. An unreadable end such as `20 _II` is allowed. Years must fall between 1950 and next year. |
| Grade level | `Grade N` if printed. Otherwise the year levels read in the grade table, e.g. `Year I, Year II`. Levels only inferred from block order are not reported. |
| Section | Every `Section …` on the page (`BONIFACIO, MALIGAYA`). |
| LRN | `LRN: ` followed by 10–12 digits, as before. |

Confidence is now the mean Tesseract confidence of the words each value came from, replacing the fixed made-up 92%. The table reader returns year levels along with the confidence of the subject cells they were read from (`SubjectRow` in `table.py`).

**Comparison with the entered details** (`StepExtraction.jsx`, `utils/compare.js`): the saved record still uses the details typed in step 1. Upload step 4 now shows a warning when the scan disagrees with them:
- **Name and section:** compared tolerantly, ignoring spacing and punctuation, with ≥ 85% / ≥ 80% similarity. OCR slips like "ELLENJOY" or "BONIFAGIO" don't trigger it, but "Pulido" vs "Pulonan" does.
- **School year:** the entered year must be one of those on the scan.
- **Grade level:** compared only when the scan shows "Grade N".

Going back to step 1 now keeps the entered details and the chosen file; it used to reset the form.

**Results**

On the original mockup, all five fields are correct:
- Name: `PULONAN, ELLEN JOY A.`
- Grade level: `Year I, Year II`
- Section: `BONIFACIO, MALIGAYA`
- School year: `2009-2010, 2010-2011`
- LRN: none on this form.

Degraded copies sometimes misread letters, e.g. "ELLENJOY" (rotated, JPEG, 800–1000px) and "BONIFAGIO" (blurred, 1000px).

Unit cases also passed:
- an elementary layout (name, LRN, `Grade 6`, `S.Y. 2024-2025`);
- a two-digit end year;
- a contradictory year range, rejected;
- garbage, rejected.

The grade results are unchanged: 788 correct auto-approvals and 0 wrong across the 1,080-cell test set.

---

### 11. "Incomplete" remarks for records that can't be decided

**Problem:** Two kinds of record were labelled **Retained** even though the pupil may have passed:
- a record with a non-numeric Final grade (e.g. `?` from an unreadable cell);
- a record with no Final grades at all.

**Fix:** `remarks_for` in `backend/api/services/grading.py` now decides in this order.

| Order | Condition | Remarks |
|---|---|---|
| 1 | Any numeric Final is below 75 | **Retained**. This is decided even if other Finals are unreadable. |
| 2 | No numeric Finals, or any Final that isn't a number | **Incomplete** (new) |
| 3 | Average ≥ 75 and every Final ≥ 75 | **Promoted** |
| 4 | Otherwise | **Retained** |

Blank (N/A) Finals are still skipped, as in the general average.

| File | Change |
|---|---|
| `backend/api/constants.py` | New `INCOMPLETE = 'Incomplete'`. |
| `frontend/src/components/ui/index.jsx` | `RemarksBadge` shows Incomplete in blue. Promoted is green, Retained amber, and Pending grey for records with no remarks stored. |

**Verified:** nine cases (all pass, one fails, average below 75, unreadable Final, unreadable + failing, blank Final skipped, no Finals, no grades, decimal Finals) all give the expected remarks.

**Existing records** keep the remarks they were saved with. Records wrongly saved as Retained before this change are not updated automatically.

---

### 12. Delete users in User Management

User accounts can now be permanently deleted from User Management. Each row has a **Delete** button, which asks for confirmation first.

**Backend:** `DELETE /api/users/<id>/` (`_delete_user` in `backend/api/views/users.py`).

| Rule | Behaviour |
|---|---|
| Who can delete | OIC only, the same as other user management (Admin gets 403) |
| Your own account | Refused (400): "You can't delete your own account." |
| The last active OIC | Refused (400), so the system always has someone who can manage users |
| What is removed | The Django account, its login token, and its entry in the MongoDB `users` mirror (`db.delete_user_in_mongo`) |
| What is kept | Records, scans and audit entries, which store the username as text |
| Audit | Logged as `DELETE_USER` with the deleted username and role |

**Frontend:**

| File | Change |
|---|---|
| `UsersPage.jsx` | Delete button on every row except your own. The confirmation explains that the action is permanent, that records are kept, and that Deactivate only blocks login. Server refusals are shown as messages. |
| `utils/api.js` | New `usersAPI.delete(id)`. |
| `AuditPage.jsx`, `data/constants.js` | `DELETE_USER` entries are described ("Deleted user: …") and shown with a red badge. |

**Verified** inside a rolled-back database transaction, with the MongoDB writes stubbed out:
- an OIC deleting a teacher → 204, and the account and token are gone;
- deleting yourself → 400;
- deleting a missing user → 404;
- an Admin trying to delete → 403;
- deleting the only active OIC → 400.

---

## Open items

1. **Media folder open without login.** `backend/ocris_backend/urls.py` still adds `static(settings.MEDIA_URL, ...)`. While `DEBUG=True`, anyone who knows a filename can fetch `/media/scans/<file>` without logging in. Downloads now go through the protected endpoint, so this line can be removed.
2. **Misread level labels.** If Tesseract misreads a level label (for example `l` instead of `I`), the second year block gets names like `English #2` instead of `English II`. The review screen still lists every flagged field.
3. **Record Detail has no teacher limit.** `GET /api/records/<id>/` does not apply the teacher grade/section limit that the list and download endpoints use.
4. **Not tested end to end.** The parser was tested on typed text from the mockup, the frontend builds (`vite build`), and `manage.py check` passes. None of these changes has been tried in the running app with a real upload.
5. **Records section filter is still a fixed list.** The section filter on the Records page still uses the fixed `SECTIONS` list, so a typed-in section that isn't on that list can't be filtered. It has to match exactly, including capitalisation.
6. **Leftover files to delete by hand.** These were not deleted automatically:
   - `backend/api/views.py`: replaced by the `views/` package, which Python loads instead, so the old file is no longer used.
   - An empty folder named `backend/api/{migrations,ocr,utils}`.
7. **Teacher with no class assigned sees all records.** Empty filters are dropped before querying MongoDB, so a teacher with no assigned grade/section gets no filter at all. This behaviour existed before the refactor and was kept on purpose.
8. **More leftover files to delete:** `frontend/src/pages/TrendsPage.jsx` and `frontend/src/pages/BatchPage.jsx` are no longer used.
9. **`backend/api/ocr/mock.py` is no longer used** (see section 8) and can be deleted.
10. **OCR accuracy is only measured on one form.** The table reader (section 9) was tuned and tested on the Form 137-A mockup alone. Collect a few real scans, especially elementary Form 137 / SF10 and handwritten grades, and re-run the measurement before relying on the auto-approval rate.

## Deploying

- Restart the Django backend, unless `runserver` has already reloaded it.
- Re-upload any forms that need the new field names.
