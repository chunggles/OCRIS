// HTTP client for the Django API. Errors are thrown as { status, data } or { status: 0, offline: true }.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// The sign-in is an HttpOnly cookie set by the server: scripts on the page can never read it.
// Every request sends it (credentials: 'include') and carries a header no other website can add,
// which the server requires on requests that change data.
const REQUEST_HEADER = { 'X-OCRIS-Request': '1' }

const qs = (params = {}) => new URLSearchParams(params).toString()

// With `quiet401`, a 401 is returned to the caller instead of sending the user to the login screen
async function send(path, { quiet401, ...opts } = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, credentials: 'include', headers: { ...REQUEST_HEADER, ...opts.headers } })
  } catch {
    throw { status: 0, offline: true }
  }
  if (res.status === 401 && !quiet401) window.location.href = '/'
  return res
}

async function request(path, opts = {}) {
  const res  = await send(path, { ...opts, headers: { 'Content-Type': 'application/json', ...opts.headers } })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, data }
  return data
}

const withBody = (method, body) => ({ method, body: JSON.stringify(body) })

// Downloads need the sign-in cookie and header, so a plain link will not do: fetch as a blob and save it
async function saveBlobResponse(res, fallbackName) {
  const cd   = res.headers.get('Content-Disposition') || ''
  const m    = cd.match(/filename\*=UTF-8''([^;]+)/i) || cd.match(/filename="?([^";]+)"?/i)
  const name = m ? decodeURIComponent(m[1]) : fallbackName
  const url  = URL.createObjectURL(await res.blob())
  const a    = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const authAPI = {
  login: async (username, password) => (await request('/auth/login/', withBody('POST', { username, password }))).user,
  logout:    () => request('/auth/logout/', { method: 'POST' }).catch(() => {}),
  logoutAll: () => request('/auth/logout-all/', { method: 'POST' }).catch(() => {}),
  // The user of the sign-in cookie if there is a live one; null when signed out. Never redirects.
  restore: async () => {
    const res = await send('/auth/me/', { quiet401: true })
    return res.ok ? res.json() : null
  },
  // Like restore, but only a 401 means signed out; any other failure throws, so a hiccup does not sign anyone out.
  // A `background` refresh (no typing or clicking since the last one) does not count as use of the session.
  refresh: async ({ background = false } = {}) => {
    const res = await send(background ? '/auth/me/?background=1' : '/auth/me/', { quiet401: true })
    if (res.status === 401) return null
    if (!res.ok) throw { status: res.status }
    return res.json()
  },
  changePassword: (current_password, new_password) =>
    request('/auth/change-password/', withBody('POST', { current_password, new_password })),
  forgotPassword: (username) => request('/auth/forgot-password/', withBody('POST', { username })),
}

export const recordsAPI = {
  list:    (params = {})   => request(`/records/?${qs(params)}`),
  options: ()              => request('/records/options/'),
  create:  (data)          => request('/records/create/', withBody('POST', data)),
  get:    (id)             => request(`/records/${id}/`),
  search: (q, params = {}) => request(`/records/search/?${qs({ q, ...params })}`),
  update: (id, data)       => request(`/records/${id}/update/`, withBody('PATCH', data)),
  delete: (id)             => request(`/records/${id}/delete/`, { method: 'DELETE' }),
}

async function postFile(path, file, fields = {}) {
  const form = new FormData()
  form.append('file', file)
  Object.entries(fields).forEach(([k, v]) => form.append(k, v))
  const res  = await send(path, { method: 'POST', body: form })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, data }
  return data
}

export const ocrAPI = {
  checkQuality: (file)            => postFile('/ocr/quality/', file),
  upload:       (file, pupilInfo) => postFile('/ocr/upload/', file, pupilInfo),
  // Uploads that were read but not saved, and one of them with what was read, to carry on from step 4
  pending:  ()         => request('/ocr/pending/'),
  scan:     (scanId)   => request(`/ocr/scans/${encodeURIComponent(scanId)}/`),
  cancel:   (scanId)   => request(`/ocr/scans/${encodeURIComponent(scanId)}/cancel/`, { method: 'DELETE' }),
  validate: (payload)  => request('/ocr/validate/', withBody('POST', payload)),
  history:  (page = 1) => request(`/ocr/history/?${qs({ page })}`),
  // The original uploaded file as a Blob, for showing or printing it in the page
  scanBlob: async (scanId) => {
    const res = await send(`/ocr/scans/${encodeURIComponent(scanId)}/file/`)
    if (!res.ok) throw { status: res.status, data: await res.json().catch(() => ({})) }
    return res.blob()
  },
  downloadFile: async (scanId, fallbackName = 'form137') => {
    const res = await send(`/ocr/scans/${encodeURIComponent(scanId)}/file/`)
    if (!res.ok) throw { status: res.status, data: await res.json().catch(() => ({})) }
    await saveBlobResponse(res, fallbackName)
  },
}

export const analyticsAPI = {
  dashboard: (params = {}) => request(`/analytics/?${qs(params)}`),
}

export const usersAPI = {
  list:   ()         => request('/users/'),
  create: (data)     => request('/users/create/', withBody('POST', data)),
  get:    (id)       => request(`/users/${id}/`),
  update: (id, data) => request(`/users/${id}/`, withBody('PATCH', data)),
  delete: (id)       => request(`/users/${id}/`, { method: 'DELETE' }),
}

// Sections are a tree: tree() returns [{ grade_level, sections: [{ section_id, name }] }]
export const sectionsAPI = {
  tree:   ()         => request('/sections/'),
  create: (data)     => request('/sections/create/', withBody('POST', data)),
  update: (id, data) => request(`/sections/${encodeURIComponent(id)}/`, withBody('PATCH', data)),
  delete: (id)       => request(`/sections/${encodeURIComponent(id)}/`, { method: 'DELETE' }),
}

// Reading the tree: the parent nodes (grade levels), and the child nodes (sections) of one parent
const nodesOf = (tree) => (Array.isArray(tree) ? tree : [])
export const gradeLevelsOf = (tree) => nodesOf(tree).map(node => node.grade_level)
export const sectionsOf = (tree, gradeLevel) => nodesOf(tree).find(node => node.grade_level === gradeLevel)?.sections || []

export const auditAPI = {
  list: (page = 1) => request(`/audit/?${qs({ page })}`),
}
