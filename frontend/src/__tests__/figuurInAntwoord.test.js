// @vitest-environment jsdom
// #610: een grafiek komt als eigen bericht na het antwoord binnen en stond daardoor ónder de bubbel. Zodra
// de vaste blokken, vervolgvragen en feedback aan het eind van het antwoord landden, schoof hij op een
// telefoon 360 px omlaag (CLS 0,38). Nu staat hij in de bubbel van het antwoord, vóór die blokken.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

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

const chat = vi.hoisted(() => ({ messages: [], busy: false }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'
import { groepeerFiguren, isFiguurBericht } from '../figuurGroep'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
const scherm = vi.hoisted(() => ({ smal: false }))
window.matchMedia = q => ({ matches: scherm.smal && q === '(max-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {} })

const FIG = JSON.stringify({ data: [{ type: 'bar', x: [2023, 2024], y: [1, 2] }], layout: { title: { text: 'Studenten' } } })
const vraag = { id: 1, role: 'user', content: 'Hoeveel mbo-studenten per jaar?', done: true, model: 'm1' }
const antwoord = {
  id: 2, role: 'assistant', content: 'Er waren 475.460 studenten.', done: true,
  tools: [{ name: 'get_cbs_data', label: 'CBS data opgehaald', done: true }],
  bronnen: ['CBS · Mbo; studenten (85354NED)'], citaties: [], vervolgvragen: ['En in 2021?'],
}
const grafiek = { id: 3, role: 'assistant', content: '', figures: [{ label: 'Grafiek aangemaakt', json: FIG }], done: true }

describe('groepeerFiguren', () => {
  it('vouwt het grafiekbericht direct na een antwoord in dat antwoord', () => {
    const rijen = groepeerFiguren([vraag, antwoord, grafiek])
    expect(rijen.map(r => r.msg.id)).toEqual([1, 2])
    expect(rijen[1]).toMatchObject({ index: 1, laatsteId: 3, gevouwen: 1 })
    expect(rijen[1].figures).toHaveLength(1)
  })

  it('houdt twee grafieken van één antwoord bij elkaar, in volgorde', () => {
    const tweede = { ...grafiek, id: 4, figures: [{ label: 'Tweede', json: FIG }] }
    const [, rij] = groepeerFiguren([vraag, antwoord, grafiek, tweede])
    expect(rij.figures.map(f => f.label)).toEqual(['Grafiek aangemaakt', 'Tweede'])
    expect(rij.laatsteId).toBe(4)
  })

  it('laat een grafiek zonder antwoord ervoor als eigen bericht staan', () => {
    expect(groepeerFiguren([vraag, grafiek]).map(r => r.msg.id)).toEqual([1, 3])
    // Een grafiek achter een ander grafiekbericht: niets om in te vouwen.
    expect(groepeerFiguren([grafiek, { ...grafiek, id: 4 }]).map(r => r.msg.id)).toEqual([3, 4])
  })

  it('kent een grafiekbericht aan zijn vorm: alleen figuren, geen tekst, stappen of fout', () => {
    expect(isFiguurBericht(grafiek)).toBe(true)
    expect(isFiguurBericht({ ...grafiek, content: 'tekst' })).toBe(false)
    expect(isFiguurBericht({ ...grafiek, tools: [{ name: 'create_plot' }] })).toBe(false)
    expect(isFiguurBericht(antwoord)).toBe(false)
  })
})

describe('de grafiek in de bubbel van het antwoord', () => {
  let root
  let container

  afterEach(async () => {
    if (root) await act(async () => root.unmount())
    container?.remove()
    root = null
    chat.messages = []
    chat.busy = false
    scherm.smal = false
  })

  // Een tweede aanroep tekent dezelfde pagina opnieuw, met wat chat dan bevat (een volgende stand van de stream).
  async function render() {
    if (!root) {
      container = document.createElement('div')
      document.body.appendChild(container)
      root = createRoot(container)
    }
    const pagina = createElement(MemoryRouter, { initialEntries: ['/chat'] },
      createElement(ChatPage, { user: 'tester', feedbackEnabled: true, openRapport: vi.fn() }))
    await act(async () => { root.render(pagina) })
  }

  it('toont één antwoordbericht met de grafiek vóór de blokken en de vervolgvragen', async () => {
    chat.messages = [vraag, antwoord, grafiek]
    await render()
    const berichten = container.querySelectorAll('.message.assistant')
    expect(berichten).toHaveLength(1)
    const bubbel = berichten[0].querySelector('.message-bubble-assistant')
    const kinderen = [...bubbel.children].map(k => k.className)
    const grafiekPlek = kinderen.findIndex(c => c.includes('plotly-figure-wrap'))
    const blokkenPlek = kinderen.findIndex(c => c.includes('answer-blocks'))
    const vervolgPlek = kinderen.findIndex(c => c.includes('question-buttons'))
    expect(grafiekPlek).toBeGreaterThan(-1)
    expect(blokkenPlek).toBeGreaterThan(grafiekPlek)
    expect(vervolgPlek).toBeGreaterThan(grafiekPlek)
  })

  it('houdt het modeletiket van de beurt, dat aan het grafiekbericht hing, één keer onder het antwoord', async () => {
    chat.messages = [vraag, antwoord, grafiek]
    await render()
    const etiketten = [...container.querySelectorAll('.message-model')].map(e => e.textContent)
    expect(etiketten).toHaveLength(1)
    expect(etiketten[0]).toMatch(/^Antwoord van /)
  })

  // #639: de grafiek komt binnen vóór de eindtekst; onder de gestreamde regels schoof ze steeds omlaag (CLS 0,096).
  it('toont de grafiek op een telefoon pas als het antwoord compleet is', async () => {
    scherm.smal = true
    chat.messages = [vraag, { ...antwoord, content: 'Er waren', done: false }, grafiek]
    chat.busy = true
    await render()
    expect(container.querySelectorAll('.message.assistant')).toHaveLength(1)
    expect(container.querySelector('.plotly-figure-wrap')).toBeNull()
    chat.messages = [vraag, antwoord, grafiek]
    chat.busy = false
    await render()
    expect(container.querySelector('.plotly-figure-wrap')).not.toBeNull()
  })

  // #808: de grafiek is er al terwijl de tekst nog moet komen. Telde ze als volgend bericht, dan stond de CSV-knop
  // al in een bubbel zonder tekst; die bubbel sprong 158 px omhoog toen de redenering bij de eerste regel inklapte,
  // en daarna schoof de knop met elke gestreamde regel omlaag (CLS 0,073–0,105 op 390 px).
  it('zet op een telefoon niets onder een antwoord dat nog streamt, ook als zijn grafiek er al is', async () => {
    scherm.smal = true
    const metTabel = { ...antwoord, tools: [{ ...antwoord.tools[0], exportKey: 'cbs:85354NED:0:ab' }] }
    const lopend = { ...metTabel, content: '', done: false, bronnen: undefined, citaties: undefined, vervolgvragen: undefined }
    chat.messages = [vraag, lopend, grafiek]
    chat.busy = true
    await render()
    // Vóór de eerste regel: alleen de redenering, nog geen bubbel die bij het inklappen kan verspringen.
    expect(container.querySelector('.reasoning-panel')).not.toBeNull()
    expect(container.querySelector('.message-bubble-assistant')).toBeNull()

    chat.messages = [vraag, { ...lopend, content: 'Er waren' }, grafiek]
    await render()
    const bubbel = container.querySelector('.message-bubble-assistant')
    expect(bubbel.textContent).toContain('Er waren')
    expect(bubbel.querySelector('.data-export, .answer-blocks, .plotly-figure-wrap')).toBeNull()

    // Klaar: alles landt in één keer onder de tekst, de grafiek eerst.
    chat.messages = [vraag, metTabel, grafiek]
    chat.busy = false
    await render()
    const kinderen = [...container.querySelector('.message-bubble-assistant').children].map(k => k.className)
    const grafiekPlek = kinderen.findIndex(c => c.includes('plotly-figure-wrap'))
    expect(grafiekPlek).toBeGreaterThan(-1)
    expect(kinderen.findIndex(c => c.includes('answer-blocks'))).toBeGreaterThan(grafiekPlek)
    expect(container.querySelector('.answer-blocks .data-export')).not.toBeNull()
  })

  it('toont de grafiek op een breed scherm al tijdens het antwoord', async () => {
    chat.messages = [vraag, { ...antwoord, content: 'Er waren', done: false }, grafiek]
    chat.busy = true
    await render()
    expect(container.querySelector('.plotly-figure-wrap')).not.toBeNull()
  })

  it('laat een grafiek zonder antwoord ervoor als eigen bericht staan', async () => {
    chat.messages = [vraag, grafiek]
    await render()
    expect(container.querySelectorAll('.message.assistant')).toHaveLength(1)
    expect(container.querySelector('.plotly-figure-wrap')).not.toBeNull()
  })
})
