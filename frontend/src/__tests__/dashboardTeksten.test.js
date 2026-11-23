// @vitest-environment jsdom
// #1181: de teksten en begrippen op de drie vaste dashboards (Mijn instelling, Landelijk, Arbeidsmarkt). Eén render van
// elk dashboard met de payloads van de server; de tests lezen wat een gebruiker leest: tekst, aria-labels, tooltips en
// de namen van de reeksen en assen van de grafieken.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import dashboards from './fixtures/dashboards.json'

// De grafiekstub toont wat Chart.js zou tekenen als tekst: de naam van het canvas, de reeksen en de astitels.
function astitels(opties) {
  return Object.values(opties?.scales ?? {}).map(as => as?.title?.text).filter(Boolean)
}
function GrafiekStub({ data, options, ...rest }) {
  const teksten = [...(data?.datasets ?? []).map(d => d.label), ...astitels(options)].filter(Boolean)
  return createElement('div', { role: 'img', 'aria-label': rest['aria-label'] }, teksten.join(' | '))
}
vi.mock('react-chartjs-2', () => ({ Bar: props => GrafiekStub(props), Line: props => GrafiekStub(props) }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const payloads = {}
vi.mock('../api', async importOriginal => ({
  ...(await importOriginal()),
  fetchDashboardData: vi.fn(async endpoint => payloads[endpoint] ?? {}),
}))

import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling/index'
import { PersoneelSection } from '../components/dashboards/mijn-instelling/personeel-section'
import { FinancienSection } from '../components/dashboards/mijn-instelling/financien-section'
import { FIN, PERS } from './fixtures/bestuurEnPersoneel'
import { InlineDashboardNationaal } from '../components/dashboards/nationaal/index'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated/index'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const HBO = dashboards.regio
// Een hogeschool zonder genoeg collega's in de regio vergelijkt met heel Nederland (#926); een wo-instelling ook.
const LANDELIJK = {
  ...HBO,
  benchmark: {
    ...HBO.benchmark,
    label: 'Landelijk, 18 andere hogescholen — te weinig hogescholen van vergelijkbare omvang in provincie Utrecht',
    populatie: 'hogescholen in heel Nederland',
    regio_type: 'nationaal',
    regio_naam: 'Nederland',
  },
}

// De bronbestanden van de app, zonder tests en fixtures.
function bestanden(map) {
  return readdirSync(map, { withFileTypes: true }).flatMap(e => {
    const pad = `${map}${e.name}`
    if (e.isDirectory()) return e.name.startsWith('__') ? [] : bestanden(`${pad}/`)
    return /\.(js|jsx)$/.test(e.name) ? [pad] : []
  })
}
// Commentaarregels en commentaar achter code vallen weg; een URL (`://`) blijft staan.
const zonderCommentaar = tekst => tekst.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '')

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

async function mijnInstelling(regio, rendement = dashboards.rendement) {
  payloads['/api/dashboard/regio'] = regio
  payloads['/api/dashboard/rendement'] = rendement
  await renderIn(createElement(InlineDashboardMijnInstelling, { instelling: regio.instelling }))
}

async function nationaal(payload = dashboards.nationaal) {
  payloads['/api/dashboard/nationaal'] = payload
  await renderIn(createElement(InlineDashboardNationaal, { instelling: payload.instelling }))
}

const MATCH_DUIDING = { drempel: 1.2, vacatures_peildatum: '2023-05-16', diplomajaren: [2023, 2024, 2025], sectormapping: {} }

async function arbeidsmarkt(regio = HBO) {
  payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_duiding: MATCH_DUIDING }
  payloads['/api/dashboard/regio'] = regio
  await renderIn(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.arbeidsmarktmatch.instelling }))
}

