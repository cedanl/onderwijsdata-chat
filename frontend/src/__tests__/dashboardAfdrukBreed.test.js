// @vitest-environment jsdom
// #973: een afgedrukt dashboard kapte af wat op het scherm zijwaarts scrolt of dicht zit. De Opleidingentabel (11
// kolommen) scrolt in .tabel-scroll, en de print-CSS liet die scrollbox staan; de NSE-thema's en de definities van de
// kengetallen zitten achter een dichte uitklap en kwamen niet op papier.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import opleidingen from './fixtures/dashboardOpleidingen.json'
import { FIN } from './fixtures/bestuurEnPersoneel'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))
vi.mock('react-plotly.js', () => ({ default: () => null }))
const api = vi.hoisted(() => ({ fetchDashboardData: vi.fn() }))
vi.mock('../api', async importOriginal => ({ ...(await importOriginal()), ...api }))

import { InlineDashboardOpleidingen } from '../components/dashboards/opleidingen/index'
import { FinancienSection } from '../components/dashboards/mijn-instelling/financien-section'
import { openUitklappenBijAfdrukken } from '../afdrukUitklap'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver ??= class { observe() {} unobserve() {} disconnect() {} }

let root
let container
afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
})

async function toon(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const afdrukken = () => act(() => { window.dispatchEvent(new Event('beforeprint')) })
const klaar = () => act(() => { window.dispatchEvent(new Event('afterprint')) })

describe('uitklappen op papier (#973)', () => {
  it("opent de NSE-thema's van Opleidingen tijdens het afdrukken en sluit ze daarna", async () => {
    api.fetchDashboardData.mockResolvedValue(opleidingen.hbo)
    await toon(createElement(InlineDashboardOpleidingen, { instelling: 'Hogeschool Utrecht' }))
    const themas = container.querySelector('details.db-uitklap')
    expect(themas.textContent).toContain("NSE-thema's per opleidingsvorm")
    expect(themas.open).toBe(false)

    afdrukken()
    expect(themas.open).toBe(true)
    klaar()
    expect(themas.open).toBe(false)
  })

  it('opent de definities van de kengetallen bij de financiën', async () => {
    await toon(createElement('div', { className: 'dashboard-content' }, createElement(FinancienSection, { data: FIN, dark: false })))
    const def = [...container.querySelectorAll('details')].find(d => d.textContent.includes('Wat de kengetallen meten'))
    const weg = openUitklappenBijAfdrukken()

    afdrukken()
    expect(def.open).toBe(true)
    klaar()
    expect(def.open).toBe(false)
    weg()
  })

  it('laat een uitklap die de gebruiker zelf opende open na het afdrukken', async () => {
    api.fetchDashboardData.mockResolvedValue(opleidingen.hbo)
    await toon(createElement(InlineDashboardOpleidingen, { instelling: 'Hogeschool Utrecht' }))
    const themas = container.querySelector('details.db-uitklap')
    themas.open = true

    afdrukken()
    klaar()
    expect(themas.open).toBe(true)
  })

  it('luistert niet meer als het dashboard weg is', async () => {
    api.fetchDashboardData.mockResolvedValue(opleidingen.hbo)
    await toon(createElement(InlineDashboardOpleidingen, { instelling: 'Hogeschool Utrecht' }))
    act(() => root.unmount())
    root = undefined
    const los = document.createElement('div')
    los.className = 'dashboard-content'
    los.innerHTML = '<details data-afdruk-open=""><summary>x</summary>y</details>'
    document.body.appendChild(los)

    afdrukken()
    expect(los.querySelector('details').open).toBe(false)
    los.remove()
  })
})

describe('brede tabellen op papier (#973)', () => {
  const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
  const print = css.slice(css.indexOf('@media print'))

  it('heft de scrollbox op en laat de tabel in de breedte passen', () => {
    expect(print).toContain('.dashboard-content .tabel-scroll { overflow: visible; }')
    expect(print).toMatch(/\.dashboard-content \.tabel-scroll table \{ font-size: 8pt !important; \}/)
    expect(print).toMatch(/\.dashboard-content \.tabel-scroll :is\(th, td\) \{ white-space: normal !important;/)
  })

  it('herhaalt de kolomkoppen en breekt geen rij of lange tabel verkeerd af', () => {
    expect(print).toContain('.dashboard-content .tabel-scroll thead { display: table-header-group; }')
    expect(print).toContain('.dashboard-content .tabel-scroll tr { break-inside: avoid; }')
    expect(print).toContain('.dashboard-content .chart-card:has(.tabel-scroll) { break-inside: auto; }')
  })
})
