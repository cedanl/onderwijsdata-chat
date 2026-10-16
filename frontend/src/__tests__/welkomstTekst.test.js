// @vitest-environment jsdom
// #591 (mobiel B9): het welkomstscherm zette "Anders" als functienaam in de zin ("Als Anders krijg je …"),
// en de functie Docent ontbrak. Een functie komt alleen in de zin als het er een uit de lijst is.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { STORAGE_SETTINGS } from '../constants'
import { FUNCTIES, welkomstSub } from '../functies'

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
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'
import SettingsModal from '../components/SettingsModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const ROLLEN = ['Bestuurder', 'Directeur', 'Beleidsmedewerker', 'Onderzoeker', 'Docent']
const ALGEMEEN = 'Vraag wat je wilt weten over instroom, voortgang, arbeidsmarkt of diplomering. Ik combineer open data ' +
  'van CBS, DUO en RIO en geef je een onderbouwd antwoord.'
const ZONDER_ROL = ['Anders', '', undefined, null, 'Rector', 'anders']

describe('FUNCTIES (#591)', () => {
  it('heeft Docent, vóór Anders', () => {
    expect(FUNCTIES).toEqual(['Bestuurder', 'Directeur', 'Beleidsmedewerker', 'Onderzoeker', 'Docent', 'Anders'])
  })
})

describe('welkomstSub (#591)', () => {
  it.each(ROLLEN)('noemt %s met een kleine letter midden in de zin', rol => {
    expect(welkomstSub(rol)).toBe(`Als ${rol.toLowerCase()} krijg je onderbouwde antwoorden over instroom, voortgang, ` +
      'arbeidsmarkt en diplomering — direct uit open onderwijsdata.')
  })

  it.each(ZONDER_ROL)('geeft bij %j de zin zonder functie', functie => {
    expect(welkomstSub(functie)).toBe(ALGEMEEN)
  })

  it.each([...ROLLEN, ...ZONDER_ROL])('zegt bij %j nooit "Als Anders"', functie => {
    expect(welkomstSub(functie)).not.toMatch(/als anders/i)
  })
})

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  if (!root) return
  act(() => root.unmount())
  container.remove()
  root = null
})

describe('het welkomstscherm (#591)', () => {
  it.each([...ROLLEN, 'Anders'])('toont bij functie %s de tekst van welkomstSub', async functie => {
    await render(createElement(ChatPage, { settings: { functie }, user: 'gast' }))
    expect(container.querySelector('.chat-welcome p').textContent).toBe(welkomstSub(functie))
  })
})

// Zoals App de instellingen leest (loadSettings): wat er in de browser staat, ongecontroleerd.
const opgeslagen = () => JSON.parse(localStorage.getItem(STORAGE_SETTINGS) || '{}')
const functieKnoppen = () => [...container.querySelectorAll('[aria-labelledby="settings-functie-label"] button')]
const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent === tekst)

describe('een opgeslagen oude functie (#591)', () => {
  it.each([['{"functie":"Rector"}'], ['{}']])('%s laadt het welkomstscherm zonder fout', async json => {
    localStorage.setItem(STORAGE_SETTINGS, json)
    await render(createElement(ChatPage, { settings: opgeslagen(), user: 'gast' }))
    expect(container.querySelector('.chat-welcome p').textContent).toBe(ALGEMEEN)
  })

  it.each([['{"functie":"Rector"}'], ['{}']])('%s opent de instellingen zonder gekozen functie, en opslaan werkt', async json => {
    localStorage.setItem(STORAGE_SETTINGS, json)
    const onSave = vi.fn()
    await render(createElement(SettingsModal, { settings: opgeslagen(), onSave, onClose: vi.fn() }))

    expect(functieKnoppen().map(b => b.textContent)).toEqual(FUNCTIES)
    expect(functieKnoppen().filter(b => b.getAttribute('aria-pressed') === 'true')).toEqual([])

    await act(async () => knop('Opslaan').click())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ functie: '' }))
  })
})
