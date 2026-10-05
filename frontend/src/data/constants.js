export const ROLES = { OIC: 'OIC', ADMIN: 'ADMIN', TEACHER: 'TEACHER' }
export const ROLE_LABELS = { OIC: 'OIC', ADMIN: 'Admin Staff', TEACHER: 'Teacher' }
export const ROLE_OPTIONS = [ROLES.TEACHER, ROLES.ADMIN, ROLES.OIC].map(value => ({ value, label: ROLE_LABELS[value] }))
export const isStaffRole = (role) => role === ROLES.OIC || role === ROLES.ADMIN

const STAFF = [ROLES.OIC, ROLES.ADMIN]

// Sidebar navigation. `key` must match a page in App.jsx; `roles` limits who sees the item.
export const NAV_ITEMS = [
  { section: 'Main' },
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'upload',    label: 'Upload Form 137' },
  { key: 'records',   label: 'Records' },
  { key: 'search',    label: 'Search' },
  { key: 'analytics', label: 'Grade Analytics' },
  { section: 'Admin' },
  { key: 'history',   label: 'Scan History' },
  { key: 'sections',  label: 'Sections',        roles: STAFF },
  { key: 'users',     label: 'User Management', roles: STAFF },
  { key: 'audit',     label: 'Audit Log',       roles: STAFF },
]

const allowed = (item, role) => !item.roles || item.roles.includes(role)
export const navItemsFor = (role) => NAV_ITEMS.filter(item => allowed(item, role))
export const canOpenPage = (key, role) => allowed(NAV_ITEMS.find(item => item.key === key) || {}, role)

// Page titles for the top bar; includes pages that aren't in the sidebar
export const PAGE_TITLES = {
  ...Object.fromEntries(NAV_ITEMS.filter(i => i.key).map(i => [i.key, i.label])),
  detail: 'Record Detail',
}

export const OCR_STEPS    = ['Upload', 'Quality', 'Processing', 'Extraction', 'Validation', 'Confirm']
export const GRADE_LEVELS = ['Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6']
// Suggestions only: sections are typed in, and filters list the sections that records actually use
export const SECTIONS     = ['Sampaguita', 'Orchid', 'Rosal', 'Ilang-Ilang', 'Jasmine']

// School years from the current one back to 1990, newest first. A school year starts in June.
const OLDEST_SCHOOL_YEAR = 1990
const today = new Date()
const currentStart = today.getMonth() >= 5 ? today.getFullYear() : today.getFullYear() - 1
export const SCHOOL_YEARS = Array.from(
  { length: currentStart - OLDEST_SCHOOL_YEAR + 1 },
  (_, i) => `${currentStart - i}-${currentStart - i + 1}`,
)
export const CURRENT_SCHOOL_YEAR = SCHOOL_YEARS[0]

export const PERM_MATRIX = [
  { perm: 'Upload Form 137',     oic: true, admin: true,  teacher: true },
  { perm: 'View records',        oic: true, admin: true,  teacher: 'Own class' },
  { perm: 'Validate OCR fields', oic: true, admin: true,  teacher: true },
  { perm: 'Edit or delete',      oic: true, admin: true,  teacher: false },
  { perm: 'View analytics',      oic: true, admin: true,  teacher: 'Own class' },
  { perm: 'Manage sections',     oic: true, admin: true,  teacher: false },
  { perm: 'Manage users',        oic: true, admin: false, teacher: false },
  { perm: 'View audit log',      oic: true, admin: true,  teacher: false },
]

export const AUDIT_BADGES = {
  LOGIN: 'b-blue', UPLOAD: 'b-blue', VALIDATE: 'b-green', EDIT: 'b-amber', DELETE: 'b-rose', DELETE_USER: 'b-rose',
  EDIT_USER: 'b-amber', RESET_PASSWORD: 'b-amber', CHANGE_PASSWORD: 'b-amber',
  ADD_SECTION: 'b-green', EDIT_SECTION: 'b-amber', DELETE_SECTION: 'b-rose',
}
