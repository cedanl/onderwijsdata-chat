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

// Zo lang moet een kaart zonder gebieden leeg blijven voordat dat telt: de eerste 'idle' kan komen voordat de
// vlakken er staan, en de melding flitste dan kort op (#642).
export const NUL_BEVESTIGING = 1000

// Volgt de kaart van `gd` en meldt via `meld` 'getekend' of 'mislukt'. Mislukt bij een fout van maplibre zonder
// getekend gebied, als na 'idle' ook NUL_BEVESTIGING later geen gebied getekend is, of na de wachttijd. Ook daarna
// blijft de controle kijken (#642): een fout is vaak niet fataal (een tegel, een stijlwaarschuwing), en een kaart die
// alsnog tekent, meldt 'getekend'. Pas dan stopt hij. Geeft een opruimfunctie terug.
export function volgKaart(gd, meld, wachttijd = KAART_WACHTTIJD) {
  const map = kaartVan(gd)
  if (!map) return () => {}
  let klaar = false
  let laatste = null
  let bevestiging = null
  const zeg = status => {
    if (status === laatste) return
    laatste = status
    meld(status)
  }
  const stop = () => {
    klaar = true
    clearTimeout(timer)
    clearTimeout(bevestiging)
    map.off('idle', tel)
    map.off('error', fout)
  }
  // Getekend telt meteen en voor altijd; geeft het aantal terug (null als de kaart niet kan tellen).
  function getekend() {
    const n = getekendeGebieden(map)
    if (n > 0) {
      stop()
      zeg('getekend')
    }
    return n
  }
  function tel() {
    if (klaar || getekend() !== 0 || bevestiging) return
    bevestiging = setTimeout(() => {
      bevestiging = null
      if (!klaar && getekend() === 0) zeg('mislukt')
    }, NUL_BEVESTIGING)
  }
  function fout() {
    if (!klaar && !(getekend() > 0)) zeg('mislukt')
  }
  const timer = setTimeout(() => {
    if (!klaar && getekend() === 0) zeg('mislukt')
  }, wachttijd)
  map.on('idle', tel)
  map.on('error', fout)
  // De kaart kan al klaar zijn voordat de controle begint; alleen een getekende kaart telt dan meteen.
  if (map.loaded?.()) getekend()
  return stop
}
