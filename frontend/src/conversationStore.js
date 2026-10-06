import { STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from './constants'
import { conversationTitle } from './conversationTitle'

export function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS) || '[]') } catch { return [] }
}

// Only the first page is cached; older pages come from the server again (#123).
export function persistConversationHistory(list) {
  try { localStorage.setItem(STORAGE_CONVERSATIONS, JSON.stringify(list.slice(0, MAX_CONVERSATIONS))) } catch { /* noop */ }
}

export const newConversationId = () => crypto.randomUUID()

const showsSomething = m =>
  !!(m.content || m.figures?.length || m.tools?.length || m.clarification || m.vervangen?.length)

// A reopened conversation shows what the chat showed (#109). Records from the old server copy
// also hold tool messages ('OK', catalogue JSON) and tool calls without text, and a stopped
// answer can be saved empty; those would render as raw JSON or a bubble that keeps typing.
export function restorableMessages(messages) {
  return messages.filter(m => m.role === 'user' || (m.role === 'assistant' && showsSomething(m)))
}

// The open conversation survives a reload as {id, messages}; older builds stored only the messages.
export function loadCurrentChat() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_CURRENT_CHAT) || 'null')
    if (Array.isArray(stored)) return { id: newConversationId(), messages: restorableMessages(stored) }
    if (typeof stored?.id === 'string' && Array.isArray(stored.messages)) {
      return { id: stored.id, messages: restorableMessages(stored.messages) }
    }
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
  return [record, ...list.filter(c => String(c.id) !== String(record.id))]
}

// The server is asked for one more than a page, so a full last page is not mistaken for "more" (#123).
export const HISTORY_FETCH_LIMIT = MAX_CONVERSATIONS + 1

export function historyPage(rows) {
  const items = rows.slice(0, MAX_CONVERSATIONS).map(c => ({
    ...c,
    messages: typeof c.messages === 'string' ? JSON.parse(c.messages) : c.messages,
  }))
  return { items, hasMore: rows.length > MAX_CONVERSATIONS }
}

// The next page starts after the last conversation shown; the server orders by (timestamp, id).
export function nextPageQuery(list) {
  const last = list.at(-1)
  return { before_ts: last.timestamp, before_id: String(last.id) }
}

export function appendPage(list, items) {
  const known = new Set(list.map(c => String(c.id)))
  return [...list, ...items.filter(c => !known.has(String(c.id)))]
}
