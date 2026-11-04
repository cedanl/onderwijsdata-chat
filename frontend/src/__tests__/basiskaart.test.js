// @vitest-environment jsdom
// #906: de basiskaart van een geo-kaart komt uit de eigen bundel, niet van cdn.plot.ly (de CSP houdt die tegen).
import { describe, it, expect, beforeEach } from 'vitest'
import { createRequire } from 'node:module'
import { basiskaartNaam, heeftBasiskaart, laadBasiskaart } from '../basiskaart'
import europe50m from '../assets/topojson/europe_50m.json'

beforeEach(() => { delete window.PlotlyGeoAssets })

describe('basiskaartNaam', () => {
  it('volgt de naam die Plotly zoekt, met Plotly\'s standaarden', () => {
    expect(basiskaartNaam({ scope: 'europe', resolution: 50 })).toBe('europe_50m')
    expect(basiskaartNaam({ scope: 'north america', resolution: 110 })).toBe('north-america_110m')
    expect(basiskaartNaam({})).toBe('world_110m')
  })
})

describe('laadBasiskaart', () => {
  it('zet de dashboardkaart klaar in PlotlyGeoAssets', async () => {
    expect(await laadBasiskaart('europe_50m')).toBe(true)
    expect(window.PlotlyGeoAssets.topojson.europe_50m).toEqual(europe50m)
  })

  it('laat wat Plotly al heeft staan', async () => {
    window.PlotlyGeoAssets = { topojson: { world_110m: { type: 'Topology', stub: true } } }
    await laadBasiskaart('europe_50m')
    expect(window.PlotlyGeoAssets.topojson.world_110m.stub).toBe(true)
    expect(window.PlotlyGeoAssets.topojson.europe_50m.type).toBe('Topology')
  })

  it('levert alleen de kaarten die de app tekent', async () => {
    expect(heeftBasiskaart('world_50m')).toBe(false)
    expect(await laadBasiskaart('world_50m')).toBe(false)
    expect(window.PlotlyGeoAssets).toBeUndefined()
  })
})

// Het bestand is een kopie uit plotly.js. Faalt dit na een update van plotly.js, kopieer dan topojson.europe_50m
// opnieuw uit dist/plotly-geo-assets.js naar src/assets/topojson/europe_50m.json.
describe('de meegeleverde basiskaart', () => {
  it('is dezelfde als die van de geïnstalleerde plotly.js', () => {
    const require = createRequire(import.meta.url)
    const { topojson } = require('plotly.js/dist/plotly-geo-assets.js')
    expect(europe50m).toEqual(topojson.europe_50m)
  })
})
