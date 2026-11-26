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
import { bronBadge, bronDetails, bronLabel, bronnenVan, bronVersiecode, DashboardSources, POPULATIE_NATIONAAL } from '../components/dashboards/shared/shell'
import { langeDatum, datumsInTekst } from '../components/dashboards/shared/datum'

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
// De vacatures sinds #1225 (data/bronblok.py, _cbs): tabel, link, licentie, kwartalen en de voorlopige kwartalen.
const KWARTALEN = ['2025 4e kwartaal', '2026 1e kwartaal', '2026 2e kwartaal', '2026 3e kwartaal']
const CBS = {
  bron: 'CBS', dataset: '83599NED', titel: 'Openstaande vacatures; SBI 2008, regio',
  url: 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table', licentie: 'CC BY 4.0',
  editie: null, last_modified: null, peilmoment: '2026 3e kwartaal; gemiddelde 2025 4e kwartaal t/m 2026 3e kwartaal',
  peildatum: null, voorlopig: true, voorlopig_jaren: KWARTALEN, opgehaald_op: OPGEHAALD,
}
const ROA = {
  bron: 'ROA', dataset: 'ais2030', titel: 'AIS tot 2030', url: 'https://doi.org/10.34894/DVQTOG',
  editie: '2026', sis: 'SIS 2025', versie: 'v20260826', last_modified: null, peilmoment: 'editie 2026, SIS 2025, versie v20260826', peildatum: null,
  voorlopig: false, voorlopig_jaren: [], opgehaald_op: OPGEHAALD,
}

describe('bronregel (#904)', () => {
  it('noemt bron, titel uit de catalogus en dataset-ID', () => {
    expect(bronLabel(P04)).toBe('DUO — Gediplomeerden in het hoger onderwijs (p04hogdipl)')
    expect(bronLabel({ ...P04, titel: 'p04hogdipl' })).toBe('DUO — p04hogdipl')
  })

  it('noemt versie, peildatum, voorlopige jaren en het ophaalmoment', () => {
    expect(bronDetails(MBO_DIPL)).toEqual([
      'versie van 8 april 2026', 'peildatum 1 oktober van het studiejaar', 'cijfers 2025 voorlopig', 'opgehaald 5 november 2026',
    ])
  })

  it('herhaalt een peildatum niet die het peilmoment al voluit noemt', () => {
    const voluit = { bron: 'DUO', dataset: 'x', peilmoment: 'peildatum 16 mei 2023', peildatum: '2023-05-16', voorlopig: false }
    expect(bronDetails(voluit)).toEqual(['peildatum 16 mei 2023'])
  })

  it('CBS 83599NED: kwartaal en gemiddelde, de voorlopige kwartalen en de licentie (#1225)', () => {
    expect(bronDetails(CBS)).toEqual([
      '2026 3e kwartaal; gemiddelde 2025 4e kwartaal t/m 2026 3e kwartaal',
      `cijfers ${KWARTALEN.join(', ')} voorlopig`,
      'licentie CC BY 4.0',
      'opgehaald 5 november 2026',
    ])
    expect(bronLabel(CBS)).toBe('CBS — Openstaande vacatures; SBI 2008, regio (83599NED)')
  })

  // #1143: elke datum als "16 mei 2023"; een technische versiecode staat in een tooltip, niet in de tekst.
  it('schrijft elke datum met de maand voluit, uit ISO of dd-mm-jjjj', () => {
    expect(langeDatum('2023-05-16')).toBe('16 mei 2023')
    expect(langeDatum('08-04-2026')).toBe('8 april 2026')
    expect(langeDatum('2026-11-20T10:15:00+00:00')).toBe('20 november 2026')
    expect(langeDatum('1 oktober')).toBe('1 oktober')
    expect(datumsInTekst('versie van 08-04-2026 en peildatum 2023-05-16')).toBe('versie van 8 april 2026 en peildatum 16 mei 2023')
  })

  it('laat de versiecode van ROA uit de tekst en zet haar in een tooltip bij de bronlink', async () => {
    expect(bronDetails(ROA)).toEqual(['editie 2026, SIS 2025', 'opgehaald 5 november 2026'])
    expect(bronVersiecode(ROA)).toBe('v20260826')
    expect(bronVersiecode(CBS)).toBeNull()
    expect(bronVersiecode(MBO_DIPL)).toBeNull() // "versie van 8 april 2026" is een datum, geen code
    await render(createElement(DashboardSources, { sources: [ROA] }))
    const link = container.querySelector('.dashboard-sources-list a')
    expect(link.getAttribute('title')).toBe('Versiecode v20260826')
    expect(container.textContent).not.toMatch(/v20260826/)
  })

  it('laat weg wat de bron niet geeft, zoals de versie van een datastore-dump', () => {
    expect(bronDetails({ bron: 'DUO', dataset: 'x', peilmoment: null, peildatum: null, voorlopig: false })).toEqual([])
  })

  it('voegt het bronblok van meer payloads samen, elke dataset één keer, en filtert op bron', () => {
    const regio = { bronnen: [P01, CBS, ROA] }
    const rendement = { bronnen: [P01, P04] }

    expect(bronnenVan([regio, rendement], ['DUO']).map(b => b.dataset)).toEqual(['p01hoinges', 'p04hogdipl'])
    expect(bronnenVan([regio, null, {}]).map(b => b.bron)).toEqual(['DUO', 'CBS', 'ROA'])
    expect(bronBadge([P01, P04, CBS, ROA])).toBe('DUO, CBS & ROA')
  })
})

