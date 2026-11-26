// De waarden van een grafiek als tabel (#664), uit dezelfde bron als de CSV: de rijen die tools/plot.py in
// layout.meta.data zet, anders de getekende reeksen. Op een telefoon is elke waarde dan te lezen zonder tooltip.
// Uitkomst: { kolommen, rijen, labels }, waarbij `labels` de voorste labelkolommen telt (x, reeks): die blijven
// zoals ze staan (2020 is geen 2.020); de rest zijn waarden. Null als er niets betrouwbaars te tonen is.
// `ondergrens` (#1261): de cellen ("rij:kolom") waarin een onderdrukte cel valt, uit layout.meta.ondergrens_rijen van
// tools/plot.py; de tabel toont ze als "≥ 1.234", zoals de hover "ten minste" zegt.

import { DISTRIBUTION_TYPES, toolRows, tracesTabel } from './figureCsv'

// Een kolom met een _ ervoor is intern (de kaartcode van #659), geen waarde voor de lezer. De kolom ondergrens (ja/nee,
// #1257) is voor de CSV; de tabel zegt het met "≥" in de cel zelf.
export const ONDERGRENS_KOLOM = 'ondergrens'
const zichtbaar = kolom => !kolom.startsWith('_') && kolom !== ONDERGRENS_KOLOM

// De rijen (als object) waarvan de waarde in y een ondergrens is.
function ondergrensRijen(meta) {
  const data = Array.isArray(meta?.data) ? meta.data : []
  const plekken = Array.isArray(meta?.ondergrens_rijen) ? meta.ondergrens_rijen : []
  return new Set(plekken.map(i => data[i]).filter(rij => rij && typeof rij === 'object'))
}

// Een kaart (create_choropleth_map, #217) noemt zelf welke kolom de plaats is en welke de waarde.
function kaartTabel(rijen, { location_col: plek, value_col: waarde }) {
  return { kolommen: [plek, waarde], rijen: rijen.map(rij => [rij[plek], rij[waarde]]), labels: 1 }
}

// Meer reeksen (een rij per punt met 'reeks', tools/plot.py with_export_rows) naast elkaar: een rij per x, een
// kolom per reeks, zoals de grafiek ze toont. Null als een x binnen een reeks terugkomt; dan blijft het een rij per punt.
function reeksenNaastElkaar(rijen, x, y, vlag) {
  const reeksen = [...new Set(rijen.map(rij => rij.reeks))]
  const perX = new Map()
  for (const rij of rijen) {
    const waarden = perX.get(rij[x]) ?? new Map()
    if (waarden.has(rij.reeks)) return null
    perX.set(rij[x], waarden.set(rij.reeks, rij))
  }
  const ondergrens = new Set()
  const tabelRijen = [...perX].map(([xWaarde, waarden], r) => [xWaarde, ...reeksen.map((reeks, c) => {
    const rij = waarden.get(reeks)
    if (rij && vlag.has(rij)) ondergrens.add(`${r}:${c + 1}`)
    return rij ? rij[y] ?? null : null
  })])
  return { kolommen: [x, ...reeksen], rijen: tabelRijen, labels: 1, ...(ondergrens.size && { ondergrens }) }
}

function uitToolRijen(rijen, meta) {
  if (meta.location_col && meta.value_col) return kaartTabel(rijen, meta)
  const { x, y } = meta
  const vlag = ondergrensRijen(meta)
  if (x && y && rijen.every(rij => 'reeks' in rij && x in rij && y in rij)) {
    const naastElkaar = reeksenNaastElkaar(rijen, x, y, vlag)
    if (naastElkaar) return naastElkaar
  }
  const kolommen = [...new Set(rijen.flatMap(Object.keys))].filter(zichtbaar)
  const waardekolom = kolommen.indexOf(y)
  const ondergrens = new Set(
    waardekolom < 0 ? [] : rijen.flatMap((rij, r) => (vlag.has(rij) ? [`${r}:${waardekolom}`] : [])),
  )
  const tabelRijen = rijen.map(rij => kolommen.map(k => rij[k] ?? null))
  return { kolommen, rijen: tabelRijen, labels: kolommen.length - 1, ...(ondergrens.size && { ondergrens }) }
}

export function figuurTabel(figure) {
  if (!figure || typeof figure !== 'object') return null
  const rijen = toolRows(figure)
  if (rijen?.length) return uitToolRijen(rijen, figure.layout.meta)
  // Een histogram of boxplot tekent een verdeling: zijn ruwe punten zijn niet de waarden die je ziet.
  if ((figure.data || []).some(t => DISTRIBUTION_TYPES.has(t?.type))) return null
  return tracesTabel(figure)
}
