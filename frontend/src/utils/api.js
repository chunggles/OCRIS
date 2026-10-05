// HTTP client for the Django API. Errors are thrown as { status, data } or { status: 0, offline: true }.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const TOKEN_KEY = 'ocris_token'

const token = {
  get:   ()  => localStorage.getItem(TOKEN_KEY),
  save:  (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: ()  => localStorage.removeItem(TOKEN_KEY),
}

const authHeader = () => {
  const t = token.get()
  return t ? { Authorization: `Token ${t}` } : {}
}

const qs = (params = {}) => new URLSearchParams(params).toString()

async function send(path, opts = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, headers: { ...authHeader(), ...opts.headers } })
  } catch {
    throw { status: 0, offline: true }
  }
  if (res.status === 401) { token.clear(); window.location.href = '/' }
  return res
}

async function request(path, opts = {}) {
  const res  = await send(path, { ...opts, headers: { 'Content-Type': 'application/json', ...opts.headers } })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, data }
  return data
}

const withBody = (method, body) => ({ method, body: JSON.stringify(body) })

// Auth is a header token, so a plain <a href> can't download — fetch as a blob and save it
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
  login: async (username, password) => {
    const data = await request('/auth/login/', withBody('POST', { username, password }))
    token.save(data.token)
    return data.user
  },
  logout: async () => {
    await request('/auth/logout/', { method: 'POST' }).catch(() => {})
    token.clear()
  },
  me: () => request('/auth/me/'),
  // True when a token from an earlier sign-in is still stored (it may have expired)
  hasSession: () => Boolean(token.get()),
  changePassword: (current_password, new_password) =>
    request('/auth/change-password/', withBody('POST', { current_password, new_password })),
}

export const recordsAPI = {
  list:    (params = {})   => request(`/records/?${qs(params)}`),
  options: ()              => request('/records/options/'),
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
  validate: (payload)  => request('/ocr/validate/', withBody('POST', payload)),
  history:  (page = 1) => request(`/ocr/history/?${qs({ page })}`),
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

export const sectionsAPI = {
  list:   ()         => request('/sections/'),
  create: (data)     => request('/sections/create/', withBody('POST', data)),
  update: (id, data) => request(`/sections/${encodeURIComponent(id)}/`, withBody('PATCH', data)),
  delete: (id)       => request(`/sections/${encodeURIComponent(id)}/`, { method: 'DELETE' }),
}

export const auditAPI = {
  list: (page = 1) => request(`/audit/?${qs({ page })}`),
}
