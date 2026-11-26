// @vitest-environment jsdom
// #1225: de vacatures van de arbeidsmarktdashboards komen uit CBS-tabel 83599NED (per kwartaal, per bedrijfstak), niet
// meer uit UWV Open Match (een momentopname van mei 2023, #1219, #1220). Elk onderdeel noemt tabel, licentie en
// kwartaal uit de payload en zegt "voorlopig" waar CBS dat zegt; de ouderdom komt uit de payload (de frontend rekent niet
// zelf), en pas boven de 12 maanden is de bronregel een waarschuwing.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import dashboards from './fixtures/dashboards.json'
import { MATCH_DUIDING } from './fixtures/matchDuiding'

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
import { VacatureBron, ouderdomTekst, cbsBron } from '../components/dashboards/shared/vacatures'
import { VacatureSection } from '../components/dashboards/shared/charts-arbeidsmarkt'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const CBS_TABEL = 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table'

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  for (const k of Object.keys(payloads)) delete payloads[k]
  vi.useRealTimers()
})

async function renderIn(element) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
  await act(async () => { await Promise.resolve() })
  return container
}

describe('de ouderdom in woorden, zoals de backend (#1219)', () => {
  it('schrijft maanden en jaren met "ruim" als er maanden over zijn', () => {
    expect(ouderdomTekst(0)).toBe('minder dan een maand')
    expect(ouderdomTekst(1)).toBe('1 maand')
    expect(ouderdomTekst(11)).toBe('11 maanden')
    expect(ouderdomTekst(12)).toBe('1 jaar')
    expect(ouderdomTekst(13)).toBe('ruim 1 jaar')
    expect(ouderdomTekst(24)).toBe('2 jaar')
    expect(ouderdomTekst(42)).toBe('ruim 3 jaar')
    expect(ouderdomTekst(null)).toBeNull()
    expect(ouderdomTekst(undefined)).toBeNull()
  })

  it('cbsBron noemt tabel, periode en voorlopig', () => {
    expect(cbsBron('2026 3e kwartaal', true)).toBe('CBS 83599NED, 2026 3e kwartaal, voorlopig')
    expect(cbsBron('2026 3e kwartaal', false)).toBe('CBS 83599NED, 2026 3e kwartaal')
    expect(cbsBron(null, true)).toBe('CBS 83599NED')
  })
})

describe('de bronregel (#1225)', () => {
  it('noemt tabel met link, licentie, kwartaal en voorlopig, zonder waarschuwing', async () => {
    await renderIn(createElement(VacatureBron, { periode: '2026 3e kwartaal', voorlopig: true, ouderdomMaanden: 1, verouderd: false }))

    const regel = container.querySelector('.db-vacaturebron')
    expect(regel.getAttribute('role')).toBe('note')
    expect(regel.classList.contains('db-momentopname--verouderd')).toBe(false)
    expect(regel.textContent).toContain('CBS-tabel 83599NED, openstaande vacatures per bedrijfstak (licentie CC BY 4.0), 2026 3e kwartaal.')
    expect(regel.textContent).toContain('CBS noemt deze cijfers voorlopig')
    expect(regel.textContent).not.toMatch(/UWV|Open Match|momentopname|Verouderd/i)
    const [link] = regel.querySelectorAll('a')
    expect(link.getAttribute('href')).toBe(CBS_TABEL)
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(link.getAttribute('aria-label')).toMatch(/opent in een nieuw tabblad/)
  })

  it('een gemiddelde zegt dat, en definitieve cijfers heten niet voorlopig', async () => {
    await renderIn(createElement(VacatureBron, { periode: '2025 4e kwartaal t/m 2026 3e kwartaal', voorlopig: false, gemiddelde: true }))

    const tekst = container.querySelector('.db-vacaturebron').textContent
    expect(tekst).toContain('gemiddeld over 2025 4e kwartaal t/m 2026 3e kwartaal.')
    expect(tekst).not.toContain('voorlopig')
  })

  it('een kwartaal van meer dan 12 maanden oud is een waarschuwing; de ouderdom komt uit de props', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-01-01T00:00:00Z'))
    await renderIn(createElement(VacatureBron, { periode: '2025 3e kwartaal', voorlopig: true, ouderdomMaanden: 13, verouderd: true }))

    const regel = container.querySelector('.db-vacaturebron')
    expect(regel.classList.contains('db-momentopname--verouderd')).toBe(true)
    expect(regel.textContent).toContain('Verouderd: het laatste kwartaal is ruim 1 jaar oud')
  })

  it('zonder periode zegt het dat', async () => {
    await renderIn(createElement(VacatureBron, {}))
    expect(container.textContent).toContain('periode onbekend.')
    expect(container.textContent).not.toContain('voorlopig')
  })
})

