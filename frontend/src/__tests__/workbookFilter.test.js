import { describe, it, expect } from 'vitest'
import { filterWorkbooks } from '../workbookFilter'

const ids = list => list.map(wb => wb.id)

// #562: tens of report cards and no way to search; the title search narrows the list.
describe('filterWorkbooks', () => {
  const rapporten = [
    { id: 'a', title: 'Instroom onderwijs hbo', description: 'economie' },
    { id: 'b', title: 'Economië en instroom' },
    { id: 'c', title: 'Uitval mbo' },
  ]

  it('ignores case', () => {
    expect(ids(filterWorkbooks(rapporten, 'ONDERWIJS'))).toEqual(['a'])
    expect(ids(filterWorkbooks([{ id: 'x', title: 'ONDERWIJS' }], 'onderwijs'))).toEqual(['x'])
  })

  it('ignores accents, in the title and in the query', () => {
    expect(ids(filterWorkbooks(rapporten, 'economie'))).toEqual(['b'])
    expect(ids(filterWorkbooks([{ id: 'x', title: 'Economie' }], 'Economië'))).toEqual(['x'])
  })

  it('matches on the title only', () => {
    expect(ids(filterWorkbooks([{ id: 'x', title: 'Uitval', description: 'economie' }], 'economie'))).toEqual([])
  })

  it('needs every word in the title, in any order, each as part of a word', () => {
    expect(ids(filterWorkbooks(rapporten, 'instroom'))).toEqual(['a', 'b'])
    expect(ids(filterWorkbooks(rapporten, 'hbo instroom'))).toEqual(['a'])
    expect(ids(filterWorkbooks(rapporten, '  instr   ECON  '))).toEqual(['b'])
    expect(ids(filterWorkbooks(rapporten, 'instroom mbo'))).toEqual([])
  })

  it('returns the list unchanged for an empty query', () => {
    for (const query of ['', '   ', '\t\n', null, undefined]) {
      expect(filterWorkbooks(rapporten, query)).toEqual(rapporten)
    }
  })

  it('returns an empty list when nothing matches', () => {
    expect(filterWorkbooks(rapporten, 'arbeidsmarkt')).toEqual([])
  })

  it('does not throw on a report without a usable title, and does not match it', () => {
    const zonderTitel = [{ id: 'u' }, { id: 'n', title: null }, { id: 'g', title: 42 }, { id: 'o', title: { x: 1 } }]
    expect(filterWorkbooks(zonderTitel, 'undefined')).toEqual([])
    expect(filterWorkbooks(zonderTitel, 'null')).toEqual([])
    expect(filterWorkbooks(zonderTitel, '42')).toEqual([])
    expect(filterWorkbooks(zonderTitel, 'object')).toEqual([])
    expect(filterWorkbooks(zonderTitel, '')).toEqual(zonderTitel)
  })

  it('does not change the list it gets', () => {
    const input = rapporten.map(wb => ({ ...wb }))
    const kopie = structuredClone(input)
    filterWorkbooks(input, 'instroom')
    filterWorkbooks(input, '')
    expect(input).toEqual(kopie)
  })
})
