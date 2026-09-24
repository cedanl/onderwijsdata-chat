// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from '../constants'
import {
  conversationRecord, loadConversationHistory, loadCurrentChat, persistConversationHistory,
  persistCurrentChat, upsertConversation,
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

  it('caps the history', () => {
    const many = Array.from({ length: MAX_CONVERSATIONS }, (_, i) => conversationRecord(`c${i}`, [question]))
    expect(upsertConversation(many, conversationRecord('nieuw', [question]))).toHaveLength(MAX_CONVERSATIONS)
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
