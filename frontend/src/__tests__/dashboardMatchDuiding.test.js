// @vitest-environment jsdom
// #900: de match-tegels zeiden "schaarste", "evenwicht" of "overaanbod" zonder bron, peildatum, drempel of definitie, en
// de banner van de UWV-grafiek noemde een vaste maand. Nu komen peildatum, drempel, diplomajaren en de herkomst van de
// sectorindeling uit `match_duiding` in de payload, en noemt elk onderdeel dat de UWV-momentopname gebruikt de peildatum.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
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

import { InlineDashboardArbeidsmarkt } from '../components/dashboards'
import { MatchScoreSection } from '../components/dashboards/arbeidsmarkt-consolidated/index'
import { peildatumTekst, jarenTekst } from '../components/dashboards/shared/momentopname'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// Zoals data/dashboard.py _match_duiding hem geeft.
const DUIDING = {
  drempel: 1.2,
  vacatures_peildatum: '2023-05-16',
  diplomajaren: [2023, 2024, 2025],
  roa_versie: 'v20251218',
  sectormapping: { herkomst: 'LLM-classificatie, niet van UWV', mapping_versie: '2026-08-17', model: 'onbekend' },
}

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

const banners = () => [...container.querySelectorAll('.db-momentopname')].map(b => b.textContent)
const duidingTekst = () => container.querySelector('.db-match-duiding')?.textContent ?? ''

describe('peildatum en jaren in woorden', () => {
  it('schrijft een ISO-peildatum als datum in het Nederlands', () => {
    expect(peildatumTekst('2023-05-16')).toBe('16 mei 2023')
    expect(peildatumTekst('2023-05-16, 2023-05-17')).toBe('16 mei 2023, 17 mei 2023')
    expect(peildatumTekst('onbekend')).toBe('onbekend')
    expect(peildatumTekst(null)).toBeNull()
  })

  it('noemt de diplomajaren als bereik', () => {
    expect(jarenTekst([2023, 2024, 2025])).toBe('2023 tot en met 2025')
    expect(jarenTekst([2025])).toBe('2025')
    expect(jarenTekst([])).toBeNull()
  })
})

describe('de arbeidsmarktmatch noemt bron, peildatum, drempel en definitie (#900)', () => {
  it('tegels, grafiek en UWV-sectie dragen elk de banner met de peildatum uit de data', async () => {
    await arbeidsmarkt(DUIDING)

    // Match-tegels, "Gediplomeerden vs. vacatures" en het vacatureaanbod in de regio.
    expect(banners()).toHaveLength(3)
    for (const banner of banners()) expect(banner).toContain('peildatum 16 mei 2023')
    expect(container.textContent).not.toContain('Momentopname mei 2023')
  })

  it('zegt onder de tegels wat de drie labels betekenen, met de drempel, de jaren en de herkomst van de indeling', async () => {
    await arbeidsmarkt(DUIDING)

    const tekst = duidingTekst()
    expect(tekst).toContain('UWV Open Match, peildatum 16 mei 2023')
    expect(tekst).toContain('DUO, gemiddeld over de diplomajaren 2023 tot en met 2025')
    expect(tekst).toContain('Schaarste: het vacature-aandeel is meer dan 1,2 keer het diploma-aandeel')
    expect(tekst).toContain('Overaanbod: het diploma-aandeel is meer dan 1,2 keer het vacature-aandeel')
    expect(tekst).toContain('Evenwicht')
    expect(tekst).toContain('geen opleidingsniveau')
    expect(tekst).toContain('LLM-classificatie, niet van UWV, versie 2026-08-17')
  })

  it('de grafiek noemt diplomajaren en peildatum in de ondertitel', async () => {
    await arbeidsmarkt(DUIDING)

    const sub = [...container.querySelectorAll('.chart-sub')].map(s => s.textContent).find(s => s.startsWith('Gemiddeld aantal gediplomeerden'))
    expect(sub).toContain('diplomajaren 2023 tot en met 2025')
    expect(sub).toContain('UWV Open Match, peildatum 16 mei 2023')
  })

  it('volgt de payload, geen vaste tekst: een andere drempel en peildatum staan er zoals de server ze geeft', async () => {
    const regio = { ...dashboards.regio, vacatureaanbod: { ...dashboards.regio.vacatureaanbod, peildatum: '2024-01-31' } }
    await arbeidsmarkt({ ...DUIDING, drempel: 1.5, vacatures_peildatum: '2024-01-31', diplomajaren: [2022, 2023, 2024] }, regio)

    for (const banner of banners()) expect(banner).toContain('peildatum 31 januari 2024')
    expect(duidingTekst()).toContain('meer dan 1,5 keer')
    expect(duidingTekst()).toContain('2022 tot en met 2024')
    expect(container.textContent).not.toContain('mei 2023')
  })

  it('zonder peildatum zegt het dat, en noemt geen maand', async () => {
    const regio = { ...dashboards.regio, vacatureaanbod: { ...dashboards.regio.vacatureaanbod, peildatum: null } }
    await arbeidsmarkt({ ...DUIDING, vacatures_peildatum: null }, regio)

    for (const banner of banners()) expect(banner).toContain('peildatum onbekend')
    expect(container.textContent).not.toContain('mei 2023')
  })
})

describe('een sector zonder score', () => {
  it('staat in een noot, niet stil weggelaten', async () => {
    await renderIn(createElement(MatchScoreSection, {
      matchScore: { TECHNIEK: 'schaarste', ONDERWIJS: null },
      duiding: DUIDING,
      dark: false,
    }))

    expect(container.querySelectorAll('.kpi-card')).toHaveLength(1)
    expect(container.textContent).toMatch(/Niet getoond \(geen beroepenclusters in de sectorindeling\): Onderwijs/)
  })
})
