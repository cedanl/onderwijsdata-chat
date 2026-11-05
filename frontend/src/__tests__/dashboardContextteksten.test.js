// @vitest-environment jsdom
// #918: de teksten van "Mijn instelling" volgen het niveau (mbo, hbo, wo) en het benchmarktype; #920: de Eerstejaars-KPI
// zegt het als zijn laatste jaar achterloopt op de ingeschrevenen. Eén render van het hele dashboard per niveau, met de
// payload zoals de server hem geeft: type "mbo" of "ho", en bij wo benchmark.regio_type "nationaal".
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
import DashboardPage from '../pages/DashboardPage'
import { MemoryRouter } from 'react-router-dom'
import { mijnInstellingBeschrijving } from '../workbooks'
import { schooljaarLabel } from '../schooljaar'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const HBO = dashboards.regio
const RATIO_ONDERTITEL = 'pipeline-gezondheid'

// Het wo-dashboard: dezelfde ho-payload, maar het benchmark is landelijk, met de reden van die terugval (#926).
const WO_TERUGVAL = 'te weinig universiteiten in provincie Utrecht (0 andere)'
const WO = {
  ...HBO,
  instelling: 'Universiteit Utrecht',
  benchmark: {
    ...HBO.benchmark,
    label: `Landelijk, 16 andere universiteiten — ${WO_TERUGVAL}`,
    populatie: 'universiteiten in heel Nederland',
    soort: 'wo',
    terugval: WO_TERUGVAL,
    regio_type: 'nationaal',
    regio_naam: 'Nederland',
    n_instellingen: 16,
    n_per_jaar: { ingeschrevenen: { 2023: 16, 2024: 16, 2025: 16 } },
    // Eigen instelling plus de 16 andere (#951): het totaal telt de eigen instelling mee.
    totaal_regio: { 2023: 326201, 2024: 328780, 2025: 330765 },
  },
}

