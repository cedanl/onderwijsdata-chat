// @vitest-environment jsdom
// #603: wat deze browser het laatst opende en welke rapporten hij als favoriet markeerde, alleen als ID's.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act, Fragment } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { STORAGE_RECENT, NOT_SESSION_DATA_KEYS, SESSION_DATA_KEYS } from '../constants'
import { inVolgorde, noteerGesprek, noteerRapport, vergeetCache, wisselFavoriet } from '../recentBekeken'

const server = vi.hoisted(() => ({ resolve: null, local: [], load: () => new Promise(() => {}) }))
vi.mock('../workbooks', () => ({
  getWorkbooks: () => server.local,
  getWorkbookType: (wb) => wb.type,
  deleteWorkbook: vi.fn(),
  isVolledig: (wb) => !wb?.samenvatting,
  loadWorkbook: vi.fn(id => server.load(id)),
  loadWorkbooksFromServer: () => new Promise(r => { server.resolve = r }),
}))
vi.mock('../components/WorkbookViewer', () => ({
  default: ({ workbook, onBack }) => createElement(Fragment, null,
    createElement('div', { 'data-testid': 'viewer' }, workbook.title),
    createElement('button', { type: 'button', 'data-testid': 'back', onClick: onBack }, 'Rapporten'),
  ),
}))
vi.mock('../components/WorkbookPreviews', () => ({ default: () => null }))

import RapportenPage from '../pages/RapportenPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const opgeslagen = () => JSON.parse(localStorage.getItem(STORAGE_RECENT))

beforeEach(() => {
  localStorage.clear()
  vergeetCache()
})

describe('de lijsten in de browser', () => {
  it('zet het laatst geopende vooraan, zonder dubbelen, hooguit tien', () => {
    for (const id of ['a', 'b', 'a', 'c']) noteerGesprek(id)
    expect(opgeslagen().gesprekken).toEqual(['c', 'a', 'b'])
    for (let i = 0; i < 12; i++) noteerRapport(`r${i}`)
    expect(opgeslagen().rapporten).toHaveLength(10)
    expect(opgeslagen().rapporten[0]).toBe('r11')
  })

  it('wisselt een favoriet aan en uit', () => {
    wisselFavoriet('r1')
    wisselFavoriet('r2')
    expect(opgeslagen().favorieten).toEqual(['r2', 'r1'])
    wisselFavoriet('r1')
    expect(opgeslagen().favorieten).toEqual(['r2'])
  })

  it('bewaart alleen ID\'s, en toont alleen wat bij dit account hoort', () => {
    noteerGesprek('van-iemand-anders')
    noteerGesprek('c1')
    expect(JSON.stringify(opgeslagen())).not.toMatch(/title|titel/)
    expect(inVolgorde(opgeslagen().gesprekken, [{ id: 'c1', title: 'Instroom' }])).toEqual([{ id: 'c1', title: 'Instroom' }])
  })

  it('blijft na uitloggen staan: alleen ID\'s, gefilterd op het account', () => {
    expect(NOT_SESSION_DATA_KEYS).toContain(STORAGE_RECENT)
    expect(SESSION_DATA_KEYS).not.toContain(STORAGE_RECENT)
  })

  it('overleeft een kapotte opslag', () => {
    localStorage.setItem(STORAGE_RECENT, '{kapot')
    vergeetCache()
    expect(() => noteerGesprek('c1')).not.toThrow()
  })
})

describe('recent bekeken en favorieten op /rapporten', () => {
  let root
  let container

  const RAPPORTEN = [
    { id: 'r1', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' },
    { id: 'r2', type: 'report', title: 'Uitval mbo', createdAt: '2026-10-02T00:00:00Z' },
    { id: 'r3', type: 'report', title: 'Diplomarendement wo', createdAt: '2026-10-03T00:00:00Z' },
  ]

  async function render() {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root.render(createElement(MemoryRouter, { initialEntries: ['/rapporten'] }, createElement(RapportenPage, { settings: {} })))
    })
    await act(async () => { server.resolve(RAPPORTEN) })
  }

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  const snel = kop => {
    const sectie = [...container.querySelectorAll('.wb-snel-rij')].find(r => r.querySelector('h2').textContent === kop)
    return sectie ? [...sectie.querySelectorAll('button')].map(b => b.textContent) : null
  }
  const ster = titel => container.querySelector(`button[aria-label="Favoriet: ${titel}"]`)

  it('toont niets extra zolang er niets bekeken of gemarkeerd is', async () => {
    await render()
    expect(container.querySelector('.wb-snel')).toBeNull()
  })

  it('markeert een favoriet met de ster en zet hem bovenaan, met de privacynoot', async () => {
    await render()
    expect(ster('Uitval mbo').getAttribute('aria-pressed')).toBe('false')
    await act(async () => { ster('Uitval mbo').click() })
    expect(ster('Uitval mbo').getAttribute('aria-pressed')).toBe('true')
    expect(snel('Favorieten')).toEqual(['Uitval mbo'])
    expect(container.querySelector('.wb-snel').textContent).toContain('Alleen in deze browser')
  })

  it('onthoudt een geopend rapport als recent bekeken', async () => {
    await render()
    await act(async () => { container.querySelector('a.wb-card').click() })
    expect(container.querySelector('[data-testid="viewer"]')).not.toBeNull()
    await act(async () => { container.querySelector('[data-testid="back"]').click() })
    expect(snel('Recent bekeken')).toEqual([RAPPORTEN.find(r => r.id === opgeslagen().rapporten[0]).title])
  })

  it('laat een ID van een ander account of een verwijderd rapport weg', async () => {
    noteerRapport('weg')
    wisselFavoriet('weg')
    await render()
    expect(container.querySelector('.wb-snel')).toBeNull()
  })

  it('opent een rapport vanuit de rij', async () => {
    noteerRapport('r3')
    await render()
    const knop = [...container.querySelectorAll('.wb-snel-rij button')].find(b => b.textContent === 'Diplomarendement wo')
    await act(async () => { knop.click() })
    expect(container.querySelector('[data-testid="viewer"]').textContent).toBe('Diplomarendement wo')
  })

  it('verbergt de rijen tijdens het zoeken', async () => {
    noteerRapport('r3')
    await render()
    const veld = container.querySelector('input[type="search"]')
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    await act(async () => { setter.call(veld, 'uitval'); veld.dispatchEvent(new Event('input', { bubbles: true })) })
    expect(container.querySelector('.wb-snel')).toBeNull()
  })
})
