// Small API client. The session token is kept in sessionStorage (cleared when the tab closes)
// and never in the URL. No secrets or API keys exist in the frontend.

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const TOKEN_KEY = 'haq.session'

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const session = {
  get: () => { try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* storage unavailable */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ } },
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

function parseError(status, body) {
  const e = body && body.error
  if (e) return new ApiError(status, e.code, e.message, e.details)
  return new ApiError(status, 'http_error', `Request failed (${status})`)
}

export async function api(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  const token = session.get()
  const h = { ...headers }
  if (token) h.Authorization = `Bearer ${token}`
  if (body !== undefined && !(body instanceof FormData)) h['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(BASE + path, { method, headers: h, body: body === undefined || body instanceof FormData ? body : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, 'network_error', 'network')
  }
  if (raw && res.ok) return res
  let data = null
  try { data = await res.json() } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    const err = parseError(res.status, data)
    if (res.status === 401 && token) onUnauthorized(err)
    throw err
  }
  return data
}

// Upload with progress (fetch cannot report upload progress).
export function uploadFile(path, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + path)
    const token = session.get()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100)) }
    xhr.onerror = () => reject(new ApiError(0, 'network_error', 'network'))
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(parseError(xhr.status, data))
    }
    const fd = new FormData()
    fd.append('file', file, file.name)
    xhr.send(fd)
  })
}

// Downloads go through an authenticated request; the file never has a public URL.
export async function openProtectedFile(evidenceId, filename) {
  const res = await api(`/api/evidence/${evidenceId}/download`, { raw: true })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'file'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

export async function openExport(claimId) {
  const res = await api(`/api/claims/${claimId}/export`, { raw: true })
  const html = await res.text()
  const blob = new Blob([html], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export const newIdempotencyKey = () =>
  (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)
