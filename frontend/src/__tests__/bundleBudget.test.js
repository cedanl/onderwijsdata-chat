import { describe, it, expect } from 'vitest'
import { initialScripts, budgetReport, routeChunks } from '../../scripts/bundleBudget.js'

// #110: /login loaded 5.5 MB. The routes are lazy now; this keeps the first load small.
describe('initialScripts', () => {
  it('takes the entry and its modulepreloads, not the lazy chunks', () => {
    const html = `<!doctype html><head>
      <script type="module" crossorigin src="/assets/index-A.js"></script>
      <link rel="modulepreload" crossorigin href="/assets/vendor-B.js">
      <link rel="stylesheet" crossorigin href="/assets/index-C.css">
    </head>`
    expect(initialScripts(html)).toEqual(['assets/index-A.js', 'assets/vendor-B.js'])
  })
})

describe('budgetReport', () => {
  it('passes under the budget and fails over it', () => {
    const sizes = { 'assets/index-A.js': 90_000, 'assets/vendor-B.js': 20_000 }
    expect(budgetReport(sizes, 120_000).ok).toBe(true)
    const over = budgetReport(sizes, 100_000)
    expect(over.ok).toBe(false)
    expect(over.message).toMatch(/110\.0 kB.*100\.0 kB/)
  })
})

// #689: the report and dashboard routes load far more than /login; each route gets its own budget.
describe('routeChunks', () => {
  const manifest = {
    'index.html': { file: 'assets/index-A.js', imports: ['_react.js'], dynamicImports: ['src/pages/RapportenPage.jsx'] },
    '_react.js': { file: 'assets/react-R.js' },
    'src/pages/RapportenPage.jsx': { file: 'assets/RapportenPage-P.js', imports: ['_react.js', '_gallery.js'], dynamicImports: ['plotly'] },
    '_gallery.js': { file: 'assets/gallery-G.js', imports: ['_modal.js'] },
    '_modal.js': { file: 'assets/modal-M.js' },
    plotly: { file: 'assets/plotly-X.js' },
  }

  it('counts the static imports of the route, transitively', () => {
    expect(routeChunks(manifest, 'src/pages/RapportenPage.jsx').sort())
      .toEqual(['assets/RapportenPage-P.js', 'assets/gallery-G.js', 'assets/modal-M.js'])
  })

  it('leaves out what the first load already has and what the route only imports lazily', () => {
    const chunks = routeChunks(manifest, 'src/pages/RapportenPage.jsx')
    expect(chunks).not.toContain('assets/react-R.js')
    expect(chunks).not.toContain('assets/plotly-X.js')
  })

  it('labels the report', () => {
    expect(budgetReport({ 'assets/x.js': 10 }, 100, 'Route rapporten').message).toMatch(/^Route rapporten \(gzip\)/)
  })
})