// Alles wat een gebruiker of schermlezer van de pagina krijgt, per stuk: de tekst van elk blad van de pagina en de
// aria-labels, titels en alt-teksten.
function teksten() {
  const stukken = []
  for (const el of container.querySelectorAll('*')) {
    if (!el.children.length && el.textContent.trim()) stukken.push(el.textContent.trim())
    for (const a of ['aria-label', 'title', 'alt']) if (el.getAttribute(a)) stukken.push(el.getAttribute(a))
  }
  return stukken
}
const alles = () => teksten().join('\n')
const kaartMetTitel = titel => [...container.querySelectorAll('.chart-card')].find(k => k.querySelector('.chart-title')?.textContent === titel)
const sectieKop = titel => [...container.querySelectorAll('h2')].find(h => h.textContent === titel)

// #1130: bij een landelijke vergelijkingsgroep zegt geen tekst "regio", "benchmark-regio" of "regiototaal".
describe('de gebiedsteksten volgen de vergelijkingsgroep (#1130)', () => {
  const REGIOWOORDEN = /benchmark-regio|regiototaal|in de regio|Regio totaal/i

  it('landelijk: geen titel, ondertitel, legenda, tabelbijschrift of alt-tekst zegt "regio"', async () => {
    await mijnInstelling(LANDELIJK)
    const tekst = alles()
    expect(tekst).not.toMatch(REGIOWOORDEN)
    // De regio van de instelling zelf (badge) blijft: dat is haar adres, niet de vergelijkingsgroep.
    expect(tekst).toContain('Regio Midden-Utrecht')
  })

  it('landelijk: de kaart, de tabel en de grafieken noemen heel Nederland', async () => {
    await mijnInstelling(LANDELIJK)
    expect(sectieKop('Locaties in heel Nederland')).toBeTruthy()
    expect(sectieKop('Locaties in heel Nederland').parentElement.textContent).toContain('Instellingen in heel Nederland (ster = eigen instelling)')
    expect(sectieKop('Overzicht concurrenten').parentElement.textContent).toMatch(/\d+ instellingen in heel Nederland/)
    expect(container.querySelector('caption.sr-only').textContent).toBe('Overzicht concurrenten in heel Nederland, gesorteerd op ingeschrevenen')
    expect(kaartMetTitel('Marktaandeel over tijd').textContent).toContain('% van het landelijke totaal ingeschrevenen')
    expect(kaartMetTitel('Marktpositie 2025/26').textContent).toContain('per instelling in heel Nederland')
  })

  it('regionaal: de regiotekst blijft staan', async () => {
    await mijnInstelling(HBO)
    expect(sectieKop('Locaties in de regio')).toBeTruthy()
    expect(sectieKop('Locaties in de regio').parentElement.textContent).toContain('Instellingen in de regio (ster = eigen instelling)')
    expect(sectieKop('Overzicht concurrenten').parentElement.textContent).toMatch(/\d+ instellingen in de regio/)
    expect(kaartMetTitel('Marktaandeel over tijd').textContent).toContain('% van het regiototaal ingeschrevenen')
    expect(kaartMetTitel('Marktpositie 2025/26').textContent).toContain('per instelling in de regio')
    expect(alles()).not.toMatch(/benchmark-regio/)
  })

  it.each([
    ['landelijk', LANDELIJK, 'hogescholen in heel Nederland'],
    ['regionaal', HBO, 'hogescholen in arbeidsmarktregio Midden-Utrecht'],
  ])('%s: de diplomeringskop en de grafiek eronder noemen dezelfde vergelijkingsgroep', async (_soort, regio, groep) => {
    await mijnInstelling(regio)
    expect(sectieKop('Diplomering').parentElement.textContent).toContain(`vergeleken met ${groep}`)
    expect(kaartMetTitel('Gediplomeerden per jaar').textContent).toContain(groep)
  })
})

// #1136: dezelfde DUO-telling van personen heet overal "Ingeschrevenen"; "Inschrijvingen" is een telling van inschrijvingen.
describe('één woord voor de telling van personen (#1136)', () => {
  const sectorTrends = () => [...container.querySelectorAll('.chart-title, .db-sectie-sub')].map(k => k.textContent).filter(t => /per sector over tijd/.test(t))

  it('Mijn instelling noemt de sectortrend "Ingeschrevenen per sector over tijd"', async () => {
    await mijnInstelling(HBO)
    expect(sectorTrends()).toEqual(['Ingeschrevenen per sector over tijd'])
  })

  it('Landelijk noemt dezelfde telling met hetzelfde woord', async () => {
    await nationaal()
    expect(sectorTrends()).toEqual(['Ingeschrevenen per sector over tijd'])
  })

  it.each([
    ['Mijn instelling', () => mijnInstelling(HBO)],
    ['Landelijk', () => nationaal()],
    ['Arbeidsmarkt', () => arbeidsmarkt()],
  ])('%s: geen tekst over "inschrijvingen" bij een telling van personen', async (_naam, laad) => {
    await laad()
    expect(alles()).not.toMatch(/inschrijvingen/i)
  })
})

