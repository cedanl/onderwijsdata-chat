// @vitest-environment jsdom
// #602: Ctrl/⌘K of de zoekknop in de kop opent één zoekveld over gesprekken en rapporten, met de zoeklogica
// die er al is: de server zoekt in titel en tekst van gesprekken (#124), de browser in rapporttitels (#562).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  fetchConversations: vi.fn(),
  fetchWorkbooks: vi.fn(),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))

import ZoekPalet from '../components/ZoekPalet'
import Nav from '../components/Nav'
import { isZoekSneltoets, sneltoetsHint, useZoekSneltoets } from '../hooks/useZoekSneltoets'
import { SEARCH_DELAY_MS } from '../hooks/useConversationSearch'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const NU = Date.now() / 1000
const GESPREKKEN = [
  { id: 'c1', title: 'Instroom hbo Utrecht', timestamp: NU },
  { id: 'c2', title: 'Uitval mbo', timestamp: NU - 86400 },
]
const WERKBOEKEN = [
  { id: 'r1', title: 'Instroom in het hbo', type: 'report', html_content: '<p/>', created_at: new Date().toISOString() },
  { id: 'd1', title: 'Instroom dashboard', type: 'dashboard', dashboard_spec: '{}', created_at: new Date().toISOString() },
  { id: 'r2', title: 'Diplomarendement wo', type: 'report', html_content: '<p/>', created_at: new Date().toISOString() },
]

let root
let container

beforeEach(() => {
  localStorage.clear()
  api.fetchConversations.mockImplementation(async ({ q }) => GESPREKKEN.filter(c => c.title.toLowerCase().includes(q.toLowerCase())))
  api.fetchWorkbooks.mockResolvedValue(WERKBOEKEN)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const palet = () => document.querySelector('[role="dialog"][aria-label="Zoeken"]')
const invoer = () => palet().querySelector('input[role="combobox"]')
const opties = () => [...palet().querySelectorAll('[role="option"]')]
const status = () => palet().querySelector('[role="status"]').textContent
const toets = (key, el = invoer()) => act(async () => { el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })) })

async function typ(tekst) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  await act(async () => {
    setter.call(invoer(), tekst)
    invoer().dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => { await new Promise(r => setTimeout(r, SEARCH_DELAY_MS + 50)) })
}

async function openPalet(props = {}) {
  const handlers = { onClose: vi.fn(), onOpenGesprek: vi.fn(), onOpenRapport: vi.fn(), ...props }
  await render(createElement(ZoekPalet, handlers))
  return handlers
}

describe('de sneltoets', () => {
  it('is Ctrl+K of ⌘K, zonder Alt of Shift', () => {
    expect(isZoekSneltoets({ key: 'k', ctrlKey: true })).toBe(true)
    expect(isZoekSneltoets({ key: 'K', metaKey: true })).toBe(true)
    expect(isZoekSneltoets({ key: 'k' })).toBe(false)
    expect(isZoekSneltoets({ key: 'k', ctrlKey: true, shiftKey: true })).toBe(false)
    expect(isZoekSneltoets({ key: 'j', ctrlKey: true })).toBe(false)
  })

  it('heeft een hint per platform', () => {
    expect(sneltoetsHint('MacIntel')).toBe('⌘K')
    expect(sneltoetsHint('Win32')).toBe('Ctrl K')
  })

  it('opent het palet en houdt de browser ervan af; zonder open-functie doet hij niets', async () => {
    const open = vi.fn()
    function Haak({ fn }) { useZoekSneltoets(fn); return null }
    await render(createElement(Haak, { fn: open }))
    const e = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true, cancelable: true })
    await act(async () => { document.dispatchEvent(e) })
    expect(open).toHaveBeenCalledTimes(1)
    expect(e.defaultPrevented).toBe(true)

    await act(async () => { root.render(createElement(Haak, { fn: null })) })
    await act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true })) })
    expect(open).toHaveBeenCalledTimes(1)
  })
})

