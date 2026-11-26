// @vitest-environment jsdom
// #1219, #1220: de UWV-vacatures (peildatum 16 mei 2023) leken naast diplomajaren tot 2025 een achterstand van de app.
// Nu noemen banner, ondertitels en matchduiding de ouderdom uit de payload (`peildatum_ouderdom_maanden`, `verouderd`;
// de frontend rekent niet zelf), is de banner boven de 12 maanden een waarschuwing met de plekken waar de actuele
// kwartaalcijfers staan, en noemt het lege UWV-blok geen vaste maand.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
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
import { MomentopnameBanner, ouderdomTekst, uwvBron } from '../components/dashboards/shared/momentopname'
import { UwvSection } from '../components/dashboards/shared/charts-arbeidsmarkt'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const UWV_DASHBOARD = 'https://www.uwv.nl/nl/arbeidsmarktinformatie/dashboards/dashboard-vacaturemarkt'
const CBS_TABEL = 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table'
// Zoals de backend het geeft op 25 november 2026 (data/arbeidsmarkt.ouderdom): 42 hele maanden, verouderd.
const OUD = { peildatum_ouderdom_maanden: 42, verouderd: true }

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

  it('uwvBron noemt de ouderdom als de payload haar geeft', () => {
    expect(uwvBron('2023-05-16', 42)).toBe('UWV Open Match, peildatum 16 mei 2023, ruim 3 jaar oud')
    expect(uwvBron('2023-05-16')).toBe('UWV Open Match, peildatum 16 mei 2023')
    expect(uwvBron(null, null)).toBe('UWV Open Match, peildatum onbekend')
  })
})

describe('de banner (#1219)', () => {
  it('noemt peildatum en ouderdom en waarschuwt bij een verouderde stand, met de bronnen van nu', async () => {
    // De klok staat op 25 november 2026; de ouderdom komt uit de props, niet uit de klok.
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-11-25T10:00:00Z'))
    await renderIn(createElement(MomentopnameBanner, { peildatum: '2023-05-16', ouderdomMaanden: 42, verouderd: true }))

    const banner = container.querySelector('.db-momentopname')
    expect(banner.getAttribute('role')).toBe('note')
    expect(banner.classList.contains('db-momentopname--verouderd')).toBe(true)
    expect(banner.textContent).toContain('peildatum 16 mei 2023 (ruim 3 jaar geleden)')
    expect(banner.textContent).toContain('UWV werkt deze open dataset sinds mei 2023 niet meer bij')
    expect(banner.textContent).toMatch(/UWV en CBS publiceren de actuele vacatures per kwartaal/)
    const links = [...banner.querySelectorAll('a')].map(a => a.getAttribute('href'))
    expect(links).toEqual([UWV_DASHBOARD, CBS_TABEL])
    for (const a of banner.querySelectorAll('a')) {
      expect(a.getAttribute('rel')).toBe('noopener noreferrer')
      expect(a.getAttribute('aria-label')).toMatch(/opent in een nieuw tabblad/)
    }
  })

  it('een stand van vorige maand: alleen peildatum en ouderdom, geen waarschuwing', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-11-25T10:00:00Z'))
    await renderIn(createElement(MomentopnameBanner, { peildatum: '2026-10-20', ouderdomMaanden: 1, verouderd: false }))

    const banner = container.querySelector('.db-momentopname')
    expect(banner.getAttribute('role')).toBe('note')
    expect(banner.classList.contains('db-momentopname--verouderd')).toBe(false)
    expect(banner.textContent).toContain('peildatum 20 oktober 2026 (1 maand geleden)')
    expect(banner.textContent).not.toMatch(/niet meer bij|per kwartaal/)
    expect(banner.querySelectorAll('a')).toHaveLength(0)
  })

  it('rekent niet zelf: zonder ouderdom in de payload staat er alleen de peildatum', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-01-01T00:00:00Z'))
    await renderIn(createElement(MomentopnameBanner, { peildatum: '2023-05-16' }))

    const tekst = container.querySelector('.db-momentopname').textContent
    expect(tekst).toContain('peildatum 16 mei 2023.')
    expect(tekst).not.toMatch(/geleden|jaar oud/)
  })
})

