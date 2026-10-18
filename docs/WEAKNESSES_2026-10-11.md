# OCRIS v3: Remaining weaknesses (2026-10-11)

What is still open after the fixes of sections A to E in [WEAKNESSES_2026-10-10.md](WEAKNESSES_2026-10-10.md). Item numbers are the same as in that file. Tick the box when an item is done.

---

## 1. Deployment and the paper

You have put items 1 to 4 off until the whole system is finished.

- [ ] **1. Not deployable to the cloud as-is.** No Render/Railway configuration, Dockerfile or production server setup.
- [ ] **2. Accounts would be lost on a cloud host.** Accounts and logins are in local SQLite (`backend/db.sqlite3`), not MongoDB. Hosts that wipe local files on deploy would lose them.
- [ ] **3. Scanned files are on local disk, not cloud storage.** The same wipe would delete every uploaded form.
- [ ] **4. OCR would time out in the cloud.** Reading one form takes 30 to 70 seconds inside one web request; cloud hosts typically cut requests at about 30 seconds. There is no background job.
- [ ] **12. Tesseract version differs.** The paper says v4.0; 5.5 is installed. This is a correction to the paper, not to the system.

## 2. OCR accuracy and coverage

These cannot be settled without real scans.

- [ ] **23. Handwriting reads poorly.** 80 of 130 grades were auto-approved on the handwriting test; the school's archive is mostly handwritten.
- [ ] **24. Only two layouts are supported:** Form 137-A and the front page of the SF10-ES (Revised 2025). Older formats and the SF10 back page (Grades 5 and 6) are not.
- [ ] **26. All accuracy figures come from generated test copies,** not from real paper that has been through a pen and a scanner.
- [ ] **27. A faded, grainy scan still needed 28 of 130 grades checked by hand.**

## 3. Reliability

- [ ] **44. Printing has not been tried on a real printer.** The print styles ask for no margin and long bond paper (8.5 x 13 in), but removing the browser's header and footer, and printing a PDF scan, are unconfirmed. Test a typed form, a scanned image and a scanned PDF.

## 4. Verification gaps

- [ ] **45. Screens never clicked through in a browser:** multi-form upload, PDF upload, the SF10 fill-out form, editing a typed form and printing; also the security screens from section D (forced password change, forgot password, reset badge, Audit Log old and new values) and, from section E, the Unfinished uploads card and the background refresh of the signed-in user.
- [ ] **46. No frontend tests, and no automated OCR tests.** The OCR accuracy checks were run by hand. (The backend has 96 automated tests.)

## 5. Known gaps not on the numbered list

- [ ] No two-step sign-in.
- [ ] MongoDB itself is not encrypted by OCRIS (names, grades and scanned text sit in it as plain data); use MongoDB or disk encryption.
- [x] The audit file (`backend/logs/audit.jsonl`) can be altered by someone with access to the server's disk. **2026-10-18:** a change now shows (hash chain, checked by `verify_audit` against the database); someone who rewrites both the file and the database is still not detected.
- [x] No idle timeout: a session lasts 12 hours. **2026-10-18:** a session ends after 30 minutes without use (`IDLE_TIMEOUT_MINUTES`).
- [x] No "sign out of every device" button (the API `POST /auth/logout-all/` exists). **2026-10-18:** on the Profile page.
- [ ] After a refresh, the not-yet-uploaded forms of a batch and corrections typed on step 5 are lost; only the form being worked on can be resumed.
- [ ] The search box cannot use a database index, and analytics reads every record it covers; fine for one school, not for a very large archive.
- [ ] Backups run only when scheduled (`manage.py maintenance`); a full restore on a second machine has not been tried, and a backup on the same disk does not survive that disk.
