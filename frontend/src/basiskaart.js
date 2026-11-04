// De basiskaart van een geo-kaart in Plotly (scattergeo; de dashboardkaart, #906). Plotly haalt die als topojson van
// cdn.plot.ly, maar de CSP laat geen derde partij toe (connect-src, server.py; #486). Gemeten op 04-11: de kaart bleef
// leeg op de legenda na, met "Connecting to 'https://cdn.plot.ly/un/europe_50m.json' violates ... connect-src".
// Plotly kijkt eerst in window.PlotlyGeoAssets.topojson (plots/geo/geo.js); daar zet de app de basiskaart uit de eigen
// bundel, zodat Plotly niets van buiten haalt. Het bestand komt uit dezelfde plotly.js (dist/plotly-geo-assets.js);
// basiskaart.test.js houdt het gelijk. Alleen de kaarten die de app tekent, als losse chunk: pas bij een kaart geladen.
const BASISKAARTEN = {
  europe_50m: () => import('./assets/topojson/europe_50m.json'),
}

// De naam die Plotly zoekt (topojson_utils.getTopojsonName), met Plotly's standaarden: scope world, resolutie 110.
export function basiskaartNaam(geo) {
  const scope = String(geo?.scope ?? 'world').replace(/ /g, '-')
  return `${scope}_${geo?.resolution ?? 110}m`
}

export const heeftBasiskaart = naam => Object.hasOwn(BASISKAARTEN, naam)

// Zet de basiskaart klaar voor Plotly. Onwaar voor een kaart die de app niet meelevert: Plotly zoekt hem dan zelf,
// de CSP houdt dat tegen en de kaart valt terug op haar tabel (KaartSection).
export async function laadBasiskaart(naam, venster = window) {
  if (!heeftBasiskaart(naam)) return false
  const assets = (venster.PlotlyGeoAssets ??= { topojson: {} })
  assets.topojson ??= {}
  assets.topojson[naam] ??= (await BASISKAARTEN[naam]()).default
  return true
}
