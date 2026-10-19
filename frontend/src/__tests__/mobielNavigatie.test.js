// @vitest-environment jsdom
// #596: op een telefoon nam alles om de berichten heen (kop, gesprekkenbalk, actierij, invoerkader met
// modelkiezer, disclaimer, tabbalk) 59 % van het scherm in. Nu is er één bovenrij met een menu, staan de
// knoppen van de chat in die rij, is het invoerkader een pil en staat de disclaimer alleen op de homepage
// en op desktop. Deze tests leggen vast wat daarvoor nodig is; de hoogtes zijn gemeten in de MR.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const api = vi.hoisted(() => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
vi.mock('react-plotly.js', () => ({ default: () => null }))
vi.mock('react-markdown', () => ({ default: ({ children }) => children }))

const chat = vi.hoisted(() => ({ messages: [] }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import Nav from '../components/Nav'
import Composer, { PLACEHOLDER_COMPACT } from '../components/Composer'
import ChatPage from '../pages/ChatPage'
import { EXTERNE_AI_MELDING } from '../components/ChatNavActies'
import { NavSlotContext } from '../navSlot'
import { PERSOONSGEGEVENS_WAARSCHUWING } from '../persoonsgegevens'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const smal = vi.hoisted(() => ({ aan: false }))
window.matchMedia = q => ({
  matches: smal.aan && q === '(max-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {},
})

let root
let container

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  smal.aan = false
  chat.messages = []
})

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const knop = naam => container.querySelector(`button[aria-label="${naam}"]`)
const klik = async el => { await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })) }) }
const toets = async key => { await act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })) }) }

const nav = (props = {}) => createElement(MemoryRouter, { initialEntries: ['/chat'] },
  createElement(Nav, { user: 'tester', onLogout: vi.fn(), onOpenSettings: vi.fn(), instelling: 'HU', ...props }))

describe('menu in de navbar (vervangt de tabbalk)', () => {
  it('is dicht tot je de menuknop gebruikt, en toont dan alle bestemmingen', async () => {
    await render(nav())
    expect(container.querySelector('#navbar-menu')).toBeNull()
    expect(knop('Menu').getAttribute('aria-expanded')).toBe('false')

    await klik(knop('Menu'))
    const menu = container.querySelector('#navbar-menu')
    expect(knop('Menu').getAttribute('aria-expanded')).toBe('true')
    expect([...menu.querySelectorAll('a')].map(a => a.textContent)).toEqual(['Home', 'Chat', 'Rapporten', 'Dashboard'])
    expect(menu.querySelector('a[aria-current="page"]').textContent).toBe('Chat')
  })

  it('heeft instellingen, bronnen, privacy en uitloggen: wat uit de chat en de navbar is gehaald', async () => {
    await render(nav())
    await klik(knop('Menu'))
    const items = [...container.querySelectorAll('#navbar-menu button, #navbar-menu a')].map(e => e.textContent)
    expect(items.some(t => t.startsWith('Instellingen') && t.includes('HU · tester'))).toBe(true)
    expect(items).toContain('Gebaseerd op open onderwijsdata')
    expect(items).toContain('Privacy-informatie')
    expect(items).toContain('Uitloggen')
  })

  it('laat Dashboard weg als de pagina uit staat, ook in de balk op desktop', async () => {
    await render(nav({ dashboardsEnabled: false }))
    await klik(knop('Menu'))
    expect(container.textContent).not.toContain('Dashboard')
  })

  it('sluit met Escape en geeft de focus aan de knop terug', async () => {
    await render(nav())
    await klik(knop('Menu'))
    await toets('Escape')
    expect(container.querySelector('#navbar-menu')).toBeNull()
    expect(document.activeElement).toBe(knop('Menu'))
  })

  it('een tik naast het menu sluit het', async () => {
    await render(nav())
    await klik(knop('Menu'))
    await klik(container.querySelector('.navbar-menu-overlay'))
    expect(container.querySelector('#navbar-menu')).toBeNull()
  })

  it('opent instellingen en sluit zichzelf', async () => {
    const onOpenSettings = vi.fn()
    await render(nav({ onOpenSettings }))
    await klik(knop('Menu'))
    await klik([...container.querySelectorAll('#navbar-menu button')].find(b => b.textContent.startsWith('Instellingen')))
    expect(onOpenSettings).toHaveBeenCalledTimes(1)
    expect(container.querySelector('#navbar-menu')).toBeNull()
  })
})

function Pagina({ user = 'tester', feedbackEnabled = false }) {
  const [slot, setSlot] = useState(null)
  return createElement(MemoryRouter, null,
    createElement(Nav, { user, slotRef: setSlot }),
    createElement(NavSlotContext.Provider, { value: slot }, createElement(ChatPage, { user, feedbackEnabled })))
}

