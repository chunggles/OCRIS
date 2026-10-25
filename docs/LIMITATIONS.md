# Testing, Known Limitations and Recommendations

This document states plainly what has and has not been verified, and what the system does not yet do.

**Last updated:** October 18, 2026 (first written October 4). An earlier version of this document listed 32 limitations. Twenty were fixed and four partly fixed on October 4; the details are in [FIXES_2026-10-04.md](FIXES_2026-10-04.md). The numbers used there refer to that earlier list. Items fixed since are struck through below with the date. The fuller, more recent list of open problems is [WEAKNESSES_2026-10-11.md](WEAKNESSES_2026-10-11.md).

## 1. Testing carried out

### Automated tests

`python manage.py test` runs 119 tests in `backend/api/tests.py`. They need MongoDB running and use a temporary database, so real data is not touched.

| Area | What is tested |
|---|---|
| Grading | The Promoted / Retained / Incomplete rules; blank grades left out of the average; quarters and terms (`grading_period`) |
| Class limits | Teachers see only their own class in lists, record detail, search, analytics, scan history and downloads; a teacher with no class sees nothing |
| Records | Search with special characters; date format; a scan cannot be saved twice; editing recalculates average and remarks; bad edits are refused; deleting a record keeps its scan and image; archived forms stay without grades and are left out of analytics |
| Accounts and sessions | Login; limits on wrong passwords; password rules; temporary passwords; the cookie and request header; several devices; session expiry and the idle limit; only a hash of the session key stored; changing your own password; OIC resetting a password and editing a user; protection of the last OIC |
| Audit trail | Old and new values; the audit file and its hash chain, including a line half-written by a crash; `verify_audit` |
| Uploads and encryption | Size and type checks; encrypted scans and backups, key rotation |
| Maintenance commands | `cleanup_scans`, `recompute_remarks`, `tidy_records`, `backup` (with `--keep`), `restore`, `maintenance`, `create_indexes`; resuming an unsaved upload; the automatic cleanup; the indexes |
| File access | The uploads folder is not reachable without going through the API |
| Cloud set-up | The health check; the address check for `TRUSTED_PROXY_COUNT` (OIC only); `create_oic`; the nightly upkeep's timing and `maintenance_loop`; the built site served with its headers, without hiding the API |

There are no automated tests for the OCR modules or for the frontend.

### Manual testing during development

Recorded in [CHANGELOG.md](../CHANGELOG.md).

| Area | What was tested | Result | Source |
|---|---|---|---|
| Grade table reader | One Form 137-A mockup in 12 variants: 1,080 grade cells | 1,080 found correctly; 788 auto-approved, all correct; 0 wrong values auto-approved; 292 flagged | Changelog §9 |
| Pupil details reader | Same mockup, plus unit cases | All five fields correct on the original image | Changelog §10 |
| Image quality check | The mockup and deliberately degraded copies | Each produced the expected verdict | Changelog §7 |
| OCR failure handling | A fake PDF and a blank page | Both returned a clear error; no file left behind | Changelog §8 |

### What has not been tested

- **Real scanned records.** All OCR accuracy figures come from one mockup layout. No real Form 137 from the school, no elementary Form 137 / SF10 layout, and no handwritten grades have been measured.
- **Some screens, by hand.** The frontend builds and the server side is tested. Several screens have been clicked through in a browser since (see the CHANGELOG), but not all; the ones still to do are item 45 of [WEAKNESSES_2026-10-11.md](WEAKNESSES_2026-10-11.md).
- **User acceptance.** No testing with school staff is recorded.
- **Load and concurrency.** Not tested.

## 2. Known limitations

### OCR and input

| # | Limitation | Effect |
|---|---|---|
| 1 | A JPG or PNG is one page; a PDF is read up to 4 pages, with the pupil's details taken from page 1. | The back page of an SF10-ES has no layout of its own yet, so it is read only if it happens to match the front's table. Skipped pages are reported in a note. |
| 2 | The grade table reader expects the column order Subject, Q1, Q2, Q3, Q4, Final, and a list of known learning areas (longer since the SF10-ES reader, 2026-10-05 to 10-10: GMRC, Makabansa, Reading and Literacy and others). | A row whose learning area matches none is kept as "Unread learning area" for the reviewer to rename. Other column layouts, including a three-term sheet, are misassigned or flagged. |
| 3 | Handwritten grades are mostly flagged for manual entry. | Little time is saved on handwritten forms. |
| 4 | OCR runs inside the web request: about 17 seconds per upload when measured on 4 October, 30 to 70 seconds per form in the 10 October review, after the SF10-ES layout and the second reading of hard scans were added. | The user waits; several simultaneous uploads slow each other (one CPU on the Render plan) and each takes about 300 MB, so each server process reads at most `OCR_MAX_CONCURRENT` (2) at once and the others wait their turn. Render allows requests of up to 100 minutes, so the cloud set-up of 2026-10-18 does not cut them off; a host with a 30-second limit would. |
| 5 | ~~On a multi-year Form 137-A, all year blocks are saved as one record with one general average and one remark.~~ Fixed 2026-10-11: the record is the year of its grade level; the other years are kept under `details.other_years`. | |
| 6 | A pupil's name typed at upload is trusted over the one read from the scan; the other details read from the scan give only a mismatch warning. (Since 2026-10-11 a name left blank is read from the scan.) | A typing mistake is saved if the warning is ignored. It can be corrected afterwards with **Edit record**. |
| 7 | The upload form offers Grade 1 to Grade 6 only. | Secondary year levels cannot be chosen at upload. They can be entered afterwards with **Edit record**. |

