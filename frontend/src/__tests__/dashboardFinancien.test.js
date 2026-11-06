// @vitest-environment jsdom
// #935, #936: de financiën van het bestuur en het personeel (WOPI) op Mijn instelling. De pagina rekent niets: elk getal,
// signaal en voorbehoud komt uit de payload. Leeg blijft leeg ("—", nooit 0), een signaal is geen oordeel, en een kaart
// op een bron die hier geen antwoord geeft (/api/config `bronnen`), vraagt niets op.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))
vi.mock('react-plotly.js', () => ({ default: () => null }))

import { FinancienSection, grensPerJaar, signaalRegels } from '../components/dashboards/mijn-instelling/financien-section'
import { PersoneelSection } from '../components/dashboards/mijn-instelling/personeel-section'
import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling'
import { BronnenAan } from '../bronnenAan'
import { FIN, PERS, FIN_BRON, WOPI_BRON } from './fixtures/bestuurEnPersoneel'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

let container
let root
beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const render = element => { act(() => root.render(element)); return container.textContent }

describe('financiën van het bestuur (#935)', () => {
  it('toont per verslagjaar het bestuur naast het gewogen sectorcijfer, met de variant', () => {
    const tekst = render(createElement(FinancienSection, { data: FIN, dark: false }))

    expect(tekst).toContain('Financiën van het bestuur')
    expect(tekst).toContain('Stichting Hogeschool Dun (bestuur 30000), verslagjaren 2021-2025')
    expect(tekst).toContain('gewogen sectorcijfer hbo van de Inspectie')
    const rij2024 = [...container.querySelectorAll('tbody tr')].find(r => r.textContent.startsWith('2024'))
    expect(rij2024.textContent).toContain('geconsolideerd')
    expect(rij2024.textContent).toContain('0,69sector 0,64')
    expect(rij2024.textContent).toContain('197')
  })

  it('laat een lege waarde leeg, nooit 0', () => {
    render(createElement(FinancienSection, { data: FIN, dark: false }))

    const rij2025 = [...container.querySelectorAll('tbody tr')].find(r => r.textContent.startsWith('2025'))
    const rentabiliteit = rij2025.querySelectorAll('td')[3].textContent
    expect(rentabiliteit).toBe('—sector -4,55%')
    expect(container.textContent).toContain('de waarde ontbreekt in de bron (geen 0)')
  })

  it('noemt een signaal in woorden, als signaal en niet als oordeel', () => {
    const tekst = render(createElement(FinancienSection, { data: FIN, dark: false }))

    expect(tekst).toContain('Signalen (geen oordeel).')
    expect(tekst).toContain('Inspectie van het Onderwijs (2024)')
    expect(tekst).toContain('2025: Solvabiliteit II 0,25 onder de signaleringswaarde 0,3; Liquiditeit 0,6 onder de signaleringswaarde 1 (totale baten van € 3 tot en met € 12 miljoen).')
    expect(tekst).not.toMatch(/ranking|rangschik|slecht|zwak|gemiddelde van de besturen/i)
  })

  it('zegt het als er geen signaal is', () => {
    const zonder = structuredClone(FIN)
    zonder.financien.eenheden[0].reeks.forEach(j => { j.signaleringen = [] })
    expect(render(createElement(FinancienSection, { data: zonder, dark: false }))).toContain('ligt geen kengetal onder een signaleringswaarde')
  })

  it('toont de voorbehouden, de meldingen en de wissel van variant', () => {
    const tekst = render(createElement(FinancienSection, { data: FIN, dark: false }))

    for (const v of FIN.financien.voorbehouden) expect(tekst).toContain(v)
    expect(tekst).toContain(FIN.financien.meldingen[0])
    expect(tekst).toContain('De variant wisselt binnen de reeks')
    expect(tekst).toContain('Wat de kengetallen meten')
  })

  it('geeft de signaleringswaarde per jaar voor de stippellijn, en geen bij solvabiliteit I of rentabiliteit', () => {
    const { reeks } = FIN.financien.eenheden[0]
    expect(grensPerJaar(FIN.financien, reeks, 'solvabiliteit_2')).toEqual([0.3, 0.3])
    expect(grensPerJaar(FIN.financien, reeks, 'liquiditeit')).toEqual([0.5, 1.0])
    expect(grensPerJaar(FIN.financien, reeks, 'rentabiliteit_procent')).toBeNull()
    expect(signaalRegels(reeks)).toHaveLength(1)
  })

  it('geeft bij een instelling zonder bestuur de nette melding', () => {
    const melding = 'Voor tUL (27YA) staat geen bestuur in DUO\'s adressenbestand: er zijn geen financiële cijfers aan te koppelen.'
    const tekst = render(createElement(FinancienSection, { data: { gevonden: true, financien: null, melding }, dark: false }))

    expect(tekst).toContain('Financiën van het bestuur')
    expect(tekst).toContain(melding)
    expect(container.querySelector('table')).toBeNull()
  })

  it('toont niets als de lading niet slaagde of de instelling onbekend is', () => {
    expect(render(createElement(FinancienSection, { data: { gevonden: true, financien: null }, dark: false }))).toBe('')
    expect(render(createElement(FinancienSection, { data: { gevonden: false }, dark: false }))).toBe('')
  })
})

