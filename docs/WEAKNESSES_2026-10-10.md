# OCRIS v3: Weaknesses and bugs (2026-10-10)

This is a list of weaknesses and bugs found by comparing the system with the capstone proposal, "OCRIS (Optical Character Recognition Information System) – School Record Management Decision Support System Using OCR for Bayombong Central School". It is based on reading the code and on the OCR tests run between October 5 and 10.

Tick the box when an item is done. Sections A, B, D and E are fixed in code, apart from the deployment items 1 to 4, the paper correction 12 and the print test 44. Section C is partly fixed (items 25, 28, 29).

**Fix first:** items 1 to 4. They decide whether the system matches the paper's title (a cloud-based system). Item 14, on whether the analytics can be trusted, is fixed.

---

## A. The paper says it, the system doesn't do it

> **Status, 2026-10-10.** Items 5 to 11 and 13 are done in code; see the notes below. Items 1 to 4 are left for deployment, which the team has put off until the whole system is finished. Item 12 is a correction to the paper, not to the system.
>
> - **5 to 7:** Grade Analytics now uses Chart.js: bar charts for class mean and pass rate by subject, a line chart of the mean grade per quarter, and a table of every subject per grading period with its failing count.
> - **8:** Search also covers subjects, school year and the text read from the scanned form, has grade, section and school-year filters, and says when more records match than the 50 shown. Only scans uploaded from now on have their text stored.
> - **9:** A grade is auto-approved only when repeated readings agree **and** their confidence is above 90%. This sends more grades to manual review than before: on the Form 137-A sample, 22 of 90 are auto-approved where 76 were, and on the filled-in SF10 PDF, 105 of 130 where all 130 were. No wrong grade was auto-approved under either rule. The level is `OCR_CONFIDENCE_THRESHOLD` in `backend/.env`.
> - **10:** A record that cannot be decided shows "Incomplete / For Verification", blank grades are labelled "For verification" at upload, and Record Detail counts a record's missing grades.
> - **11:** Screens narrower than 900 px get a slide-in menu and single-column layout. Checked at phone width on the analytics page only.
> - **13:** HTTPS is required whenever `DEBUG` is off: plain HTTP is redirected and cookies are HTTPS-only.
> - **12:** Tesseract 5.5 is installed. Version 4.0 is no longer the current release and uses the same recognition engine; the paper should say 5.x.

- [ ] **1. Not deployable to the cloud as-is.** There is no Render/Railway configuration, Dockerfile or production server setup. The system runs only with the local development server.
- [ ] **2. Accounts would be lost on a cloud host.** User accounts and logins are kept in a local SQLite file (`backend/db.sqlite3`), not in MongoDB as the paper states. Hosts like Render wipe local files on each deploy.
- [ ] **3. Scanned files are on local disk, not cloud storage.** Uploads go to `backend/media/scans/`. The same wipe would delete every uploaded Form 137.
- [ ] **4. OCR would time out in the cloud.** Reading one form takes 30 to 70 seconds inside a single web request. Cloud hosts typically cut requests at about 30 seconds, and there is no background job.
- [x] **5. No Chart.js.** The paper names it for bar and line charts. It is not installed; the dashboard uses plain coloured bars.
- [x] **6. No analytics per grading period.** The paper promises class means per quarter and trends across grading periods. Only final grades are analysed, and there is no trend view.
- [x] **7. No subject pass rates or "subjects with the most failing grades".** Pass rate is shown per grade level only, based on the general average.
- [x] **8. Search is narrower than described.** It covers name, LRN, section and grade level. There is no subject search, no school-year filter, and no search of the scanned text. Results stop at 50 without saying so.
- [x] **9. Auto-approval is not the ">90% confidence" rule.** A grade is approved when repeated readings of its cell agree, with a confidence floor of 50.
- [x] **10. Missing grades are not labelled "Incomplete/For Verification".** They are stored as N/A. "Incomplete" exists only as a remark on the whole record.
- [x] **11. Not usable on mobile.** The paper says desktop and mobile devices; the layout has no small-screen rules.
- [ ] **12. Tesseract version differs.** The paper says v4.0; version 5.5 is installed.
- [x] **13. HTTPS is not enforced** anywhere in the settings.

## B. Data correctness bugs

