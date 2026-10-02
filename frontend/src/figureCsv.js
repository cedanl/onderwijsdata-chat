// Plotly figure → semicolon CSV (Dutch Excel default).
//
// tools/plot.py stores the rows a chart was built from in layout.meta.data:
// those rows are the export, exactly as the tool computed them. Figures
// without them (run_analysis figures, older conversations) fall back to the
// drawn traces, without ever dropping a point (#183).

import { plotlyArray } from './plotlyArrays'

function axisTitle(axis) {
  const title = axis?.title
  return typeof title === 'string' ? title : title?.text
}

function cell(value) {
  const s = String(value ?? '')
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

const toCsv = rows => rows.map(r => r.map(cell).join(';')).join('\n')

// A horizontal bar draws its categories on y and its values on x.
const isHorizontal = trace => trace.orientation === 'h'
const xsOf = trace => plotlyArray(isHorizontal(trace) ? trace.y : (trace.x ?? trace.labels)) ?? []
const ysOf = trace => plotlyArray(isHorizontal(trace) ? trace.x : (trace.y ?? trace.values)) ?? []
// Heatmaps and maps keep their values in z: x and y are only labels, so the
// traces cannot be read as points. Without tool rows they get no CSV (#217).
const hasZ = trace => trace.z != null
const hasRepeatedX = trace => new Set(xsOf(trace)).size < xsOf(trace).length

function rowsToCsv(rows) {
  const columns = [...new Set(rows.flatMap(Object.keys))]
  return toCsv([columns, ...rows.map(row => columns.map(c => row[c]))])
}

// Wide: one row per distinct x, one column per trace. Traces need not share
// their x values (one trace per year), so each value is placed by its x.
function wideCsv(traces, xName, yName) {
  const xVals = [...new Set(traces.flatMap(xsOf))]
  const byX = traces.map(t => new Map(xsOf(t).map((x, i) => [x, ysOf(t)[i]])))
  const header = [xName, ...traces.map(t => t.name || yName)]
  return toCsv([header, ...xVals.map(x => [x, ...byX.map(values => values.get(x))])])
}

// Long: one row per point. Needed when an x label repeats within a trace,
// where a row per x would have to drop or silently merge values.
function longCsv(traces, xName, yName) {
  const withSeries = traces.length > 1
  const header = withSeries ? ['reeks', xName, yName] : [xName, yName]
  const rows = traces.flatMap(t => xsOf(t).map((x, i) => {
    const point = [x, ysOf(t)[i]]
    return withSeries ? [t.name || '', ...point] : point
  }))
  return toCsv([header, ...rows])
}

// Why a drawn trace cannot be exported faithfully, or null when it can. A
// figure that does not add up must not yield a CSV that looks fine next to a
// broken chart (#217).
const DISTRIBUTION_TYPES = new Set(['histogram', 'box', 'violin'])

function traceProblem(trace) {
  if (DISTRIBUTION_TYPES.has(trace.type)) return null
  const xs = xsOf(trace)
  const ys = ysOf(trace)
  if (!ys.length) return 'y-waarden ontbreken'
  if (xs.length !== ys.length) return `x (${xs.length}) en y (${ys.length}) zijn niet even lang`
  if (ys.every(y => y == null)) return 'alle y-waarden zijn leeg'
  if (ys.some(y => y != null && typeof y !== 'number')) return 'y-waarden zijn niet numeriek'
  return null
}

function tracesProblem(figure) {
  const traces = (figure.data || []).filter(t => !hasZ(t) && (xsOf(t).length || ysOf(t).length))
  for (const trace of traces) {
    const problem = traceProblem(trace)
    if (problem) return problem
  }
  return null
}

// A reason to show instead of a download button, or null when exportable.
// Figures with tool rows in layout.meta.data export those, not the traces.
export function figureCsvProblem(figure) {
  return hasToolRows(figure) ? null : tracesProblem(figure)
}

function tracesToCsv(figure) {
  const traces = figure.data || []
  if (traces.some(hasZ) || !traces.some(t => xsOf(t).length) || tracesProblem(figure)) return null

  const layout = figure.layout || {}
  const [catAxis, valAxis] = traces.every(isHorizontal) ? [layout.yaxis, layout.xaxis] : [layout.xaxis, layout.yaxis]
  const xName = layout.meta?.x || axisTitle(catAxis) || 'categorie'
  const yName = layout.meta?.y || axisTitle(valAxis) || 'waarde'
  return traces.some(hasRepeatedX) ? longCsv(traces, xName, yName) : wideCsv(traces, xName, yName)
}

const toolRows = figure => figure.layout?.meta?.data
const hasToolRows = figure => Array.isArray(toolRows(figure)) && toolRows(figure).length > 0

// Source and selections from tools/plot.py, as '#' lines above the header:
// pandas skips them with comment='#', a spreadsheet shows them as text (#118).
function withProvenance(csv, figure) {
  const lines = figure.layout?.meta?.herkomst
  if (!csv || !Array.isArray(lines) || !lines.length) return csv
  return [...lines.map(line => `# ${line}`), csv].join('\n')
}

export function figureToCsv(figure) {
  return withProvenance(hasToolRows(figure) ? rowsToCsv(toolRows(figure)) : tracesToCsv(figure), figure)
}
