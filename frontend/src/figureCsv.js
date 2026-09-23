// Plotly figure → semicolon CSV (Dutch Excel default), using the real
// column names that tools/plot.py stores in layout.meta.

function axisTitle(axis) {
  const title = axis?.title
  return typeof title === 'string' ? title : title?.text
}

function cell(value) {
  const s = String(value ?? '')
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function figureToCsv(figure) {
  const traces = figure.data || []
  if (traces.length === 0) return null
  const xVals = traces[0].x || traces[0].labels || []
  if (xVals.length === 0) return null

  const layout = figure.layout || {}
  const xName = layout.meta?.x || axisTitle(layout.xaxis) || 'categorie'
  const yName = layout.meta?.y || axisTitle(layout.yaxis) || 'waarde'
  const header = [xName, ...traces.map(t => t.name || yName)]
  const rows = xVals.map((x, i) => [x, ...traces.map(t => (t.y || t.values)?.[i])])
  return [header, ...rows].map(r => r.map(cell).join(';')).join('\n')
}