> **Status, 2026-10-10.** Items 14 to 22 are done in code; see the notes below. Records saved before this change are repaired by running `python manage.py tidy_records` (add `--dry-run` to preview); it needs to be run once on the real database.
>
> - **14 and 15:** A form that holds several school years (the SF10-ES, or a Form 137-A with year levels I to VI) is saved as **one record for one year**: the block that matches the grade level chosen at upload, or the last block when none matches. The subject names carry no year suffix any more, and the average, remarks and analytics use that year only. The other years are kept under the record's `details.other_years` and shown on Record Detail as "Also on this form". A typed form already worked this way (its record is the last block with grades, the sheet is kept under `details.blocks`), so the two now follow one rule. The school year of an earlier block is not read from the form, so those blocks are labelled by grade ("Grade 5"), not by year.
> - **16:** A pupil may have one record per school year. Saving or editing a record that has the same LRN, or the same name and grade level (when the LRNs do not differ), in the same school year is refused with `409` and names the existing record. The scan stays unsaved so it can be corrected.
> - **17:** An LRN must be 12 digits (spaces and dashes are removed). It is optional. An LRN that already belongs to a pupil with another surname is refused. Checked at upload, validation, typed-in forms and edits; an edit that leaves the LRN unchanged is not re-checked, so old records can still be edited.
> - **18:** The validation step has a "Learning area names" card for rows the OCR could not name ("Unread learning area Grade 2") or read twice ("English #2"), and Record Detail's edit mode lets staff rename any subject.
> - **19:** Subject names are tidied when saved: "EPP", "TLE" and "EPP / TLE" are one subject, "GMRC (Good Manners ...)" is "GMRC". Two names that become one are merged.
> - **20:** Renaming or moving a section also changes its records and its teachers. A section that teachers are assigned to cannot be deleted. The Sections page shows how many records and teachers use each section, and the edit and delete windows say what will be affected. Records of a deleted section keep its name as plain text.
> - **21:** Every edit and every correction made during validation must be a number from 0 to 100, or blank. A grade that was not changed is not re-checked.
> - **22:** The name boxes on the upload step are optional. When left blank, the name (and LRN) read from the form fill the boxes on the last step, where they can be corrected.

- [x] **14. Scanned SF10 records distort the analytics.** All four year blocks go into one record as "Filipino Grade 1", "Filipino Grade 2" and so on. Subject means split into many names, and the record's general average and pass/fail remark span four school years.
- [x] **15. Typed and scanned SF10 forms are stored differently.** A typed form keeps only its last block as the record's grades; a scanned one keeps all blocks.
- [x] **16. Duplicate records are allowed.** The same pupil, LRN and school year can be saved any number of times.
- [x] **17. The LRN is not validated** for length, digits or uniqueness.
- [x] **18. Subject names cannot be corrected.** A row saved as "Unread learning area" or "English I #2" cannot be renamed during validation or afterwards.
- [x] **19. Subject names are inconsistent.** A typed form saves "EPP"; a scan saves "EPP / TLE". They are counted as different subjects.
- [x] **20. Sections are matched as text.** Renaming or deleting a section on the Sections page silently orphans its records and its teacher.
- [x] **21. Staff edits of scanned records accept any text as a grade.** The 0 to 100 check applies to typed-in forms only.
- [x] **22. The pupil's name must be retyped at upload** even though the OCR reads it from the form.

## C. OCR weaknesses

> **Status, 2026-10-11.** Items 25, 28 and 29 are changed in code. Items 23, 24, 26 and 27 are left open: they are limits of accuracy or of the layouts supported, and cannot be settled without real scans and a new layout.
>
> - **25:** Up to 4 pages of a PDF are read. The pupil's details and the page text come from page 1; the grade tables of the later pages are added. A page with no grade table, or one that repeats learning areas already read, is skipped, and a note on the Extracted Fields step says so. A page past the fourth is not read, with a note. Each extra page adds 20 to 30 seconds. Tested with a three-page PDF (form, blank page, same form again) and with unit tests; not tried on a real SF10 back page, which has no layout of its own (item 24).
> - **28:** The row just above a block's first recognised learning area is now kept as "Unread learning area" when its name is unreadable, unless it reads like the table heading ("Learning Areas"). Rows further up are still left out, because the heading's "1 2 3 4" would pass as grades. Not exercised by any of the sample scans; the sample results did not change.
> - **29:** Year blocks are named after their "Classified as Grade" more often. Blocks that could not be read are filled in from the others when the grades read agree, and one misread number (a 2 read for a 3) is corrected when most of the other blocks agree. Each correction is shown as a note. The risk: a pupil who repeated a grade (Grade 3, 3, 4, 5) would have the first block filed as Grade 2, with a note. Before this change such a form fell back to "Block 1" to "Block 4".
> - **Check on the sample scans:** the five sample files (Form 137-A mockup, secondary form, handwritten form, a typed SF10 PDF and an exported SF10 PDF) were read before and after the changes; the 95 fields of each are identical.

