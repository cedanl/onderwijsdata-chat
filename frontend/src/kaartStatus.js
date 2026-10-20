// Of een kaart in de chat echt getekend is (#632). Maplibre tekent de vlakken op een WebGL-canvas, dus de DOM zegt
// niets: de kaart zelf telt wat ze getekend heeft. De maplibre-kaart hangt aan private Plotly-API
// (`gd._fullLayout.map._subplot.map`), daarom is alles hier defensief: zonder kaart (jsdom, een andere grafiek) meldt
// dit niets, zodat er nooit vals alarm is.

// Zo lang wacht de controle op een kaart die nooit 'idle' wordt; daarna telt hij wat er staat.
export const KAART_WACHTTIJD = 15000

// De maplibre-kaart van een Plotly-grafiek, of null.
export function kaartVan(gd) {
  try {
    const layout = gd?._fullLayout
    const id = layout?._subplots?.map?.[0] ?? 'map'
    const map = layout?.[id]?._subplot?.map
    return typeof map?.on === 'function' ? map : null
  } catch {
    return null
  }
}

// Het aantal verschillende gebieden dat op de kaart getekend is (een gebied over twee tegels telt één keer), of
// null als de kaart dat niet kan zeggen. Plotly geeft elk gebied id 0 en zijn eigen eigenschappen (het midden `ct`
// en de kleur), dus die maken het gebied herkenbaar.
export function getekendeGebieden(map) {
  try {
    const vlakken = map.queryRenderedFeatures().filter(f => f.layer?.type === 'fill')
    return new Set(vlakken.map(f => JSON.stringify(f.properties ?? f.id))).size
  } catch {
    return null
  }
}

// Volgt de kaart van `gd` en meldt via `meld` 'getekend' of 'mislukt'. Mislukt alleen bij een fout van maplibre
// zonder getekend gebied, of als na 'idle' of na de wachttijd geen gebied getekend is. Een kaart die daarna alsnog
// tekent, meldt nog 'getekend'. Geeft een opruimfunctie terug.
export function volgKaart(gd, meld, wachttijd = KAART_WACHTTIJD) {
  const map = kaartVan(gd)
  if (!map) return () => {}
  let klaar = false
  const stop = () => {
    klaar = true
    clearTimeout(timer)
    map.off('idle', tel)
    map.off('error', fout)
  }
  function tel() {
    const n = getekendeGebieden(map)
    if (klaar || n === null) return
    if (n > 0) {
      stop()
      meld('getekend')
    } else {
      meld('mislukt')
    }
  }
  function fout() {
    if (klaar) return
    const n = getekendeGebieden(map)
    stop()
    meld(n > 0 ? 'getekend' : 'mislukt')
  }
  const timer = setTimeout(tel, wachttijd)
  map.on('idle', tel)
  map.on('error', fout)
  // De kaart kan al klaar zijn voordat de controle begint; alleen een getekende kaart telt dan meteen.
  if (map.loaded?.() && getekendeGebieden(map) > 0) {
    stop()
    meld('getekend')
  }
  return stop
}