describe('personeel van een universiteit (#936)', () => {
  it('toont het laatste jaar in fte zonder GEZO, met peildatum en aandeel tijdelijk', () => {
    const tekst = render(createElement(PersoneelSection, { data: PERS, dark: false }))

    expect(tekst).toContain('Personeel (wo)')
    expect(tekst).toContain('In fte, zonder GEZO; WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025')
    expect(tekst).toContain('6.184,36 fte')
    expect(tekst).toContain('3.584,05 fte')
    expect(tekst).toContain('2.600,31 fte')
    expect(tekst).toContain('36,6%')
    expect(tekst).toContain('peildatum 31-12-2025')
    expect(tekst).not.toMatch(/medewerkers|mensen/)
  })

  it('toont de vaste zinnen', () => {
    const tekst = render(createElement(PersoneelSection, { data: PERS, dark: false }))
    for (const v of PERS.personeel.voorbehouden) expect(tekst).toContain(v)
    expect(tekst).toContain(PERS.personeel.definitie)
    expect(tekst).toContain(PERS.personeel.noot)
  })

  it('verschijnt niet bij een hogeschool of mbo-instelling', () => {
    expect(render(createElement(PersoneelSection, { data: { gevonden: true, sector: 'hbo', personeel: null }, dark: false }))).toBe('')
    expect(render(createElement(PersoneelSection, { data: { gevonden: true, sector: 'mbo', personeel: null }, dark: false }))).toBe('')
  })

  it('geeft bij een universiteit buiten WOPI de vaste melding', () => {
    const melding = 'Theologische Universiteit Apeldoorn (21QO) is een wo-instelling, maar geen lid van Universiteiten van Nederland en staat niet in het WOPI-bestand: er zijn geen personeelscijfers.'
    const tekst = render(createElement(PersoneelSection, { data: { gevonden: true, sector: 'wo', personeel: null, melding }, dark: false }))

    expect(tekst).toContain(melding)
    expect(tekst).not.toContain('fte')
  })
})

