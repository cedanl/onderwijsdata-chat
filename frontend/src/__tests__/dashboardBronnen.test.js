// @vitest-environment jsdom
// De bronvermelding van Arbeidsmarkt en Landelijk klopt met wat het dashboard gebruikt (#917, #919): de badge en de
// footer komen uit dezelfde lijst, de DUO-gediplomeerden staan erin met dataset-ID, ROA heet zoals de DOI-pagina, en
// Landelijk noemt per niveau de populatie en de ene bron.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated'
import { InlineDashboardNationaal } from '../components/dashboards/nationaal'
import { PrognoseSection, RoaSection } from '../components/dashboards/shared/charts-arbeidsmarkt'
import { bronnenArbeidsmarkt, bronBadge, BRONNEN_NATIONAAL, POPULATIE_NATIONAAL } from '../components/dashboards/shared/shell'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))

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
const badge = () => [...container.querySelectorAll('.meta-badge')].map(b => b.textContent).find(t => t.startsWith('Bron:'))

const ROA_LABEL = 'ROA — AIS tot 2030, incl. SIS 2024'

describe('arbeidsmarkt: bronnen (#917)', () => {
  it('noemt voor een ho-instelling de DUO-gediplomeerden p04hogdipl, UWV en ROA, en dezelfde namen in de badge', () => {
    const bronnen = bronnenArbeidsmarkt('ho')

    expect(bronnen.map(b => b.label)).toEqual([
      'DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)',
      'UWV Open Match — Vacaturedata per provincie en beroepscluster',
      ROA_LABEL,
    ])
    expect(bronnen[0].url).toBe('https://onderwijsdata.duo.nl/datasets/p04hogdipl')
    expect(bronBadge(bronnen)).toBe('DUO, UWV & ROA')
  })

  it('noemt voor een mbo-instelling gediplomeerde-mbo-studenten, de dataset die load_dashboard_arbeidsmarktmatch leest', () => {
    const [duo] = bronnenArbeidsmarkt('mbo')

    expect(duo.label).toContain('(gediplomeerde-mbo-studenten)')
    expect(duo.url).toBe('https://onderwijsdata.duo.nl/datasets/gediplomeerde-mbo-studenten')
  })

  it('laat DUO weg uit footer en badge als er geen niveau is, zodat de badge niet meer belooft dan de footer', () => {
    const bronnen = bronnenArbeidsmarkt(undefined)

    expect(bronnen.map(b => b.kort)).toEqual(['UWV', 'ROA'])
    expect(bronBadge(bronnen)).toBe('UWV & ROA')
  })

  it('wijst ROA naar de DOI met de titel van die pagina', () => {
    const roa = bronnenArbeidsmarkt('ho').at(-1)

    expect(roa.url).toBe('https://doi.org/10.34894/DVQTOG')
    expect(roa.label).toBe(ROA_LABEL)
  })

  for (const [type, id] of [['ho', 'p04hogdipl'], ['mbo', 'gediplomeerde-mbo-studenten']]) {
    it(`toont op de pagina van een ${type}-instelling footer en badge uit dezelfde lijst`, async () => {
      await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'X' }), {
        '/api/dashboard/arbeidsmarktmatch': { gevonden: true, type, provincie: 'Utrecht', gediplomeerden_per_sector: {}, vacatures_per_sector: {} },
      })

      const links = footer()
      expect(links).toHaveLength(3)
      expect(links[0].href).toContain(`/datasets/${id}`)
      expect(links.at(-1).tekst).toBe(ROA_LABEL)
      expect(badge()).toBe('Bron: DUO, UWV & ROA')
    })
  }

  it('noemt ROA in de grafiekteksten met dezelfde namen als de footer', () => {
    const roa = { 'mbo 4': { werkloosheid: 2, 'vast dienstverband': 70, 'buiten de vakrichting': 10 } }
    const prognose = { 'mbo 4': { totaal: 'goed' } }
    act(() => root.render(createElement('div', null,
      createElement(RoaSection, { data: { arbeidsmarkt_roa: roa }, dark: false }),
      createElement(PrognoseSection, { data: { arbeidsmarkt_prognose: prognose } }),
    )))

    expect(container.textContent).toContain('ROA, AIS tot 2030')
    expect(container.textContent).toContain('SIS 2024')
    expect(container.textContent).not.toContain('AIS2030')
    expect(ROA_LABEL).toContain('AIS tot 2030')
    expect(ROA_LABEL).toContain('SIS 2024')
    // Geen vaste editie: die komt uit de data (/version) en een vast label loopt dan achter.
    expect(container.textContent).not.toContain('editie')
    expect(ROA_LABEL).not.toContain('editie')
  })
})

describe('landelijk: populatie en bron per niveau (#919)', () => {
  it('geeft per niveau één bron met dataset-ID in het label, ook voor mbo', () => {
    expect(BRONNEN_NATIONAAL.ho.map(b => b.label)).toEqual(['DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)'])
    expect(BRONNEN_NATIONAAL.mbo.map(b => b.label)).toEqual(['DUO Open Onderwijsdata — MBO studenten per instelling (mbo-studenten-per-instelling)'])
    expect(BRONNEN_NATIONAAL.ho[0].url).toBe('https://onderwijsdata.duo.nl/datasets/p01hoinges')
    expect(BRONNEN_NATIONAAL.mbo[0].url).toBe('https://onderwijsdata.duo.nl/datasets/mbo-studenten-per-instelling')
  })

  it('noemt de populatie van het ho hbo + wo, die van het mbo alle MBO-instellingen', () => {
    expect(POPULATIE_NATIONAAL).toEqual({ ho: 'alle HO-instellingen (hbo + wo)', mbo: 'alle MBO-instellingen' })
  })

  const PAYLOAD = type => ({
    gevonden: true, type, alle_instellingen: [{ naam: 'X', ingeschrevenen: 10 }], eigen_positie: { zorg: 1 },
  })

  for (const [type, populatie, id, ander] of [
    ['ho', 'alle HO-instellingen (hbo + wo)', 'p01hoinges', 'mbo-studenten-per-instelling'],
    ['mbo', 'alle MBO-instellingen', 'mbo-studenten-per-instelling', 'p01hoinges'],
  ]) {
    it(`toont voor ${type} de populatie in beide ondertitels en alleen de bron ${id}`, async () => {
      await render(createElement(InlineDashboardNationaal, { instelling: 'X' }), { '/api/dashboard/nationaal': PAYLOAD(type) })

      const tekst = container.textContent
      expect(tekst).toContain(`Totaal ingeschrevenen — ${populatie}`)
      expect(tekst).toContain(`Ranking binnen ${populatie} per sector/leerweg`)
      expect(tekst).not.toContain('alle instellingen')
      const links = footer()
      expect(links).toHaveLength(1)
      expect(links[0].href).toContain(`/datasets/${id}`)
      expect(links[0].tekst).toContain(`(${id})`)
      expect(links[0].href).not.toContain(ander)
    })
  }
})
