// The hero numbers come from /api/catalog/counts: the sources the chat can query
// and their datasets. A hard-coded "5" also counted ROA and UWV, which the chat
// cannot load (#200).
export function heroStats(counts) {
  const values = Object.values(counts || {})
  if (values.length === 0) return { bronnen: '–', datasets: '–' }
  return {
    bronnen: values.length,
    datasets: values.reduce((sum, n) => sum + n, 0).toLocaleString('nl-NL'),
  }
}