// Het mbo-dashboard: instromende-mbo-studenten loopt een jaar achter op de ingeschrevenen (2024 tegen 2025).
const MBO = {
  ...HBO,
  type: 'mbo',
  instelling: 'ROC van Amsterdam',
  eerstejaars: { 2023: 11000, 2024: 11602 },
  geslacht: undefined,
  geslacht_trend: undefined,
  benchmark: {
    ...HBO.benchmark,
    label: 'Arbeidsmarktregio Groot Amsterdam, 6 andere mbo-instellingen',
    populatie: 'mbo-instellingen in arbeidsmarktregio Groot Amsterdam',
    soort: 'mbo',
    regio_naam: 'Groot Amsterdam',
    eerstejaars: { 2023: 5000, 2024: 5200 },
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

async function renderIn(element) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
}

async function dashboard(regio) {
  payloads['/api/dashboard/regio'] = regio
  await renderIn(createElement(InlineDashboardMijnInstelling, { instelling: regio.instelling }))
  return container
}

const tekst = () => container.textContent
// De Eerstejaars-KPI van de instroomsectie; de tegel in de kerncijfers heet nog "Eerstejaars 2025" (notatie: #904).
const instroomKpiLabel = () => [...container.querySelectorAll('.kpi-label')].find(k => /^Eerstejaars \d{4}\//.test(k.textContent))?.textContent
const noten = () => [...container.querySelectorAll('[data-testid="jaarnoot"]')]

describe('schooljaarlabel', () => {
  it('schrijft een startjaar zoals chat en rapport: 2024/25', () => {
    expect(schooljaarLabel(2024)).toBe('2024/25')
    expect(schooljaarLabel('2025')).toBe('2025/26')
    expect(schooljaarLabel(2099)).toBe('2099/00')
  })
})

describe('de kaartbeschrijving van Mijn instelling (#918)', () => {
  it('noemt gender bij hbo en wo, niet bij mbo', () => {
    expect(mijnInstellingBeschrijving('hbo')).toMatch(/gender/)
    expect(mijnInstellingBeschrijving('wo')).toMatch(/gender/)
    expect(mijnInstellingBeschrijving('mbo')).not.toMatch(/gender/)
  })

  it('belooft geen gender als het niveau onbekend is', () => {
    expect(mijnInstellingBeschrijving(null)).not.toMatch(/gender/)
  })

  it("belooft diploma's per eerstejaars alleen bij mbo, en nergens een rendement (#898)", () => {
    expect(mijnInstellingBeschrijving('mbo')).toMatch(/diploma's per eerstejaars/)
    for (const sector of ['hbo', 'wo', null]) expect(mijnInstellingBeschrijving(sector)).not.toMatch(/per eerstejaars/)
    for (const sector of ['mbo', 'hbo', 'wo', null]) expect(mijnInstellingBeschrijving(sector)).not.toMatch(/rendement/)
  })

  it.each([
    ['ROC van Amsterdam', false],
    ['Hogeschool Utrecht', true],
    ['Universiteit Utrecht', true],
  ])('toont in de galerij voor %s gender: %s', async (naam, gender) => {
    const type = naam.startsWith('ROC') ? 'mbo' : naam.startsWith('Hogeschool') ? 'hbo' : 'wo'
    const instellingen = [{ naam, type, aliassen: [] }]
    await renderIn(createElement(MemoryRouter, null, createElement(DashboardPage, { settings: { instelling: naam }, instellingen })))
    const kaart = [...container.querySelectorAll('.wb-card')].find(k => k.textContent.includes('Mijn instelling'))
    expect(kaart.textContent.includes('gender')).toBe(gender)
  })
})

describe('"(HO)" in de ondertitel van Instroom ratio (#918)', () => {
  it.each([
    ['hbo', HBO, true],
    ['wo', WO, true],
    ['mbo', MBO, false],
  ])('%s: ondertitel noemt "(HO)": %s', async (_niveau, regio, ho) => {
    await dashboard(regio)
    const ondertitel = [...container.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.includes(RATIO_ONDERTITEL))
    expect(ondertitel).toBeTruthy()
    expect(ondertitel.textContent.includes('(HO)')).toBe(ho)
  })
})

describe('de totaal-KPI volgt het benchmarktype (#918) en telt de eigen instelling mee (#951)', () => {
  it('wo: "Landelijk totaal" met de eigen universiteit en de andere', async () => {
    await dashboard(WO)
    expect(tekst()).toContain('Landelijk totaal 2025')
    expect(tekst()).toContain('330.765')
    expect(tekst()).not.toContain('Regio totaal')
    expect(tekst()).toContain('Universiteit Utrecht en 16 andere universiteiten in heel Nederland')
  })

  // "Regio totaal" was de som van de peers zonder de eigen instelling, naast "6 instellingen in regio" terwijl de
  // tabel er 8 toonde (#951).
  it.each([
    ['hbo', HBO, 'Hogeschool Utrecht en 6 andere hogescholen in arbeidsmarktregio Midden-Utrecht'],
    ['mbo', MBO, 'ROC van Amsterdam en 6 andere mbo-instellingen in arbeidsmarktregio Groot Amsterdam'],
  ])('%s: "Regio totaal" noemt de eigen instelling en de andere', async (_niveau, regio, groep) => {
    await dashboard(regio)
    expect(tekst()).toContain('Regio totaal 2025')
    expect(tekst()).toContain('78.311')
    expect(tekst()).not.toContain('Landelijk totaal')
    expect(tekst()).toContain(groep)
    expect(tekst()).not.toMatch(/\d+ instellingen in regio/)
  })
})

// #951: "Gediplomeerden per jaar" beloofde een vergelijking met het gemiddelde die bij het mbo ontbrak.
describe('een lijngrafiek belooft het gemiddelde alleen als het er is (#951)', () => {
  const ondertitel = titel => [...container.querySelectorAll('.chart-card')]
    .find(k => k.querySelector('.chart-title')?.textContent === titel)?.querySelector('.chart-sub')?.textContent

  it('met gemiddelde: eigen instelling vs. de groep', async () => {
    await dashboard(HBO)
    expect(ondertitel('Gediplomeerden per jaar')).toContain('eigen instelling vs. gemiddelde hogescholen')
  })

  it('zonder gemiddelde: zegt dat het er niet is', async () => {
    const { gediplomeerden: _weg, ...zonder } = HBO.benchmark
    await dashboard({ ...HBO, benchmark: zonder })
    expect(ondertitel('Gediplomeerden per jaar')).toContain('geen gemiddelde van de vergelijkingsgroep')
    expect(ondertitel('Gediplomeerden per jaar')).not.toContain(' vs. ')
  })
})

describe('de kop en de teksten noemen de vergelijkingsgroep (#926)', () => {
  it.each([
    ['hbo', HBO, 'hogescholen in arbeidsmarktregio Midden-Utrecht'],
    ['wo', WO, 'universiteiten in heel Nederland'],
    ['mbo', MBO, 'mbo-instellingen in arbeidsmarktregio Groot Amsterdam'],
  ])('%s: kop met regio, aantal en terugval; ondertitels met het type', async (_niveau, regio, populatie) => {
    await dashboard(regio)
    expect(tekst()).toContain(`${regio.instelling} vs. ${regio.benchmark.label}`)
    expect(tekst()).toContain(`Gem. ${populatie}`)
    expect(tekst()).toContain(`eigen instelling vs. gemiddelde ${populatie}`)
    expect(tekst()).not.toMatch(/excl\. eigen instelling|nationaal wo gemiddelde/i)
  })

  it('wo: de kop zegt waarom de vergelijking landelijk is', async () => {
    await dashboard(WO)
    expect(tekst()).toContain('Universiteit Utrecht vs. Landelijk, 16 andere universiteiten — te weinig universiteiten in provincie Utrecht (0 andere)')
  })
})

describe('de jaarnoot bij de Eerstejaars-KPI (#920)', () => {
  it('mbo: eerstejaars 2024 tegen ingeschrevenen 2025 krijgt een noot met schooljaar en bron', async () => {
    await dashboard(MBO)
    expect(noten()).toHaveLength(2) // de KPI-kaart en de tegel in de kerncijfers
    for (const noot of noten()) {
      expect(noot.textContent).toContain('2024/25')
      expect(noot.textContent).toContain('laatst beschikbare jaar')
      expect(noot.textContent).toContain('Instromende MBO-studenten')
      expect(noot.textContent).toContain('2025/26')
    }
    expect(instroomKpiLabel()).toBe('Eerstejaars 2024/25')
  })

  it.each([['hbo', HBO], ['wo', WO]])('%s: eerstejaars en ingeschrevenen lopen even ver, dus geen noot', async (_niveau, regio) => {
    await dashboard(regio)
    expect(noten()).toHaveLength(0)
    expect(instroomKpiLabel()).toBe('Eerstejaars 2025/26')
  })

  it('ho: een eerstejaarsreeks die achterloopt krijgt de noot met de ho-bron', async () => {
    await dashboard({ ...HBO, eerstejaars: { 2023: 6593, 2024: 6548 } })
    expect(noten().length).toBeGreaterThan(0)
    expect(noten()[0].textContent).toContain('Eerstejaars HO per instelling')
  })
})
