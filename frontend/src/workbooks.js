const KEY = 'edudata_workbooks'

export const BUILTIN = {
  id: '__builtin__',
  title: 'Instroom & Diplomering',
  description: 'Overzicht instroom, diplomarendement en regionale herkomst. Demowerkboek met statische data.',
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

export function saveWorkbook({ title, description, htmlContent }) {
  const workbooks = getWorkbooks()
  const wb = {
    id: crypto.randomUUID(),
    title,
    description,
    htmlContent,
    createdAt: new Date().toISOString(),
  }
  localStorage.setItem(KEY, JSON.stringify([...workbooks, wb]))
  return wb
}

export function deleteWorkbook(id) {
  localStorage.setItem(KEY, JSON.stringify(getWorkbooks().filter(w => w.id !== id)))
}
