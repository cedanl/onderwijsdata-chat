import { STORAGE_MODEL } from './constants'

// A stored choice only counts while the server still offers that model.
export function pickModel(models, stored, fallback) {
  return models.some(m => m.id === stored) ? stored : fallback
}

export function loadModelChoice() {
  try { return localStorage.getItem(STORAGE_MODEL) } catch { return null }
}

export function saveModelChoice(id) {
  try { localStorage.setItem(STORAGE_MODEL, id) } catch { /* noop */ }
}