describe('het arbeidsmarktdashboard noemt overal CBS 83599NED (#1225)', () => {
  it('ondertitels, bronregels en de matchduiding', async () => {
    payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_duiding: MATCH_DUIDING }
    payloads['/api/dashboard/regio'] = dashboards.regio
    await renderIn(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.arbeidsmarktmatch.instelling }))

    const subs = [...container.querySelectorAll('.chart-sub, .db-sectie-sub')].map(s => s.textContent)
    const gediplomeerden = subs.find(s => s.startsWith('Gemiddeld aantal gediplomeerden'))
    expect(gediplomeerden).toContain('(CBS 83599NED, gemiddelde 2025 4e kwartaal t/m 2026 3e kwartaal, voorlopig)')
    expect(gediplomeerden).toContain('Een bedrijfstak die bij meer sectoren hoort, telt per sector naar rato mee.')
    expect(subs).toContain('Openstaande vacatures per bedrijfstak — CBS 83599NED, 2026 3e kwartaal, voorlopig')
    const regels = [...container.querySelectorAll('.db-vacaturebron')].map(r => r.textContent)
    expect(regels).toHaveLength(3)
    expect(regels.filter(r => r.includes('gemiddeld over 2025 4e kwartaal t/m 2026 3e kwartaal'))).toHaveLength(2)
    expect(regels.filter(r => r.includes('per bedrijfstak (licentie CC BY 4.0), 2026 3e kwartaal.'))).toHaveLength(1)
    const duiding = container.querySelector('.db-match-duiding').textContent
    expect(duiding).toContain('niet per beroep')
    expect(duiding).toContain('Het label per sector is daarom indicatief.')
    expect(duiding).toContain('met de hand opgesteld, geen taalmodel, bijgewerkt op 26 november 2026')
    // UWV Open Match staat nergens meer op het dashboard: geen data, geen banner, geen tekst.
    expect(container.textContent).not.toMatch(/UWV|Open Match|momentopname|beroepencluster/i)
  })

  it('het vacatureaanbod toont de bedrijfstakken, het totaal en het kwartaal', async () => {
    const tekst = (await renderIn(createElement(VacatureSection, { data: dashboards.regio, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain('Openstaande vacatures provincie Utrecht')
    expect(tekst).toContain('34.400')
    expect(tekst).toContain('alle bedrijfstakken, 2026 3e kwartaal (voorlopig)')
    expect(tekst).toContain('een vacature telt bij de bedrijfstak van de werkgever, niet bij het beroep')
  })

  it('een bedrijfstak zonder cijfer staat eronder, niet als 0; een totaal zonder cijfer is een streepje', async () => {
    const vacatureaanbod = { ...dashboards.regio.vacatureaanbod, totaal: null, geen_gegevens: ['B Delfstoffenwinning'] }
    const tekst = (await renderIn(createElement(VacatureSection, { data: { vacatureaanbod }, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain('Niet getoond (CBS heeft voor dit kwartaal geen cijfer): B Delfstoffenwinning.')
    expect(container.querySelector('.kpi-value').textContent).toBe('—')
  })
})

describe('het lege vacatureblok', () => {
  it('noemt de tabel en geen vaste maand', async () => {
    const tekst = (await renderIn(createElement(VacatureSection, { data: { vacatureaanbod: {} }, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain('Geen vacaturegegevens beschikbaar voor Utrecht in CBS-tabel 83599NED.')
    expect(tekst).not.toMatch(/UWV|mei 2023/)
  })
})