describe('arbeidsmarkt: bronnen uit de payload (#904, #917)', () => {
  const MATCH = bronnen => ({ gevonden: true, type: 'mbo', provincie: 'Utrecht', gediplomeerden_per_sector: {}, vacatures_per_sector: {}, bronnen })

  it('toont in footer en badge de bronnen van de lading, met de editie van ROA', async () => {
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'X' }), {
      '/api/dashboard/arbeidsmarktmatch': MATCH([MBO_DIPL, CBS, ROA]),
      // De DUO-bronnen van /api/dashboard/regio horen bij Mijn instelling, niet hier.
      '/api/dashboard/regio': { gevonden: true, bronnen: [P01, CBS, ROA] },
    })

    const links = footer()
    expect(links.map(l => l.tekst)).toEqual([
      'DUO — Gediplomeerde mbo-studenten (gediplomeerde-mbo-studenten)',
      'CBS — Openstaande vacatures; SBI 2008, regio (83599NED)',
      'ROA — AIS tot 2030 (ais2030)',
    ])
    expect(links[1].href).toBe('https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table')
    expect(details()[1]).toContain('licentie CC BY 4.0')
    expect(details()[1]).toContain('voorlopig')
    expect(links[0].href).toBe('https://onderwijsdata.duo.nl/dataset/gediplomeerde-mbo-studenten')
    expect(links[2].href).toBe('https://doi.org/10.34894/DVQTOG')
    expect(details()[2]).toContain('editie 2026, SIS 2025')
    expect(details()[0]).toContain('cijfers 2025 voorlopig')
    expect(badge()).toBe('Bron: DUO, CBS & ROA')
  })

  it('noemt een bron die niet laadde niet in footer en badge', async () => {
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'X' }), {
      '/api/dashboard/arbeidsmarktmatch': MATCH([MBO_DIPL, ROA]),
      '/api/dashboard/regio': { gevonden: true, bronnen: [] },
    })

    expect(footer().map(l => l.tekst)).not.toContain('CBS — Openstaande vacatures; SBI 2008, regio (83599NED)')
    expect(badge()).toBe('Bron: DUO & ROA')
  })

  it('zet de ROA-editie uit het bronblok in de grafiekteksten', () => {
    const roa = { 'mbo 4': { werkloosheid: 2, 'vast dienstverband': 70, 'buiten de vakrichting': 10 } }
    const prognose = { 'mbo 4': { totaal: 'goed' } }
    act(() => root.render(createElement('div', null,
      createElement(RoaSection, { data: { arbeidsmarkt_roa: roa, bronnen: [ROA] }, dark: false }),
      createElement(PrognoseSection, { data: { arbeidsmarkt_prognose: prognose, bronnen: [ROA] } }),
    )))

    // #1091: editie en SIS-jaar komen uit het bronblok, zoals de backend ze uit het geladen bestand haalt.
    expect(container.textContent).toContain('ROA, SIS 2025, editie 2026')
    expect(container.textContent).toContain('ROA, AIS tot 2030, editie 2026')
    expect(container.textContent).not.toContain('SIS 2024')
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
  it('toont de DUO-bestanden van beide ladingen samen, zonder CBS-vacatures en ROA', async () => {
    await render(createElement(InlineDashboardMijnInstelling, { instelling: 'X' }), {
      '/api/dashboard/regio': { gevonden: true, type: 'ho', bronnen: [P01, CBS, ROA] },
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

  // #950: het marktaandeel rekent over het totaal van het eigen type; de pagina noemt die noemer.
  for (const [type, soort, populatie, studenten] of [
    ['ho', 'hbo', 'alle hogescholen (hbo)', 'alle hbo-studenten'],
    ['ho', 'wo', 'alle universiteiten (wo)', 'alle wo-studenten'],
    ['mbo', 'mbo', 'alle mbo-instellingen', 'alle mbo-studenten'],
  ]) {
    it(`noemt voor ${soort} de populatie van het marktaandeel`, async () => {
      const payload = {
        ...PAYLOAD(type, soort, 10, P01),
        eigen_sectoren: { RECHT: { 2025: 300 } },
        sectoren_landelijk: { RECHT: { 2025: 3000 } },
      }
      await render(createElement(InlineDashboardNationaal, { instelling: 'X' }), { '/api/dashboard/nationaal': payload })

      const tekst = container.textContent
      expect(tekst).toContain(`Aandeel in het landelijke totaal van ${populatie} per sector`)
      expect(tekst).toContain(`Aandeel van ${studenten} per sector, 2025`)
      expect(tekst).not.toContain('Percentage van landelijk totaal')
    })
  }
})
