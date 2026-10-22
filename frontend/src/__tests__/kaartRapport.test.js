// @vitest-environment jsdom
// #642: in het rapportframe (sandbox zonder allow-same-origin) en in een bestand van schijf start maplibre zijn
// worker niet en blijft een choroplethmap leeg; het script tekent hem als choropleth op een geo-subplot.
import { describe, it, expect, beforeEach } from 'vitest'
import { KAART_ALS_SVG_JS, heeftKaartAlsSvg, kaartAlsSvgScript } from '../kaartRapport'

let getekend
beforeEach(() => {
  getekend = []
  delete window.PlotlyGeoAssets
  window.Plotly = { newPlot: (gd, data, layout) => getekend.push({ data, layout }), react: (gd, fig) => getekend.push(fig) }
  new Function(KAART_ALS_SVG_JS)()
})

const kaart = () => [{ type: 'choroplethmap', geojson: { type: 'FeatureCollection', features: [] }, featureidkey: 'id',
  locations: ['PV26'], z: [5], coloraxis: 'coloraxis', subplot: 'map', below: '' }]

describe('een kaart in het rapport', () => {
  it('tekent als choropleth op een geo-subplot die op de gebieden past', () => {
    window.Plotly.newPlot('k', kaart(), { map: { center: { lat: 52.3, lon: 5.3 }, zoom: 6 }, coloraxis: { colorscale: 'Blues' } })
    const [{ data, layout }] = getekend
    expect(data[0]).toMatchObject({ type: 'choropleth', geo: 'geo', locations: ['PV26'], z: [5], featureidkey: 'id', coloraxis: 'coloraxis' })
    expect(data[0].subplot).toBeUndefined()
    expect(layout.map).toBeUndefined()
    expect(layout.geo).toMatchObject({ fitbounds: 'locations', visible: false })
    expect(layout.coloraxis).toEqual({ colorscale: 'Blues' })
  })

  // De geo-subplot haalde world_110m.json van cdn.plot.ly; de policy van het rapport hield dat tegen en de kaart bleef leeg.
  it('geeft Plotly een lege wereld mee, zodat er niets van buiten nodig is', () => {
    window.Plotly.newPlot('k', kaart(), {})
    expect(window.PlotlyGeoAssets.topojson.world_110m).toMatchObject({ type: 'Topology', arcs: [] })
    expect(getekend[0].layout.geo).toMatchObject({ scope: 'world', resolution: 110 })
  })

  // #659: het rapport toont bij een tik dezelfde gebiedsnaam als de chat, niet de CBS-code.
  it('houdt de gebiedsnaam en het hoverlabel van de kaart', () => {
    const data = kaart()
    data[0].hovertext = ['Utrecht']
    data[0].hovertemplate = '<b>%{hovertext}</b><br>Mbo-studenten: %{z:,}<extra></extra>'
    window.Plotly.newPlot('k', data, {})
    expect(getekend[0].data[0]).toMatchObject({
      type: 'choropleth', locations: ['PV26'], hovertext: ['Utrecht'],
      hovertemplate: '<b>%{hovertext}</b><br>Mbo-studenten: %{z:,}<extra></extra>',
    })
  })

  it('werkt ook als de figuur als één object komt (Plotly.react)', () => {
    window.Plotly.react('k', { data: kaart(), layout: {} })
    expect(getekend[0].data[0].type).toBe('choropleth')
    expect(getekend[0].layout.geo.fitbounds).toBe('locations')
  })

  it('laat een gewone grafiek en een nieuwe aanroep zonder layout met rust', () => {
    const staaf = [{ type: 'bar', x: [1], y: [2] }]
    window.Plotly.newPlot('k', staaf, { title: 'T' })
    window.Plotly.newPlot('k', staaf)
    expect(getekend[0]).toEqual({ data: staaf, layout: { title: 'T' } })
    expect(getekend[1].data).toBe(staaf)
  })

  it('wikkelt Plotly één keer in, ook als het script twee keer staat', () => {
    const eerste = window.Plotly.newPlot
    new Function(KAART_ALS_SVG_JS)()
    expect(window.Plotly.newPlot).toBe(eerste)
  })

  it('herkent HTML die het script al heeft', () => {
    expect(heeftKaartAlsSvg(`<script src="/p.js"></script>${kaartAlsSvgScript()}`)).toBe(true)
    expect(heeftKaartAlsSvg('<script src="/p.js"></script>')).toBe(false)
    expect(heeftKaartAlsSvg(null)).toBe(false)
  })

  // d3 kleurde met de GeoJSON-richting (buitenring tegen de klok in) de rest van de wereld (gemeten in de MR).
  it('legt de buitenring met de klok mee en een gat ertegenin, in een kopie', () => {
    const tegen = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    const gat = [[0.2, 0.2], [0.2, 0.8], [0.8, 0.8], [0.8, 0.2], [0.2, 0.2]]
    const data = kaart()
    data[0].geojson.features = [
      { id: 'A', geometry: { type: 'Polygon', coordinates: [tegen, gat] } },
      { id: 'B', geometry: { type: 'MultiPolygon', coordinates: [[tegen]] } },
    ]
    const gj = data[0].geojson
    const origineel = JSON.stringify(gj)
    window.Plotly.newPlot('k', data, {})
    const [a, b] = getekend[0].data[0].geojson.features
    expect(a.geometry.coordinates[0]).toEqual([...tegen].reverse())
    expect(a.geometry.coordinates[1]).toEqual([...gat].reverse())
    expect(b.geometry.coordinates[0][0]).toEqual([...tegen].reverse())
    expect(a.id).toBe('A')
    expect(JSON.stringify(gj)).toBe(origineel)
  })

  it('draait een ring die al goed ligt niet om', () => {
    const mee = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]
    const data = kaart()
    data[0].geojson.features = [{ id: 'A', geometry: { type: 'Polygon', coordinates: [mee] } }]
    window.Plotly.newPlot('k', data, {})
    expect(getekend[0].data[0].geojson.features[0].geometry.coordinates[0]).toEqual(mee)
  })
})