describe('mijn instelling: de kaarten volgen /api/config (#935, #936)', () => {
  const antwoord = body => ({ status: 200, ok: true, json: async () => body })

  async function laad(bronnen, payloads, { instelling = 'Universiteit Utrecht', sector = null, wacht = false } = {}) {
    // `wacht`: alleen de regio antwoordt, de rest blijft laden, zodat de laadvlakken in beeld blijven.
    const fetch = vi.fn(path => {
      const pad = path.split('?')[0]
      if (wacht && pad !== '/api/dashboard/regio') return new Promise(() => {})
      return Promise.resolve(antwoord(payloads[pad] ?? { gevonden: true }))
    })
    vi.stubGlobal('fetch', fetch)
    await act(async () => {
      root.render(createElement(BronnenAan.Provider, { value: bronnen }, createElement(InlineDashboardMijnInstelling, { instelling, sector })))
    })
    return fetch.mock.calls.map(([pad]) => pad.split('?')[0])
  }

  // #973: het personeel bestaat alleen voor wo; een bekende hogeschool of mbo-instelling vraagt het niet op en krijgt
  // geen laadvlak (in de testlog vroeg elke hbo- en mbo-instelling het eindpunt op voor de kaart verdween).
  it.each([
    ['Hogeschool Utrecht', 'hbo'],
    ['ROC Midden Nederland', 'mbo'],
  ])('vraagt bij %s (%s) het personeel niet op', async (instelling, sector) => {
    const regio = { '/api/dashboard/regio': { gevonden: true, type: sector === 'mbo' ? 'mbo' : 'ho', bronnen: [] } }
    const paden = await laad({ financien: true, wo_personeel: true }, regio, { instelling, sector, wacht: true })

    expect(paden).toContain('/api/dashboard/financien')
    expect(paden).not.toContain('/api/dashboard/personeel')
    expect(container.querySelector('[aria-label="Financiën van het bestuur laden"]')).not.toBeNull()
    expect(container.querySelector('[aria-label="Personeel laden"]')).toBeNull()
  })

  it.each([
    ['een universiteit', 'wo'],
    ['een instelling die de lijst niet kent', null],
  ])('vraagt bij %s het personeel wel op', async (_, sector) => {
    const regio = { '/api/dashboard/regio': { gevonden: true, type: 'ho', bronnen: [] } }
    const paden = await laad({ financien: true, wo_personeel: true }, regio, { sector, wacht: true })

    expect(paden).toContain('/api/dashboard/personeel')
    expect(container.querySelector('[aria-label="Personeel laden"]')).not.toBeNull()
  })

  it('vraagt niets op als de bronnen hier geen antwoord geven', async () => {
    const paden = await laad({}, {})

    expect(paden).not.toContain('/api/dashboard/financien')
    expect(paden).not.toContain('/api/dashboard/personeel')
    expect(container.textContent).not.toContain('Financiën van het bestuur')
  })

  it('laadt beide kaarten, met hun bronnen in de footer en een gat bovenaan', async () => {
    const paden = await laad({ financien: true, wo_personeel: true }, {
      '/api/dashboard/regio': { gevonden: true, type: 'ho', bronnen: [] },
      '/api/dashboard/financien': { gevonden: true, sector: 'wo', financien: null, bronnen: [], niet_beschikbaar: [{ onderdeel: 'Financiën van het bestuur', bron: 'DUO', reden: 'de bron antwoordde niet op tijd' }] },
      '/api/dashboard/personeel': { ...PERS, bronnen: [WOPI_BRON] },
    })

    expect(paden).toContain('/api/dashboard/financien')
    expect(paden).toContain('/api/dashboard/personeel')
    const tekst = container.textContent
    expect(tekst).toContain('Financiën van het bestuur: de bron antwoordde niet op tijd.')
    expect(tekst).toContain('Personeel (wo)')
    const footer = [...container.querySelectorAll('.dashboard-sources-list li')].map(li => li.textContent)
    expect(footer.some(t => t.includes('UNL — Universiteiten van Nederland, WOPI-personeelsbestand (unl:wopi)'))).toBe(true)
  })

  it('zet de editie van de financiën in de footer', async () => {
    await laad({ financien: true }, {
      '/api/dashboard/regio': { gevonden: true, type: 'ho', bronnen: [] },
      '/api/dashboard/financien': { ...FIN, bronnen: [FIN_BRON] },
    })

    const footer = [...container.querySelectorAll('.dashboard-sources-list li')].map(li => li.textContent).join(' | ')
    expect(footer).toContain('DUO — Financiële verantwoording uit XBRL (financien)')
    expect(footer).toContain('editie verslagjaren 2021-2025, versie van 15 september 2026')
    expect(footer).toContain('peildatum 31 december 2025')
  })
})