// #1137: één spelling per begrip.
describe('één spelling per begrip (#1137)', () => {
  it('de arbeidsmarkt schrijft "beroepencluster", niet "beroepscluster"', async () => {
    await arbeidsmarkt()
    expect(alles()).not.toMatch(/beroepscluster/i)
  })

  it('de totaal-tegel van Mijn instelling heet "Regiototaal", één woord zoals de ondertitels', async () => {
    await mijnInstelling(HBO)
    expect([...container.querySelectorAll('.kpi-label')].map(e => e.textContent)).toContain('Regiototaal 2025/26')
    expect(alles()).not.toMatch(/regio totaal/i)
  })

  // De afgekeurde varianten staan nergens in de broncode van de app (tests en commentaar niet meegeteld).
  it('geen afgekeurde variant in frontend/src', () => {
    const afgekeurd = /beroepscluster|Regio totaal|regio-totaal/i
    const root = `${join(__dirname, '..')}/`
    const overtreders = bestanden(root)
      .filter(pad => afgekeurd.test(zonderCommentaar(readFileSync(pad, 'utf8'))))
      .map(pad => pad.slice(root.length))
    expect(overtreders).toEqual([])
  })
})

// #1135: de verhouding gediplomeerden/ingeschrevenen is geen rendement.
describe('de verhouding gediplomeerden/ingeschrevenen heet geen rendement (#1135)', () => {
  const VERHOUDING = "Diploma's per 100 ingeschrevenen"
  const REDEN_HO = 'Voor hbo en wo staat hier geen rendement. DUO publiceert voor het hoger onderwijs geen cohorten.'
  // Mbo: DUO publiceert de gediplomeerden tot en met 2025, ook van de peers.
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
          'Hogeschool voor de Kunsten Utrecht': { 2023: 870, 2024: 869, 2025: 900 },
          'Universiteit Utrecht': { 2023: 12040, 2024: 12136, 2025: 12500 },
        },
      },
    },
  }
  const MBO_RENDEMENT = {
    instelling: 'ROC van Amsterdam', gevonden: true, type: 'mbo',
    definitie: { naam: "Diploma's na 3 jaar per eerstejaars", termijn: 3, definitie: "Per cohort de diploma's 3 jaar later, gedeeld door de eerstejaars." },
    perioden: { cohorten: 'schooljaar', gediplomeerden: 'diplomajaar' },
    pseudo_cohorten: [{ instroom_jaar: 2021, instroom: 4459, gediplomeerden_t3: 4037, gediplomeerden_t4: null, gediplomeerden_t5: null }],
    rendement_per_jaar: { 2021: 0.9054 },
    weggelaten: {},
  }
  // Wat een kop, tegel, reeks of as zegt: geen lopende uitleg.
  const labels = () => [...container.querySelectorAll('h2, h3, .kpi-label, th, [role="img"]')].map(e => e.textContent)

  it('hbo: grafiek, reeks, as en tegel heten "Diploma\'s per 100 ingeschrevenen", en niets heet rendement', async () => {
    await mijnInstelling(HBO, { ...dashboards.rendement, geen_rendement: REDEN_HO })
    const kaart = kaartMetTitel(VERHOUDING)
    expect(kaart).toBeTruthy()
    // De reeks en de titel van de as (met eenheid) van de grafiek.
    expect(kaart.querySelector('[role="img"]').textContent).toBe(`${VERHOUDING} | ${VERHOUDING}`)
    expect([...container.querySelectorAll('.kpi-label')].map(e => e.textContent)).toContain(VERHOUDING)
    expect(labels().filter(t => /rendement/i.test(t))).toEqual([])
    // De noot zegt dat er geen rendement is, maar er staat geen rendementskop boven.
    expect(container.textContent).toContain('geen rendement')
    expect(sectieKop("Diploma's per cohort")).toBeTruthy()
  })

  it('mbo: de verhouding heet hetzelfde en de cohortmaat houdt haar eigen naam', async () => {
    await mijnInstelling(MBO, MBO_RENDEMENT)
    expect(kaartMetTitel(VERHOUDING)).toBeTruthy()
    expect(sectieKop("Diploma's na 3 jaar per eerstejaars")).toBeTruthy()
    expect(labels().filter(t => /rendement/i.test(t))).toEqual([])
  })
})

