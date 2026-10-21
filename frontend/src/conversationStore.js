import { STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from './constants'
import { conversationTitle } from './conversationTitle'
import { metDeeltekst } from './turnTrace'

export function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS) || '[]') } catch { return [] }
}

// What the sidebar needs of a conversation: id, title and timestamp, never the messages (#509).
export const conversationSummary = ({ id, title, timestamp }) => ({ id, title, timestamp })

// Only the first page is cached; older pages come from the server again (#123). Without
// messages: the cache stays small whatever the conversations hold, and figure JSON
// does not compete with the open chat for the ~5 MB of localStorage (#511).
// Returns 'ok' or 'mislukt', so the page can report a full storage (#521).
export function persistConversationHistory(list) {
  try {
    localStorage.setItem(STORAGE_CONVERSATIONS, JSON.stringify(list.slice(0, MAX_CONVERSATIONS).map(conversationSummary)))
    return 'ok'
  } catch {
    return 'mislukt'
  }
}

export const newConversationId = () => crypto.randomUUID()

const showsSomething = m =>
  !!(m.content || m.figures?.length || m.tools?.length || m.clarification || m.vervangen?.length)

// A reopened conversation shows what the chat showed (#109). Records from the old server copy
// also hold tool messages ('OK', catalogue JSON) and tool calls without text, and a stopped
// answer can be saved empty; those would render as raw JSON or a bubble that keeps typing.
// An answer still being written when the page went away (a reload during a question) was cut off: it comes back
// as such, with its text, the "onvolledig" line and "Probeer opnieuw" (#635), and the server closes that turn (#548).
// A cut-off answer without text of its own gets its last interim text back (#652), also one saved before that fix.
const afgebrokenBijHerladen = m => {
  if (m.role !== 'assistant' || !(m.done === false || m.interrupted)) return m
  return metDeeltekst({ ...m, done: true, interrupted: true })
}

export function restorableMessages(messages) {
  return messages.filter(m => m.role === 'user' || (m.role === 'assistant' && showsSomething(m))).map(afgebrokenBijHerladen)
}

// The open conversation survives a reload as {id, messages}; older builds stored only the messages.
// A snapshot saved without its figures says so with onvolledig (#521).
export function loadCurrentChat() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_CURRENT_CHAT) || 'null')
    if (Array.isArray(stored)) return { id: newConversationId(), messages: restorableMessages(stored) }
    if (typeof stored?.id === 'string' && Array.isArray(stored.messages)) {
      const chat = { id: stored.id, messages: restorableMessages(stored.messages) }
      return stored.onvolledig === true ? { ...chat, onvolledig: true } : chat
    }
  } catch { /* unreadable: start fresh */ }
  return { id: newConversationId(), messages: [] }
}

// localStorage is ~5 MB; een vol quotum gooide hier en de catch slikte dat stil (#511).
// Figuur-JSON is veruit het grootst, dus de terugval bewaart het gesprek zonder figuren.
// De uitkomst zegt wat er is gelukt, zodat de pagina het één keer kan melden.
// De terugval draagt onvolledig, zodat het herstel na verversen het kan zeggen; past
// ook die niet, dan gaat de oude momentopname weg in plaats van als actueel terug te komen (#521).
export function persistCurrentChat(id, messages) {
  try {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id, messages }))
    return 'ok'
  } catch { /* vol: probeer zonder figuren */ }
  try {
    const zonderFiguren = messages.filter(m => !m.figures)
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id, messages: zonderFiguren, onvolledig: true }))
    return 'zonder_figuren'
  } catch {
    clearCurrentChat()
    return 'mislukt'
  }
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
// The list keeps only the summary: the record's messages go to the server, not to the sidebar.
export function upsertConversation(list, record) {
  return [conversationSummary(record), ...list.filter(c => String(c.id) !== String(record.id))]
}

// The server is asked for one more than a page, so a full last page is not mistaken for "more" (#123).
export const HISTORY_FETCH_LIMIT = MAX_CONVERSATIONS + 1

export function historyPage(rows) {
  const items = rows.slice(0, MAX_CONVERSATIONS).map(conversationSummary)
  return { items, hasMore: rows.length > MAX_CONVERSATIONS }
}

// A stored conversation as the chat shows it; the server sends the messages parsed (#509),
// an older localStorage copy may still hold them as a JSON string.
export function conversationMessages(conv) {
  const messages = typeof conv.messages === 'string' ? JSON.parse(conv.messages) : conv.messages
  return restorableMessages(Array.isArray(messages) ? messages : [])
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