describe('de chat op een telefoon', () => {
  it('zet de gesprekkenknop in de navbar, niet in een tweede balk', async () => {
    smal.aan = true
    await render(createElement(Pagina))
    expect(container.querySelector('.chat-mobile-topbar')).toBeNull()
    expect(container.querySelector('.navbar-pagina').contains(knop('Gesprekken en suggesties'))).toBe(true)
  })

  it('toont het ⋯-menu pas als er een gesprek is', async () => {
    smal.aan = true
    await render(createElement(Pagina))
    expect(knop('Meer acties')).toBeNull()
  })

  it('biedt het exporteren van het gesprek aan in het ⋯-menu, zodra er berichten zijn', async () => {
    smal.aan = true
    chat.messages = [
      { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true },
      { id: 2, role: 'assistant', content: 'Veel.', done: true, tools: [] },
    ]
    await render(createElement(Pagina))
    await klik(knop('Meer acties'))
    const menu = container.querySelector('#navbar-meer-menu')
    expect(menu.textContent).toContain('Exporteer gesprek')
    // De vaste actierij boven het invoerveld is er op een telefoon niet meer.
    expect(container.querySelector('.chat-actions')).toBeNull()
  })

  // #608: met de disclaimer verdwenen op een telefoon (#596) waren ook de externe-AI-melding, de privacy-informatie
  // en de feedbacklink uit de chat weg. Ze staan nu in het ⋯-menu: twee tikken vanuit een lopend gesprek.
  it('zet de externe-AI-melding, privacy-informatie en feedback in het ⋯-menu', async () => {
    smal.aan = true
    chat.messages = [
      { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true },
      { id: 2, role: 'assistant', content: 'Veel.', done: true, tools: [] },
    ]
    await render(createElement(Pagina, { feedbackEnabled: true }))
    await klik(knop('Meer acties'))
    const menu = container.querySelector('#navbar-meer-menu')
    expect(menu.querySelector('.navbar-meer-noot').textContent).toBe(EXTERNE_AI_MELDING)
    expect(EXTERNE_AI_MELDING).toContain('externe AI-dienst')
    const items = [...menu.querySelectorAll('.navbar-menu-item')].map(k => k.textContent)
    expect(items).toEqual(['Privacy-informatie', 'Geef feedback'])
    // Tik twee (na het menu): het feedbackformulier.
    await klik([...menu.querySelectorAll('.navbar-menu-item')].find(k => k.textContent === 'Geef feedback'))
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Feedback over openEDUdata+')
  })

  it('laat de feedbackknop weg uit het ⋯-menu als het formulier uitstaat', async () => {
    smal.aan = true
    chat.messages = [
      { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true },
      { id: 2, role: 'assistant', content: 'Veel.', done: true, tools: [] },
    ]
    await render(createElement(Pagina))
    await klik(knop('Meer acties'))
    const items = [...container.querySelectorAll('#navbar-meer-menu .navbar-menu-item')].map(k => k.textContent)
    expect(items).toEqual(['Privacy-informatie'])
  })

  it('toont geen disclaimer onder het invoerveld, en de privacyzin staat in de placeholder', async () => {
    smal.aan = true
    await render(createElement(Pagina))
    expect(container.querySelector('.chat-disclaimer')).toBeNull()
    expect(container.querySelector('textarea.chat-input').placeholder).toBe(PLACEHOLDER_COMPACT)
    expect(PLACEHOLDER_COMPACT.toLowerCase()).toContain('persoonsgegevens')
  })

  it('houdt op desktop de disclaimer, de actierij en de bekende placeholder', async () => {
    chat.messages = [
      { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true },
      { id: 2, role: 'assistant', content: 'Veel.', done: true, tools: [] },
    ]
    await render(createElement(Pagina))
    expect(container.querySelector('.chat-disclaimer').textContent).toContain(PERSOONSGEGEVENS_WAARSCHUWING)
    expect(container.querySelector('.chat-actions')).not.toBeNull()
    expect(container.querySelector('textarea.chat-input').placeholder).toBe('Stel een vervolgvraag...')
  })
})

describe('invoerkader als pil', () => {
  const modellen = [{ id: 'a', name: 'Model A', provider: 'Microsoft Azure AI Foundry' }]
  const props = {
    hasMessages: false, connected: true, busy: false, models: modellen, selectedModel: 'a',
    onModelChange: () => {}, onStop: () => {}, onSubmit: () => true, max: 4000, rejectedDraft: null,
    clearRejectedDraft: () => {},
  }

  it('toont de modelkiezer en de providerregel in het kader op desktop', async () => {
    await render(createElement(Composer, props))
    expect(container.querySelector('.chat-input-footer .model-picker-provider').textContent).toBe('Via Microsoft Azure AI Foundry')
  })

  it('laat ze compact weg: de keuze staat dan in de drawer', async () => {
    await render(createElement(Composer, { ...props, compact: true }))
    expect(container.querySelector('.model-picker')).toBeNull()
    expect(container.querySelector('.send-btn')).not.toBeNull()
  })
})

describe('stijlen', () => {
  const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')

  it('kent de tabbalk en de focusklasse ervoor niet meer', () => {
    expect(css).not.toMatch(/\.mobile-tab/)
    expect(css).not.toMatch(/invoer-actief/)
    expect(css).not.toMatch(/--mobile-tabs-h/)
  })

  it('maakt de navbar op een telefoon 52 px en de chat even hoog als de rest van het scherm', () => {
    expect(css).toMatch(/:root \{ --navbar-h: 52px; \}/)
    expect(css).toMatch(/\.chat-layout \{[^}]*height: calc\(100dvh - var\(--navbar-h\)\)/)
  })

  it('geeft de voortgang op een telefoon geen hoogte: er is niets dat het invoerveld laat verspringen', () => {
    expect(css).toMatch(/\.chat-statusrij \{ min-height: 0; height: 0; position: relative; \}/)
  })
})