- [ ] **23. Handwriting reads poorly.** On the handwriting-style test, 80 of 130 grades were auto-approved and 50 needed manual review. The school's archive is mostly handwritten.
- [ ] **24. Only two layouts are supported:** Form 137-A and the front page of the SF10-ES (Revised 2025). Older formats and the SF10 back page (Grades 5 and 6) are not.
- [x] **25. Only page 1 of a PDF is read.** The other pages are ignored, with a warning.
- [ ] **26. All accuracy figures come from generated test copies,** not from real paper that has been through a pen and a scanner.
- [ ] **27. A faded, grainy scan still needed 28 of 130 grades checked by hand.**
- [x] **28. A row at the very top of a block can still be dropped** when its learning-area name is unreadable. Rows lower in the block are kept as "Unread learning area".
- [x] **29. Block labels fall back to "Block 1" to "Block 4"** when a "Classified as Grade" number is misread.

## D. Security and privacy

> **Status, 2026-10-11.** Items 30 to 38 are done in code and covered by 22 new automated tests (85 tests in all). Details are in [SECURITY.md](SECURITY.md). Things to do once on the real system: run `python manage.py migrate`; add `DATA_ENCRYPTION_KEY` to `backend/.env` (and keep a copy of it elsewhere), then run `python manage.py encrypt_scans`. Everyone is signed out by the upgrade and signs in again.
>
> - **30:** After 5 wrong passwords for one username (20 from one address) within 15 minutes, sign-in is refused with `429` and a wait time, even with the right password; it frees itself. Unknown usernames count too, so the answer does not reveal which accounts exist. Failures and lockouts are in the audit log. The counts are kept in the database, so they survive restarts.
> - **31:** A password needs 10 characters or more, letters and numbers, and must not be common, all digits, or like the username or name. The OIC's passwords (new account or reset) are temporary: the user must change theirs before anything else will work, enforced by the server for every endpoint, and by a window that cannot be closed in the app. The OIC setting their own password is not temporary.
> - **32:** The sign-in is an HttpOnly cookie that scripts cannot read; nothing is kept in `localStorage`. Because a cookie is sent by the browser on its own, every request that changes data (and login) must carry an `X-OCRIS-Request` header, which another website cannot add, and CORS allows only the listed origin. Cookies are `Secure` when HTTPS is required, and `SameSite=None` then, so a site and a server on different domains (the cloud case) still work.
> - **33:** Each sign-in is its own session. Signing out ends that device only; `POST /auth/logout-all/` ends all (no button for it in the app yet). Changing your password ends the other devices; an OIC reset ends all of that user's.
> - **34:** Scans are encrypted before they are written to disk and backups are encrypted as a whole, using `DATA_ENCRYPTION_KEY` (keys can be rotated). The server will not start without a key when `DEBUG` is off. The OCR reads a scan from a temporary decrypted copy that is removed straight after. **Not covered:** MongoDB itself holds names, grades and scanned text as ordinary data; use MongoDB or disk encryption for that. **Lose the key and the files cannot be read.**
> - **35:** `EDIT` entries keep the old and new value of every changed field and grade; `VALIDATE` keeps what the OCR read and what a person entered instead; `EDIT_USER` keeps old and new values (never passwords); `DELETE` keeps a snapshot of the record. Failed logins, lockouts, sign-outs and reset requests are logged too. Every entry is also appended to `backend/logs/audit.jsonl` before it goes into MongoDB, so the trail survives a wiped database. The file itself is plain text on the server's disk.
> - **36:** Deleting a record keeps its scan (marked "record deleted", still downloadable and in Scan History); the audit entry holds a snapshot of the record. To remove old personal data deliberately, run `python manage.py cleanup_scans --deleted-days N`. This changes the earlier behaviour, in which delete removed the scan too.
> - **37:** The server refuses a file over `MAX_UPLOAD_MB` (20) from the declared request size before reading the body (`413`), and checks every file on both the quality check and the upload: it must be a JPG, PNG or PDF by its first bytes, its name must agree, an image must open and be at most 120 megapixels (`400`, `413`, `415`). Refused files are never stored.
> - **38:** **Forgot your password?** on the login screen asks the OIC for a reset. OCRIS has no email, so the request shows as "Password reset asked" beside the account on User Management, and the OIC sets a new temporary password (which clears it). The answer is the same whether or not the account exists, and requests are limited to 5 per address per 15 minutes. If the OIC forgets their own password, the person who maintains the server runs `python manage.py changepassword <username>`. Emailing a link is not possible until the system has a mail service.

- [x] **30. No limit on login attempts.** A password can be guessed indefinitely.
- [x] **31. Weak password rule.** Eight characters is the only requirement, and a temporary password does not have to be changed at first sign-in.
- [x] **32. The login token is kept in browser storage,** where a malicious script could read it.
- [x] **33. One token per user.** Signing out on one device signs the user out on all devices.
- [x] **34. Scans and backups are unencrypted.**
- [x] **35. The audit log is thin.** It records which fields changed but not the old and new values, and it is erased if the database is wiped.
- [x] **36. Deleting a record permanently deletes its scan.** The paper says original scanned documents are preserved as an audit trail.
- [x] **37. No server-side limit on upload size or file type.**
- [x] **38. No forgotten-password route** other than asking the OIC.

