// Een Chart.js-grafiek van de dashboards als Plotly-figuur (#905), zodat de chat en de dashboards één beschrijving
// (figuurBeschrijving, #588) en één waardentabel (figuurTabel, #664) delen. Alleen wat die twee lezen: per reeks de
// labels als x en de waarden als y, de titel en de assen. Een liggende staaf (indexAxis 'y') leest net zo: de labels
// zijn de categorieën.

const JAAR = /^\d{4}(\s*[-–/]\s*\d{2,4})?$/

// De naam van de labelkolom: 'Jaar' voor jaartallen, anders wat de grafiek opgeeft, of 'Categorie'.
function categorieNaam(labels, categorie) {
  if (categorie) return categorie
  return labels.length && labels.every(l => JAAR.test(String(l))) ? 'Jaar' : 'Categorie'
}

// De titel van de waardeas uit de Chart.js-opties: y voor een staande grafiek, x voor een liggende.
export function waardeAsTitel(options) {
  const as = options?.indexAxis === 'y' ? options?.scales?.x : options?.scales?.y
  return as?.title?.display ? as.title.text : undefined
}

const getal = v => (typeof v === 'number' && Number.isFinite(v) ? v : null)

// Een reeks zonder één waarde (een lege concurrent) blijft weg: de tabel weigert anders de hele grafiek. Een reeks met
// `waarden` tekent een afgekapte staaf (`data`, #952): beschrijving en tabel noemen dan de echte waarde.
export function alsFiguur(soort, data, { titel, categorie, waardeAs } = {}) {
  const labels = (data?.labels ?? []).map(String)
  const traces = (data?.datasets ?? [])
    .map(ds => ({
      type: soort === 'bar' ? 'bar' : 'scatter',
      ...(soort !== 'bar' && { mode: 'lines' }),
      name: ds.label,
      x: labels,
      y: labels.map((_, i) => getal((ds.waarden ?? ds.data)?.[i])),
    }))
    .filter(t => t.y.some(v => v != null))
  return {
    data: traces,
    layout: {
      ...(titel && { title: { text: titel } }),
      xaxis: { title: { text: categorieNaam(labels, categorie) } },
      ...(waardeAs && { yaxis: { title: { text: waardeAs } } }),
    },
  }
}
