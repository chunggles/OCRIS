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

- [ ] **45. Screens never clicked through in a browser:** uploading several forms at once with OCR, OCR of a PDF upload, printing on paper; also the security screens from section D (forced password change, forgot password, reset badge, Audit Log old and new values) and, from section E, the Unfinished uploads card and a teacher's class change showing without signing in again. Not tried either: the teacher role, phone width, and the idle sign-out while the server cannot be reached. **2026-10-18:** the SF10 fill-out form (terms and quarters), editing a typed form, the print view on screen, the archive-only upload (image and PDF) with every page that shows archived records, the idle sign-out and Sign out of every device were clicked through (see the CHANGELOG).
- [ ] **46. No frontend tests, and no automated OCR tests.** The OCR accuracy checks were run by hand. (The backend has 111 automated tests.)

## 5. Known gaps not on the numbered list

- [ ] No two-step sign-in.
- [ ] MongoDB itself is not encrypted by OCRIS (names, grades and scanned text sit in it as plain data); use MongoDB or disk encryption.
- [x] The audit file (`backend/logs/audit.jsonl`) can be altered by someone with access to the server's disk. **2026-10-18:** a change now shows (hash chain, checked by `verify_audit` against the database); someone who rewrites both the file and the database is still not detected.
- [x] No idle timeout: a session lasts 12 hours. **2026-10-18:** a session ends after 30 minutes without use (`IDLE_TIMEOUT_MINUTES`).
- [x] No "sign out of every device" button (the API `POST /auth/logout-all/` exists). **2026-10-18:** on the Profile page.
- [ ] After a refresh, the not-yet-uploaded forms of a batch and corrections typed on step 5 are lost; only the form being worked on can be resumed.
- [ ] The search box cannot use a database index, and analytics reads every record it covers; fine for one school, not for a very large archive.
- [ ] Backups run only when scheduled (`manage.py maintenance`); a full restore on a second machine has not been tried, and a backup on the same disk does not survive that disk.

## 6. Found in the review of 2026-10-18

- [x] Migration `0003_session_last_active` was not applied to the working database, so every signed-in request failed. **Applied.**
- [x] Four backups from before encryption (`.zip`, 7 to 11 October) were still in `backend/backups/`, holding every record, scan and the accounts file unencrypted. **Deleted**, after the newest `.zip.enc` was checked with `restore` (no `--yes`).
- [x] The 2026-10-14 to 10-18 work was not committed, and the new migration and audit files were not tracked by git. **Committed.**
- [x] One line half-written by a crash broke the audit chain for good, so `verify_audit` failed from then on. **Fixed.**
- [x] Session keys were stored as they are, so a copy of `db.sqlite3` or a backup could be used to sign in, and ended sessions whose browser never came back were never deleted. **Fixed:** only a hash is stored (migration `0004`), and ended sessions are cleared at each sign-in.
- [x] When the idle limit passed while the server could not be reached, the records stayed on screen. **Fixed.**
- [x] A stray empty file `backend/file`, and out-of-date figures in LIMITATIONS.md (26 tests, items fixed since) and OCR_PIPELINE.md (all year blocks averaged together). **Removed and updated.**
- [ ] **The sign-in limit per address can be bypassed with a wrong proxy setting.** `TRUSTED_PROXY_COUNT` defaults to 1 whenever HTTPS is required, so the server takes the caller's address from the `X-Forwarded-For` header. That is right behind one proxy, as on a cloud host. On a server reached directly over HTTPS, with no proxy, the caller writes that header, can give a new address on every try, and is never stopped by the limit of 20 wrong passwords per address. The limit of 5 per username still holds. Set `TRUSTED_PROXY_COUNT=0` on such a server; a safer default, or a warning, would prevent the mistake.
- [ ] **Another website can keep an idle session open (low risk).** With HTTPS the sign-in cookie is sent with `SameSite=None` (`AUTH_COOKIE_SAMESITE`), so that the site and the server can be on different domains. A hostile page open in the same browser can then send read requests to OCRIS with the cookie, in browsers that still send cookies to other sites. It cannot read the answers (CORS) or change data (the `X-OCRIS-Request` header), but a request to `/auth/me/` counts as use, so such a page could stop a session from ending after 30 minutes without use. Serving the site and the API from the same domain, so the cookie can be `SameSite=Lax`, would close it.
