// @vitest-environment jsdom
// #765: de dashboardbouwer is weg. /dashboards toont de drie vaste dashboards; een link naar een opgeslagen dashboard
// zegt dat het niet meer opent en waar het wel staat, en het dashboard zelf blijft los te verwijderen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([
    { id: 'db-1', title: 'Mijn dashboard', type: 'dashboard', created_at: '2026-09-01T00:00:00.000Z' },
    { id: 'r-1', title: 'Mijn rapport', type: 'report', created_at: '2026-09-02T00:00:00.000Z' },
  ]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  // De miniaturen van de vaste dashboards (#933) blijven hier laden.
  fetchDashboardData: vi.fn(() => new Promise(() => {})),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import DashboardPage, { BOUWER_WEG } from '../pages/DashboardPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(pad) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [pad] }, createElement(DashboardPage, { settings: {} })))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  localStorage.clear()
})

describe('/dashboards zonder dashboardbouwer (#765)', () => {
  it('toont de drie vaste dashboards, geen nieuw-kaart, en het opgeslagen dashboard alleen in de lijst', async () => {
    await render('/dashboards')
    const titels = [...container.querySelectorAll('.wb-grid .wb-card-title')].map(t => t.textContent)
    expect(titels).toEqual(['Mijn instelling', 'Arbeidsmarkt', 'Landelijk'])
    expect(container.textContent).not.toContain('Nieuw dashboard')
    const lijst = container.querySelector('.wb-opgeslagen')
    expect(lijst.textContent).toContain('Mijn dashboard')
    expect(lijst.textContent).not.toContain('Mijn rapport')
    expect(container.querySelector('[role="alert"]')).toBeNull()
  })

  it('zegt bij een link naar een opgeslagen dashboard dat het niet meer opent', async () => {
    await render('/dashboards?id=db-1')
    expect(container.querySelector('[role="alert"]').textContent).toBe(BOUWER_WEG)
    expect(container.querySelector('.wb-viewer')).toBeNull()
  })
})
