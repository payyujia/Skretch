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
export const createEdge = (data) => request('/api/edges', { method: 'POST', body: JSON.stringify(data) })
export const deleteEdge = (id) => request(`/api/edges/${id}`, { method: 'DELETE' })
