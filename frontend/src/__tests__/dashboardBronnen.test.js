// @vitest-environment jsdom
// De bronvermelding van de dashboards komt uit het bronblok van de payload (#904): footer, badge en de ROA-teksten
// noemen wat de lading echt gebruikte, met versie of editie, peildatum, voorlopige jaren en ophaalmoment. Landelijk
// noemt per niveau de populatie (#919).
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated'
import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling'
import { InlineDashboardNationaal } from '../components/dashboards/nationaal'
import { PrognoseSection, RoaSection } from '../components/dashboards/shared/charts-arbeidsmarkt'
import { bronBadge, bronDetails, bronLabel, bronnenVan, POPULATIE_NATIONAAL } from '../components/dashboards/shared/shell'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))
vi.mock('react-plotly.js', () => ({ default: () => null }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const antwoord = body => ({ status: 200, ok: true, json: async () => body })

let root
let container

beforeEach(() => {
  localStorage.clear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function render(element, payloads = {}) {
  vi.stubGlobal('fetch', vi.fn(path => Promise.resolve(antwoord(payloads[path.split('?')[0]] ?? { gevonden: true }))))
  await act(async () => { root.render(element) })
}

const footer = () => [...container.querySelectorAll('.dashboard-sources-list a')].map(a => ({ tekst: a.textContent, href: a.href }))
const details = () => [...container.querySelectorAll('.dashboard-sources-meta')].map(d => d.textContent)
const badge = () => [...container.querySelectorAll('.meta-badge')].map(b => b.textContent).find(t => t.startsWith('Bron:'))

// Regels zoals data/bronblok.py ze geeft.
const OPGEHAALD = '2026-11-05T09:30:00+00:00'
const duo = (dataset, titel, extra = {}) => ({
  bron: 'DUO', dataset, titel, url: `https://onderwijsdata.duo.nl/dataset/${dataset}`,
  editie: null, last_modified: '2026-04-08T03:04:43', peilmoment: 'versie van 08-04-2026', peildatum: '1 oktober',
  voorlopig: false, voorlopig_jaren: [], opgehaald_op: OPGEHAALD, ...extra,
})
const P01 = duo('p01hoinges', 'Ingeschrevenen hoger onderwijs')
const P04 = duo('p04hogdipl', 'Gediplomeerden in het hoger onderwijs')
const MBO_DIPL = duo('gediplomeerde-mbo-studenten', 'Gediplomeerde mbo-studenten', {
  peildatum: '1 oktober van het studiejaar', voorlopig: true, voorlopig_jaren: ['2025'],
})
const UWV = {
  bron: 'UWV', dataset: 'uwv-open-match-data', titel: 'UWV Open Match Data', url: 'https://data.overheid.nl/dataset/uwv-open-match-data',
  editie: null, last_modified: null, peilmoment: 'peildatum 2023-05-16', peildatum: '2023-05-16',
  voorlopig: false, voorlopig_jaren: [], opgehaald_op: OPGEHAALD,
}
const ROA = {
  bron: 'ROA', dataset: 'ais2030', titel: 'AIS tot 2030', url: 'https://doi.org/10.34894/DVQTOG',
  editie: '2025', versie: 'v20251218', last_modified: null, peilmoment: 'editie 2025, versie v20251218', peildatum: null,
  voorlopig: false, voorlopig_jaren: [], opgehaald_op: OPGEHAALD,
}

describe('bronregel (#904)', () => {
  it('noemt bron, titel uit de catalogus en dataset-ID', () => {
    expect(bronLabel(P04)).toBe('DUO — Gediplomeerden in het hoger onderwijs (p04hogdipl)')
    expect(bronLabel({ ...P04, titel: 'p04hogdipl' })).toBe('DUO — p04hogdipl')
  })

  it('noemt versie, peildatum, voorlopige jaren en het ophaalmoment', () => {
    expect(bronDetails(MBO_DIPL)).toEqual([
      'versie van 08-04-2026', 'peildatum 1 oktober van het studiejaar', 'cijfers 2025 voorlopig', 'opgehaald 5 nov 2026',
    ])
  })

  it('herhaalt de peildatum van UWV niet', () => {
    expect(bronDetails(UWV)).toEqual(['peildatum 2023-05-16', 'opgehaald 5 nov 2026'])
  })

  it('laat weg wat de bron niet geeft, zoals de versie van een datastore-dump', () => {
    expect(bronDetails({ bron: 'DUO', dataset: 'x', peilmoment: null, peildatum: null, voorlopig: false })).toEqual([])
  })

  it('voegt het bronblok van meer payloads samen, elke dataset één keer, en filtert op bron', () => {
    const regio = { bronnen: [P01, UWV, ROA] }
    const rendement = { bronnen: [P01, P04] }

    expect(bronnenVan([regio, rendement], ['DUO']).map(b => b.dataset)).toEqual(['p01hoinges', 'p04hogdipl'])
    expect(bronnenVan([regio, null, {}]).map(b => b.bron)).toEqual(['DUO', 'UWV', 'ROA'])
    expect(bronBadge([P01, P04, UWV, ROA])).toBe('DUO, UWV & ROA')
  })
})

describe('arbeidsmarkt: bronnen uit de payload (#904, #917)', () => {
  const MATCH = bronnen => ({ gevonden: true, type: 'mbo', provincie: 'Utrecht', gediplomeerden_per_sector: {}, vacatures_per_sector: {}, bronnen })

  it('toont in footer en badge de bronnen van de lading, met de editie van ROA', async () => {
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'X' }), {
      '/api/dashboard/arbeidsmarktmatch': MATCH([MBO_DIPL, UWV, ROA]),
      // De DUO-bronnen van /api/dashboard/regio horen bij Mijn instelling, niet hier.
      '/api/dashboard/regio': { gevonden: true, bronnen: [P01, UWV, ROA] },
    })

    const links = footer()
    expect(links.map(l => l.tekst)).toEqual([
      'DUO — Gediplomeerde mbo-studenten (gediplomeerde-mbo-studenten)',
      'UWV — UWV Open Match Data (uwv-open-match-data)',
      'ROA — AIS tot 2030 (ais2030)',
    ])
    expect(links[0].href).toBe('https://onderwijsdata.duo.nl/dataset/gediplomeerde-mbo-studenten')
    expect(links[2].href).toBe('https://doi.org/10.34894/DVQTOG')
    expect(details()[2]).toContain('editie 2025, versie v20251218')
    expect(details()[0]).toContain('cijfers 2025 voorlopig')
    expect(badge()).toBe('Bron: DUO, UWV & ROA')
  })

  it('noemt een bron die niet laadde niet in footer en badge', async () => {
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'X' }), {
      '/api/dashboard/arbeidsmarktmatch': MATCH([MBO_DIPL, ROA]),
      '/api/dashboard/regio': { gevonden: true, bronnen: [] },
    })

    expect(footer().map(l => l.tekst)).not.toContain('UWV — UWV Open Match Data (uwv-open-match-data)')
    expect(badge()).toBe('Bron: DUO & ROA')
  })

  it('zet de ROA-editie uit het bronblok in de grafiekteksten', () => {
    const roa = { 'mbo 4': { werkloosheid: 2, 'vast dienstverband': 70, 'buiten de vakrichting': 10 } }
    const prognose = { 'mbo 4': { totaal: 'goed' } }
    act(() => root.render(createElement('div', null,
      createElement(RoaSection, { data: { arbeidsmarkt_roa: roa, bronnen: [ROA] }, dark: false }),
      createElement(PrognoseSection, { data: { arbeidsmarkt_prognose: prognose, bronnen: [ROA] } }),
    )))

    expect(container.textContent).toContain('ROA, SIS 2024, editie 2025, versie v20251218')
    expect(container.textContent).toContain('ROA, AIS tot 2030, editie 2025, versie v20251218')
    expect(container.textContent).not.toContain('AIS2030')
  })

  it('noemt zonder bronblok de onderdelen zonder editie, in plaats van een vaste editie', () => {
    const prognose = { 'mbo 4': { totaal: 'goed' } }
    act(() => root.render(createElement(PrognoseSection, { data: { arbeidsmarkt_prognose: prognose } })))

    expect(container.textContent).toContain('ROA, AIS tot 2030')
    expect(container.textContent).not.toContain('editie')
  })
})

