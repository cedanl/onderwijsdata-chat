const KEY = 'edudata_workbooks'

export const BUILTIN = {
  id: '__builtin__',
  title: 'Instroom & Diplomering',
  description: 'Overzicht instroom, diplomarendement en regionale herkomst. Voorbeelddashboard met statische data.',
  createdAt: '2024-10-01T00:00:00.000Z',
  builtin: true,
}

export const BUILTIN_ARBEIDSMARKT = {
  id: '__builtin_arbeidsmarkt__',
  title: 'Arbeidsmarkt',
  description: 'Opleidingsniveau werkzoekenden, vacaturedruk en arbeidsmarktpositie HU-alumni in de regio Utrecht.',
  createdAt: '2024-10-01T00:00:00.000Z',
  builtin: true,
}

function stripMessage(m) {
  return { role: m.role, content: m.content }
}

export function getWorkbooks() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'wb-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)
}

export function saveWorkbook({ title, description, messages, figures, instelling, htmlContent }) {
  const wb = {
    id: generateId(),
    title,
    description,
    messages: messages?.map(stripMessage),
    figures,
    instelling,
    htmlContent,
    createdAt: new Date().toISOString(),
  }
  const payload = JSON.stringify(wb)
  console.log('[workbooks] saveWorkbook called', { title, hasHtml: !!htmlContent, htmlLen: htmlContent?.length, payloadKB: (payload.length / 1024).toFixed(1) })
  try {
    const workbooks = getWorkbooks()
    const full = JSON.stringify([...workbooks, wb])
    console.log('[workbooks] writing to localStorage', { totalKB: (full.length / 1024).toFixed(1), existingCount: workbooks.length })
    localStorage.setItem(KEY, full)
    console.log('[workbooks] save OK')
    return { ok: true, workbook: wb }
  } catch (e1) {
    console.warn('[workbooks] first save failed:', e1.message)
    try {
      const wbSmall = { ...wb, figures: [], messages: undefined }
      const workbooks = getWorkbooks()
      localStorage.setItem(KEY, JSON.stringify([...workbooks, wbSmall]))
      console.log('[workbooks] save OK (stripped)')
      return { ok: true, workbook: wbSmall }
    } catch (e2) {
      console.error('[workbooks] save FAILED completely:', e2.message)
      return { ok: false, error: e2.message, workbook: wb }
    }
  }
}

export function deleteWorkbook(id) {
  localStorage.setItem(KEY, JSON.stringify(getWorkbooks().filter(w => w.id !== id)))
}
