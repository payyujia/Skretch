const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`${options.method || 'GET'} ${path} failed (${res.status})`)
  return res.status === 204 ? null : res.json()
}

export const getBoard = () => request('/api/board')
export const createNode = (data) => request('/api/nodes', { method: 'POST', body: JSON.stringify(data) })
export const updateNode = (id, data) => request(`/api/nodes/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
export const deleteNode = (id) => request(`/api/nodes/${id}`, { method: 'DELETE' })

// ── Document / RAG endpoints ──────────────────────────────────────────────────

/**
 * Upload a project document for RAG retrieval.
 * Deliberately bypasses request() to avoid setting Content-Type on multipart.
 */
export async function uploadDocument(file, boardId = 'default') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('board_id', boardId)
  const res = await fetch(`${BASE}/api/documents`, { method: 'POST', body: formData })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Upload failed (${res.status})`)
  }
  return res.json() // { doc_name, chunk_count, board_id }
}

export const getDocuments = (boardId = 'default') =>
  request(`/api/documents?board_id=${encodeURIComponent(boardId)}`)

export const deleteDocument = (docName, boardId = 'default') =>
  request(`/api/documents/${encodeURIComponent(docName)}?board_id=${encodeURIComponent(boardId)}`, {
    method: 'DELETE',
  })
