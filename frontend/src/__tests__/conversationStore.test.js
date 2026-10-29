// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS } from '../constants'
import {
  appendPage, conversationMessages, conversationRecord, historyPage, loadConversationHistory, loadCurrentChat,
  nextPageQuery, persistConversationHistory, persistCurrentChat, restorableMessages, upsertConversation,
} from '../conversationStore'
import { clarificationAnswer, hasOpenClarification } from '../clarificationState'
import herstelClarify from './fixtures/herstelClarify.json'

const question = { role: 'user', content: 'Hoeveel studenten heeft de HU?' }
const answer = { role: 'assistant', content: '26.370', figures: ['{"data":[]}'] }

beforeEach(() => localStorage.clear())

describe('upsertConversation', () => {
  it('puts the summary in the list, never the messages (#509)', () => {
    const record = conversationRecord('c1', [question, answer])
    expect(upsertConversation([], record)).toEqual([{ id: 'c1', title: record.title, timestamp: record.timestamp }])
  })

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

  // #757: elke opslag na een antwoord heeft de automatische titel; een gekozen titel in de lijst blijft staan.
  it('keeps the title a conversation already has in the list', () => {
    const renamed = { id: 'conv-a', title: 'Analyse instroom', timestamp: 1 }
    const record = conversationRecord('conv-a', [question, answer])
    const [first] = upsertConversation([renamed], record)
    expect(first).toEqual({ id: 'conv-a', title: 'Analyse instroom', timestamp: record.timestamp })
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

  // #509: the list is id, title and timestamp; the messages come when a conversation is opened.
  it('keeps only the summary of each conversation', () => {
    expect(historyPage([row('c0', 1)]).items).toEqual([{ id: 'c0', title: 'c0', timestamp: 1 }])
  })

  it('stores no messages in localStorage, also when a record still holds them', () => {
    persistConversationHistory([{ id: 'c0', title: 'c0', timestamp: 1, messages: [question, answer] }])
    expect(loadConversationHistory()).toEqual([{ id: 'c0', title: 'c0', timestamp: 1 }])
  })

  it('reads the messages of a fetched conversation, parsed or as an older JSON string', () => {
    const parsed = { id: 'c0', messages: [question, { role: 'assistant', content: '' }] }
    expect(conversationMessages(parsed)).toEqual([question])
    expect(conversationMessages(row('c0', 1))).toEqual([question])
    expect(conversationMessages({ id: 'c0' })).toEqual([])
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
  afterEach(() => vi.restoreAllMocks())

  it('round-trips through storage and survives corrupt data', () => {
    persistConversationHistory([{ id: 'a', title: 'T' }])
    expect(loadConversationHistory()).toEqual([{ id: 'a', title: 'T' }])
    localStorage.setItem('openEDUdata_conversations', 'x')
    expect(loadConversationHistory()).toEqual([])
  })

  it('says ok when the list was written', () => {
    expect(persistConversationHistory([{ id: 'a', title: 'T' }])).toBe('ok')
  })

  // #521: a full storage was swallowed here without a word.
  it('says mislukt when storage is full', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('vol', 'QuotaExceededError') })
    expect(persistConversationHistory([{ id: 'a', title: 'T' }])).toBe('mislukt')
  })
})

// #109: a reopened conversation showed raw tool JSON, 'OK' and a bubble that kept typing.
describe('restorableMessages', () => {
  // #635: herladen tijdens een vraag liet het halve antwoord terugkomen zonder dat het zei dat het onvolledig was.
  it('brengt een antwoord dat nog liep terug als afgebroken, met zijn tekst', () => {
    const [vraag, half] = restorableMessages([
      { id: 1, role: 'user', content: 'Hoeveel?', done: true },
      { id: 2, role: 'assistant', content: '| 2023 | 470.000 |', done: false },
    ])
    expect(vraag).toEqual({ id: 1, role: 'user', content: 'Hoeveel?', done: true })
    expect(half).toMatchObject({ content: '| 2023 | 470.000 |', done: true, interrupted: true })
  })

  it('laat een afgerond antwoord en een oud record zonder done zoals het is', () => {
    const klaar = { id: 2, role: 'assistant', content: 'Klaar.', done: true }
    const oud = { role: 'assistant', content: 'Van de oude server.' }
    expect(restorableMessages([klaar, oud])).toEqual([klaar, oud])
  })

  // #652: het issue vroeg om deze rondreis; de deeltekst van een afgebroken antwoord komt terug.
  it('bewaart de deeltekst van een afgebroken antwoord en brengt hem na herladen terug', () => {
    const deeltekst = 'Het aantal mbo-studenten groeit licht. '.repeat(10).slice(0, 400)
    persistCurrentChat('conv-b', [
      { id: 1, role: 'user', content: 'Hoeveel?', done: true },
      { id: 2, role: 'assistant', content: deeltekst, tools: [], done: true, interrupted: true },
    ])
    expect(loadCurrentChat().messages[1]).toMatchObject({ content: deeltekst, done: true, interrupted: true })
  })

  // #652: een antwoord dat afbrak tussen twee modelrondes had geen eigen tekst; wat het schreef stond als tussentekst
  // in de dichte redeneerkaart. Ook een zo bewaard gesprek toont die tekst weer als deeltekst.
  it('zet bij een afgebroken antwoord zonder tekst de laatste tussentekst terug als deeltekst', () => {
    const stap = { name: 'search_catalog', label: 'Catalogus doorzoeken', done: true }
    const [, eerder, zonder] = restorableMessages([
      { id: 1, role: 'user', content: 'Hoeveel?', done: true },
      { id: 2, role: 'assistant', content: '', tools: [stap], tussentekst: ['Eerst de catalogus.', 'Nu de tabel.'], done: true, interrupted: true },
      { id: 3, role: 'assistant', content: '', tools: [stap], tussentekst: ['Ik zoek eerst.'], done: false },
    ])
    expect(eerder).toMatchObject({ content: 'Nu de tabel.', tussentekst: ['Eerst de catalogus.'], interrupted: true })
    expect(zonder).toMatchObject({ content: 'Ik zoek eerst.', tussentekst: [], done: true, interrupted: true })
  })

  it('laat de tussentekst van een afgerond of gestopt antwoord in de redeneerkaart', () => {
    const stap = { name: 'search_catalog', label: 'Catalogus doorzoeken', done: true }
    const klaar = { id: 2, role: 'assistant', content: 'Klaar.', tools: [stap], tussentekst: ['Eerst de catalogus.'], done: true }
    const gestopt = { id: 3, role: 'assistant', content: '', tools: [stap], tussentekst: ['Eerst de catalogus.'], done: true, stopped: true }
    expect(restorableMessages([klaar, gestopt])).toEqual([klaar, gestopt])
  })

  const { messages } = herstelClarify
  const restored = restorableMessages(messages)

  it('keeps only what the chat itself showed', () => {
    expect(restored.map(m => m.id)).toEqual([1, 2, 3, 4, 5])
  })

  it('shows no tool results, OK or catalogue JSON', () => {
    const text = restored.map(m => m.content).join('\n')
    expect(text).not.toMatch(/_ckan_id|^OK$/m)
    expect(restored.some(m => m.tool_calls)).toBe(false)
  })

  it('leaves no assistant message that renders as an empty or typing bubble', () => {
    const empty = restored.filter(m => m.role === 'assistant' && !m.content && !m.figures?.length && !m.tools?.length)
    expect(empty).toEqual([])
  })

  it('keeps the card answered after a reload', () => {
    const card = restored.findIndex(m => m.clarification)
    expect(clarificationAnswer(restored, card)).toEqual({ answered: true, choice: '2023/24' })
    expect(hasOpenClarification(restored)).toBe(false)
  })

  it('applies to the chat that was open before the reload', () => {
    persistCurrentChat('conv-a', messages)
    expect(loadCurrentChat().messages).toEqual(restored)
  })
})

// #511: een vol quotum bewaarde niets en zei niets.
describe('persistCurrentChat bij een volle opslag', () => {
  afterEach(() => vi.restoreAllMocks())

  it('valt terug op het gesprek zonder figuren', () => {
    let eersteGooit = true
    const echt = Storage.prototype.setItem
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (key, value) {
      if (eersteGooit) { eersteGooit = false; throw new DOMException('vol', 'QuotaExceededError') }
      return echt.call(this, key, value)
    })

    const uitkomst = persistCurrentChat('c1', [
      { id: 1, role: 'user', content: 'vraag', done: true },
      { id: 2, role: 'assistant', content: '', figures: [{ json: 'x'.repeat(100) }], done: true },
    ])

    expect(uitkomst).toBe('zonder_figuren')
    const bewaard = JSON.parse(localStorage.getItem('openEDUdata_current_chat'))
    expect(bewaard.messages).toHaveLength(1)
    expect(bewaard.messages[0].content).toBe('vraag')
  })

  // #521: zonder vlag kwam een gesprek zonder grafieken terug alsof het compleet was.
  it('markeert de terugval als onvolledig en leest dat terug', () => {
    let eersteGooit = true
    const echt = Storage.prototype.setItem
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (key, value) {
      if (eersteGooit) { eersteGooit = false; throw new DOMException('vol', 'QuotaExceededError') }
      return echt.call(this, key, value)
    })

    persistCurrentChat('c1', [question, answer])

    expect(loadCurrentChat()).toEqual({ id: 'c1', messages: [question], onvolledig: true })
  })

  it('zegt het wanneer ook de terugval niet past', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('vol', 'QuotaExceededError') })
    expect(persistCurrentChat('c1', [{ id: 1, role: 'user', content: 'vraag', done: true }])).toBe('mislukt')
  })

  // #521: een oudere momentopname kwam na verversen terug alsof die actueel was.
  it('laat bij mislukt geen oudere momentopname achter', () => {
    persistCurrentChat('oud', [question])
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('vol', 'QuotaExceededError') })

    expect(persistCurrentChat('c1', [question, answer])).toBe('mislukt')
    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
  })

  it('gooit niet wanneer ook het wissen faalt', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('vol', 'QuotaExceededError') })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('kapot') })
    expect(persistCurrentChat('c1', [question])).toBe('mislukt')
  })

  it('geeft ok terug wanneer het past', () => {
    expect(persistCurrentChat('c1', [{ id: 1, role: 'user', content: 'vraag', done: true }])).toBe('ok')
  })
})
