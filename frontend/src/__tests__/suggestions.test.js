import { describe, it, expect } from 'vitest'
import { SUGGESTED, SECTOREN } from '../constants'
import { personalizeQuestion, suggestionsFor } from '../suggestions'

const questionsFor = sector => suggestionsFor(sector).flatMap(c => c.questions)
const all = SUGGESTED.flatMap(c => c.questions).map(q => q.tekst)
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

  it('does not ask for dropout within the own programmes in hbo or wo; there it is only national', () => {
    const own = s => questionsFor(s).filter(q => /uitval/i.test(q) && FIRST_PERSON.test(q))
    expect([...own('hbo'), ...own('wo'), ...own(null)]).toEqual([])
  })

  // "Regio" means the location of the institution in one source and where students live in
  // another; until the region is derived in code (#448), a question names the province.
  it('does not leave "mijn regio" for the model to interpret', () => {
    expect(all.filter(q => q.includes('mijn regio'))).toEqual([])
  })
})

// Which questions the sources answer depends on the sector of the institution (#447).
describe('suggestionsFor', () => {
  it('gives every sector, and an unknown one, at least one question per category', () => {
    for (const sector of [...SECTOREN, null]) {
      const cats = suggestionsFor(sector)
      expect(cats.map(c => c.category)).toEqual(SUGGESTED.map(c => c.category))
      expect(cats.filter(c => c.questions.length === 0)).toEqual([])
    }
  })

  it('tags every question with known sectors', () => {
    const tags = SUGGESTED.flatMap(c => c.questions).flatMap(q => q.sectoren)
    expect(tags.filter(s => !SECTOREN.includes(s))).toEqual([])
  })

  it('asks where students come from only in mbo; hbo and wo have no place of residence', () => {
    expect(questionsFor('mbo').some(q => /vandaan/.test(q))).toBe(true)
    for (const sector of ['hbo', 'wo', null]) expect(questionsFor(sector).filter(q => /vandaan|woongemeente/.test(q))).toEqual([])
  })

  // With one university in most provinces, the institution is the region.
  it('compares a university with the wo nationally, not with its province', () => {
    expect(questionsFor('wo').filter(q => /provincie/.test(q) && !/vacature/i.test(q))).toEqual([])
  })

  it('shows only the questions that hold for every sector when the sector is unknown', () => {
    const everywhere = SUGGESTED.flatMap(c => c.questions).filter(q => SECTOREN.every(s => q.sectoren.includes(s)))
    expect(questionsFor(null)).toEqual(everywhere.map(q => q.tekst))
  })
})
