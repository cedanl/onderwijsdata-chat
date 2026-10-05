// Performance budget for the first load (#110): the JavaScript that /login fetches before
// anything is shown, gzipped as it goes over the line. Run after `vite build`.
import { readFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

// Measured 94 kB at the time of #110; the margin leaves room for normal growth, not for Plotly.
export const BUDGET_BYTES = 125_000

const SCRIPT = /<script[^>]*\bsrc="\/([^"]+\.js)"/g
const PRELOAD = /<link[^>]*rel="modulepreload"[^>]*href="\/([^"]+\.js)"/g

export function initialScripts(html) {
  return [...html.matchAll(SCRIPT), ...html.matchAll(PRELOAD)].map(m => m[1])
}

const kB = bytes => `${(bytes / 1000).toFixed(1)} kB`

export function budgetReport(sizes, budget = BUDGET_BYTES) {
  const total = Object.values(sizes).reduce((a, b) => a + b, 0)
  const lines = Object.entries(sizes).map(([file, size]) => `  ${file}: ${kB(size)}`)
  const ok = total <= budget
  const message = `Initial JS (gzip) ${kB(total)} of ${kB(budget)}${ok ? '' : ' — over budget'}\n${lines.join('\n')}`
  return { ok, message }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dist = join(fileURLToPath(new URL('..', import.meta.url)), 'dist')
  const files = initialScripts(readFileSync(join(dist, 'index.html'), 'utf8'))
  const sizes = Object.fromEntries(files.map(f => [f, gzipSync(readFileSync(join(dist, f))).length]))
  const { ok, message } = budgetReport(sizes)
  console.log(message)
  if (!ok) process.exit(1)
}