**What D leaves open** (not on the list above, found while fixing it): no two-step sign-in; MongoDB itself is not encrypted by OCRIS; the audit file can be altered by someone with access to the server's disk; no idle timeout (a session lasts 12 hours); no button for "sign out of every device"; the new screens (forced password change, forgot password, reset badge, the Audit Log's old and new values) were built and compile, and the API behind them is tested, but they were not clicked through in a browser (see item 45).

## E. Reliability and maintenance

> **Status, 2026-10-11.** Items 39 to 43 are done in code and covered by 11 new automated tests (96 in all). Item 44 is left open: it needs a printer. Things to do once on the real system: schedule `python manage.py maintenance` (see [INSTALLATION.md](INSTALLATION.md#scheduled-backups)); nothing else, the indexes are created by the server the first time it connects.
>
> - **39:** New `restore` command: `python manage.py restore <backup>` lists what a backup holds, and with `--yes` replaces the accounts, records, scans, audit log and sections with it (a `.zip.enc` needs the same key). It first backs up the current data into `backups/before-restore/`. `backup --keep N` deletes all but the newest N backups, and the new `maintenance` command does backup + keep (`BACKUP_KEEP`, 14) + cleanup of old uploads + indexes in one go, to be scheduled with Task Scheduler or cron (commands in INSTALLATION.md). OCRIS still has no scheduler of its own, so **nothing runs until the school schedules it**, and a backup on the same disk does not survive that disk. The restore is tested for the MongoDB data, scan files, an encrypted backup and a refused junk file, and the SQLite part on its own; a full restore on a second machine was not tried.
> - **40:** The server deletes unsaved uploads older than `PENDING_SCAN_DAYS` (7; `0` turns it off), with their files, by itself: whenever someone uploads, at most once an hour per server process, and a failure never stops the upload. `cleanup_scans` still works on demand and shares the same code.
> - **41:** A form that has been read is already stored on the server, so the Upload page now lists the user's unsaved uploads under **Unfinished uploads** and **Continue** reopens one at step 4 with the scan and everything read (new `GET /ocr/pending/` and `GET /ocr/scans/<id>/`; the reader's notes are now stored on the scan). The browser also asks before a refresh or close while a form is between step 2 and saving. **Not covered:** forms of a batch that were not uploaded yet must be chosen again, and the correction typed on step 5 before the refresh is lost (the form returns to step 4).
> - **42:** The server never used a stale class: it reads the account on every request. The cached copy was in the browser. The app now asks `GET /auth/me/` when the window gets focus and every 3 minutes, and updates the user only if it changed, so a teacher sees the new class without signing in again; an ended session returns to the login screen (only a `401` does that).
> - **43:** Indexes are created on records (`record_id` unique, `lrn`, school year + name, grade level, `created_at`, `scan_id`), scans (`scan_id` unique, outcome + date, uploader + outcome, grade level, date), the audit log (`timestamp`), users (`username` unique) and sections (grade level unique, section id), by `db.ensure_indexes()` the first time the server connects, and by `create_indexes`/`maintenance`. One that cannot be built is logged and skipped. **Limit:** the search box (text inside names, subjects and scanned text) and the case-insensitive section match cannot use an index, and analytics still reads the records it covers; see [DATABASE.md](DATABASE.md#indexes).

- [x] **39. Backups are manual, and there is no restore command.**
- [x] **40. Abandoned uploads pile up** until someone runs the `cleanup_scans` command.
- [x] **41. Refreshing the page mid-upload loses the whole batch.**
- [x] **42. A teacher's class change needs a fresh sign-in** before the screens reflect it.
- [x] **43. No database indexes.**
- [ ] **44. Printing depends on browser behaviour.** Removing the browser's header and footer, and printing a PDF scan, have not been tried on a real printer. The print styles already ask for no margin (`@page { margin: 0 }`) and long bond paper, but that is unconfirmed until someone prints a typed form, a scanned image and a scanned PDF on the school's printer.

## F. Verification gaps

- [ ] **45. Most recent screens have never been clicked through in a browser:** multi-form upload, PDF upload, the SF10 fill-out form, editing a typed form, and printing.
- [ ] **46. No frontend tests, and no automated OCR tests.** The OCR accuracy checks were run by hand.
- [x] **47. Uncommitted work and a stale changelog.** Committed on 2026-10-10, with a changelog entry for October 5 to 10.
