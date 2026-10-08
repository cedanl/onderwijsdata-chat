import { describe, it, expect } from 'vitest'
import { SUGGESTED } from '../constants'
import { personalizeQuestion } from '../suggestions'

const all = SUGGESTED.flatMap(c => c.questions)
const FIRST_PERSON = /\b(ons|onze|mijn)\b/i

describe('personalizeQuestion', () => {
  it('names the institution wherever a question speaks in the first person', () => {
    const left = all
      .filter(q => FIRST_PERSON.test(q))
      .map(q => personalizeQuestion(q, 'Hogeschool Utrecht'))
      .filter(q => FIRST_PERSON.test(q) || !q.includes('Hogeschool Utrecht'))
    expect(left).toEqual([])
  })

  it('leaves questions alone without an institution', () => {
    for (const q of all) expect(personalizeQuestion(q, '')).toBe(q)
  })

  it('reads naturally', () => {
    expect(personalizeQuestion('Wat is in mijn regio het opleidingsniveau van werkzoekenden?', 'ROC Midden Nederland'))
      .toBe('Wat is in de regio van ROC Midden Nederland het opleidingsniveau van werkzoekenden?')
    expect(personalizeQuestion('Hoeveel vacatures staan er in mijn provincie open?', 'ROC Midden Nederland'))
      .toBe('Hoeveel vacatures staan er in de provincie van ROC Midden Nederland open?')
  })
})

// The labour-market sources are a UWV snapshot per province and a national ROA forecast.
// No source links graduates to jobs, so a question must not promise that (#446).
describe('suggested questions promise only what the data can show', () => {
  it('never promises a match between graduates and jobs, or regional labour demand', () => {
    expect(all.filter(q => /aansluit|arbeidsmarktvraag|arbeidsmarktpotentieel/i.test(q))).toEqual([])
  })

  it('names the UWV snapshot whenever it asks about vacancies', () => {
    expect(all.filter(q => /vacature/i.test(q) && !(q.includes('UWV') && q.includes('mei 2023')))).toEqual([])
  })

  it('calls a ROA forecast national', () => {
    expect(all.filter(q => q.includes('ROA') && !q.includes('landelijk'))).toEqual([])
  })

  it('asks about vacancies per province, the only level UWV has', () => {
    expect(all.filter(q => /vacature/i.test(q) && !q.includes('provincie'))).toEqual([])
  })

  it('does not ask for dropout within the own programmes; hbo and wo only have it nationally', () => {
    expect(all.filter(q => /uitval/i.test(q) && FIRST_PERSON.test(q))).toEqual([])
  })
})
