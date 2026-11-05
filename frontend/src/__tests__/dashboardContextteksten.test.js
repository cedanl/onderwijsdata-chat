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

// Het wo-dashboard: dezelfde ho-payload, maar het benchmark is het nationale wo-gemiddelde.
const WO = {
  ...HBO,
  instelling: 'Universiteit Utrecht',
  benchmark: {
    ...HBO.benchmark,
    label: 'Nationaal WO gemiddelde (excl. eigen instelling)',
    regio_type: 'nationaal',
    n_instellingen: 16,
    n_per_jaar: { ingeschrevenen: { 2023: 16, 2024: 16, 2025: 16 } },
    totaal_ingeschrevenen: { 2023: 290000, 2024: 293000, 2025: 295707 },
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
  benchmark: { ...HBO.benchmark, eerstejaars: { 2023: 5000, 2024: 5200 } },
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

describe('de totaal-KPI volgt het benchmarktype (#918)', () => {
  it('wo: "Landelijk totaal" en geen "in regio"', async () => {
    await dashboard(WO)
    expect(tekst()).toContain('Landelijk totaal 2025')
    expect(tekst()).toContain('295.707')
    expect(tekst()).not.toContain('Regio totaal')
    expect(tekst()).not.toContain('instellingen in regio')
    expect(tekst()).toContain('16 instellingen')
  })

  it.each([['hbo', HBO], ['mbo', MBO]])('%s: blijft "Regio totaal" met "instellingen in regio"', async (_niveau, regio) => {
    await dashboard(regio)
    expect(tekst()).toContain('Regio totaal')
    expect(tekst()).not.toContain('Landelijk totaal')
    expect(tekst()).toMatch(/\d+ instellingen in regio/)
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