// #655: op een telefoon toont een tik op een provincie het hoverlabel, maar in een los bestand (de HTML-download)
// stuurt de browser na de klik mouseout en haalt Plotly het label meteen weer weg. Het script beweegt dan nog één
// keer over de getikte plek, zodat naam en waarde blijven staan.
describe('een tik op een gebied in het rapport (#655)', () => {
  const nepGrafiek = () => {
    const op = {}
    return { op, on: (naam, fn) => { op[naam] = fn } }
  }

  it('laat het label staan als Plotly het direct na de klik weghaalt', async () => {
    const gd = nepGrafiek()
    window.Plotly.newPlot = () => Promise.resolve(gd)
    delete window.Plotly.__kaartAlsSvg
    new Function(KAART_ALS_SVG_JS)()
    await window.Plotly.newPlot('k', kaart(), {})
    const doel = document.createElement('div')
    const bewogen = []
    doel.addEventListener('mousemove', e => bewogen.push([e.clientX, e.clientY]))
    document.elementFromPoint = () => doel
    gd.op.plotly_click({ points: [{ curveNumber: 0, pointNumber: 0 }], event: { clientX: 120, clientY: 340 } })
    gd.op.plotly_unhover()
    await new Promise(r => setTimeout(r, 10))
    expect(bewogen).toEqual([[120, 340]])
  })

  it('laat een label weggaan zonder tik ervoor, en laat een gewone grafiek met rust', async () => {
    const gd = nepGrafiek()
    window.Plotly.newPlot = () => Promise.resolve(gd)
    delete window.Plotly.__kaartAlsSvg
    new Function(KAART_ALS_SVG_JS)()
    await window.Plotly.newPlot('k', kaart(), {})
    const bewogen = []
    document.elementFromPoint = () => ({ dispatchEvent: e => bewogen.push(e) })
    gd.op.plotly_unhover()
    await new Promise(r => setTimeout(r, 10))
    expect(bewogen).toEqual([])

    const staaf = nepGrafiek()
    window.Plotly.newPlot = () => Promise.resolve(staaf)
    delete window.Plotly.__kaartAlsSvg
    new Function(KAART_ALS_SVG_JS)()
    await window.Plotly.newPlot('k', [{ type: 'bar', x: [1], y: [2] }], {})
    expect(staaf.op).toEqual({})
  })
})
