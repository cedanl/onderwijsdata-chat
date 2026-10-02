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
    try {
      const body = await res.json()
      // Own routes answer {error}; FastAPI's HTTPException answers {detail}.
      if (body.error) detail = body.error
      else if (typeof body.detail === 'string') detail = body.detail
    } catch { /* noop */ }
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

export async function renameConversationApi(id, title) {
  return apiFetch(`/api/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) })
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

export async function fetchCatalogCounts() {
  return apiFetch('/api/catalog/counts')
}

export async function fetchSettingsConfig() {
  return apiFetch('/api/settings/config')
}

export async function refreshDashboard(spec, settings = {}) {
  return apiFetch('/api/dashboard/refresh', {
    method: 'POST',
    body: JSON.stringify({
      recipe: spec.recipe,
      figure_recipes: spec.figure_recipes,
      spec,
      settings,
    }),
  })
}

export async function fetchFeedbackQuestions() {
  return apiFetch('/api/feedback/questions')
}

export async function fetchFeedbackGiven() {
  return apiFetch('/api/feedback/given')
}

export async function postFeedback(feedback) {
  return apiFetch('/api/feedback', { method: 'POST', body: JSON.stringify(feedback) })
}
