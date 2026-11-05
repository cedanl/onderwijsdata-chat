// @vitest-environment jsdom
// #898: het "rendement" in Mijn instelling. Mbo houdt de tegel onder een eerlijke naam, met de definitie en wat niet
// meetelt; hbo en wo krijgen geen tegel maar één noot. Elk cohort dat afvalt, staat er met de reden, ook als er geen
// enkel cohort overblijft (eerder gaf de sectie dan `null` vóór de uitleg).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))

import { RendementSection, weggelatenPerReden } from '../components/dashboards/mijn-instelling/rendement-section'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

let container
let root
function render(data) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(createElement(RendementSection, { data, instelling: 'Curio', dark: false })))
  return container
}
afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = container = undefined
})

const DEFINITIE = {
  naam: "Diploma's na 3 jaar per eerstejaars",
  termijn: 3,
  definitie: 'Per cohort de mbo-diploma\'s die de instelling 3 jaar later uitreikte, gedeeld door de eerstejaars.',
  niet_meegeteld: 'in de eerstejaars wie een jaar eerder al in het mbo stond ingeschreven',
  wel_meegeteld: "in de diploma's ook die van studenten uit een ander cohort",
}

// De getallen van Curio uit de bevroren DUO-fixtures (tests/test_dashboard_rendement.py rekent ze na).
const CURIO = {
  instelling: 'Curio', gevonden: true, type: 'mbo', definitie: DEFINITIE,
  perioden: { cohorten: 'schooljaar', gediplomeerden: 'diplomajaar' },
  pseudo_cohorten: [
    { instroom_jaar: 2021, instroom: 4459, gediplomeerden_t3: 4037, gediplomeerden_t4: 3925, gediplomeerden_t5: null },
    { instroom_jaar: 2022, instroom: 4341, gediplomeerden_t3: 3925, gediplomeerden_t4: null, gediplomeerden_t5: null },
  ],
  rendement_per_jaar: { 2021: 0.9054, 2022: 0.9042 },
  weggelaten: {},
  benchmark_label: 'Provincie gemiddelde (Noord-Brabant, excl. eigen instelling)',
  benchmark_rendement: { 2021: 0.7294, 2022: 0.8511 },
  benchmark_n_per_jaar: { 2021: 1, 2022: 1 },
  peers_rendement: { SiNTLUCAS: { 2021: 0.7294, 2022: 0.8511 } },
  peers_weggelaten: { 'BBO de Schalm': { 2021: 'geen eerstejaars bekend', 2022: 'geen eerstejaars bekend' } },
}

describe('mbo: diploma\'s na 3 jaar per eerstejaars (#898)', () => {
  it('heet naar wat het telt, met de definitie, wat niet en wat wel meetelt', () => {
    const tekst = render(CURIO).textContent

    expect(tekst).toContain("Diploma's na 3 jaar per eerstejaars")
    expect(tekst).toContain('geen cohortrendement')
    expect(tekst).toContain(`Definitie: ${DEFINITIE.definitie}`)
    expect(tekst).toContain(`Niet meegeteld: ${DEFINITIE.niet_meegeteld}.`)
    expect(tekst).toContain(`Wel meegeteld: ${DEFINITIE.wel_meegeteld}.`)
    expect(tekst).not.toMatch(/Rendement cohort|Diplomarendement/)
  })

  it('toont het laatste cohort met teller en noemer', () => {
    const tekst = render(CURIO).textContent

    // Het cohort is een schooljaar, het diplomajaar heet zo (#904).
    expect(tekst).toContain('Cohort 2022/23')
    expect(tekst).toContain('90,4%')
    expect(tekst).toContain("3.925 diploma's in diplomajaar 2025 / 4.341 eerstejaars")
  })

  it('noemt een peer die niet in het regiogemiddelde telt, met de reden', () => {
    expect(render(CURIO).textContent).toContain(
      'Niet getoond (niet in het regiogemiddelde: geen eerstejaars bekend): BBO de Schalm (2021/22, 2022/23).',
    )
  })

  it('legt zich uit als er geen enkel cohort overblijft', () => {
    const tekst = render({
      ...CURIO, pseudo_cohorten: [], rendement_per_jaar: {}, benchmark_rendement: {}, peers_rendement: {},
      weggelaten: { 2021: 'geen eerstejaars bekend', 2022: 'geen eerstejaars bekend' },
    }).textContent

    expect(tekst).toContain(`Definitie: ${DEFINITIE.definitie}`)
    expect(tekst).toContain('Niet getoond (geen eerstejaars bekend): 2021/22, 2022/23.')
  })

  it('zegt welke cohorten de tabel weglaat, ook als er geen rij overblijft', () => {
    const tekst = render({
      ...CURIO, rendement_per_jaar: {},
      pseudo_cohorten: [{ instroom_jaar: 2023, instroom: 10, gediplomeerden_t3: null, gediplomeerden_t4: null, gediplomeerden_t5: null }],
    }).textContent

    expect(tekst).toContain('Niet getoond (nog geen diplomajaar na 3, 4 of 5 jaar): 2023/24.')
  })
})

describe('hbo en wo: geen rendement, wel de reden (#898)', () => {
  it('toont één noot en geen cijfers', () => {
    const reden = 'Voor hbo en wo staat hier geen rendement. Vraag het in de chat of zet het in een rapport.'
    const el = render({ instelling: 'Hogeschool Utrecht', gevonden: true, type: 'ho', geen_rendement: reden })

    expect(el.querySelector('[role="note"]').textContent).toBe(reden)
    expect(el.querySelectorAll('[role="note"]')).toHaveLength(1)
    expect(el.querySelector('.kpi-card')).toBeNull()
    expect(el.querySelector('table')).toBeNull()
    expect(el.textContent).not.toContain('Definitie')
  })
})

describe('weggelatenPerReden', () => {
  it('groepeert de cohorten van de instelling per reden', () => {
    expect(weggelatenPerReden({ 2021: 'a', 2022: 'b', 2023: 'a' })).toEqual([
      { reden: 'a', namen: ['2021', '2023'] },
      { reden: 'b', namen: ['2022'] },
    ])
  })

  it('noemt een peer met zijn cohorten, per reden', () => {
    expect(weggelatenPerReden({ X: { 2021: 'a', 2022: 'b' }, Y: { 2021: 'a' } }, true)).toEqual([
      { reden: 'a', namen: ['X (2021)', 'Y (2021)'] },
      { reden: 'b', namen: ['X (2022)'] },
    ])
  })

  it('zonder weggelaten cohorten niets', () => {
    expect(weggelatenPerReden(undefined)).toEqual([])
  })
})
