// @vitest-environment jsdom
// #904, besluiten B en B: de regio- en provinciebadges krijgen een sterretje en één noot (adres van de hoofdvestiging
// bij DUO; vestigingen elders tellen niet mee; bij de arbeidsmarkt: vacatures gaan over deze provincie). Zonder adres
// zegt de noot dat de provincie uit de inschrijvingen komt; zonder herkomst staat er geen provinciebadge. Elk dashboard
// heeft een afdrukknop; de print-CSS toont alleen het dashboard, met het bronblok.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import dashboards from './fixtures/dashboards.json'

vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub() { return null },
  Line: function LineStub() { return null },
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const payloads = {}
vi.mock('../api', async importOriginal => ({
  ...(await importOriginal()),
  fetchDashboardData: vi.fn(async endpoint => payloads[endpoint] ?? {}),
}))

import { RegioBadges, regioNoot, AfdrukKnop } from '../components/dashboards/shared/shell'
import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling/index'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated/index'
import { InlineDashboardNationaal } from '../components/dashboards/nationaal/index'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

let root
let container
afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  for (const k of Object.keys(payloads)) delete payloads[k]
  vi.restoreAllMocks()
})

function render(el) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(el))
  return container
}

async function renderAsync(el) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(el) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
  return container
}

const badges = el => [...el.querySelectorAll('.meta-badge')].map(b => b.textContent)
const noot = el => el.querySelector('.db-regionoot')?.textContent

describe('regioNoot', () => {
  it('met adres: regio en provincie volgen de hoofdvestiging bij DUO, vestigingen elders tellen niet mee', () => {
    expect(regioNoot({ arbeidsmarktregio: 'Midden-Utrecht', herkomst: 'adres' })).toBe(
      '* Regio en provincie volgen het adres van de hoofdvestiging bij DUO. Vestigingen in andere regio\'s tellen niet mee.',
    )
  })

  it('bij de vacatures: die gaan over deze provincie', () => {
    expect(regioNoot({ arbeidsmarktregio: 'Midden-Utrecht', herkomst: 'adres', vacatures: true }))
      .toContain('tellen niet mee; vacatures (UWV) gaan over deze provincie.')
  })

  it('zonder adres: de provincie komt uit de inschrijvingen, en dat staat erbij', () => {
    const tekst = regioNoot({ herkomst: 'inschrijvingen', vacatures: true })
    expect(tekst).toContain('geen adres met een provincie')
    expect(tekst).toContain('het vaakst bij de instelling staat')
    expect(tekst).toContain('vacatures (UWV) gaan over deze provincie')
  })

  it('zonder regio en zonder provincie: geen noot', () => {
    expect(regioNoot({})).toBeNull()
  })
})

describe('RegioBadges', () => {
  it('zet een sterretje bij regio en provincie en de noot eronder', () => {
    const el = render(createElement(RegioBadges, { instelling: 'HU', provincie: 'Utrecht', herkomst: 'adres', arbeidsmarktregio: 'Midden-Utrecht', bron: 'DUO' }))
    expect(badges(el)).toEqual(['HU', 'Regio Midden-Utrecht*', 'Provincie Utrecht*', 'Bron: DUO'])
    expect(noot(el)).toContain('adres van de hoofdvestiging bij DUO')
    expect(el.querySelector('.db-regionoot').getAttribute('role')).toBe('note')
  })

  it('zonder herkomst geen stellige provinciebadge (ook niet "Onbekend")', () => {
    const el = render(createElement(RegioBadges, { instelling: 'X', provincie: 'Onbekend', herkomst: null }))
    expect(badges(el)).toEqual(['X'])
    expect(noot(el)).toBeUndefined()
  })
})

describe('de dashboards', () => {
  it('Mijn instelling: badges met sterretje, de noot zonder vacatures, en een afdrukknop', async () => {
    payloads['/api/dashboard/regio'] = dashboards.regio
    payloads['/api/dashboard/rendement'] = dashboards.rendement
    const el = await renderAsync(createElement(InlineDashboardMijnInstelling, { instelling: dashboards.regio.instelling }))
    expect(badges(el)).toContain('Provincie Utrecht*')
    expect(noot(el)).toContain('Regio en provincie volgen het adres van de hoofdvestiging bij DUO')
    expect(noot(el)).not.toContain('UWV')
    expect(el.querySelector('.db-afdrukknop')).toBeTruthy()
  })

  it('Arbeidsmarkt: de noot zegt dat de vacatures over deze provincie gaan', async () => {
    payloads['/api/dashboard/arbeidsmarktmatch'] = dashboards.arbeidsmarktmatch
    payloads['/api/dashboard/regio'] = dashboards.regio
    const el = await renderAsync(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.regio.instelling }))
    expect(noot(el)).toContain('vacatures (UWV) gaan over deze provincie')
  })

  it('Landelijk heeft ook de afdrukknop', async () => {
    payloads['/api/dashboard/nationaal'] = dashboards.nationaal
    const el = await renderAsync(createElement(InlineDashboardNationaal, { instelling: dashboards.nationaal.instelling }))
    expect(el.querySelector('.db-afdrukknop')).toBeTruthy()
  })
})

describe('afdrukken', () => {
  it('de knop roept de afdrukdialoog van de browser aan', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const el = render(createElement(AfdrukKnop))
    act(() => el.querySelector('button').click())
    expect(print).toHaveBeenCalledTimes(1)
  })

  it('de print-CSS toont alleen het dashboard, zonder knoppen, met het bronblok', () => {
    const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
    const print = css.slice(css.indexOf('@media print'))
    expect(print).toContain('body:has(.dashboard-content) * { visibility: hidden; }')
    expect(print).toContain('.dashboard-content button, .db-afdrukbalk { display: none !important; }')
    expect(print).toContain('.dashboard-sources')
  })
})
