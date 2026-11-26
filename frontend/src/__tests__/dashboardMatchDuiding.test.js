// @vitest-environment jsdom
// #900: de match-tegels zeiden "schaarste", "evenwicht" of "overaanbod" zonder bron, periode, drempel of definitie. Nu
// komen bron en kwartalen, drempel, diplomajaren en de koppeltabel uit `match_duiding` in de payload, en noemt elk
// onderdeel dat de vacatures gebruikt de tabel en het kwartaal. Sinds #1225 zijn dat de vacatures van CBS 83599NED per
// bedrijfstak (niet meer de UWV-momentopname), en zegt de duiding dat de score indicatief is.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import dashboards from './fixtures/dashboards.json'
import { MATCH_DUIDING as DUIDING } from './fixtures/matchDuiding'

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

import { InlineDashboardArbeidsmarkt } from '../components/dashboards'
import { MatchScoreSection } from '../components/dashboards/arbeidsmarkt-consolidated/index'
import { jarenTekst } from '../components/dashboards/shared/vacatures'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  for (const k of Object.keys(payloads)) delete payloads[k]
})

async function renderIn(element) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
}

async function arbeidsmarkt(duiding, regio = dashboards.regio) {
  payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_duiding: duiding }
  payloads['/api/dashboard/regio'] = regio
  await renderIn(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.arbeidsmarktmatch.instelling }))
}

const bronregels = () => [...container.querySelectorAll('.db-vacaturebron')].map(b => b.textContent)
const duidingTekst = () => container.querySelector('.db-match-duiding')?.textContent ?? ''

describe('jaren in woorden', () => {
  it('noemt de diplomajaren als bereik', () => {
    expect(jarenTekst([2023, 2024, 2025])).toBe('2023 tot en met 2025')
    expect(jarenTekst([2025])).toBe('2025')
    expect(jarenTekst([])).toBeNull()
  })
})

describe('de arbeidsmarktmatch noemt bron, kwartalen, drempel en definitie (#900, #1225)', () => {
  it('tegels, grafiek en vacatureaanbod dragen elk de bronregel met het kwartaal uit de data', async () => {
    await arbeidsmarkt(DUIDING)

    // Match-tegels, "Gediplomeerden en vacatures" en het vacatureaanbod in de regio.
    expect(bronregels()).toHaveLength(3)
    for (const regel of bronregels()) expect(regel).toMatch(/CBS-tabel 83599NED.*2026 3e kwartaal/)
    expect(container.textContent).not.toMatch(/Momentopname|UWV/)
  })

  it('zegt onder de tegels wat de drie labels betekenen, met de drempel, de jaren en de koppeltabel', async () => {
    await arbeidsmarkt(DUIDING)

    const tekst = duidingTekst()
    expect(tekst).toContain('vacatures van zijn bedrijfstakken (CBS 83599NED, gemiddelde 2025 4e kwartaal t/m 2026 3e kwartaal, voorlopig)')
    expect(tekst).toContain('DUO, gemiddeld over de diplomajaren 2023 tot en met 2025')
    expect(tekst).toContain('Schaarste: het vacature-aandeel is meer dan 1,2 keer het diploma-aandeel')
    expect(tekst).toContain('Overaanbod: het diploma-aandeel is meer dan 1,2 keer het vacature-aandeel')
    expect(tekst).toContain('Evenwicht')
    expect(tekst).toContain('per bedrijfstak van de werkgever (SBI), niet per beroep')
    expect(tekst).toContain('indicatief')
    expect(tekst).toContain('gemiddelde voorraad over 4 kwartalen')
    expect(tekst).toContain('koppeltabel van bedrijfstakken en sectoren is met de hand opgesteld, geen taalmodel')
  })

  it('de grafiek noemt diplomajaren en kwartalen in de ondertitel', async () => {
    await arbeidsmarkt(DUIDING)

    const sub = [...container.querySelectorAll('.chart-sub')].map(s => s.textContent).find(s => s.startsWith('Gemiddeld aantal gediplomeerden'))
    expect(sub).toContain('diplomajaren 2023 tot en met 2025')
    expect(sub).toContain('CBS 83599NED, gemiddelde 2025 4e kwartaal t/m 2026 3e kwartaal, voorlopig')
  })

  it('volgt de payload, geen vaste tekst: een andere drempel en andere kwartalen staan er zoals de server ze geeft', async () => {
    const regio = { ...dashboards.regio, vacatureaanbod: { ...dashboards.regio.vacatureaanbod, periode: '2027 1e kwartaal', voorlopig: false } }
    const vacatures = { ...DUIDING.vacatures, periode: '2026 2e kwartaal t/m 2027 1e kwartaal', voorlopig: false }
    await arbeidsmarkt({ ...DUIDING, drempel: 1.5, vacatures, diplomajaren: [2022, 2023, 2024] }, regio)

    for (const regel of bronregels()) expect(regel).toContain('2027 1e kwartaal')
    for (const regel of bronregels()) expect(regel).not.toContain('voorlopig')
    expect(duidingTekst()).toContain('meer dan 1,5 keer')
    expect(duidingTekst()).toContain('2022 tot en met 2024')
    expect(container.textContent).not.toContain('2026 3e kwartaal')
  })

  it('zonder kwartalen (CBS laadde niet) zegt het dat', async () => {
    const vacatures = { ...DUIDING.vacatures, periode: null, perioden: [], voorlopig: false }
    await arbeidsmarkt({ ...DUIDING, vacatures }, { ...dashboards.regio, vacatureaanbod: {} })

    for (const regel of bronregels()) expect(regel).toContain('periode onbekend')
    expect(duidingTekst()).toContain('(CBS 83599NED)')
  })
})

describe('een sector zonder score', () => {
  it('staat in een noot, niet stil weggelaten', async () => {
    await renderIn(createElement(MatchScoreSection, {
      matchScore: { TECHNIEK: 'schaarste', SECTOROVERSTIJGEND: null },
      duiding: DUIDING,
      dark: false,
    }))

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(1)
    expect(container.textContent).toMatch(/Niet getoond \(geen vacaturegegevens per bedrijfstak voor deze sector\): Sectoroverstijgend/)
  })

  it('met de reden uit de payload (`match_weggelaten`)', async () => {
    await renderIn(createElement(MatchScoreSection, {
      matchScore: { TECHNIEK: 'schaarste', SECTOROVERSTIJGEND: null },
      weggelaten: { SECTOROVERSTIJGEND: 'geen vacaturegegevens per bedrijfstak voor deze sector' },
      duiding: DUIDING,
      dark: false,
    }))

    expect(container.textContent).toContain('Niet getoond (geen vacaturegegevens per bedrijfstak voor deze sector): Sectoroverstijgend.')
  })
})
