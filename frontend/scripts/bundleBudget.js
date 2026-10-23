// Performance budgets, gzipped as they go over the line. Run after `vite build`.
// - the first load (#110): the JavaScript that /login fetches before anything is shown;
// - per route (#689): what chat, rapporten and dashboards fetch on top of that, from the Vite manifest;
// - the two Plotly bundles (#689): the full one for figures in the app, and the maplibre-free one that a report
//   frame loads (#660). Set at the measured size plus a margin, so growth is a decision, not an accident.
import { readFileSync, readdirSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

// Measured 94 kB at the time of #110; the margin leaves room for normal growth, not for Plotly.
export const BUDGET_BYTES = 125_000

// Measured on 23-10-2026 (gzip, on top of the first load): chat 102 kB, rapporten 148 kB, dashboards 151 kB.
export const ROUTE_BUDGETS = {
  'src/pages/ChatPage.jsx': 130_000,
  'src/pages/RapportenPage.jsx': 185_000,
  'src/pages/DashboardPage.jsx': 185_000,
}

// Measured on 23-10-2026: react-plotly with full Plotly 1417 kB, the report Plotly 1086 kB (3.3 MB raw).
export const PLOTLY_BUDGETS = {
  'node_modules/react-plotly.js/dist/index.mjs': 1_500_000,
  'plotly-rapport': 1_150_000,
}

const SCRIPT = /<script[^>]*\bsrc="\/([^"]+\.js)"/g
const PRELOAD = /<link[^>]*rel="modulepreload"[^>]*href="\/([^"]+\.js)"/g

export function initialScripts(html) {
  return [...html.matchAll(SCRIPT), ...html.matchAll(PRELOAD)].map(m => m[1])
}

// The chunks a manifest entry pulls in statically, without what the first load already has.
export function routeChunks(manifest, key) {
  const closure = (start) => {
    const seen = new Set()
    const visit = (k) => {
      if (seen.has(k) || !manifest[k]) return
      seen.add(k)
      for (const imp of manifest[k].imports || []) visit(imp)
    }
    visit(start)
    return seen
  }
  const initial = closure('index.html')
  return [...closure(key)].filter(k => !initial.has(k)).map(k => manifest[k].file)
}

const kB = bytes => `${(bytes / 1000).toFixed(1)} kB`

export function budgetReport(sizes, budget = BUDGET_BYTES, label = 'Initial JS') {
  const total = Object.values(sizes).reduce((a, b) => a + b, 0)
  const lines = Object.entries(sizes).map(([file, size]) => `  ${file}: ${kB(size)}`)
  const ok = total <= budget
  const message = `${label} (gzip) ${kB(total)} of ${kB(budget)}${ok ? '' : ' — over budget'}\n${lines.join('\n')}`
  return { ok, message }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dist = join(fileURLToPath(new URL('..', import.meta.url)), 'dist')
  const gzip = f => gzipSync(readFileSync(join(dist, f))).length
  const sizesOf = files => Object.fromEntries(files.map(f => [f, gzip(f)]))
  const manifest = JSON.parse(readFileSync(join(dist, '.vite', 'manifest.json'), 'utf8'))
  const rapportPlotly = readdirSync(join(dist, 'assets')).find(f => f.startsWith('plotly-rapport'))

  const reports = [
    budgetReport(sizesOf(initialScripts(readFileSync(join(dist, 'index.html'), 'utf8')))),
    ...Object.entries(ROUTE_BUDGETS).map(([key, budget]) => budgetReport(sizesOf(routeChunks(manifest, key)), budget, `Route ${key}`)),
    budgetReport(sizesOf(routeChunks(manifest, 'node_modules/react-plotly.js/dist/index.mjs')), PLOTLY_BUDGETS['node_modules/react-plotly.js/dist/index.mjs'], 'Plotly (app)'),
    budgetReport(sizesOf([`assets/${rapportPlotly}`]), PLOTLY_BUDGETS['plotly-rapport'], 'Plotly (report frame)'),
  ]
  for (const { message } of reports) console.log(message)
  if (reports.some(r => !r.ok)) process.exit(1)
}
