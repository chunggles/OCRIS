# OCRIS v3: Weaknesses and bugs (2026-10-10)

This is a list of weaknesses and bugs found by comparing the system with the capstone proposal, "OCRIS (Optical Character Recognition Information System) – School Record Management Decision Support System Using OCR for Bayombong Central School". It is based on reading the code and on the OCR tests run between October 5 and 10.

Tick the box when an item is done. Sections A and B are fixed in code, apart from the deployment items 1 to 4 and the paper correction 12.

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

- [ ] **30. No limit on login attempts.** A password can be guessed indefinitely.
- [ ] **31. Weak password rule.** Eight characters is the only requirement, and a temporary password does not have to be changed at first sign-in.
- [ ] **32. The login token is kept in browser storage,** where a malicious script could read it.
- [ ] **33. One token per user.** Signing out on one device signs the user out on all devices.
- [ ] **34. Scans and backups are unencrypted.**
- [ ] **35. The audit log is thin.** It records which fields changed but not the old and new values, and it is erased if the database is wiped.
- [ ] **36. Deleting a record permanently deletes its scan.** The paper says original scanned documents are preserved as an audit trail.
- [ ] **37. No server-side limit on upload size or file type.**
- [ ] **38. No forgotten-password route** other than asking the OIC.

## E. Reliability and maintenance

- [ ] **39. Backups are manual, and there is no restore command.**
- [ ] **40. Abandoned uploads pile up** until someone runs the `cleanup_scans` command.
- [ ] **41. Refreshing the page mid-upload loses the whole batch.**
- [ ] **42. A teacher's class change needs a fresh sign-in** before the screens reflect it.
- [ ] **43. No database indexes.**
- [ ] **44. Printing depends on browser behaviour.** Removing the browser's header and footer, and printing a PDF scan, have not been tried on a real printer.

## F. Verification gaps

- [ ] **45. Most recent screens have never been clicked through in a browser:** multi-form upload, PDF upload, the SF10 fill-out form, editing a typed form, and printing.
- [ ] **46. No frontend tests, and no automated OCR tests.** The OCR accuracy checks were run by hand.
- [x] **47. Uncommitted work and a stale changelog.** Committed on 2026-10-10, with a changelog entry for October 5 to 10.