describe('mijn instelling: de DUO-bronnen van regio en rendement (#904)', () => {
  it('toont de DUO-bestanden van beide ladingen samen, zonder UWV en ROA', async () => {
    await render(createElement(InlineDashboardMijnInstelling, { instelling: 'X' }), {
      '/api/dashboard/regio': { gevonden: true, type: 'ho', bronnen: [P01, UWV, ROA] },
      '/api/dashboard/rendement': { gevonden: true, type: 'ho', bronnen: [P01, P04] },
    })

    expect(footer().map(l => l.tekst)).toEqual([bronLabel(P01), bronLabel(P04)])
    expect(badge()).toBe('Bron: DUO')
  })
})

describe('landelijk: populatie en bron per type (#919, #928)', () => {
  it('noemt per type van de instelling de populatie van de ranking', () => {
    expect(POPULATIE_NATIONAAL).toEqual({ hbo: 'hogescholen (hbo)', wo: 'universiteiten (wo)', mbo: 'mbo-instellingen' })
  })

  const MBO_STUDENTEN = duo('mbo-studenten-per-instelling', 'Mbo-studenten per instelling')
  const PAYLOAD = (type, soort, n, bron) => ({
    gevonden: true, type, alle_instellingen: [{ naam: 'X', ingeschrevenen: 10, type: soort }], eigen_positie: { zorg: 1 },
    positie_populatie: { zorg: n - 1 }, populatie: { soort, n }, bronnen: [bron],
  })

  for (const [type, soort, n, populatie, bron] of [
    ['ho', 'hbo', 36, 'alle 36 hogescholen (hbo)', P01],
    ['ho', 'wo', 18, 'alle 18 universiteiten (wo)', P01],
    ['mbo', 'mbo', 54, 'alle 54 mbo-instellingen', MBO_STUDENTEN],
  ]) {
    it(`toont voor ${soort} de populatie in beide ondertitels, de positie met populatie en de bron uit de payload`, async () => {
      await render(createElement(InlineDashboardNationaal, { instelling: 'X' }), { '/api/dashboard/nationaal': PAYLOAD(type, soort, n, bron) })

      const tekst = container.textContent
      expect(tekst).toContain(`Totaal ingeschrevenen — ${populatie}`)
      expect(tekst).toContain(`Ranking binnen ${populatie} per sector/leerweg`)
      expect(tekst).toContain(`1e van ${n - 1} ${soort}`)
      expect(tekst).not.toContain('hbo + wo')
      const links = footer()
      expect(links).toHaveLength(1)
      expect(links[0].href).toBe(bron.url)
      expect(links[0].tekst).toContain(`(${bron.dataset})`)
      expect(badge()).toBe('Bron: DUO, som per instelling')
    })
  }
})
