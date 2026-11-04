// @vitest-environment jsdom
// Dashboardcijfers heten wat ze tellen en tellen op tot hun totaal (#899); ontbreekt is geen 0 (#902).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub({ data }) { return createElement('pre', { 'data-chart': 'bar' }, JSON.stringify(data)) },
  Line: function LineStub({ data }) { return createElement('pre', { 'data-chart': 'line' }, JSON.stringify(data)) },
}))

import { buildLeerwegenData, buildSectorTrendData, HoofdgroepenChart, LEERWEGEN_MBO } from '../components/dashboards/shared/charts-sector'
import { OndergrensNoot, isOndergrens } from '../components/dashboards/shared/ondergrens'
import { pctVrouwFromGeslacht } from '../components/dashboards/mijn-instelling/gender-section'
import { verdeelCohorten } from '../components/dashboards/mijn-instelling/rendement-section'
import { buildMarktaandeelPerSector } from '../components/dashboards/nationaal/index'

let container
let root
function render(el) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(el))
  return container
}
afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = container = undefined
})

describe('mbo-leerwegen (#899)', () => {
  it('tekent Extraneus mee, zodat de leerwegen optellen tot het totaal ingeschrevenen', () => {
    const leerwegen = {
      2024: { BBL: 4000, 'BOL voltijd': 14000, 'BOL deeltijd': 0, Extraneus: 200 },
      2025: { BBL: 4100, 'BOL voltijd': 14100, 'BOL deeltijd': 0, Extraneus: 234 },
    }
    const data = buildLeerwegenData(leerwegen)

    expect(LEERWEGEN_MBO).toContain('Extraneus')
    expect(data.datasets.map(d => d.label)).toEqual(LEERWEGEN_MBO)
    const som2025 = data.datasets.reduce((s, d) => s + d.data[1], 0)
    expect(som2025).toBe(4100 + 14100 + 234)
  })
})

describe('HoofdgroepenChart (#899)', () => {
  it('noemt TOTAAL MBO ingeschrevenen, geen eerstejaars of sectorkamers', () => {
    const el = render(createElement(HoofdgroepenChart, { perHoofdgroep: { 'Zorg en welzijn': 5000, Entree: 300 }, dark: false }))
    const tekst = el.textContent

    expect(tekst).toContain('Ingeschrevenen per hoofdgroep')
    expect(tekst).toContain('Geen eerstejaars')
    expect(tekst).not.toMatch(/sectorkamer/i)
    expect(tekst).not.toMatch(/eerstejaars per hoofdgroep/i)
    const data = JSON.parse(el.querySelector('[data-chart="bar"]').textContent)
    expect(data.datasets[0].label).toBe('Ingeschrevenen')
    expect(data.labels).toEqual(['Zorg en welzijn', 'Entree'])
  })
})

describe('ontbrekende waarden blijven een gat (#902)', () => {
  it('tekent een sector zonder waarde in een jaar als gat, niet als val naar 0', () => {
    const data = buildSectorTrendData({ ECONOMIE: { 2023: 100, 2025: 120 }, TECHNIEK: { 2023: 50, 2024: 55, 2025: 60 } })

    expect(data.labels).toEqual(['2023', '2024', '2025'])
    expect(data.datasets[0].data).toEqual([100, null, 120])
  })

  it('tekent een leerweg zonder waarde als gat', () => {
    const data = buildLeerwegenData({ 2023: { BBL: 300, 'BOL voltijd': 2000 }, 2025: { BBL: 310, 'BOL voltijd': 2100, 'BOL deeltijd': 0, Extraneus: 5 } })

    expect(data.datasets.find(d => d.label === 'Extraneus').data).toEqual([null, 5])
    expect(data.datasets.find(d => d.label === 'BOL deeltijd').data).toEqual([null, 0])
  })

  it('geeft geen aandeel vrouw als vrouw of man ontbreekt', () => {
    expect(pctVrouwFromGeslacht({ VROUW: 60 })).toBeNull()
    expect(pctVrouwFromGeslacht({ VROUW: 60, MAN: 40 })).toBe(60)
  })

  it('laat een sector zonder eigen of landelijke waarde weg en noemt hem, aflopend op aandeel', () => {
    const uit = buildMarktaandeelPerSector(
      { ECONOMIE: { 2025: 50 }, TECHNIEK: { 2025: 300 }, ONDERWIJS: { 2024: 10 }, BOLDT: { 2025: 0 } },
      { ECONOMIE: { 2025: 1000 }, TECHNIEK: { 2025: 1000 }, ONDERWIJS: { 2024: 500 }, BOLDT: { 2025: 100 } },
    )

    expect(uit.jaar).toBe(2025)
    expect(uit.data.labels).toEqual(['Techniek', 'Economie'])
    expect(uit.data.datasets[0].data).toEqual([30, 5])
    expect(uit.weggelaten).toEqual(['Onderwijs', 'BOLDT'])
  })

  it('verdeelt de cohorten in getoond, meer diploma\'s dan instroom en zonder diplomajaar', () => {
    const { rows, teVeel, zonderDiploma } = verdeelCohorten([
      { instroom_jaar: 2019, instroom: 100, gediplomeerden_t3: 60, gediplomeerden_t4: 70, gediplomeerden_t5: null },
      { instroom_jaar: 2020, instroom: 100, gediplomeerden_t3: 140, gediplomeerden_t4: null, gediplomeerden_t5: null },
      { instroom_jaar: 2023, instroom: 100, gediplomeerden_t3: null, gediplomeerden_t4: null, gediplomeerden_t5: null },
    ])

    expect(rows.map(c => c.instroom_jaar)).toEqual([2019])
    expect(teVeel).toEqual([2020])
    expect(zonderDiploma).toEqual([2023])
  })
})

describe('een som over onderdrukte cellen is een ondergrens (#902)', () => {
  it('herkent een jaar met lege cellen, ook met de jaarsleutel als tekst', () => {
    expect(isOndergrens({ 2023: 2 }, 2023)).toBe(true)
    expect(isOndergrens({ 2023: 2 }, '2023')).toBe(true)
    expect(isOndergrens({ 2023: 2 }, 2024)).toBe(false)
    expect(isOndergrens(undefined, 2024)).toBe(false)
  })

  it('zegt "ten minste" met de jaren per reeks, en niets zonder lege cellen', () => {
    const el = render(createElement(OndergrensNoot, { reeksen: [
      { label: 'Ingeschrevenen', onderdrukt: { 2024: 1, 2022: 3 } },
      { label: 'Eerstejaars', onderdrukt: {} },
    ] }))

    expect(el.textContent).toContain('Ingeschrevenen in 2022, 2024: ten minste')
    expect(el.textContent).not.toContain('Eerstejaars')
  })

  it('toont geen noot zonder onderdrukte cellen', () => {
    const el = render(createElement(OndergrensNoot, { reeksen: [{ label: 'Ingeschrevenen', onderdrukt: undefined }] }))

    expect(el.textContent).toBe('')
  })
})
