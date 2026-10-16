// #588 (mobiel B3): een grafiek in de chat krijgt een toegankelijke naam, een Nederlandse zin uit de
// figuurdata zelf: soort, titel, assen, aantal punten en de eerste en laatste waarde per reeks.
import { describe, it, expect } from 'vitest'
import { figuurBeschrijving } from '../figuurBeschrijving'

const as = tekst => ({ title: { text: tekst } })
const binair = (Typed, waarden) => ({
  dtype: { Float64Array: 'f8', Int32Array: 'i4' }[Typed.name],
  bdata: btoa(String.fromCharCode(...new Uint8Array(new Typed(waarden).buffer))),
})

function bevroren(waarde) {
  if (waarde && typeof waarde === 'object') Object.values(waarde).forEach(bevroren)
  return Object.freeze(waarde)
}

const JAREN = ["2020/'21", "2021/'22", "2022/'23", "2023/'24", "2024/'25"]
const lijn = {
  data: [{ type: 'scatter', mode: 'lines', name: 'Mbo', x: JAREN, y: [518940, 510000, 500000, 490000, 475460] }],
  layout: { title: { text: 'Mbo-studenten totaal' }, xaxis: as('Studiejaar'), yaxis: as('Aantal') },
}

describe('figuurBeschrijving: soorten (#588)', () => {
  it('lijngrafiek', () => {
    expect(figuurBeschrijving(lijn)).toBe(
      "Lijngrafiek: Mbo-studenten totaal. X-as: Studiejaar, y-as: Aantal. Mbo: 5 punten, eerste 2020/'21: 518.940, " +
      "laatste 2024/'25: 475.460.")
  })

  it('een scatter zonder mode is een lijn, zoals Plotly hem tekent', () => {
    const figuur = { data: [{ x: ['a', 'b'], y: [1, 2] }], layout: { title: 'Zonder type' } }
    expect(figuurBeschrijving(figuur)).toBe('Lijngrafiek: Zonder type. 2 punten, eerste a: 1, laatste b: 2.')
  })

  it('staafdiagram, staand', () => {
    const figuur = {
      data: [{ type: 'bar', x: ['ROC A', 'ROC B'], y: [1200, 12.5] }],
      layout: { title: 'Instroom', xaxis: as('Instelling'), yaxis: as('Studenten') },
    }
    expect(figuurBeschrijving(figuur)).toBe(
      'Staafdiagram: Instroom. X-as: Instelling, y-as: Studenten. 2 punten, eerste ROC A: 1.200, laatste ROC B: 12,5.')
  })

  it('staafdiagram, liggend: de categorieën staan op y', () => {
    const figuur = {
      data: [{ type: 'bar', orientation: 'h', y: ['ROC A', 'ROC B', 'ROC C'], x: [300, 200, 100] }],
      layout: { title: 'Top 3', xaxis: as('Aantal'), yaxis: as('Instelling') },
    }
    expect(figuurBeschrijving(figuur)).toBe(
      'Staafdiagram: Top 3. X-as: Aantal, y-as: Instelling. 3 punten, eerste ROC A: 300, laatste ROC C: 100.')
  })

  it('cirkeldiagram', () => {
    const figuur = { data: [{ type: 'pie', labels: ['mbo', 'hbo', 'wo'], values: [50, 30, 20] }], layout: { title: 'Verdeling' } }
    expect(figuurBeschrijving(figuur)).toBe('Cirkeldiagram: Verdeling. 3 delen, eerste mbo: 50, laatste wo: 20.')
  })

  it('kaart, met het aantal gebieden', () => {
    const figuur = {
      data: [{ type: 'choroplethmapbox', locations: ['GM0363', 'GM0599', 'GM0344'], z: [1, 2, 3] }],
      layout: { title: { text: 'Studenten per gemeente' } },
    }
    expect(figuurBeschrijving(figuur)).toBe('Kaart: Studenten per gemeente. 3 gebieden.')
  })

  it('spreidingsdiagram', () => {
    const figuur = {
      data: [{ type: 'scatter', mode: 'markers', x: [10, 20], y: [3, 4] }],
      layout: { xaxis: as('Uitval'), yaxis: as('Rendement') },
    }
    expect(figuurBeschrijving(figuur)).toBe('Spreidingsdiagram. X-as: Uitval, y-as: Rendement. 2 punten, eerste 10: 3, laatste 20: 4.')
  })

  it('een onbekende soort heet grafiek', () => {
    const figuur = { data: [{ type: 'heatmap', z: [[1, 2], [3, 4]] }], layout: { title: 'Warmte', xaxis: as('Jaar') } }
    expect(figuurBeschrijving(figuur)).toBe('Grafiek: Warmte. X-as: Jaar.')
  })

  it('een reeks met één punt noemt geen eerste en laatste', () => {
    const figuur = { data: [{ type: 'bar', x: ['2023'], y: [7] }], layout: {} }
    expect(figuurBeschrijving(figuur)).toBe('Staafdiagram. 1 punt, 2023: 7.')
  })
})

