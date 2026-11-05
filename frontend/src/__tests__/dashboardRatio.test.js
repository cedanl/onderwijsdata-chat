// @vitest-environment jsdom
// #927: de ratio diploma/inschrijving deelt gediplomeerden en ingeschrevenen van hetzelfde jaar (bij hbo/wo loopt
// DUO's diplomareeks een jaar achter, dus 2024 en niet 2025), de peers volgen dezelfde regel, de pagina zegt waarom de
// diplomareeks eerder stopt, en de staafkleur in de vergelijking schakelt niet meer bij een drempel zonder uitleg.
// Twee payloads zoals de server ze geeft: hbo/wo (diploma's t/m 2024, ingeschrevenen t/m 2025) en mbo (beide t/m 2025).
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

import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling/index'
import { buildRendementVergelijkingData } from '../components/dashboards/shared/charts-rendement'
import { ratioJaar, ratioPercentage, diplomaRatio } from '../components/dashboards/shared/diploma-ratio'
import { gediplomeerdenNoot } from '../components/dashboards/shared/kpis'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// hbo: ingeschrevenen 2023-2025, gediplomeerden 2022-2024; de peers zitten in dezelfde jaren.
const HBO = dashboards.regio

// mbo: DUO publiceert de gediplomeerden hier tot en met 2025, dus beide reeksen lopen even ver.
const MBO = {
  ...HBO,
  type: 'mbo',
  instelling: 'ROC van Amsterdam',
  gediplomeerden: { 2023: 5854, 2024: 6438, 2025: 6200 },
  benchmark: {
    ...HBO.benchmark,
    peers: {
      ...HBO.benchmark.peers,
      gediplomeerden: {
        'Protestantse Theologische Universiteit': { 2023: 40, 2024: 51, 2025: 60 },
        'Hogeschool voor de Kunsten Utrecht': { 2023: 870, 2024: 869, 2025: 900 },
        'Marnix Academie': { 2023: 374, 2024: 305, 2025: 400 },
        'Universiteit Utrecht': { 2023: 12040, 2024: 12136, 2025: 12500 },
      },
    },
  },
}

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  for (const k of Object.keys(payloads)) delete payloads[k]
})

async function dashboard(regio) {
  payloads['/api/dashboard/regio'] = regio
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(InlineDashboardMijnInstelling, { instelling: regio.instelling })) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
  return container
}

const kpiTegel = label => [...container.querySelectorAll('.kpi-card')].find(k => k.querySelector('.kpi-label')?.textContent.startsWith(label))
const noten = () => [...container.querySelectorAll('[data-testid="diplomanoot"]')]
const kaart = titel => [...container.querySelectorAll('.chart-card')].find(k => k.querySelector('.chart-title')?.textContent === titel)

describe('het jaar van de ratio', () => {
  it('hbo: het laatste jaar waarin gediplomeerden en ingeschrevenen er allebei zijn, 2024 en niet 2025', () => {
    expect(ratioJaar(HBO.gediplomeerden, HBO.ingeschrevenen)).toBe('2024')
  })

  it('mbo: beide reeksen lopen tot 2025, dus 2025', () => {
    expect(ratioJaar(MBO.gediplomeerden, MBO.ingeschrevenen)).toBe('2025')
  })

  it('geeft niets zonder gemeenschappelijk jaar of zonder reeks', () => {
    expect(ratioJaar({ 2020: 5 }, { 2021: 10 })).toBeNull()
    expect(ratioJaar(undefined, { 2021: 10 })).toBeNull()
    expect(ratioJaar({ 2021: 5 }, null)).toBeNull()
  })

  it('slaat een jaar zonder ingeschrevenen over (delen door 0)', () => {
    expect(ratioJaar({ 2023: 5, 2024: 6 }, { 2023: 10, 2024: 0 })).toBe('2023')
  })

  it('rondt de ratio af op een geheel percentage, uit hetzelfde jaar', () => {
    expect(ratioPercentage(HBO.gediplomeerden, HBO.ingeschrevenen, '2024')).toBe(18) // 6438 / 35780
    expect(ratioPercentage(HBO.gediplomeerden, HBO.ingeschrevenen, '2025')).toBeNull() // geen diploma's in 2025
  })

  it('diplomaRatio bundelt jaar en percentage van de eigen instelling', () => {
    expect(diplomaRatio(HBO)).toEqual({ jaar: '2024', procent: 18 })
    expect(diplomaRatio(MBO)).toEqual({ jaar: '2025', procent: 18 }) // 6200 / 35058
    expect(diplomaRatio({})).toBeNull()
  })
})

