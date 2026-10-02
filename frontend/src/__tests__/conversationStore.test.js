// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from '../constants'
import {
  appendPage, conversationRecord, historyPage, loadConversationHistory, loadCurrentChat, nextPageQuery,
  persistConversationHistory, persistCurrentChat, upsertConversation,
} from '../conversationStore'

const question = { role: 'user', content: 'Hoeveel studenten heeft de HU?' }
const answer = { role: 'assistant', content: '26.370', figures: ['{"data":[]}'] }

beforeEach(() => localStorage.clear())

describe('upsertConversation', () => {
  it('replaces an earlier save of the same conversation instead of adding a copy', () => {
    let list = []
    for (let i = 0; i < 11; i++) {
      list = upsertConversation(list, conversationRecord('conv-a', [question, answer]))
    }
    expect(list).toHaveLength(1)
  })

  it('puts the latest save first and keeps the others', () => {
    const older = conversationRecord('conv-b', [{ role: 'user', content: 'Andere vraag' }])
    const list = upsertConversation([older], conversationRecord('conv-a', [question]))
    expect(list.map(c => c.id)).toEqual(['conv-a', 'conv-b'])
  })

  it('matches legacy numeric ids against their string form', () => {
    const legacy = { id: 1727000000000, title: 'Oud', timestamp: 1, messages: [question] }
    const list = upsertConversation([legacy], conversationRecord('1727000000000', [question, answer]))
    expect(list).toHaveLength(1)
  })

  it('keeps older pages that were loaded with "meer laden" (#123)', () => {
    const many = Array.from({ length: MAX_CONVERSATIONS + 5 }, (_, i) => conversationRecord(`c${i}`, [question]))
    expect(upsertConversation(many, conversationRecord('nieuw', [question]))).toHaveLength(MAX_CONVERSATIONS + 6)
  })
})

describe('history pages (#123)', () => {
  const row = (id, timestamp) => ({ id, title: id, timestamp, messages: JSON.stringify([question]) })
  const rows = n => Array.from({ length: n }, (_, i) => row(`c${i}`, 1000 - i))

  it('knows there is more when the server sent one beyond the page', () => {
    const page = historyPage(rows(MAX_CONVERSATIONS + 1))
    expect(page.items).toHaveLength(MAX_CONVERSATIONS)
    expect(page.hasMore).toBe(true)
  })

  it('knows the last page, also when it is exactly full', () => {
    expect(historyPage(rows(MAX_CONVERSATIONS)).hasMore).toBe(false)
  })

  it('parses the stored messages', () => {
    expect(historyPage([row('c0', 1)]).items[0].messages).toEqual([question])
  })

  it('asks for the page after the last conversation shown', () => {
    const list = historyPage(rows(3)).items
    expect(nextPageQuery(list)).toEqual({ before_ts: 998, before_id: 'c2' })
  })

  it('adds a page without repeating a conversation already in the list', () => {
    const list = historyPage(rows(2)).items
    const page = historyPage([row('c1', 999), row('c9', 5)]).items
    expect(appendPage(list, page).map(c => c.id)).toEqual(['c0', 'c1', 'c9'])
  })

  it('caches only the first page in localStorage', () => {
    persistConversationHistory(historyPage(rows(MAX_CONVERSATIONS + 1)).items.concat([row('oud', 1)]))
    expect(loadConversationHistory()).toHaveLength(MAX_CONVERSATIONS)
  })
})

describe('conversationRecord', () => {
  it('keeps the full conversation, figures included, titled by the first question', () => {
    const record = conversationRecord('conv-a', [question, answer])
    expect(record.title).toBe('Hoeveel studenten heeft de HU?')
    expect(record.messages[1].figures).toEqual(['{"data":[]}'])
  })

  it('has nothing to save before a question was asked', () => {
    expect(conversationRecord('conv-a', [])).toBeNull()
  })
})

describe('current chat', () => {
  it('keeps its id across a reload', () => {
    persistCurrentChat('conv-a', [question])
    expect(loadCurrentChat()).toEqual({ id: 'conv-a', messages: [question] })
  })

  it('reads the older message-only format under a fresh id', () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify([question]))
    const chat = loadCurrentChat()
    expect(chat.messages).toEqual([question])
    expect(chat.id).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('starts empty when nothing or garbage is stored', () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, 'not-json')
    expect(loadCurrentChat().messages).toEqual([])
  })
})

describe('conversation history', () => {
  it('round-trips through storage and survives corrupt data', () => {
    persistConversationHistory([{ id: 'a', title: 'T' }])
    expect(loadConversationHistory()).toEqual([{ id: 'a', title: 'T' }])
    localStorage.setItem('openEDUdata_conversations', 'x')
    expect(loadConversationHistory()).toEqual([])
  })
})
