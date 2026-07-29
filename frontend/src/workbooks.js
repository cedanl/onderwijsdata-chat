import { STORAGE_WORKBOOKS } from './constants'
import { fetchWorkbooks, putWorkbook, deleteWorkbookApi } from './api'

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
  } catch (e1) {
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

export function updateWorkbookTitle(id, title) {
  const wbs = getWorkbooks()
  const wb = wbs.find(w => w.id === id)
  if (!wb) return
  wb.title = title
  try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(wbs)) } catch {}
  putWorkbook(id, { ...wb, htmlContent: wb.htmlContent, dashboardSpec: wb.dashboardSpec, createdAt: wb.createdAt }).catch(e => console.warn('Workbook sync failed:', e.message))
}

export function updateWorkbookSpec(id, dashboardSpec) {
  const wbs = getWorkbooks()
  const wb = wbs.find(w => w.id === id)
  if (!wb) return
  wb.dashboardSpec = dashboardSpec
  try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(wbs)) } catch {}
  putWorkbook(id, { ...wb, dashboardSpec, createdAt: wb.createdAt }).catch(e => console.warn('Workbook sync failed:', e.message))
}

export function deleteWorkbook(id) {
  try { localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(getWorkbooks().filter(w => w.id !== id))) } catch {}
  deleteWorkbookApi(id).catch(e => console.warn('Workbook sync failed:', e.message))
}

export async function loadWorkbooksFromServer() {
  try {
    const wbs = await fetchWorkbooks()
    const parsed = wbs.map(wb => ({
      ...wb,
      messages: typeof wb.messages === 'string' ? JSON.parse(wb.messages) : wb.messages,
      figures: typeof wb.figures === 'string' ? JSON.parse(wb.figures) : wb.figures,
      htmlContent: wb.html_content ?? wb.htmlContent,
      dashboardSpec: typeof wb.dashboard_spec === 'string' ? JSON.parse(wb.dashboard_spec) : wb.dashboard_spec ?? wb.dashboardSpec,
      createdAt: wb.created_at ?? wb.createdAt,
    }))
    localStorage.setItem(STORAGE_WORKBOOKS, JSON.stringify(parsed))
    return parsed
  } catch {
    return getWorkbooks()
  }
}

export async function saveWorkbookWithSync({ title, description, messages, figures, instelling, htmlContent, dashboardSpec, type }) {
  const result = saveWorkbook({ title, description, messages, figures, instelling, htmlContent, dashboardSpec, type })
  if (result.ok && result.workbook) {
    const wb = result.workbook
    putWorkbook(wb.id, {
      title: wb.title,
      description: wb.description,
      messages: wb.messages,
      figures: wb.figures,
      instelling: wb.instelling,
      htmlContent: wb.htmlContent,
      dashboardSpec: wb.dashboardSpec,
      type: wb.type,
      createdAt: wb.createdAt,
    }).catch(e => console.warn('Workbook sync failed:', e.message))
  }
  return result
}

export async function migrateLocalWorkbooks() {
  try {
    const serverWbs = await fetchWorkbooks()
    if (serverWbs.length > 0) {
      localStorage.removeItem(STORAGE_WORKBOOKS)
      return
    }
    const localWbs = getWorkbooks()
    if (localWbs.length === 0) return
    const results = await Promise.allSettled(localWbs.map(wb =>
      putWorkbook(wb.id, {
        title: wb.title,
        description: wb.description || '',
        messages: wb.messages,
        figures: wb.figures,
        instelling: wb.instelling,
        htmlContent: wb.htmlContent,
        dashboardSpec: wb.dashboardSpec,
        type: wb.type,
        createdAt: wb.createdAt,
      })
    ))
    if (results.every(r => r.status === 'fulfilled')) {
      localStorage.removeItem(STORAGE_WORKBOOKS)
    }
  } catch (e) {
    console.warn('Workbook migration failed:', e.message)
  }
}
