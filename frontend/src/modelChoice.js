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

// The model of the conversation is the one its last question went out with (#242).
export function conversationModel(messages) {
  return messages.findLast(m => m.role === 'user' && m.model)?.model ?? null
}
