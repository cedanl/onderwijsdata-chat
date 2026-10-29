import { STORAGE_WORKBOOKS } from './constants'
import { fetchWorkbooks, fetchWorkbook, putWorkbook, deleteWorkbookApi } from './api'
import { getToken, sessionEndedSince } from './auth'
import { volgOpslag } from './gesprekOpslag'
import { terugInLijst } from './verwijderenMetUitstel'

export const BUILTIN_MIJN_INSTELLING = {
  id: '__builtin_mijn_instelling__',
  title: 'Mijn instelling',
  description: 'Kerncijfers, instroom, diplomering, rendement, gender en regionale benchmark in één overzicht.',
  createdAt: '2026-07-01T00:00:00.000Z',
  builtin: true,
}

export const BUILTIN_ARBEIDSMARKT = {
  id: '__builtin_arbeidsmarkt__',
  title: 'Arbeidsmarkt',
  description: 'Match-score per sector, vacatures (UWV), ROA-indicatoren en arbeidsmarktprognose.',
  createdAt: '2026-07-01T00:00:00.000Z',
  builtin: true,
}

export const BUILTIN_NATIONAAL = {
  id: '__builtin_nationaal__',
  title: 'Landelijk',
  description: 'Landelijke ranking, marktaandeel per sector en sectortrends voor de instelling.',
  createdAt: '2026-07-01T00:00:00.000Z',
  builtin: true,
}

function stripMessage(m) {
  return { role: m.role, content: m.content }
}

export function getWorkbooks() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_WORKBOOKS) || '[]')
  } catch {
    return []
  }
}

function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'wb-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
}

export function getWorkbookType(wb) {
  if (wb.type) return wb.type
  if (wb.htmlContent && !wb.dashboardSpec) return 'report'
  return 'dashboard'
}

export function saveWorkbook({ title, description, messages, figures, instelling, htmlContent, dashboardSpec, type }) {
  const wb = {
    id: generateId(),
    title,
    description,
    messages: messages?.map(stripMessage),
    figures,
    instelling,
    htmlContent,
    dashboardSpec,
    type: type || (dashboardSpec ? 'dashboard' : htmlContent ? 'report' : 'dashboard'),
    createdAt: new Date().toISOString(),
  }
  try {
    const workbooks = getWorkbooks()
    const full = JSON.stringify([...workbooks, wb])
    localStorage.setItem(STORAGE_WORKBOOKS, full)
    return { ok: true, workbook: wb }
  } catch {
    try {
      const wbSmall = { ...wb, figures: [], messages: undefined }
      const workbooks = getWorkbooks()
      localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify([...workbooks, wbSmall]))
      return { ok: true, workbook: wbSmall }
    } catch (e2) {
      return { ok: false, error: e2.message, workbook: wb }
    }
  }
}

// Workbooks fetched in this tab, so a thumbnail scrolled back into view and the report opened from it
// fetch once. Bounded: a long gallery scrolled top to bottom does not keep every report in memory.
const VOLLEDIG_MAX = 30
const volledig = new Map()

// Weg op het scherm is weg op de server (#778): lukt de DELETE niet, dan staat het werkboek weer op zijn plaats in
// de lokale lijst en wijst de belofte af. Niet na het uitloggen: de lijst van deze gebruiker hoort dan niet terug.
export function deleteWorkbook(id) {
  volledig.delete(String(id))
  const lijst = getWorkbooks()
  const index = lijst.findIndex(w => w.id === id)
  const token = getToken()
  try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(lijst.filter(w => w.id !== id))) } catch { /* noop */ }
  return volgOpslag(deleteWorkbookApi(id)).catch(err => {
    if (index >= 0 && !sessionEndedSince(token)) {
      try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(terugInLijst(getWorkbooks(), lijst[index], index))) } catch { /* noop */ }
    }
    throw err
  })
}

// The server list holds what a card shows, not the content (#633): with every report's HTML in it, 85
// reports made 2.1 MB and /rapporten crashed the tab. A summary says so; the content comes per workbook.
export function isVolledig(wb) {
  return Boolean(wb?.builtin) || !wb?.samenvatting
}

function samenvatting(wb) {
  return { ...wb, createdAt: wb.created_at ?? wb.createdAt, samenvatting: true }
}

function volledigWerkboek(wb) {
  return {
    ...wb,
    messages: typeof wb.messages === 'string' ? JSON.parse(wb.messages) : wb.messages,
    figures: typeof wb.figures === 'string' ? JSON.parse(wb.figures) : wb.figures,
    htmlContent: wb.html_content ?? wb.htmlContent,
    dashboardSpec: typeof wb.dashboard_spec === 'string' ? JSON.parse(wb.dashboard_spec) : wb.dashboard_spec ?? wb.dashboardSpec,
    createdAt: wb.created_at ?? wb.createdAt,
  }
}

export function loadWorkbook(id) {
  const key = String(id)
  if (!volledig.has(key)) {
    const laden = fetchWorkbook(key).then(volledigWerkboek)
    laden.catch(() => volledig.delete(key))
    volledig.set(key, laden)
    if (volledig.size > VOLLEDIG_MAX) volledig.delete(volledig.keys().next().value)
  }
  return volledig.get(key)
}

export async function loadWorkbooksFromServer() {
  try {
    let wbs = await fetchWorkbooks()
    if (wbs.length === 0 && await migrateLocalWorkbooks()) wbs = await fetchWorkbooks()
    const lijst = wbs.map(samenvatting)
    localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(lijst))
    return lijst
  } catch {
    return getWorkbooks()
  }
}

// What the server stores of a workbook; the id travels in the URL.
function serverFields(wb) {
  return {
    title: wb.title,
    description: wb.description || '',
    messages: wb.messages,
    figures: wb.figures,
    instelling: wb.instelling,
    htmlContent: wb.htmlContent,
    dashboardSpec: wb.dashboardSpec,
    type: wb.type,
    createdAt: wb.createdAt,
  }
}

// Saved means saved on the server: the gallery reads the server list, so a
// workbook opened before its PUT lands shows up missing or empty (#189).
export async function saveWorkbookWithSync(fields) {
  const { workbook } = saveWorkbook(fields)
  try {
    await putWorkbook(workbook.id, serverFields(workbook))
  } catch (e) {
    return { ok: false, error: `Opslaan op de server mislukt: ${e.message}`, workbook }
  }
  return { ok: true, workbook }
}

// The viewer holds the workbook and the server stores it; the local list is only a
// cache. A workbook missing from that cache is still saved (#176).
export async function updateWorkbook(workbook, changes) {
  // The PUT replaces the whole row: a summary would save the report without its HTML.
  if (!isVolledig(workbook)) throw new Error('Werkboek is nog niet geladen')
  const updated = { ...workbook, ...changes }
  const cached = getWorkbooks()
  if (cached.some(w => w.id === updated.id)) {
    const next = cached.map(w => (w.id === updated.id ? updated : w))
    try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(next)) } catch { /* noop */ }
  }
  await putWorkbook(updated.id, serverFields(updated))
  volledig.set(String(updated.id), Promise.resolve(updated))
  return updated
}

// Workbooks saved only in this browser (from before the server stored them) go up once, when the server
// has none. A summary has no content to send. True when something went up.
async function migrateLocalWorkbooks() {
  const localWbs = getWorkbooks().filter(isVolledig)
  if (localWbs.length === 0) return false
  const results = await Promise.allSettled(localWbs.map(wb => putWorkbook(wb.id, serverFields(wb))))
  if (results.some(r => r.status === 'rejected')) console.warn('Workbook migration failed')
  return results.some(r => r.status === 'fulfilled')
}