describe('de vergelijking per instelling', () => {
  it('hbo: de eigen instelling en de peers delen 2024 door 2024', () => {
    const data = buildRendementVergelijkingData(HBO, HBO.instelling, false)
    expect(data.jaar).toBe('2024')
    const perNaam = Object.fromEntries(data.labels.map((naam, i) => [naam, data.datasets[0].data[i]]))
    expect(perNaam[HBO.instelling]).toBe(18) // 6438 / 35780
    expect(perNaam['Universiteit Utrecht']).toBe(32) // 12136 / 37700, niet 12136 / 37090 (2025)
    expect(perNaam['Marnix Academie']).toBe(24) // 305 / 1280
    expect(perNaam['Hogeschool voor de Kunsten Utrecht']).toBe(21) // 869 / 4086
    expect(perNaam['Protestantse Theologische Universiteit']).toBe(38) // 51 / 134
  })

  it('mbo: beide jaren zijn 2025 en de peers delen 2025 door 2025', () => {
    const data = buildRendementVergelijkingData(MBO, MBO.instelling, false)
    expect(data.jaar).toBe('2025')
    const perNaam = Object.fromEntries(data.labels.map((naam, i) => [naam, data.datasets[0].data[i]]))
    expect(perNaam['Universiteit Utrecht']).toBe(34) // 12500 / 37090
    expect(perNaam['Marnix Academie']).toBe(30) // 400 / 1338
  })

  it('een peer zonder cijfers in dat jaar valt weg en wordt genoemd, in plaats van een ander jaar te lenen', () => {
    const peers = structuredClone(HBO.benchmark.peers)
    delete peers.gediplomeerden['Marnix Academie']['2024']
    const data = buildRendementVergelijkingData({ ...HBO, benchmark: { ...HBO.benchmark, peers } }, HBO.instelling, false)
    expect(data.labels).not.toContain('Marnix Academie')
    expect(data.weggelaten).toEqual(['Marnix Academie'])
  })

  it('sorteert aflopend', () => {
    const waarden = buildRendementVergelijkingData(HBO, HBO.instelling, false).datasets[0].data
    expect(waarden).toEqual([...waarden].sort((a, b) => b - a))
  })

  it('kleurt alleen de eigen instelling anders, ook bij een peer boven de oude drempel van 70 %', () => {
    const peers = structuredClone(HBO.benchmark.peers)
    peers.gediplomeerden['Universiteit Utrecht']['2024'] = 30000 // 80 % van 37.700
    const data = buildRendementVergelijkingData({ ...HBO, benchmark: { ...HBO.benchmark, peers } }, HBO.instelling, false)
    const kleuren = data.datasets[0].backgroundColor
    expect(data.datasets[0].data).toContain(80)
    const eigen = data.labels.indexOf(HBO.instelling)
    expect(new Set(kleuren.filter((_, i) => i !== eigen)).size).toBe(1)
    expect(kleuren[eigen]).not.toBe(kleuren[eigen === 0 ? 1 : 0])
  })

  it('geeft niets als de eigen instelling geen gemeenschappelijk jaar heeft', () => {
    expect(buildRendementVergelijkingData({ ...HBO, gediplomeerden: { 2019: 1 } }, HBO.instelling, false)).toBeNull()
  })
})

