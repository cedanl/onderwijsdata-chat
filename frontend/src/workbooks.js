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

export function getWorkbooks() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

export function saveWorkbook({ title, description, messages, figures, instelling, htmlContent }) {
  const wb = {
    id: crypto.randomUUID(),
    title,
    description,
    messages,
    figures,
    instelling,
    htmlContent,
    createdAt: new Date().toISOString(),
  }
  try {
    const workbooks = getWorkbooks()
    localStorage.setItem(KEY, JSON.stringify([...workbooks, wb]))
  } catch {
    try {
      // quota exceeded — strip figures and retry
      const wbSmall = { ...wb, figures: [] }
      const workbooks = getWorkbooks()
      localStorage.setItem(KEY, JSON.stringify([...workbooks, wbSmall]))
    } catch {
      // localStorage unavailable — wb still returned for in-session navigation
    }
  }
  return wb
}

export function deleteWorkbook(id) {
  localStorage.setItem(KEY, JSON.stringify(getWorkbooks().filter(w => w.id !== id)))
}
