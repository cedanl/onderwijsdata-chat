// Het beeld van een kaart in de chat (#642). De server geeft één centrum en zoom 6 mee (tools/plot.py, KAART_OPTIES);
// op 390 px viel Nederland daarmee links en rechts buiten de kaart (Zeeland, het westen van Zuid-Holland), en op een
// breed scherm Limburg onderaan. Hier volgen centrum en zoom uit de gebieden zelf en de ruimte die de kaart echt heeft.

// Zo hoog is een kaart in de chat (ChatPage, PlotlyFigure).
export const KAART_HOOGTE = 480
// De kleurenbalk rechts neemt plotbreedte in (balk, ticks en getallen).
const KLEURENBALK = 90
// Wat ruimte rond de gebieden, zodat de randen niet tegen de rand van de kaart liggen.
const MARGE = 0.92
// Maplibre rekent in tegels van 512 px.
const TEGEL = 512

function grenzen(data) {
  const g = { west: 180, oost: -180, zuid: 90, noord: -90 }
  const loop = c => {
    if (typeof c?.[0] === 'number') {
      g.west = Math.min(g.west, c[0]); g.oost = Math.max(g.oost, c[0])
      g.zuid = Math.min(g.zuid, c[1]); g.noord = Math.max(g.noord, c[1])
    } else if (Array.isArray(c)) c.forEach(loop)
  }
  for (const trace of data || []) for (const f of trace?.geojson?.features || []) loop(f?.geometry?.coordinates)
  return g.west <= g.oost ? g : null
}

// Web-Mercator, 0..1 over de wereld.
const mx = lon => (lon + 180) / 360
const my = lat => (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) / 2
const lat = y => (Math.atan(Math.exp(Math.PI * (1 - 2 * y))) * 360) / Math.PI - 90

// Centrum en zoom waarmee alle gebieden van de kaart in `breedte` x `hoogte` px passen, of null zonder gebieden of
// zonder bekende maat.
export function kaartPassend(data, breedte, hoogte, metKleurenbalk = true) {
  const g = grenzen(data)
  const w = breedte - (metKleurenbalk ? KLEURENBALK : 0)
  if (!g || w <= 0 || hoogte <= 0) return null
  const dx = mx(g.oost) - mx(g.west)
  const dy = my(g.zuid) - my(g.noord)
  const zoom = Math.log2(Math.min((w * MARGE) / (dx * TEGEL), (hoogte * MARGE) / (dy * TEGEL)))
  const midden = (my(g.zuid) + my(g.noord)) / 2
  return { center: { lon: (g.west + g.oost) / 2, lat: lat(midden) }, zoom: Math.round(zoom * 100) / 100 }
}

// De achtergrond van de kaart in de kleur van de bubbel: 'white-bg' bleef wit in het donkere thema. Een eigen
// maplibre-stijl met alleen een achtergrondlaag, zoals 'white-bg', zonder tegels van buiten (#486).
export const kaartStijl = kleur => ({
  version: 8,
  sources: {},
  layers: [{ id: 'achtergrond', type: 'background', paint: { 'background-color': kleur } }],
})
