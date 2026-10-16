// @vitest-environment jsdom
// #585 (mobiel B10): een tik op de grijze verstuurknop deed stil niets. Nu zegt één live region bij de
// composer waarom versturen niet kan; de knop blijft aria-disabled en dus in de Tab-volgorde.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MAX_CHAT_TURNS, MAX_MESSAGE_CHARS } from '../constants'

vi.mock('../api', async importOriginal => ({
  ...await importOriginal(),
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const chat = vi.hoisted(() => ({ messages: [], resetting: false, reportBusy: false, send: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: chat.resetting, historyDataKeys: 0, toasts: [], reportBusy: chat.reportBusy,
    reportProgress: { steps: 0, label: null },
    reportSpec: null, send: chat.send, sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import Composer from '../components/Composer'
import ChatPage from '../pages/ChatPage'
import { SEND_NOTICE_MS } from '../components/SendNotice'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const BASIS = {
  hasMessages: true, connected: true, busy: false, resetting: false, reportBusy: false, atContextLimit: false,
  models: [], selectedModel: '', onModelChange: () => {}, max: MAX_MESSAGE_CHARS, rejectedDraft: null, clearRejectedDraft: () => {},
}

let root
let container
let props

async function mount(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

async function renderComposer(extra = {}) {
  props = { ...BASIS, onStop: vi.fn(), onSubmit: vi.fn(() => true), ...extra }
  await mount(createElement(Composer, props))
}

async function rerender(extra) {
  props = { ...props, ...extra }
  await act(async () => { root.render(createElement(Composer, props)) })
}

const textarea = () => container.querySelector('textarea.chat-input')
const notice = () => container.querySelector('.chat-input-wrap [role="status"][aria-live="polite"].send-notice')
const sendBtn = () => container.querySelector('.send-btn')

async function typ(tekst) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(textarea(), tekst)
    textarea().dispatchEvent(new Event('input', { bubbles: true }))
  })
}
const tik = () => act(async () => sendBtn().click())
const enter = () => act(async () => {
  textarea().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
})
// Hoe vaak een tekst als eigen tekstknoop op de pagina staat: een reden hoort er één keer te staan.
const keerOpPagina = tekst => [...container.querySelectorAll('*')]
  .filter(el => [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent === tekst)).length

beforeEach(() => {
  localStorage.clear()
  chat.messages = []
  chat.resetting = false
  chat.reportBusy = false
  chat.send = vi.fn(() => true)
})

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = null
  vi.useRealTimers()
})

describe('de live region (#585)', () => {
  it('staat er leeg vanaf de eerste render, in de composer maar buiten de footer', async () => {
    await renderComposer()
    const regio = notice()
    expect(regio).not.toBeNull()
    expect(regio.textContent).toBe('')
    expect(regio.closest('.chat-input-footer')).toBeNull()
  })

  it('houdt de reden na een tik in hetzelfde element', async () => {
    await renderComposer()
    const regio = notice()
    await tik()
    expect(notice()).toBe(regio)
    expect(regio.textContent).toBe('Typ eerst een vraag')
    expect(keerOpPagina('Typ eerst een vraag')).toBe(1)
  })
})

describe('de reden bij een tik of Enter (#585)', () => {
  it('leeg concept: "Typ eerst een vraag", ook bij alleen spaties', async () => {
    await renderComposer()
    await tik()
    expect(notice().textContent).toBe('Typ eerst een vraag')

    await typ('   ')
    await enter()
    expect(notice().textContent).toBe('Typ eerst een vraag')
    expect(props.onSubmit).not.toHaveBeenCalled()
  })

  it('geen verbinding: "Geen verbinding"', async () => {
    await renderComposer({ connected: false })
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Geen verbinding')
    expect(props.onSubmit).not.toHaveBeenCalled()
  })

  it('te lang: "Bericht te lang"', async () => {
    await renderComposer({ max: 10 })
    await typ('x'.repeat(11))
    await tik()
    expect(notice().textContent).toBe('Bericht te lang')
    expect(textarea().value).toBe('x'.repeat(11))
  })

  it('Enter terwijl een antwoord loopt: "Even wachten: het vorige antwoord is nog bezig"', async () => {
    await renderComposer({ busy: true })
    await typ('Nog een vraag')
    await enter()
    expect(notice().textContent).toBe('Even wachten: het vorige antwoord is nog bezig')
    expect(props.onSubmit).not.toHaveBeenCalled()
  })

  it.each([
    ['een nieuw gesprek dat start', { resetting: true }, 'Even wachten: het nieuwe gesprek wordt gestart'],
    ['een rapport dat wordt gemaakt', { reportBusy: true }, 'Even wachten: er wordt een rapport gemaakt'],
    ['een volle chat', { atContextLimit: true }, 'Chat is vol: begin een nieuw gesprek'],
  ])('%s', async (_naam, staat, verwacht) => {
    await renderComposer(staat)
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe(verwacht)
    expect(props.onSubmit).not.toHaveBeenCalled()
  })

  it('een geweigerde vraag (send() gaf false) krijgt ook een reden, en het concept blijft', async () => {
    await renderComposer({ onSubmit: vi.fn(() => false) })
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Even wachten: probeer het zo opnieuw')
    expect(textarea().value).toBe('Hoeveel studenten?')
  })
})

describe('de gewone toestand (#585)', () => {
  it('verstuurt het getrimde concept, maakt het leeg en zegt niets', async () => {
    await renderComposer()
    await typ('  Hoeveel studenten?  ')
    await tik()
    expect(props.onSubmit).toHaveBeenCalledWith('Hoeveel studenten?')
    expect(textarea().value).toBe('')
    expect(notice().textContent).toBe('')
  })

  it('een geslaagde vraag haalt een melding weg die nog staat', async () => {
    const onSubmit = vi.fn().mockReturnValueOnce(false).mockReturnValue(true)
    await renderComposer({ onSubmit })
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Even wachten: probeer het zo opnieuw')

    await tik()
    expect(onSubmit).toHaveBeenCalledTimes(2)
    expect(notice().textContent).toBe('')
  })
})

describe('de melding gaat weg (#585)', () => {
  it(`na ${SEND_NOTICE_MS} ms`, async () => {
    expect(SEND_NOTICE_MS).toBe(4000)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await renderComposer()
    await tik()
    await act(async () => vi.advanceTimersByTime(SEND_NOTICE_MS - 1))
    expect(notice().textContent).toBe('Typ eerst een vraag')
    await act(async () => vi.advanceTimersByTime(1))
    expect(notice().textContent).toBe('')
  })

  it('een nieuwe tik start de tijd opnieuw', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await renderComposer()
    await tik()
    await act(async () => vi.advanceTimersByTime(3000))
    await tik()
    await act(async () => vi.advanceTimersByTime(3000))
    expect(notice().textContent).toBe('Typ eerst een vraag')
    await act(async () => vi.advanceTimersByTime(1000))
    expect(notice().textContent).toBe('')
  })

  it('de timer stopt bij unmount', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await renderComposer()
    await tik()
    expect(vi.getTimerCount()).toBe(1)
    act(() => root.unmount())
    root = null
    expect(vi.getTimerCount()).toBe(0)
  })

  it('typen haalt "Typ eerst een vraag" meteen weg, en hij komt niet terug zonder tik', async () => {
    await renderComposer()
    await tik()
    await typ('H')
    expect(notice().textContent).toBe('')
    await typ('')
    expect(notice().textContent).toBe('')
  })

  it('de verbinding terug haalt "Geen verbinding" meteen weg', async () => {
    await renderComposer({ connected: false })
    await typ('Hoeveel studenten?')
    await tik()
    await rerender({ connected: true })
    expect(notice().textContent).toBe('')
    await rerender({ connected: false })
    expect(notice().textContent).toBe('')
  })

  it('een afgelopen antwoord haalt de wachttekst meteen weg', async () => {
    await renderComposer({ busy: true })
    await typ('Nog een vraag')
    await enter()
    await rerender({ busy: false })
    expect(notice().textContent).toBe('')
  })
})

