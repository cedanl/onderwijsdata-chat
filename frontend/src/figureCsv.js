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

// Excel runs a text cell that starts with = + - or @ as a formula (#483); OWASP
// (CSV injection) also lists a leading tab or CR (#607). Such text gets a
// leading ' (so the CSV differs from the tool rows there, on purpose); numbers
// and numeric text like '-1' or '-0,5' stay as they are. Same rule as _veilig
// in tools/csv_export.py.
const NEEDS_PREFIX = /^[=+\-@\t\r]/
const NUMERIC = /^[+-]?\d+([.,]\d+)*$/

function safeText(value) {
  const s = String(value ?? '')
  if (typeof value === 'number' || !NEEDS_PREFIX.test(s) || NUMERIC.test(s)) return s
  return `'${s}`
}

// A CR outside quotes ends a row for Excel and csv readers, like a newline.
function cell(value) {
  const s = safeText(value)
  return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

// Also the row format of the cited-numbers export (citatieCsv.js).
export const toCsv = rows => rows.map(r => r.map(cell).join(';')).join('\n')

// A horizontal bar draws its categories on y and its values on x. Also read by figuurBeschrijving.js.
const isHorizontal = trace => trace.orientation === 'h'
export const xsOf = trace => plotlyArray(isHorizontal(trace) ? trace.y : (trace.x ?? trace.labels)) ?? []
export const ysOf = trace => plotlyArray(isHorizontal(trace) ? trace.x : (trace.y ?? trace.values)) ?? []
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
function wideRows(traces, xName, yName) {
  const xVals = [...new Set(traces.flatMap(xsOf))]
  const byX = traces.map(t => new Map(xsOf(t).map((x, i) => [x, ysOf(t)[i]])))
  const kolommen = [xName, ...traces.map(t => t.name || yName)]
  return { kolommen, rijen: xVals.map(x => [x, ...byX.map(values => values.get(x) ?? null)]), labels: 1 }
}

// Long: one row per point. Needed when an x label repeats within a trace,
// where a row per x would have to drop or silently merge values.
function longRows(traces, xName, yName) {
  const withSeries = traces.length > 1
  const kolommen = withSeries ? ['reeks', xName, yName] : [xName, yName]
  const rijen = traces.flatMap(t => xsOf(t).map((x, i) => {
    const point = [x, ysOf(t)[i]]
    return withSeries ? [t.name || '', ...point] : point
  }))
  return { kolommen, rijen, labels: kolommen.length - 1 }
}

// Why a drawn trace cannot be exported faithfully, or null when it can. A
// figure that does not add up must not yield a CSV that looks fine next to a
// broken chart (#217).
export const DISTRIBUTION_TYPES = new Set(['histogram', 'box', 'violin'])

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

// The drawn traces as columns and rows, or null when they cannot be read as points. `labels` counts the
// leading label columns (x, and the series in the long form); the rest are values. Also read by figuurTabel.js.
export function tracesTabel(figure) {
  const traces = figure.data || []
  if (traces.some(hasZ) || !traces.some(t => xsOf(t).length) || tracesProblem(figure)) return null

  const layout = figure.layout || {}
  const [catAxis, valAxis] = traces.every(isHorizontal) ? [layout.yaxis, layout.xaxis] : [layout.xaxis, layout.yaxis]
  const xName = layout.meta?.x || axisTitle(catAxis) || 'categorie'
  const yName = layout.meta?.y || axisTitle(valAxis) || 'waarde'
  return traces.some(hasRepeatedX) ? longRows(traces, xName, yName) : wideRows(traces, xName, yName)
}

function tracesToCsv(figure) {
  const tabel = tracesTabel(figure)
  return tabel && toCsv([tabel.kolommen, ...tabel.rijen])
}

// A tool row is an object; anything else in a stored meta (null, a list, text) is skipped rather than
// taking the whole answer down (#642). The rows are also read by figuurTabel.js.
const isRij = rij => rij !== null && typeof rij === 'object' && !Array.isArray(rij)
export const toolRows = figure => (Array.isArray(figure.layout?.meta?.data) ? figure.layout.meta.data.filter(isRij) : null)
const hasToolRows = figure => toolRows(figure)?.length > 0

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

// Veilig voor een bestandsnaam: accenten vallen weg (é → e), al het andere dan letters en cijfers wordt een
// underscore.
const bestandsdeel = tekst => String(tekst ?? '')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')

// Bestandsnaam van de CSV bij een grafiek (#496 F11, #533): `<titel>_<dataset-id>.csv`, de titel van de grafiek
// (hoogstens 80 tekens, zonder titel `fallback`) en het dataset-id uit layout.meta.dataset (tools/plot.py); zonder
// id alleen `<titel>.csv`. Dezelfde regel als bestandsnaam in tools/csv_export.py: de twee moeten gelijk opgaan.
export function figureCsvFilename(figure, fallback = 'data') {
  const title = figure?.layout?.title
  const tekst = typeof title === 'string' ? title : title?.text
  const titel = bestandsdeel(tekst).slice(0, 80).replace(/_+$/, '') || bestandsdeel(fallback) || 'data'
  const dataset = bestandsdeel(figure?.layout?.meta?.dataset)
  return `${dataset ? `${titel}_${dataset}` : titel}.csv`
}