describe('het zoekpalet', () => {
  it('opent met de focus in het zoekveld en een uitleg', async () => {
    await openPalet()
    expect(palet().getAttribute('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(invoer())
    expect(status()).toContain('Typ om te zoeken')
  })

  it('vindt een gesprek én een rapporttitel, geen dashboard', async () => {
    await openPalet()
    await typ('instroom')
    expect(api.fetchConversations).toHaveBeenCalledWith({ q: 'instroom', limit: 50 })
    const groepen = [...palet().querySelectorAll('[role="group"]')].map(g => [
      g.querySelector('.zoek-groep-kop').textContent, [...g.querySelectorAll('.zoek-optie-titel')].map(t => t.textContent),
    ])
    expect(groepen).toEqual([['Gesprekken', ['Instroom hbo Utrecht']], ['Rapporten', ['Instroom in het hbo']]])
    expect(status()).toBe('2 treffers')
  })

  it('gaat met de pijltjes door de treffers en opent met Enter', async () => {
    const h = await openPalet()
    await typ('instroom')
    expect(invoer().getAttribute('aria-activedescendant')).toBe(opties()[0].id)
    await toets('ArrowDown')
    expect(invoer().getAttribute('aria-activedescendant')).toBe(opties()[1].id)
    expect(opties()[1].getAttribute('aria-selected')).toBe('true')
    await toets('Enter')
    expect(h.onOpenRapport).toHaveBeenCalledWith('r1')
    await toets('ArrowDown')
    await toets('Enter')
    expect(h.onOpenGesprek).toHaveBeenCalledWith('c1')
  })

  it('opent een treffer met een klik of tik', async () => {
    const h = await openPalet()
    await typ('instroom')
    await act(async () => { opties()[0].click() })
    expect(h.onOpenGesprek).toHaveBeenCalledWith('c1')
  })

  it('zegt het als er niets is', async () => {
    await openPalet()
    await typ('vavo')
    expect(opties()).toEqual([])
    expect(status()).toBe('Niets gevonden')
  })

  it('toont de rapporten als gesprekken zoeken mislukt', async () => {
    api.fetchConversations.mockRejectedValue(new Error('HTTP 500'))
    await openPalet()
    await typ('instroom')
    expect(status()).toContain('Gesprekken zoeken lukt nu niet')
    expect(opties().map(o => o.querySelector('.zoek-optie-titel').textContent)).toEqual(['Instroom in het hbo'])
  })

  // #654: dezelfde vraag twee keer gesteld geeft twee gesprekken met één titel; de tijd houdt ze uit elkaar.
  it('toont bij gesprekken met dezelfde titel de tijd erbij', async () => {
    const d = new Date()
    const gisteren = (h, min) => new Date(d.getFullYear(), d.getMonth(), d.getDate() - 1, h, min).getTime() / 1000
    api.fetchConversations.mockResolvedValue([
      { id: 'c7', title: 'Instroom hbo', timestamp: gisteren(14, 32) },
      { id: 'c8', title: 'Instroom hbo', timestamp: gisteren(14, 42) },
    ])
    api.fetchWorkbooks.mockResolvedValue([])
    await openPalet()
    await typ('instroom')
    expect(opties().map(o => o.querySelector('.zoek-optie-titel').textContent)).toEqual(['Instroom hbo', 'Instroom hbo'])
    const [eerste, tweede] = opties().map(o => o.querySelector('.zoek-optie-datum').textContent)
    expect(eerste).not.toBe(tweede)
    expect(eerste).toMatch(/\d{2}:\d{2}$/)
    expect(tweede).toMatch(/\d{2}:\d{2}$/)
    expect([eerste, tweede]).toEqual(['Gisteren 14:32', 'Gisteren 14:42'])
  })

  it('toont bij een rapport ook datum en tijd, en niets zonder geldige datum', async () => {
    const d = new Date()
    api.fetchConversations.mockResolvedValue([])
    api.fetchWorkbooks.mockResolvedValue([
      { id: 'r5', title: 'Instroom 2024', type: 'report', html_content: '<p/>',
        created_at: new Date(d.getFullYear(), d.getMonth(), d.getDate(), 9, 5).toISOString() },
      { id: 'r6', title: 'Instroom zonder datum', type: 'report', html_content: '<p/>', created_at: 'onbekend' },
    ])
    await openPalet()
    await typ('instroom')
    const rij = titel => opties().find(o => o.querySelector('.zoek-optie-titel').textContent === titel)
    expect(rij('Instroom 2024').querySelector('.zoek-optie-datum').textContent).toBe('Vandaag 09:05')
    expect(rij('Instroom zonder datum').querySelector('.zoek-optie-datum')).toBeNull()
  })

  it('sluit met Escape', async () => {
    const h = await openPalet()
    await act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })) })
    expect(h.onClose).toHaveBeenCalled()
  })
})

describe('de zoekknop in de kop', () => {
  it('opent het palet en toont de sneltoets', async () => {
    const onZoek = vi.fn()
    await render(createElement(MemoryRouter, null, createElement(Nav, { user: 'gast', onZoek })))
    const knop = container.querySelector('button[aria-label="Zoeken"]')
    expect(knop.querySelector('kbd').textContent).toMatch(/K$/)
    expect(knop.getAttribute('aria-keyshortcuts')).toBe('Control+K Meta+K')
    await act(async () => { knop.click() })
    expect(onZoek).toHaveBeenCalled()
  })

  it('ontbreekt zonder palet (voor het inloggen)', async () => {
    await render(createElement(MemoryRouter, null, createElement(Nav, { user: null })))
    expect(container.querySelector('button[aria-label="Zoeken"]')).toBeNull()
  })
})
