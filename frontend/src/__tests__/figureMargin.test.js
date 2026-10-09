import { describe, it, expect } from 'vitest'
import { topMargin, topMarginOfJson } from '../figureMargin'

const metNoot = { title: { text: 'HO', subtitle: { text: 'Afgerond op 10-tallen' } }, margin: { t: 100 } }

// CH-34: the chat set the top margin to 32 px, so title and note covered the plot.
describe('topMargin', () => {
  it('keeps the margin the server gave a chart with a note', () => {
    expect(topMargin(metNoot, 32)).toBe(100)
  })

  it('uses the base margin for a chart without a note', () => {
    expect(topMargin({ title: { text: 'HO' }, margin: { t: 60 } }, 32)).toBe(32)
    expect(topMargin(undefined, 32)).toBe(32)
  })

  it('never goes below the base margin', () => {
    expect(topMargin({ ...metNoot, margin: { t: 20 } }, 48)).toBe(48)
  })

  it('reads the figure JSON of a report, and falls back on invalid JSON', () => {
    expect(topMarginOfJson(JSON.stringify({ data: [], layout: metNoot }), 48)).toBe(100)
    expect(topMarginOfJson('{niet json', 48)).toBe(48)
  })
})