describe('de verstuurknop (#585)', () => {
  const blokkades = [
    ['leeg', {}, ''],
    ['geen verbinding', { connected: false }, 'vraag'],
    ['te lang', { max: 3 }, 'vraag'],
    ['een nieuw gesprek dat start', { resetting: true }, 'vraag'],
    ['een rapport', { reportBusy: true }, 'vraag'],
    ['een volle chat', { atContextLimit: true }, 'vraag'],
  ]

  it.each(blokkades)('is aria-disabled bij %s, nooit disabled', async (_naam, staat, concept) => {
    await renderComposer(staat)
    await typ(concept)
    expect(sendBtn().getAttribute('aria-disabled')).toBe('true')
    expect(sendBtn().hasAttribute('disabled')).toBe(false)
  })

  it('is niet aria-disabled als de vraag weg kan', async () => {
    await renderComposer()
    await typ('vraag')
    expect(sendBtn().getAttribute('aria-disabled')).toBe('false')
    expect(sendBtn().hasAttribute('disabled')).toBe(false)
  })

  it('wordt tijdens een antwoord de stopknop, die het antwoord stopt', async () => {
    await renderComposer({ busy: true })
    await tik()
    expect(props.onStop).toHaveBeenCalledOnce()
    expect(notice().textContent).toBe('')
  })
})

