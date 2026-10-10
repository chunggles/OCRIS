# Testing, Known Limitations and Recommendations

This document states plainly what has and has not been verified, and what the system does not yet do.

**Last updated:** October 4, 2026. An earlier version of this document listed 32 limitations. Twenty were fixed and four partly fixed on that date; the details are in [FIXES_2026-10-04.md](FIXES_2026-10-04.md). The numbers used there refer to that earlier list. This document lists what remains.

## 1. Testing carried out

### Automated tests

`python manage.py test` runs 26 tests in `backend/api/tests.py`. They need MongoDB running and use a temporary database, so real data is not touched.

| Area | What is tested |
|---|---|
| Grading | The Promoted / Retained / Incomplete rules; blank grades left out of the average |
| Class limits | Teachers see only their own class in lists, record detail, search, analytics, scan history and downloads; a teacher with no class sees nothing |
| Records | Search with special characters; date format; a scan cannot be saved twice; editing recalculates average and remarks; bad edits are refused; deleting a record removes its scan and image |
| Accounts | Login; session expiry; changing your own password; OIC resetting a password and editing a user; protection of the last OIC |
| Maintenance commands | `cleanup_scans`, `recompute_remarks`, `backup` |
| File access | The uploads folder is not reachable without going through the API |

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
- **The screens, by hand, after the October 4 fixes.** The frontend builds and the server side is tested, but the changed screens have not been clicked through in a browser.
- **User acceptance.** No testing with school staff is recorded.
- **Load and concurrency.** Not tested.

## 2. Known limitations

### OCR and input

| # | Limitation | Effect |
|---|---|---|
| 1 | One page per upload: a JPG, a PNG, or the first page of a PDF. Multi-page forms are not supported. | A form with grades on two pages needs two uploads and produces two records. The other pages of a PDF are ignored, with a warning at the quality step. |
| 2 | The grade table reader expects the column order Subject, Q1, Q2, Q3, Q4, Final, and a fixed list of nine subjects. | Other subjects are skipped. Other column layouts are misassigned or flagged. |
| 3 | Handwritten grades are mostly flagged for manual entry. | Little time is saved on handwritten forms. |
| 4 | OCR takes about 17 seconds per upload and runs inside the web request. | The user waits; several simultaneous uploads would slow the server. |
| 5 | On a multi-year Form 137-A, all year blocks are saved as one record with one general average and one remark. | The average spans several school years, and the record carries the single grade level and school year typed at upload. |
| 6 | Pupil details read from the scan are used only for a mismatch warning. | The typed details are trusted; a typing mistake is saved if the warning is ignored. It can be corrected afterwards with **Edit record**. |
| 7 | The upload form offers Grade 1 to Grade 6 only. | Secondary year levels cannot be chosen at upload. They can be entered afterwards with **Edit record**. |

### Records and accounts

| # | Limitation | Effect |
|---|---|---|
| 8 | There is no check for an existing record of the same pupil and school year. | Uploading the same paper form twice creates two records. |
| 9 | A teacher can upload a form for any grade and section. | A teacher who types a class other than their own will not see the record afterwards. |
| 10 | The sign-in token is kept in the browser's `localStorage`. | Any script running on the page could read it. Sessions do expire after 12 hours. |
| 11 | A username cannot be changed from the interface. | It can be changed through the API or the Django admin site. |
| 12 | Unfinished uploads are removed only when `cleanup_scans` is run. | Someone has to run it, or schedule it. |
| 13 | Failed logins, sign-outs and record views are not written to the audit log. | The log shows what was changed, not every access. |

### Deployment

| # | Limitation | Needed before real use |
|---|---|---|
| 14 | The backend is run with Django's development server. | Use a production WSGI server behind a web server, with HTTPS. |
| 15 | MongoDB is used without authentication by default. | Enable MongoDB authentication and put the credentials in `MONGO_URI`. |
| 16 | Backups are made only when `python manage.py backup` is run, and restoring is done by hand. | Schedule the backup command and rehearse a restore. |

## 3. Recommendations

In suggested order of priority:

1. **Measure OCR accuracy on real scans.** Collect a sample of the school's actual Form 137 records, including elementary layouts and handwritten grades, and repeat the measurement in changelog §9. This is the main claim of the project and currently rests on one mockup.
2. **Click through every screen** with one account of each role, then run a user acceptance test with school staff.
3. **Add automated tests for the OCR modules**, using a few sample images with known grades.
4. **Decide how a multi-year Form 137-A should be stored.** One record per school year would make averages and remarks meaningful.
5. **Support multi-page forms**, including the back page of the SF10-ES (Grades 5 and 6), which the system has no layout for yet. (PDF files are read since 2026-10-08, first page only.)
6. **Warn when a record for the same pupil and school year already exists.**
7. **Move OCR to a background job** so uploads do not block the web server.
8. **Prepare a production deployment** (items 14 to 16) and schedule `backup` and `cleanup_scans`.
