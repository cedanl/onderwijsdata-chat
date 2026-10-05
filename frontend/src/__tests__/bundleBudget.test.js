import { describe, it, expect } from 'vitest'
import { initialScripts, budgetReport } from '../../scripts/bundleBudget.js'

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