describe('de ondertitels en de matchduiding noemen de ouderdom (#1219)', () => {
  it('vacatureaanbod, gediplomeerden tegenover vacatures en de duiding', async () => {
    const duiding = {
      drempel: 1.2, vacatures_peildatum: '2023-05-16', ...OUD, diplomajaren: [2023, 2024, 2025], sectormapping: {},
    }
    payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_duiding: duiding }
    payloads['/api/dashboard/regio'] = { ...dashboards.regio, vacatureaanbod: { ...dashboards.regio.vacatureaanbod, ...OUD } }
    await renderIn(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.arbeidsmarktmatch.instelling }))

    const subs = [...container.querySelectorAll('.chart-sub, .db-sectie-sub')].map(s => s.textContent)
    const gediplomeerden = subs.find(s => s.startsWith('Gemiddeld aantal gediplomeerden'))
    expect(gediplomeerden).toContain('UWV Open Match, peildatum 16 mei 2023, ruim 3 jaar oud')
    expect(container.textContent).toMatch(/Openstaande vacatures per beroepencluster|Clusters passend bij opleidingssectoren/)
    expect(container.textContent).toMatch(/— UWV Open Match, peildatum 16 mei 2023, ruim 3 jaar oud \(momentopname\)/)
    expect(container.querySelector('.db-match-duiding').textContent).toContain('UWV Open Match, peildatum 16 mei 2023, ruim 3 jaar oud')
    const banners = [...container.querySelectorAll('.db-momentopname')]
    expect(banners).toHaveLength(3)
    for (const banner of banners) {
      expect(banner.classList.contains('db-momentopname--verouderd')).toBe(true)
      expect(banner.textContent).toContain('peildatum 16 mei 2023 (ruim 3 jaar geleden)')
    }
  })
})

describe('het lege UWV-blok noemt geen vaste maand (#1220)', () => {
  it('noemt de periode van de UWV-catalogus uit de payload', async () => {
    const data = { vacatureaanbod: {}, uwv_periode: '2019-11-26 t/m 2023-05-16 (wekelijkse snapshots)' }
    const tekst = (await renderIn(createElement(UwvSection, { data, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain(
      'Geen vacaturegegevens beschikbaar voor Utrecht in de data van UWV Open Match, die loopt van 26 november 2019 t/m 16 mei 2023 (wekelijkse snapshots).',
    )
    expect(tekst).not.toContain('Open Match data')
  })

  it('noemt de peildatum uit de payload als die er is', async () => {
    const data = { vacatureaanbod: { peildatum: '2023-05-16', clusters: {} }, uwv_periode: '2019-11-26 t/m 2023-05-16' }
    const tekst = (await renderIn(createElement(UwvSection, { data, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain('in de data van UWV Open Match, peildatum 16 mei 2023.')
    expect(tekst).not.toContain('26 november 2019')
  })

  it('zonder peildatum en periode geen maand', async () => {
    const tekst = (await renderIn(createElement(UwvSection, { data: {}, provincie: 'Utrecht', dark: false }))).textContent

    expect(tekst).toContain('Geen vacaturegegevens beschikbaar voor Utrecht in de data van UWV Open Match.')
    expect(tekst).not.toMatch(/mei 2023/)
  })

  it('de component zelf noemt geen vaste maand', () => {
    const bron = readFileSync(join(__dirname, '..', 'components', 'dashboards', 'shared', 'charts-arbeidsmarkt.jsx'), 'utf8')
    expect(bron).not.toContain('t/m mei 2023')
    expect(bron).not.toContain('Open Match data')
  })
})
