import { getToken, endSessionIfCurrent } from './auth'
import { saveFile } from './saveFile'
import { metVoorbehoud } from './voorbehoud'

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// A 401 for the token that was sent means the server no longer accepts it: the session ends (#480).
async function throwIfFailed(res, sentToken) {
  if (res.status === 401) {
    endSessionIfCurrent(sentToken)
    throw Object.assign(new Error('Unauthorized'), { status: 401 })
  }
  if (res.ok) return
  let detail = `API ${res.status}`
  try {
    const body = await res.json()
    // Own routes answer {error}; FastAPI's HTTPException answers {detail}.
    if (body.error) detail = body.error
    else if (typeof body.detail === 'string') detail = body.detail
  } catch { /* noop */ }
  throw Object.assign(new Error(detail), { status: res.status })
}

async function apiFetch(path, options = {}) {
  const token = getToken()
  const res = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authHeaders(token), ...options.headers },
  })
  await throwIfFailed(res, token)
  return res.json()
}

// The table behind an answer as a file (#269). A plain link cannot carry the token,
// so the CSV is fetched and handed to the browser as a blob. Returns the server's notice
// when the data was fetched again after a restart (#472), else null. `voorbehoud` (voorbehoud.js, #1257): het
// Uitgangspunt, "Niet meegeteld", "Bron en definitie" en de controleregels van het antwoord, als '#'-regels boven die
// van de server; de server kent het antwoord niet, alleen de tabel.
export async function downloadDataCsv(key, voorbehoud = []) {
  const token = getToken()
  const res = await fetch(`/api/data/csv?${new URLSearchParams({ key })}`, { headers: authHeaders(token) })
  await throwIfFailed(res, token)
  const filename = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || 'data.csv'
  const blob = await res.blob()
  if (!voorbehoud.length) {
    saveFile(blob, filename)
  } else {
    // Met BOM, zoals de server hem stuurt: anders leest Excel é als Ã©.
    const tekst = (await blob.text()).replace(/^\uFEFF/, '')
    saveFile(new Blob(['\uFEFF' + metVoorbehoud(tekst, voorbehoud)], { type: 'text/csv;charset=utf-8' }), filename)
  }
  return res.headers.get('X-Data-Herladen')
}

// Everything the server keeps under this account as one JSON file (#645), fetched as a blob for the same
// reason. The server writes the file row by row, so a failure halfway leaves the headers sent and the file
// short. The browser then mostly fails to read the blob; the closing newline catches the rest: the server
// writes it last and nowhere else (JSON escapes a newline inside a string). A truncated file is never saved.
export async function downloadMijnGegevens({ save = saveFile } = {}) {
  const token = getToken()
  const res = await fetch('/api/mijn-gegevens/export', { headers: authHeaders(token) })
  await throwIfFailed(res, token)
  const filename = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || 'mijn-gegevens.json'
  const blob = await res.blob()
  if ((await blob.slice(-1).text()) !== '\n') throw new Error('Export onvolledig')
  save(blob, filename)
}

// Everything the server keeps under this account, erased (#646); the server also revokes the token sent. It demands
// this fixed confirmation; what the user typed is checked by the dialog. Resolves to { ok, verwijderd: counts }.
export async function deleteMijnGegevens() {
  return apiFetch('/api/mijn-gegevens', { method: 'DELETE', body: JSON.stringify({ bevestig: 'verwijder' }) })
}

export async function fetchConversations(params = {}) {
  const query = new URLSearchParams(params).toString()
  return apiFetch(query ? `/api/conversations?${query}` : '/api/conversations')
}

// The list carries no messages (#509); opening a conversation fetches them.
export async function fetchConversation(id) {
  return apiFetch(`/api/conversations/${id}`)
}

export async function putConversation(id, data) {
  return apiFetch(`/api/conversations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export async function renameConversationApi(id, title) {
  return apiFetch(`/api/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) })
}

// A delete that finds nothing has its outcome: the item is gone (#778).
function alWeg(err) {
  if (err.status !== 404) throw err
}

// `keepalive`: the request may outlive the page (a deferred delete when the tab closes, #493).
export async function deleteConversationApi(id, { keepalive = false } = {}) {
  return apiFetch(`/api/conversations/${id}`, { method: 'DELETE', keepalive }).catch(alWeg)
}

export async function fetchWorkbooks() {
  return apiFetch('/api/workbooks')
}

// The list carries no content (#633); opening a report or showing its thumbnail fetches it.
export async function fetchWorkbook(id) {
  return apiFetch(`/api/workbooks/${encodeURIComponent(id)}`)
}

export async function putWorkbook(id, data) {
  return apiFetch(`/api/workbooks/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

// A stored report as a Word document (#1038): the server renders the report it keeps; the form carries only the
// chart images. Without a Content-Type header the browser sets the multipart boundary itself.
export async function downloadRapportDocx(id, form) {
  const token = getToken()
  const res = await fetch(`/api/workbooks/${encodeURIComponent(id)}/docx`, {
    method: 'POST', headers: authHeaders(token), body: form,
  })
  await throwIfFailed(res, token)
  return res.blob()
}

export async function deleteWorkbookApi(id) {
  return apiFetch(`/api/workbooks/${id}`, { method: 'DELETE' }).catch(alWeg)
}

export async function fetchCatalogCounts() {
  return apiFetch('/api/catalog/counts')
}

// Release, catalogus en de dataversie van UWV en ROA (editie en SIS-jaar van het geladen ROA-bestand, #1091).
export async function fetchVersion() {
  return apiFetch('/api/version')
}

export async function fetchSettingsConfig() {
  return apiFetch('/api/settings/config')
}

// The data behind a built-in dashboard; with login on the server wants the token (#636).
export async function fetchDashboardData(endpoint, instelling, { signal } = {}) {
  return apiFetch(`${endpoint}?${new URLSearchParams({ instelling })}`, { signal })
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

// General feedback from the Feedback link (#600): { tekst, soort, pagina }.
export async function postAlgemeneFeedback(body) {
  return apiFetch('/api/feedback/algemeen', { method: 'POST', body: JSON.stringify(body) })
}
