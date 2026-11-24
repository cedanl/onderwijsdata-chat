// @vitest-environment jsdom
// #1098: zonder gekozen instelling tonen de vaste dashboards de cijfers van Hogeschool Utrecht. Dat staat er dan bij als
// voorbeeld, met een knop die Instellingen opent; na het kiezen van een instelling (of met een instelling in de link)
// verdwijnt de melding.
import { describe, it, expect, afterEach, vi } from 'vitest'
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

import DashboardPage, { isVoorbeeldInstelling } from '../pages/DashboardPage'
import { DEFAULT_INSTELLING } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const MIJN = '__builtin_mijn_instelling__'

let root
let container

async function render(pad, settings = {}, onOpenSettings = vi.fn()) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [pad] },
      createElement(DashboardPage, { settings, onOpenSettings })))
  })
  await vi.waitFor(async () => {
    await act(async () => {})
    if (!container.querySelector('.wb-card, .meta-badge.instelling')) throw new Error('nog niet getoond')
  })
  return onOpenSettings
}

const melding = () => container.querySelector('.db-voorbeeld')
const knop = () => melding()?.querySelector('button')

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = null
  container = null
  localStorage.clear()
})

describe('isVoorbeeldInstelling (#1098)', () => {
  it('is alleen zo als noch de link noch het profiel een instelling heeft', () => {
    expect(isVoorbeeldInstelling(null, undefined)).toBe(true)
    expect(isVoorbeeldInstelling('  ', '')).toBe(true)
    expect(isVoorbeeldInstelling(null, 'Hogeschool Rotterdam')).toBe(false)
    expect(isVoorbeeldInstelling('ROC Midden Nederland', '')).toBe(false)
  })
})

describe('/dashboards zonder gekozen instelling (#1098)', () => {
  it('zegt in de galerij dat het een voorbeeld is en opent Instellingen met de knop', async () => {
    const open = await render('/dashboards')
    expect(melding().textContent).toContain(`${DEFAULT_INSTELLING} is een voorbeeld`)
    expect(melding().textContent).toContain('Kies je eigen instelling')
    await act(async () => { knop().click() })
    expect(open).toHaveBeenCalledOnce()
  })

  it('zegt het ook boven het dashboard zelf', async () => {
    await render(`/dashboards?id=${MIJN}`)
    expect(melding().textContent).toContain(`${DEFAULT_INSTELLING} is een voorbeeld`)
    expect(knop().textContent).toBe('Kies je instelling')
  })

  it('laat de melding weg met een gekozen instelling', async () => {
    await render('/dashboards', { instelling: 'Hogeschool Rotterdam' })
    expect(melding()).toBeNull()
    await act(async () => root.unmount())
    container.remove()
    await render(`/dashboards?id=${MIJN}`, { instelling: 'Hogeschool Rotterdam' })
    expect(melding()).toBeNull()
  })

  it('laat de melding weg bij een gedeelde link met een instelling', async () => {
    await render(`/dashboards?id=${MIJN}&instelling=ROC+Midden+Nederland`)
    expect(melding()).toBeNull()
  })
})
