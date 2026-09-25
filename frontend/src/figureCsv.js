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

const xsOf = trace => trace.x || trace.labels || []
const ysOf = trace => trace.y || trace.values || []

// One row per distinct x across all traces: traces need not share their x
// values (one trace per year), so each value is placed by its x, not its index.
export function figureToCsv(figure) {
  const traces = figure.data || []
  const xVals = [...new Set(traces.flatMap(xsOf))]
  if (xVals.length === 0) return null

  const layout = figure.layout || {}
  const xName = layout.meta?.x || axisTitle(layout.xaxis) || 'categorie'
  const yName = layout.meta?.y || axisTitle(layout.yaxis) || 'waarde'
  const header = [xName, ...traces.map(t => t.name || yName)]
  const byX = traces.map(t => new Map(xsOf(t).map((x, i) => [x, ysOf(t)[i]])))
  const rows = xVals.map(x => [x, ...byX.map(values => values.get(x))])
  return [header, ...rows].map(r => r.map(cell).join(';')).join('\n')
}
