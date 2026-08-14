const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Auth token helper ─────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('skretch_token')
}

function authHeaders(extra = {}) {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

// ── Core request ──────────────────────────────────────────────────────────────

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: authHeaders(),
    ...options,
  })
  if (!res.ok) throw new Error(`${options.method || 'GET'} ${path} failed (${res.status})`)
  return res.status === 204 ? null : res.json()
}

// ── Node / Board endpoints ────────────────────────────────────────────────────

export const getBoard = (boardId) =>
  request(`/api/board?board_id=${encodeURIComponent(boardId)}`)

export const createNode = (data, boardId) =>
  request(`/api/nodes?board_id=${encodeURIComponent(boardId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateNode = (id, data) =>
  request(`/api/nodes/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const deleteNode = (id) =>
  request(`/api/nodes/${id}`, { method: 'DELETE' })

// ── Boards management endpoints ───────────────────────────────────────────────

export const getBoards = () => request('/api/boards')

export const createBoard = (name = 'Untitled Board') =>
  request('/api/boards', { method: 'POST', body: JSON.stringify({ name }) })

// ── Document / RAG endpoints ──────────────────────────────────────────────────

/**
 * Upload a project document for RAG retrieval.
 * Deliberately bypasses request() to avoid setting Content-Type on multipart.
 */
export async function uploadDocument(file, boardId) {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('board_id', boardId)
  const res = await fetch(`${BASE}/api/documents`, {
    method: 'POST',
    body: formData,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Upload failed (${res.status})`)
  }
  return res.json() // { doc_name, chunk_count, board_id }
}

export const getDocuments = (boardId) =>
  request(`/api/documents?board_id=${encodeURIComponent(boardId)}`)

export const deleteDocument = (docName, boardId) =>
  request(`/api/documents/${encodeURIComponent(docName)}?board_id=${encodeURIComponent(boardId)}`, {
    method: 'DELETE',
  })