describe('de noot bij de gediplomeerden', () => {
  it('noemt het laatste jaar uit de data als de diploma\'s achterlopen op de ingeschrevenen', () => {
    expect(gediplomeerdenNoot({ diplJaar: '2024', ingesJaar: '2025', perioden: HBO.perioden })).toBe(
      'DUO publiceert de gediplomeerden tot en met diplomajaar 2024; de ingeschrevenen lopen door tot 2025/26.',
    )
  })

  it('laat de jaartallen kaal zonder het soort jaar uit de payload (#904)', () => {
    expect(gediplomeerdenNoot({ diplJaar: '2024', ingesJaar: '2025' })).toBe(
      'DUO publiceert de gediplomeerden tot en met 2024; de ingeschrevenen lopen door tot 2025.',
    )
  })

  it.each([
    [{ diplJaar: '2025', ingesJaar: '2025' }],
    [{ diplJaar: undefined, ingesJaar: '2025' }],
    [{ diplJaar: '2024', ingesJaar: undefined }],
  ])('zwijgt als er niets achterloopt of een jaar ontbreekt (%j)', args => {
    expect(gediplomeerdenNoot(args)).toBeNull()
  })
})

describe('Mijn instelling met hbo/wo-data (diploma\'s 2024, inschrijvingen 2025)', () => {
  it('de ratio-KPI noemt het jaar van beide cijfers, als diplomajaar en als schooljaar (#904)', async () => {
    await dashboard(HBO)
    const tegel = kpiTegel('Ratio diploma/inschrijving')
    expect(tegel).toBeTruthy()
    expect(tegel.querySelector('.kpi-value').textContent).toBe('18%')
    expect(tegel.textContent).toContain('gediplomeerden diplomajaar 2024 en ingeschrevenen 2024/25')
    expect(tegel.textContent).not.toContain('2025/26')
  })

  it('de gediplomeerden-KPI en de kerncijfers-tegel zeggen tot en met welk jaar DUO publiceert', async () => {
    await dashboard(HBO)
    expect(noten()).toHaveLength(2)
    for (const noot of noten()) {
      expect(noot.textContent).toContain('tot en met diplomajaar 2024')
      expect(noot.textContent).toContain('tot 2025/26')
      expect(noot.closest('.kpi-card').querySelector('.kpi-label').textContent).toBe('Gediplomeerden diplomajaar 2024')
    }
  })

  it('de grafiek Gediplomeerden per jaar herhaalt het in haar onderschrift', async () => {
    await dashboard(HBO)
    expect(kaart('Gediplomeerden per jaar').querySelector('.chart-sub').textContent).toContain('tot en met diplomajaar 2024')
  })

  it('de vergelijking noemt het jaar en geen groene drempel', async () => {
    await dashboard(HBO)
    const sub = kaart('Rendement vergelijking').querySelector('.chart-sub').textContent
    expect(sub).toContain('2024')
    expect(sub).not.toMatch(/groen|70/)
  })
})

describe('Mijn instelling met mbo-data (beide 2025)', () => {
  it('de ratio-KPI gebruikt 2025 en er is geen diplomanoot', async () => {
    await dashboard(MBO)
    const tegel = kpiTegel('Ratio diploma/inschrijving')
    expect(tegel.textContent).toContain('gediplomeerden diplomajaar 2025 en ingeschrevenen 2025/26')
    expect(tegel.querySelector('.kpi-value').textContent).toBe('18%')
    expect(noten()).toHaveLength(0)
    expect(kaart('Gediplomeerden per jaar').querySelector('.chart-sub').textContent).not.toContain('tot en met')
  })

  it('de vergelijking noemt 2025', async () => {
    await dashboard(MBO)
    expect(kaart('Rendement vergelijking').querySelector('.chart-sub').textContent).toContain('2025')
  })
})
