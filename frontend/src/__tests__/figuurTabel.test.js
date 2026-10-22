// #664: de waarden van een grafiek als tabel, uit dezelfde rijen als de CSV.
import { describe, it, expect } from 'vitest'
import { figuurTabel } from '../figuurTabel'

const f64 = waarden => ({ dtype: 'f8', bdata: btoa(String.fromCharCode(...new Uint8Array(new Float64Array(waarden).buffer))) })

describe('figuurTabel uit de rijen van de tool', () => {
  it('geeft één reeks als twee kolommen, met de x-kolom als label', () => {
    const figuur = {
      data: [{ type: 'bar', x: [2023, 2024], y: [1, 2] }],
      layout: { meta: { x: 'Jaar', y: 'Studenten', data: [{ Jaar: 2023, Studenten: 518940 }, { Jaar: 2024, Studenten: 475460 }] } },
    }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Jaar', 'Studenten'], rijen: [[2023, 518940], [2024, 475460]], labels: 1 })
  })

  it('zet meerdere reeksen naast elkaar: een rij per x, een kolom per reeks', () => {
    const figuur = {
      data: [],
      layout: {
        meta: {
          x: 'Jaar', y: 'Studenten',
          data: [
            { reeks: 'hbo', Jaar: 2023, Studenten: 10 }, { reeks: 'hbo', Jaar: 2024, Studenten: 11 },
            { reeks: 'wo', Jaar: 2024, Studenten: 7 },
          ],
        },
      },
    }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Jaar', 'hbo', 'wo'], rijen: [[2023, 10, null], [2024, 11, 7]], labels: 1 })
  })

  it('houdt een rij per punt als een x binnen een reeks terugkomt', () => {
    const rijen = [{ reeks: 'hbo', Jaar: 2024, Studenten: 10 }, { reeks: 'hbo', Jaar: 2024, Studenten: 12 }]
    const figuur = { data: [], layout: { meta: { x: 'Jaar', y: 'Studenten', data: rijen } } }
    expect(figuurTabel(figuur)).toEqual({
      kolommen: ['reeks', 'Jaar', 'Studenten'], rijen: [['hbo', 2024, 10], ['hbo', 2024, 12]], labels: 2,
    })
  })

  it('geeft een heatmap als rij, kolom en waarde', () => {
    const figuur = { data: [{ type: 'heatmap', z: [[1]] }], layout: { meta: { data: [{ Sector: 'Zorg', Jaar: 2024, waarde: 5 }] } } }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Sector', 'Jaar', 'waarde'], rijen: [['Zorg', 2024, 5]], labels: 2 })
  })

  it('laat interne kolommen (met een _) en rijen die geen object zijn weg', () => {
    const figuur = { data: [], layout: { meta: { data: [null, ['x', 1], { Instelling: 'HU', _code: 'X1', Aantal: 3 }] } } }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Instelling', 'Aantal'], rijen: [['HU', 3]], labels: 1 })
  })

  it('geeft bij een kaart plaats en waarde uit location_col en value_col', () => {
    const figuur = {
      data: [{ type: 'choroplethmap', locations: ['PV20'], z: [24310] }],
      layout: { meta: { location_col: 'Provincie', value_col: 'Studenten', data: [{ Provincie: 'Groningen', Studenten: 24310, _kaartcode: 'PV20' }] } },
    }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Provincie', 'Studenten'], rijen: [['Groningen', 24310]], labels: 1 })
  })
})

describe('figuurTabel uit de getekende reeksen', () => {
  it('leest een staaf zonder toolrijen, met de astitels als kop', () => {
    const figuur = {
      data: [{ type: 'bar', x: ['HU', 'Fontys'], y: [3, 4] }],
      layout: { xaxis: { title: { text: 'Instelling' } }, yaxis: { title: { text: 'Aantal' } } },
    }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Instelling', 'Aantal'], rijen: [['HU', 3], ['Fontys', 4]], labels: 1 })
  })

  it('geeft een kolom per reeks en leest binaire arrays en liggende staven', () => {
    const figuur = {
      data: [
        { type: 'bar', orientation: 'h', name: 'VT', y: ['2021', '2022'], x: f64([10, 12]) },
        { type: 'bar', orientation: 'h', name: 'DT', y: ['2022'], x: [3] },
      ],
      layout: { meta: { x: 'Jaar', y: 'Aantal' } },
    }
    expect(figuurTabel(figuur)).toEqual({ kolommen: ['Jaar', 'VT', 'DT'], rijen: [['2021', 10, null], ['2022', 12, 3]], labels: 1 })
  })

  it('geeft geen tabel bij een figuur die niet klopt, zonder punten of met alleen een verdeling', () => {
    expect(figuurTabel({ data: [{ x: [1, 2], y: [1] }], layout: {} })).toBeNull()
    expect(figuurTabel({ data: [{ type: 'heatmap', z: [[1, 2]] }], layout: {} })).toBeNull()
    expect(figuurTabel({ data: [{ type: 'histogram', x: [1, 1, 2] }], layout: {} })).toBeNull()
    expect(figuurTabel({ data: [], layout: {} })).toBeNull()
    expect(figuurTabel(null)).toBeNull()
  })
})
