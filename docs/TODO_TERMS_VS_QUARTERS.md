# TODO: terms vs quarters (Record Detail, Analytics, OCR)

Reminder written 2026-10-14. Not started.

## Background

The Fill Out Form 137 page now uses the two-page SF10-ES with **three terms** per learning area (saved as `Q1` to `Q3`; `Q4` is stored as `N/A`). Scanned (OCR) records and older records still use **four quarters**. The rest of the app still assumes four quarters.

## Still to do

1. **Add `grading_period` to each record** (`"term"` or `"quarter"`).
   - The new form sets `term`; OCR scans and existing records default to `quarter` (no data migration needed).
   - Save and validate it in `backend/api/views/records.py` and store it in `db.py`.
   - Do not guess it from "Q4 is N/A": a quarterly form with Q4 not yet filled in would be mistaken for a term record.

2. **Record Detail page** (`frontend/src/pages/RecordDetailPage.jsx`): one table per record, chosen by `grading_period`.
   - `term`: columns Term 1, 2, 3.
   - `quarter`: columns Q1 to Q4.
   - Edit mode follows the same field (three or four editable columns).
   - Do not show both kinds of column in one record.

3. **Analytics page** (`frontend/src/pages/AnalyticsPage.jsx`, `backend/api/views/analytics.py`): do not average terms and quarters together.
   - Group by `grading_period`: a switch or two sections.
   - The "by period" charts and the period means table need the grouping.

4. **OCR** (`backend/api/ocr/table.py`, `parser.py`): decide whether scanned forms will also move to three terms.
   - If yes, the table reader expects four quarter columns today and would put grades in the wrong columns.
   - If old four-quarter forms are still scanned, leave it as is.

5. **Docs:** update `docs/USER_MANUAL.md` (still describes quarters), `docs/API.md` (new field) and `docs/DATABASE.md`.

## Known caveat

Editing an old typed record that had Q4 grades recalculates its final ratings from three terms (ratings typed by hand are kept). Setting `grading_period` on each record would let the form keep four quarters for old records.

## Decisions already made

- Keep the stored keys `Q1` to `Q3`. Renaming them to `T1` to `T3` would need a data migration and an API change for no user-visible benefit.
- The back page of the form uses tighter rows to fit four blocks and three certification boxes on 13 in paper. This has not been checked on a real printer yet.
