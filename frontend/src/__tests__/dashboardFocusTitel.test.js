// @vitest-environment jsdom
// #1172 en #1173: een dashboard openen of verlaten laat de focus niet op <body> vallen (WCAG 2.4.3), en de
// tabbladtitel noemt het geopende dashboard (WCAG 2.4.2).
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchDashboardData: vi.fn(() => new Promise(() => {})),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import DashboardPage from '../pages/DashboardPage'
import { BUILTIN_NATIONAAL } from '../workbooks'

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

beforeEach(() => { document.title = 'vorige' })

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  localStorage.clear()
})

const kaart = () => container.querySelector(`.wb-card[data-wb-id="${BUILTIN_NATIONAAL.id}"]`)
const klik = async el => { await act(async () => { el.click() }) }

describe('paginatitel van een dashboard (#1173)', () => {
  it('blijft in de galerij "Dashboards"', async () => {
    await render('/dashboards')
    expect(document.title).toBe('Dashboards — openEDUdata+')
  })

  it('noemt het geopende vaste dashboard', async () => {
    await render(`/dashboards?id=${BUILTIN_NATIONAAL.id}`)
    expect(document.title).toBe('Landelijk — openEDUdata+')
  })

  it('valt terug op "Dashboards" bij een id die niet opent', async () => {
    await render('/dashboards?id=db-oud')
    expect(document.title).toBe('Dashboards — openEDUdata+')
  })

  it('volgt het openen en sluiten van een dashboard', async () => {
    await render('/dashboards')
    await klik(kaart())
    expect(document.title).toBe('Landelijk — openEDUdata+')
    await klik(container.querySelector('.wb-back-btn'))
    expect(document.title).toBe('Dashboards — openEDUdata+')
  })
})

describe('focus bij openen en terugkeren (#1172)', () => {
  it('staat na het openen op de h1 van het dashboard', async () => {
    await render('/dashboards')
    await klik(kaart())
    const kop = container.querySelector('h1.wb-viewer-heading')
    expect(kop.tabIndex).toBe(-1)
    expect(document.activeElement).toBe(kop)
  })

  it('staat na "Dashboards" terug op de kaart van het dashboard dat open was', async () => {
    await render('/dashboards')
    await klik(kaart())
    await klik(container.querySelector('.wb-back-btn'))
    expect(document.activeElement).toBe(kaart())
  })

  it('laat een rechtstreekse link de focus niet stelen bij het laden', async () => {
    await render(`/dashboards?id=${BUILTIN_NATIONAAL.id}`)
    expect(document.activeElement).toBe(document.body)
  })
})
