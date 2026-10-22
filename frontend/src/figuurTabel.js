// De waarden van een grafiek als tabel (#664), uit dezelfde bron als de CSV: de rijen die tools/plot.py in
// layout.meta.data zet, anders de getekende reeksen. Op een telefoon is elke waarde dan te lezen zonder tooltip.
// Uitkomst: { kolommen, rijen, labels }, waarbij `labels` de voorste labelkolommen telt (x, reeks): die blijven
// zoals ze staan (2020 is geen 2.020); de rest zijn waarden. Null als er niets betrouwbaars te tonen is.

import { DISTRIBUTION_TYPES, toolRows, tracesTabel } from './figureCsv'

// Een kolom met een _ ervoor is intern (de kaartcode van #659), geen waarde voor de lezer.
const zichtbaar = kolom => !kolom.startsWith('_')

// Een kaart (create_choropleth_map, #217) noemt zelf welke kolom de plaats is en welke de waarde.
function kaartTabel(rijen, { location_col: plek, value_col: waarde }) {
  return { kolommen: [plek, waarde], rijen: rijen.map(rij => [rij[plek], rij[waarde]]), labels: 1 }
}

// Meer reeksen (een rij per punt met 'reeks', tools/plot.py with_export_rows) naast elkaar: een rij per x, een
// kolom per reeks, zoals de grafiek ze toont. Null als een x binnen een reeks terugkomt; dan blijft het een rij per punt.
function reeksenNaastElkaar(rijen, x, y) {
  const reeksen = [...new Set(rijen.map(rij => rij.reeks))]
  const perX = new Map()
  for (const rij of rijen) {
    const waarden = perX.get(rij[x]) ?? new Map()
    if (waarden.has(rij.reeks)) return null
    perX.set(rij[x], waarden.set(rij.reeks, rij[y]))
  }
  const tabelRijen = [...perX].map(([xWaarde, waarden]) => [xWaarde, ...reeksen.map(r => waarden.get(r) ?? null)])
  return { kolommen: [x, ...reeksen], rijen: tabelRijen, labels: 1 }
}

function uitToolRijen(rijen, meta) {
  if (meta.location_col && meta.value_col) return kaartTabel(rijen, meta)
  const { x, y } = meta
  if (x && y && rijen.every(rij => 'reeks' in rij && x in rij && y in rij)) {
    const naastElkaar = reeksenNaastElkaar(rijen, x, y)
    if (naastElkaar) return naastElkaar
  }
  const kolommen = [...new Set(rijen.flatMap(Object.keys))].filter(zichtbaar)
  return { kolommen, rijen: rijen.map(rij => kolommen.map(k => rij[k] ?? null)), labels: kolommen.length - 1 }
}

export function figuurTabel(figure) {
  if (!figure || typeof figure !== 'object') return null
  const rijen = toolRows(figure)
  if (rijen?.length) return uitToolRijen(rijen, figure.layout.meta)
  // Een histogram of boxplot tekent een verdeling: zijn ruwe punten zijn niet de waarden die je ziet.
  if ((figure.data || []).some(t => DISTRIBUTION_TYPES.has(t?.type))) return null
  return tracesTabel(figure)
}
