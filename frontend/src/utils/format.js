const LOCALE = 'en-PH'

export const NA = 'N/A'
// How a missing grade is labelled. Nothing is ever estimated to fill one in.
export const FOR_VERIFICATION = 'Incomplete / For Verification'
export const PASSING_GRADE = 75

export const isNA = (v) => v === undefined || v === null || v === '' || v === NA
// A form stored with Archive only: never scanned, so it has no grades, average or remarks
export const isArchived = (record) => Boolean(record?.details?.archive_only)
// 'term' or 'quarter' (see GRADING_PERIODS); records saved before the field existed use quarters
export const gradingPeriodOf = (record) => (record?.grading_period === 'term' ? 'term' : 'quarter')

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

export const formatDate = (iso, opts = { month: 'short', day: 'numeric', year: 'numeric' }) =>
  iso ? new Date(iso).toLocaleDateString(LOCALE, opts) : '—'

export const formatDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString(LOCALE, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'

export const formatLongDate = (date = new Date()) =>
  date.toLocaleDateString(LOCALE, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

export const formatMB = (bytes) => `${((bytes || 0) / 1024 / 1024).toFixed(1)} MB`

// 'offline' is a sentinel StatusBanner renders as the "start the backend" banner
export const errorMessage = (e, fallback) => (e?.offline ? 'offline' : e?.data?.detail || fallback)

export const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
