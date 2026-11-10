// The hero dataset count comes from /api/catalog/counts: the datasets the chat can search. The source count no longer
// comes from here but from bronnenLijst.js (aantalBronnen, #1010), so it also counts UWV and ROA and is right before
// the counts load.
export function heroStats(counts) {
  const values = Object.values(counts || {})
  if (values.length === 0) return { datasets: '–' }
  return { datasets: values.reduce((sum, n) => sum + n, 0).toLocaleString('nl-NL') }
}
