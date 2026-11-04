// De kaart van het regiodashboard (#906): de figuur komt van de server (data/dashboard.py, _build_kaart_figure) met
// lichte kleuren, de instellingen als rijen (layout.meta.data) en wie niet op de kaart past (layout.meta.zonder_locatie).
// Hier krijgt ze het thema, een vaste hoogte en geen sleepmodus, en komen beschrijving en tabel uit dezelfde rijen.

// De hoogte die de server de kaart geeft; de kaart past haar gebied erin, dus de kaart wordt nooit afgesneden.
export const KAART_HOOGTE = 340

const THEMA = {
  licht: { land: '#F8FAFC', zee: '#EFF6FF', grens: '#94A3B8', tekst: '#1F2937', legenda: 'rgba(255,255,255,0.9)', rand: '#E2E8F0', eigen: '#1E40AF' },
  donker: { land: '#1E2535', zee: '#111827', grens: '#6B7280', tekst: '#E5E7EB', legenda: 'rgba(26,31,46,0.9)', rand: '#3D4A5C', eigen: '#93C5FD' },
}

// De layout voor het thema. Geen sleepmodus (#740): op een telefoon at het slepen de veeg op, zodat de pagina niet
// scrolde, en de kaart toont al precies de regio (de server rekent het bereik uit). Letters van 13 px (#613).
export function kaartLayout(layout, dark) {
  const t = dark ? THEMA.donker : THEMA.licht
  return {
    ...layout,
    height: KAART_HOOGTE,
    autosize: true,
    dragmode: false,
    font: { ...layout?.font, size: 13, color: t.tekst },
    legend: { ...layout?.legend, bgcolor: t.legenda, bordercolor: t.rand, font: { size: 13, color: t.tekst } },
    geo: { ...layout?.geo, landcolor: t.land, oceancolor: t.zee, countrycolor: t.grens },
  }
}

// De naam van de eigen instelling staat als tekst bij de ster; in het donkere thema licht, anders onleesbaar.
export function kaartData(data, dark) {
  const t = dark ? THEMA.donker : THEMA.licht
  return (data ?? []).map(trace => (String(trace?.mode ?? '').includes('text')
    ? { ...trace, textfont: { ...trace.textfont, size: 13, color: t.eigen } }
    : trace))
}

const rijenVan = figuur => (Array.isArray(figuur?.layout?.meta?.data) ? figuur.layout.meta.data : [])

export const zonderLocatie = figuur => {
  const namen = figuur?.layout?.meta?.zonder_locatie
  return Array.isArray(namen) ? namen.filter(n => typeof n === 'string' && n) : []
}

// De toegankelijke naam van de kaart (#588): wat er staat, niet hoe het eruitziet.
export function kaartBeschrijving(figuur) {
  const rijen = rijenVan(figuur)
  if (!rijen.length) return 'Kaart van de instellingen in de regio.'
  const namen = rijen.map(r => (r.Rol === 'eigen instelling' ? `${r.Instelling} (eigen instelling)` : r.Instelling))
  return `Kaart met ${rijen.length} ${rijen.length === 1 ? 'instelling' : 'instellingen'} in de regio, op benaderde plaatscoördinaten: ${namen.join(', ')}.`
}

// De punten als tabel (FiguurTabel): alle kolommen zijn labels, geen getallen.
export function kaartTabel(figuur) {
  const rijen = rijenVan(figuur)
  if (!rijen.length) return null
  const kolommen = [...new Set(rijen.flatMap(Object.keys))]
  return { kolommen, rijen: rijen.map(r => kolommen.map(k => r[k] ?? '')), labels: kolommen.length }
}