describe('figuurBeschrijving: waarden (#588)', () => {
  it('leest x als label zoals geschreven, ook een getal', () => {
    const figuur = { data: [{ type: 'scatter', mode: 'lines', x: [2020, 2024], y: [518940, 475460] }], layout: {} }
    expect(figuurBeschrijving(figuur)).toBe('Lijngrafiek. 2 punten, eerste 2020: 518.940, laatste 2024: 475.460.')
  })

  it('leest binaire Plotly-arrays', () => {
    const figuur = {
      data: [{ type: 'scatter', mode: 'lines', x: binair(Int32Array, [2020, 2024]), y: binair(Float64Array, [518940, 12.5]) }],
      layout: {},
    }
    expect(figuurBeschrijving(figuur)).toBe('Lijngrafiek. 2 punten, eerste 2020: 518.940, laatste 2024: 12,5.')
  })

  it('slaat lege punten over voor de eerste en de laatste', () => {
    const figuur = { data: [{ type: 'bar', x: ['a', 'b', 'c', 'd', 'e'], y: [null, NaN, 100, 200, null] }], layout: {} }
    expect(figuurBeschrijving(figuur)).toBe('Staafdiagram. 2 punten, eerste c: 100, laatste d: 200.')
  })

  it('haalt <br> en andere tags uit titel, aslabels en reeksnaam', () => {
    const figuur = {
      data: [{ type: 'bar', name: '<i>Mbo</i>', x: ['a'], y: [1] }],
      layout: { title: { text: 'Mbo<br><sup>bron: CBS</sup>' }, xaxis: as('<b>Jaar</b>'), yaxis: as('Aantal<br />studenten') },
    }
    expect(figuurBeschrijving(figuur)).toBe('Staafdiagram: Mbo bron: CBS. X-as: Jaar, y-as: Aantal studenten. Mbo: 1 punt, a: 1.')
  })

  it('noemt bij meer dan 5 reeksen er 5, en hoeveel er nog zijn', () => {
    const data = Array.from({ length: 12 }, (_, i) => ({ type: 'bar', name: `R${i + 1}`, x: ['2023'], y: [i + 1] }))
    expect(figuurBeschrijving({ data, layout: { title: 'Twaalf' } })).toBe(
      'Staafdiagram: Twaalf. R1: 1 punt, 2023: 1. R2: 1 punt, 2023: 2. R3: 1 punt, 2023: 3. R4: 1 punt, 2023: 4. ' +
      'R5: 1 punt, 2023: 5. En nog 7 reeksen.')
  })

  it('verandert de figuur niet', () => {
    const figuur = bevroren(structuredClone(lijn))
    expect(() => figuurBeschrijving(figuur)).not.toThrow()
    expect(figuur).toEqual(lijn)
  })
})

describe('figuurBeschrijving: zonder data of titel (#588)', () => {
  it.each([
    ['een lege figuur', { data: [], layout: {} }],
    ['een figuur zonder data', { layout: { title: 'Leeg' } }],
    ['null', null],
    ['undefined', undefined],
  ])('%s geeft null', (_naam, figuur) => {
    expect(figuurBeschrijving(figuur)).toBeNull()
  })

  it('een figuur zonder titel geeft een zin zonder undefined of lege plekken', () => {
    const figuur = { data: [{ type: 'bar', x: ['a', 'b'], y: [1, 2] }] }
    const zin = figuurBeschrijving(figuur)
    expect(zin).toBe('Staafdiagram. 2 punten, eerste a: 1, laatste b: 2.')
    expect(zin).not.toMatch(/undefined|, ,|: \.|\.\./)
  })
})
