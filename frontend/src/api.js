import { getToken } from './auth'

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options.headers },
  })
  if (res.status === 401) throw Object.assign(new Error('Unauthorized'), { status: 401 })
  if (!res.ok) {
    let detail = `API ${res.status}`
    try { const body = await res.json(); if (body.error) detail = body.error } catch {}
    throw new Error(detail)
  }
  return res.json()
}

export async function fetchConversations() {
  return apiFetch('/api/conversations')
}

export async function putConversation(id, data) {
  return apiFetch(`/api/conversations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export async function deleteConversationApi(id) {
  return apiFetch(`/api/conversations/${id}`, { method: 'DELETE' })
}

export async function fetchWorkbooks() {
  return apiFetch('/api/workbooks')
}

export async function putWorkbook(id, data) {
  return apiFetch(`/api/workbooks/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export async function deleteWorkbookApi(id) {
  return apiFetch(`/api/workbooks/${id}`, { method: 'DELETE' })
}

export async function refreshDashboard(recipe, settings = {}) {
  return apiFetch('/api/dashboard/refresh', {
    method: 'POST',
    body: JSON.stringify({ recipe, settings }),
  })
}