describe('ChatPage: elke weigering zegt waarom (#585)', () => {
  const page = () => createElement(ChatPage, { settings: {}, user: 'gast' })
  const vraag = { id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }

  it('heeft geen eigen melding boven de composer meer', async () => {
    chat.send = vi.fn(() => false)
    await mount(page())
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Even wachten: probeer het zo opnieuw')
    expect(keerOpPagina('Even wachten: probeer het zo opnieuw')).toBe(1)
    expect(container.querySelectorAll('.chat-input-area [role="status"].context-limit-banner')).toHaveLength(0)
  })

  it('na "Nieuw gesprek", terwijl het gesprek nog start', async () => {
    chat.resetting = true
    await mount(page())
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Even wachten: het nieuwe gesprek wordt gestart')
    expect(chat.send).not.toHaveBeenCalled()
  })

  it('terwijl een rapport wordt gemaakt', async () => {
    chat.reportBusy = true
    await mount(page())
    await typ('Hoeveel studenten?')
    await tik()
    expect(notice().textContent).toBe('Even wachten: er wordt een rapport gemaakt')
  })

  it('als de chat vol is', async () => {
    chat.messages = Array.from({ length: MAX_CHAT_TURNS }, (_, i) => [
      { id: 2 * i, role: 'user', content: `Vraag ${i}`, done: true },
      { id: 2 * i + 1, role: 'assistant', content: `Antwoord ${i}.`, tools: [], done: true },
    ]).flat()
    await mount(page())
    await typ('Nog een vraag')
    await tik()
    expect(notice().textContent).toBe('Chat is vol: begin een nieuw gesprek')
    expect(chat.send).not.toHaveBeenCalled()
  })

  it('als "Opnieuw" onder een fout geweigerd wordt', async () => {
    chat.messages = [vraag, { id: 2, role: 'assistant', content: 'Er ging iets mis.', isError: true, done: true }]
    chat.send = vi.fn(() => false)
    await mount(page())
    const opnieuw = [...container.querySelectorAll('button')].find(b => b.textContent === 'Opnieuw')

    await act(async () => opnieuw.click())

    expect(chat.send).toHaveBeenCalledWith('Hoeveel studenten?')
    expect(notice().textContent).toBe('Even wachten: probeer het zo opnieuw')
  })
})