### Records and accounts

| # | Limitation | Effect |
|---|---|---|
| 8 | ~~There is no check for an existing record of the same pupil and school year.~~ Fixed 2026-10-11: one record per pupil per school year, and an LRN belongs to one pupil. | |
| 9 | ~~A teacher can upload a form for any grade and section.~~ Fixed 2026-10-05 to 10-10: a teacher's class is locked on the upload form and checked by the server. | |
| 10 | ~~A sign-in lasts a fixed 12 hours from the moment of signing in; there is no idle timeout.~~ Fixed 2026-10-18: a session also ends after 30 minutes without use (`IDLE_TIMEOUT_MINUTES`). | |
| 11 | A username cannot be changed from the interface. | It can be changed through the API, or the Django admin site where it is enabled (development only by default). |
| 12 | ~~Unfinished uploads are removed only when `cleanup_scans` is run.~~ Fixed 2026-10-11: the server removes unsaved uploads older than `PENDING_SCAN_DAYS` (7) by itself, at most once an hour, when someone uploads. | It happens only while people upload; on a server nobody uses it waits, which does no harm. `cleanup_scans` and `maintenance` do it on demand. |
| 13 | Record views are not written to the audit log. | The log shows what was changed and who signed in, failed to sign in, or downloaded a scan, but not every record that was opened. |
| 13a | Security gaps that remain: there is no two-step sign-in; MongoDB itself is not encrypted by OCRIS (records, names and the text read from scans sit in it as plain data, so use MongoDB encryption at rest or an encrypted disk); a scan is decrypted into a temporary folder for the 30 to 70 seconds the OCR reads it; the audit file is appended to by the server and could be altered by someone with access to the server's disk (since 2026-10-18 `verify_audit` shows such a change, unless the database is rewritten to match as well). | Protect the server, the database and the disk; keep the encryption key apart from the backups. |

### Deployment

| # | Limitation | Needed before real use |
|---|---|---|
| 14 | The backend is run with Django's development server. Since 2026-10-18 the cloud set-up runs gunicorn behind Render's HTTPS proxy ([DEPLOYMENT.md](DEPLOYMENT.md)). | On a server at the school, use a production WSGI server behind a web server, with HTTPS. |
| 15 | MongoDB is used without authentication by default. | Enable MongoDB authentication and put the credentials in `MONGO_URI`. MongoDB Atlas, used by the cloud set-up, always requires it. |
| 16 | Backups are still made only when something runs them: OCRIS has no scheduler. Since 2026-10-11 there is `python manage.py restore` and `python manage.py maintenance` (backup, keep the newest 14, tidy), and INSTALLATION.md shows how to schedule it. Since 2026-10-18 the cloud container runs it every night by itself (`maintenance_loop`). | Schedule `maintenance` on the server (not needed in the cloud set-up), copy the backups off that machine (on Render, with `scp`, see DEPLOYMENT.md), and rehearse a restore on a copy. The restore of the accounts file, the encrypted case and the MongoDB data are tested; a full restore on a second machine has not been tried. |
| 17 | The search box cannot use a database index (it looks for text inside names, subjects and scanned text), and the analytics page reads every record that matches its filters. | Fast enough for the thousands of records of one school; a much larger archive would need MongoDB text search and stored totals. |
| 18 | Only the form being worked on can be picked up again after a refresh. The other forms of a batch had not been uploaded yet. | Choose them again. |
| 19 | Printing has not been tried on a real printer. The print layout asks for no browser header or footer and for long bond paper (8.5 x 13 in), but whether a given browser and printer honour that is not confirmed, nor is printing a PDF scan. | Do a test print of a typed form, a scanned image and a scanned PDF before relying on it. |

## 3. Recommendations

In suggested order of priority:

1. **Measure OCR accuracy on real scans.** Collect a sample of the school's actual Form 137 records, including elementary layouts and handwritten grades, and repeat the measurement in changelog §9. This is the main claim of the project and currently rests on one mockup.
2. **Click through every screen** with one account of each role, then run a user acceptance test with school staff.
3. **Add automated tests for the OCR modules**, using a few sample images with known grades.
4. ~~**Decide how a multi-year Form 137-A should be stored.**~~ Done 2026-10-11: one record per school year.
5. **Support the back page of the SF10-ES** (Grades 5 and 6), which the system has no layout for yet. (Since 2026-10-11 a PDF is read up to 4 pages.)
6. ~~**Warn when a record for the same pupil and school year already exists.**~~ Done 2026-10-11: the second one is refused.
7. **Move OCR to a background job** so uploads do not block the web server.
8. ~~**Prepare a production deployment** (items 14 to 16) and schedule `maintenance`.~~ Done for Render 2026-10-18 ([DEPLOYMENT.md](DEPLOYMENT.md)); the Docker image is first built there.
9. ~~**Move to Django 5.2.**~~ Done 2026-10-25: Django 5.2.18, supported until April 2028.