// #1133: geen Engelse woorden en vakjargon in de zichtbare teksten, grafiekreeksen en alt-teksten.
describe('geen Engelse woorden of jargon op de dashboards (#1133)', () => {
  const VERBODEN = /\b(stacked|ratio|pipeline|score|peers?|proxy|llm|pp)\b|\bvs\.|t\.o\.v\.|\bgem\.|dipl\.|\bt\+\d/i
  const COHORTEN = {
    instelling: 'Hogeschool Utrecht', gevonden: true, type: 'mbo',
    definitie: { naam: "Diploma's na 3 jaar per eerstejaars", termijn: 3, definitie: "Per cohort de diploma's 3 jaar later, gedeeld door de eerstejaars." },
    perioden: { cohorten: 'schooljaar', gediplomeerden: 'diplomajaar' },
    pseudo_cohorten: [
      { instroom_jaar: 2020, instroom: 4300, gediplomeerden_t3: 3900, gediplomeerden_t4: 3800, gediplomeerden_t5: 3700 },
      { instroom_jaar: 2021, instroom: 4459, gediplomeerden_t3: 4037, gediplomeerden_t4: 3925, gediplomeerden_t5: null },
    ],
    rendement_per_jaar: { 2020: 0.9, 2021: 0.9054 },
    weggelaten: {},
    benchmark_populatie: 'mbo-instellingen in heel Nederland',
    benchmark_rendement: { 2020: 0.8, 2021: 0.85 },
    benchmark_n_per_jaar: { 2020: 3, 2021: 3 },
    peers_rendement: { 'Hogeschool A': { 2020: 0.8, 2021: 0.85 } },
  }
  const overtredingen = () => teksten().filter(t => VERBODEN.test(t))

  it.each([
    ['regionaal', HBO],
    ['landelijk', LANDELIJK],
  ])('Mijn instelling (%s, met de cohortmaat)', async (_soort, regio) => {
    await mijnInstelling(regio, COHORTEN)
    expect(overtredingen()).toEqual([])
  })

  it('Landelijk', async () => {
    await nationaal()
    expect(overtredingen()).toEqual([])
  })

  it('Arbeidsmarkt', async () => {
    await arbeidsmarkt()
    expect(overtredingen()).toEqual([])
  })

  it('de arbeidsmarktmatch heeft op de galerij en de pagina één naam', async () => {
    const { BUILTIN_ARBEIDSMARKT } = await import('../workbooks')
    await arbeidsmarkt()
    expect(BUILTIN_ARBEIDSMARKT.description).toContain('Aansluiting op de arbeidsmarkt')
    expect(sectieKop('Aansluiting op de arbeidsmarkt')).toBeTruthy()
  })

  it('de sectorgrafiek noemt sectoren, niet faculteiten', async () => {
    await mijnInstelling(HBO)
    expect(kaartMetTitel('Ingeschrevenen per sector over tijd').textContent).toContain('welke sectoren groeien of krimpen')
    expect(alles()).not.toMatch(/faculteit/i)
  })
})

