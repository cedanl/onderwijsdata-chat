// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
}))

vi.mock('react-plotly.js', () => ({
  default: function PlotStub() { return null },
}))

import { fetchWorkbooks, deleteWorkbookApi } from '../api'
import RapportenPage from '../pages/RapportenPage'
import DashboardGallery from '../components/DashboardGallery'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const wb = {
  id: 'wb-1',
  title: 'Mijn rapport',
  description: 'Beschrijving',
  messages: [{ role: 'assistant', content: 'Samenvatting van het rapport.' }],
  figures: [],
  htmlContent: '<p>Rapport</p>',
  createdAt: '2026-01-01T00:00:00.000Z',
}

let root
let container

function renderIn(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  return act(async () => { root.render(element) })
}

const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === tekst)

async function clickDeleteBtn() {
  const btn = container.querySelector('.wb-delete-btn')
  const event = new MouseEvent('click', { bubbles: true, cancelable: true })
  await act(async () => { btn.dispatchEvent(event) })
  return event
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

describe('RapportenPage verwijderknop', () => {
  beforeEach(async () => {
    fetchWorkbooks.mockResolvedValue([wb])
    await renderIn(
      createElement(MemoryRouter, { initialEntries: ['/rapporten'] },
        createElement(RapportenPage, { settings: {} }))
    )
  })

  it('voorkomt de navigatie van de geneste link en opent het bevestigingsvenster', async () => {
    const event = await clickDeleteBtn()
    expect(event.defaultPrevented).toBe(true)
    expect(container.textContent).toContain('Weet je zeker dat je dit rapport wilt verwijderen?')
  })

  it('verwijderen bevestigen verwijdert het werkboek via de API', async () => {
    await clickDeleteBtn()
    await act(async () => {
      const confirm = [...container.querySelectorAll('button')].find(b => b.textContent.trim() === 'Verwijderen')
      confirm.click()
    })
    expect(deleteWorkbookApi).toHaveBeenCalledWith('wb-1')
  })
})

// #765: de dashboardbouwer is weg; een opgeslagen dashboard opent niet meer, maar is nog los te verwijderen.
describe('DashboardGallery: opgeslagen dashboards', () => {
  const vast = { id: '__builtin_nationaal__', title: 'Landelijk', description: 'd', builtin: true }
  const opgeslagen = { ...wb, id: 'db-1', title: 'Mijn dashboard', type: 'dashboard', htmlContent: undefined }

  it('roept onDelete aan zonder onSelect, en de vaste dashboards hebben geen verwijderknop', async () => {
    const onDelete = vi.fn()
    const onSelect = vi.fn()
    await renderIn(createElement(DashboardGallery, {
      workbooks: [vast], opgeslagen: [opgeslagen], instelling: 'Hogeschool Utrecht', onDelete, onSelect,
    }))

    expect(container.querySelector('.wb-grid .wb-delete-btn')).toBeNull()
    expect(container.querySelector('.wb-opgeslagen').textContent).toContain('Mijn dashboard')
    await clickDeleteBtn()
    expect(onDelete).toHaveBeenCalledWith('db-1')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('toont geen lijst zonder opgeslagen dashboards', async () => {
    await renderIn(createElement(DashboardGallery, { workbooks: [vast], instelling: 'HU', onDelete: vi.fn(), onSelect: vi.fn() }))
    expect(container.querySelector('.wb-opgeslagen')).toBeNull()
  })
})
// #778: een DELETE die niet lukt, laat het rapport niet stil verdwijnen.
describe('rapport verwijderen dat op de server mislukt (#778)', () => {
  beforeEach(async () => {
    localStorage.clear()
    fetchWorkbooks.mockResolvedValue([wb])
    await renderIn(
      createElement(MemoryRouter, { initialEntries: ['/rapporten'] },
        createElement(RapportenPage, { settings: {} }))
    )
  })
  const kaarten = () => container.querySelectorAll('.wb-grid .wb-card').length
  const melding = () => container.querySelector('[role="alert"]')

  it('zet het rapport terug met een melding, en "Opnieuw proberen" verwijdert het alsnog', async () => {
    deleteWorkbookApi.mockRejectedValueOnce(Object.assign(new Error('API 503'), { status: 503 }))
    await clickDeleteBtn()
    await act(async () => { knop('Verwijderen').click() })

    expect(kaarten()).toBe(1)
    expect(melding().textContent).toContain('"Mijn rapport" verwijderen is niet gelukt. Het staat weer in de lijst.')

    await act(async () => { knop('Opnieuw proberen').click() })

    expect(deleteWorkbookApi).toHaveBeenCalledTimes(2)
    expect(kaarten()).toBe(0)
    expect(melding()).toBeNull()
  })

  it('zegt niets als de DELETE lukt', async () => {
    await clickDeleteBtn()
    await act(async () => { knop('Verwijderen').click() })
    expect(kaarten()).toBe(0)
    expect(melding()).toBeNull()
  })
})

// #776: de verwijderknop verdwijnt met zijn kaart; de focus gaat naar de kaart erna, de vorige, of de kop.
describe('focus na een rapport verwijderen (#776)', () => {
  const tweede = { ...wb, id: 'wb-2', title: 'Tweede rapport' }

  async function verwijderEnBevestig(titel) {
    const knop = container.querySelector(`[aria-label="Verwijder rapport ${titel}"]`)
    await act(async () => { knop.focus(); knop.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })) })
    await act(async () => {
      [...container.querySelectorAll('button')].find(b => b.textContent.trim() === 'Verwijderen').click()
    })
  }

  async function toon(rapporten) {
    fetchWorkbooks.mockResolvedValue(rapporten)
    await renderIn(
      createElement(MemoryRouter, { initialEntries: ['/rapporten'] },
        createElement(RapportenPage, { settings: {} }))
    )
  }

  it('gaat naar de kaart die erna stond', async () => {
    await toon([wb, tweede])
    const volgorde = [...container.querySelectorAll('.wb-grid .wb-card')].map(k => k.dataset.wbId)
    await verwijderEnBevestig(volgorde[0] === 'wb-1' ? 'Mijn rapport' : 'Tweede rapport')
    expect(document.activeElement.dataset.wbId).toBe(volgorde[1])
  })

  it('gaat naar de kaart ervoor als het laatste rapport weg is', async () => {
    await toon([wb, tweede])
    const volgorde = [...container.querySelectorAll('.wb-grid .wb-card')].map(k => k.dataset.wbId)
    await verwijderEnBevestig(volgorde[1] === 'wb-1' ? 'Mijn rapport' : 'Tweede rapport')
    expect(document.activeElement.dataset.wbId).toBe(volgorde[0])
  })

  it('gaat naar de kop als er geen rapport over is', async () => {
    await toon([wb])
    await verwijderEnBevestig('Mijn rapport')
    expect(document.activeElement).toBe(container.querySelector('.wb-gallery-title'))
  })
})
