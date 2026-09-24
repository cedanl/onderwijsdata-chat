import { STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from './constants'
import { conversationTitle } from './conversationTitle'

export function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS) || '[]') } catch { return [] }
}

export function persistConversationHistory(list) {
  try { localStorage.setItem(STORAGE_CONVERSATIONS, JSON.stringify(list)) } catch { /* noop */ }
}

export const newConversationId = () => crypto.randomUUID()

// The open conversation survives a reload as {id, messages}; older builds stored only the messages.
export function loadCurrentChat() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_CURRENT_CHAT) || 'null')
    if (Array.isArray(stored)) return { id: newConversationId(), messages: stored }
    if (typeof stored?.id === 'string' && Array.isArray(stored.messages)) return stored
  } catch { /* unreadable: start fresh */ }
  return { id: newConversationId(), messages: [] }
}

export function persistCurrentChat(id, messages) {
  try { localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id, messages })) } catch { /* noop */ }
}

export function clearCurrentChat() {
  try { localStorage.removeItem(STORAGE_CURRENT_CHAT) } catch { /* noop */ }
}

// Nothing to keep until something has been asked.
export function conversationRecord(id, messages) {
  const firstQuestion = messages.find(m => m.role === 'user')
  if (!firstQuestion) return null
  return { id, title: conversationTitle(firstQuestion.content), timestamp: Date.now(), messages }
}

// Saving a conversation again replaces its earlier version instead of adding a copy.
export function upsertConversation(list, record) {
  return [record, ...list.filter(c => String(c.id) !== String(record.id))].slice(0, MAX_CONVERSATIONS)
}
