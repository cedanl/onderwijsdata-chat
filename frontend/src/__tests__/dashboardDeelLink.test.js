// @vitest-environment jsdom
// #1071: een gedeelde link naar een vast dashboard draagt de instelling. `?instelling=` gaat voor het profiel, het
// profiel voor de standaard; openen zet de instelling in de URL, teruggaan haalt haar weg, het profiel blijft.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, useLocation } from 'react-router-dom'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  // De ladingen blijven hangen: het dashboard toont zijn laadvlak, met de instelling in de band.
  fetchDashboardData: vi.fn(() => new Promise(() => {})),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import DashboardPage, { effectieveInstelling, MAX_URL_INSTELLING } from '../pages/DashboardPage'
import { DEFAULT_INSTELLING } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const MIJN = '__builtin_mijn_instelling__'

let root
let container
let locatie

function Locatie() {
  locatie = useLocation()
  return null
}

async function render(pad, settings = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [pad] },
      createElement(DashboardPage, { settings }), createElement(Locatie)))
  })
}

// Het dashboard laadt lui (WorkbookViewer): wacht tot de band met de instelling er staat.
async function band() {
  await vi.waitFor(async () => {
    await act(async () => {})
    if (!container.querySelector('.meta-badge.instelling')) throw new Error('nog geen band')
  })
  return container.querySelector('.meta-badge.instelling').textContent
}
const params = () => new URLSearchParams(locatie.search)

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  localStorage.clear()
})

describe('effectieveInstelling (#1071)', () => {
  it('URL gaat voor profiel, profiel voor standaard', () => {
    expect(effectieveInstelling('ROC Midden Nederland', 'Hogeschool Rotterdam')).toBe('ROC Midden Nederland')
    expect(effectieveInstelling(null, 'Hogeschool Rotterdam')).toBe('Hogeschool Rotterdam')
    expect(effectieveInstelling('   ', ' Hogeschool Rotterdam ')).toBe('Hogeschool Rotterdam')
    expect(effectieveInstelling(null, '')).toBe(DEFAULT_INSTELLING)
    expect(effectieveInstelling(undefined, undefined)).toBe(DEFAULT_INSTELLING)
  })

  it('begrenst vrije tekst uit de URL', () => {
    expect(effectieveInstelling('x'.repeat(5000), null)).toHaveLength(MAX_URL_INSTELLING)
  })
})

describe('/dashboards met ?instelling= (#1071)', () => {
  it('toont de instelling uit de URL, ook met een ander profiel', async () => {
    const settings = { instelling: 'Hogeschool Rotterdam' }
    await render(`/dashboards?id=${MIJN}&instelling=ROC+Midden+Nederland`, settings)
    expect(await band()).toBe('ROC Midden Nederland')
    expect(settings).toEqual({ instelling: 'Hogeschool Rotterdam' })
  })

  it('zonder param: het profiel, anders de standaard', async () => {
    await render(`/dashboards?id=${MIJN}`, { instelling: 'Hogeschool Rotterdam' })
    expect(await band()).toBe('Hogeschool Rotterdam')
    act(() => root.unmount())
    container.remove()
    await render(`/dashboards?id=${MIJN}`, {})
    expect(await band()).toBe(DEFAULT_INSTELLING)
  })

  it('openen zet id en instelling in de URL, teruggaan haalt beide weg', async () => {
    await render('/dashboards', { instelling: 'Hogeschool Rotterdam' })
    const kaart = [...container.querySelectorAll('.wb-card')].find(k => k.textContent.includes('Mijn instelling'))
    await act(async () => kaart.click())
    expect(params().get('id')).toBe(MIJN)
    expect(params().get('instelling')).toBe('Hogeschool Rotterdam')
    expect(await band()).toBe('Hogeschool Rotterdam')
    await act(async () => container.querySelector('.wb-back-btn').click())
    expect(params().get('id')).toBeNull()
    expect(params().get('instelling')).toBeNull()
  })

  it('een link met instelling geeft bij openen vanuit de galerij die instelling door', async () => {
    await render('/dashboards?instelling=Universiteit+Utrecht', { instelling: 'Hogeschool Rotterdam' })
    const kaart = [...container.querySelectorAll('.wb-card')].find(k => k.textContent.includes('Landelijk'))
    await act(async () => kaart.click())
    expect(params().get('instelling')).toBe('Universiteit Utrecht')
  })
})
