import { describe, it, expect } from 'vitest'
import { groupByMonth } from '../workbookGroups'

// #427: 140 report cards in one flat grid; grouped by month, newest first.
describe('groupByMonth', () => {
  it('groups reports by the month they were made, newest month and report first', () => {
    const groups = groupByMonth([
      { id: 'sep', createdAt: '2026-09-24T10:00:00Z' },
      { id: 'okt-1', createdAt: '2026-10-01T10:00:00Z' },
      { id: 'okt-6', createdAt: '2026-10-06T10:00:00Z' },
    ])
    expect(groups.map(g => g.label)).toEqual(['Oktober 2026', 'September 2026'])
    expect(groups[0].workbooks.map(w => w.id)).toEqual(['okt-6', 'okt-1'])
  })

  it('keeps a report without a usable date, under its own heading', () => {
    const groups = groupByMonth([{ id: 'x', createdAt: '' }, { id: 'y', createdAt: '2026-10-06T10:00:00Z' }])
    expect(groups.map(g => g.label)).toEqual(['Oktober 2026', 'Zonder datum'])
  })
})