// #1134: noten noemen geen interne datasetcodes of kolomwaarden en geen onbekende afkortingen.
describe('noten zonder interne codes en afkortingen (#1134)', () => {
  // Een dataset-ID, een ruwe kolomwaarde of een afkorting die de lezer niet kent. De bronblokken (links met ID) vallen erbuiten.
  const INTERN = /p0\d[a-z]+|\b\d{5}NED\b|TOTAAL MBO|\bGEZO\b|\bOBP\b|\bXBRL\b|instromende-mbo|mbo-studenten-per/i
  const stukken = () => teksten().filter(t => INTERN.test(t))
  // Wat de server meegeeft bij "Landelijk" (data/dashboard.py, _landelijk_definitie).
  const LANDELIJK_NOOT = {
    maat: 'duo_som_per_instelling', dataset: 'p01hoinges', chat_dataset: '85423NED',
    definitie: 'de som van de DUO-aantallen ingeschrevenen per instelling over alle hogescholen; onderdrukte cellen tellen niet mee, dus een totaal kan een ondergrens zijn',
    verschil_met_chat: 'De chat geeft het landelijke aantal uit de CBS-cijfers over het hoger onderwijs. Dat is een andere telling, dus het getal in de chat kan van deze som afwijken.',
  }

  it('Landelijk zegt in gewone woorden waarom het getal van de chat kan afwijken', async () => {
    await nationaal({ ...dashboards.nationaal, landelijk: LANDELIJK_NOOT })
    expect(stukken()).toEqual([])
    expect(container.textContent).toContain('het getal in de chat kan van deze som afwijken')
  })

  it('de mbo-hoofdgroepen noemen geen bestand of kolomwaarde', async () => {
    await mijnInstelling({ ...HBO, type: 'mbo', ingeschrevenen_per_hoofdgroep: { Zorg: 4000, Techniek: 3000 }, ingeschrevenen_per_hoofdgroep_jaar: 2025 })
    expect(kaartMetTitel('Ingeschrevenen per hoofdgroep')).toBeTruthy()
    expect(stukken()).toEqual([])
  })

  it('het personeel en de financiën schrijven GEZO, OBP en XBRL niet uit in de teksten van de pagina', () => {
    for (const [Sectie, data] of [[PersoneelSection, PERS], [FinancienSection, FIN]]) {
      container = document.createElement('div')
      document.body.appendChild(container)
      root = createRoot(container)
      act(() => root.render(createElement(Sectie, { data, dark: false })))
      // De voorbehouden en definities komen woordelijk van de server en leggen de afkorting uit; de eigen koppen en
      // ondertitels van de pagina gebruiken ze niet.
      const eigen = [...container.querySelectorAll('h2, h3, .db-sectie-sub, .chart-sub, .kpi-label, [role="img"]')].map(e => e.textContent)
      expect(eigen.filter(t => INTERN.test(t))).toEqual([])
      act(() => root.unmount())
      container.remove()
      root = container = undefined
    }
  })
})

// #1146: de spatie tussen "ten minste" en het getal staat in de tekst, niet alleen als marge.
describe('"ten minste" staat los van het getal in de tekst (#1146)', () => {
  it('elke KPI met een ondergrens zegt "ten minste" met een spatie voor het getal', async () => {
    await mijnInstelling({ ...HBO, onderdrukt: { ingeschrevenen: { 2025: 2 } }, benchmark: { ...HBO.benchmark, onderdrukt: { ingeschrevenen: { 2025: 1 } } } })
    const waarden = [...container.querySelectorAll('.kpi-value, .kpi-trend')].map(e => e.textContent).filter(t => t.includes('ten minste'))
    expect(waarden.length).toBeGreaterThanOrEqual(2)
    for (const tekst of waarden) expect(tekst).toMatch(/ten minste \d/)
    expect(container.textContent).not.toMatch(/ten minste\d/)
  })

  it('de ruimte komt niet dubbel: geen marge naast de spatie', () => {
    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
    expect(css).toMatch(/\.kpi-ondergrens\s*{[^}]*white-space:\s*pre-wrap/)
    expect(css).toMatch(/\.kpi-trend \.kpi-ondergrens\s*{[^}]*white-space:\s*normal/)
    const bron = readFileSync(join(__dirname, '..', 'components/dashboards/shared/ondergrens.jsx'), 'utf8')
    expect(bron).not.toMatch(/marginRight/)
  })
})
