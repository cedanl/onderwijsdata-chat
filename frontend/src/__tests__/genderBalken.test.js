// @vitest-environment jsdom
// #931: de genderbalk per sector zei "totaal" voor vrouw + man, zonder de studenten met geslacht onbekend. Het label
// noemt nu de noemer van het percentage, en de onbekenden als die er zijn.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))

import { GenderSection } from '../components/dashboards/mijn-instelling/gender-section'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// DUO p01hoinges, studiejaar 2025 (opgehaald 05-11-2026): Tilburg University heeft in Gedrag en maatschappij 8
// studenten met geslacht onbekend; Breda University of Applied Sciences heeft er geen. Het regiodashboard geeft
// ONBEKEND ook als 0, of zonder die sleutel.
const TILBURG = { GEDRAG_EN_MAATSCHAPPIJ: { VROUW: 3641, MAN: 1278, ONBEKEND: 8 } }
const BREDA = { ECONOMIE: { VROUW: 3264, MAN: 1596, ONBEKEND: 0 }, TECHNIEK: { VROUW: 571, MAN: 1211 } }

let container
let root

function render(geslachtPerSector) {
  const data = { laatste_jaar: 2025, geslacht: { VROUW: 1, MAN: 1 }, geslacht_per_sector: geslachtPerSector }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(createElement(GenderSection, { data, instelling: 'X', dark: false })))
  return container.textContent
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('genderbalken per sector (#931)', () => {
  it('noemt teller en noemer, met de onbekenden erbij', () => {
    const tekst = render(TILBURG)
    expect(tekst).toContain('74,0% vrouw (3.641 van 4.919 vrouwen en mannen; 8 met geslacht onbekend tellen niet mee)')
    expect(tekst).not.toContain('totaal')
  })

  // #951: "32%" stond naast "67,2%", en "1.782 vrouw + man" las als een rekensom.
  it('zegt niets over onbekenden als die er niet zijn, en geeft elk aandeel met één decimaal', () => {
    const tekst = render(BREDA)
    expect(tekst).toContain('67,2% vrouw (3.264 van 4.860 vrouwen en mannen)')
    expect(tekst).toContain('32,0% vrouw (571 van 1.782 vrouwen en mannen)')
    expect(tekst).not.toContain('onbekend')
    expect(tekst).not.toContain('vrouw + man')
  })

  // #951: de sectorcode (GEDRAG_EN_MAATSCHAPPIJ) stond ruw boven de balk.
  it('noemt de sector bij zijn naam, niet bij zijn code', () => {
    const tekst = render(TILBURG)
    expect(tekst).toContain('Gedrag & Maatschappij')
    expect(tekst).not.toContain('GEDRAG_EN_MAATSCHAPPIJ')
  })
})
