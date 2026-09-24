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

describe('DashboardGallery verwijderknop', () => {
  it('voorkomt navigatie en roept onDelete aan zonder onSelect', async () => {
    const onDelete = vi.fn()
    const onSelect = vi.fn()
    await renderIn(createElement(DashboardGallery, {
      workbooks: [wb],
      instelling: 'Hogeschool Utrecht',
      onDelete,
      onSelect,
      onNew: vi.fn(),
    }))

    const event = await clickDeleteBtn()
    expect(event.defaultPrevented).toBe(true)
    expect(onDelete).toHaveBeenCalledWith('wb-1')
    expect(onSelect).not.toHaveBeenCalled()
  })
})