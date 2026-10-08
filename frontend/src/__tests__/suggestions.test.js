import { describe, it, expect } from 'vitest'
import { SUGGESTED, SECTOREN } from '../constants'
import { personalizeQuestion, suggestionsFor } from '../suggestions'

const questionsFor = (sector, profiel = true) => suggestionsFor(sector, { profiel }).flatMap(c => c.questions)
// Every question as a user can see it: each sector, an unknown one, with and without a profile.
const all = [...new Set([...SECTOREN, null].flatMap(s => [...questionsFor(s), ...questionsFor(s, false)]))]
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
  it('never shows an empty category', () => {
    for (const sector of [...SECTOREN, null]) {
      for (const profiel of [true, false]) {
        expect(suggestionsFor(sector, { profiel }).filter(c => c.questions.length === 0)).toEqual([])
      }
    }
  })

  it('gives every sector at least three categories', () => {
    for (const sector of [...SECTOREN, null]) expect(suggestionsFor(sector).length).toBeGreaterThanOrEqual(3)
  })

  it('tags every question with known sectors', () => {
    const tags = SUGGESTED.flatMap(c => c.questions).flatMap(q => q.sectoren)
    expect(tags.filter(s => !SECTOREN.includes(s))).toEqual([])
  })

  // Audit 17 (CH-43) said no open source has a place of residence per institution; for mbo DUO
  // has one (mbo-studenten-per-instelling, woongemeente per instelling), for hbo and wo not.
  it('asks where students live only in mbo; hbo and wo have no place of residence', () => {
    expect(questionsFor('mbo').filter(q => /woongemeente/.test(q))).toHaveLength(1)
    for (const sector of ['hbo', 'wo', null]) expect(questionsFor(sector).filter(q => /vandaan|woongemeente/.test(q))).toEqual([])
  })

  // With one university in most provinces, the institution is the region.
  it('compares a university with the wo nationally, not with its province', () => {
    expect(questionsFor('wo').filter(q => /provincie/.test(q) && !/vacature/i.test(q))).toEqual([])
  })

  it('shows only the questions that hold for every sector when the sector is unknown', () => {
    const everywhere = SUGGESTED.flatMap(c => c.questions).filter(q => SECTOREN.every(s => q.sectoren.includes(s)))
    expect(questionsFor(null)).toHaveLength(everywhere.filter(q => q.profiel !== false).length)
  })
})

// CH-42 (#465): without an institution in the profile, "onze instelling" ended in a scope refusal.
describe('suggestions without a profile', () => {
  it('never speak of an institution or a province the chat does not know', () => {
    expect(questionsFor(null, false).filter(q => FIRST_PERSON.test(q))).toEqual([])
  })

  it('still offer a question in every category', () => {
    expect(suggestionsFor(null, { profiel: false }).map(c => c.category)).toEqual(SUGGESTED.map(c => c.category))
  })
})

// CH-43 (#469): sector variants were separate questions, and the set held near-duplicates.
describe('the suggestion set', () => {
  it('fills in every sector variant', () => {
    expect(all.filter(q => /[{}]/.test(q))).toEqual([])
  })

  it('asks about UWV vacancies once per view', () => {
    for (const sector of [...SECTOREN, null]) {
      for (const profiel of [true, false]) expect(questionsFor(sector, profiel).filter(q => /UWV/.test(q))).toHaveLength(1)
    }
  })

  it('asks for ho dropout through the CBS cohorts, not an old rendement table', () => {
    const uitval = s => questionsFor(s).filter(q => /diploma \(CBS-cohorten\)/.test(q))
    expect(uitval('hbo')).toHaveLength(1)
    expect(uitval('wo')).toHaveLength(1)
    expect(all.filter(q => /zonder diploma/.test(q))).toEqual([])
  })

  it('puts the vacancy question under the labour market', () => {
    const regionaal = SUGGESTED.find(c => c.category === 'Regionale Context').questions
    expect(regionaal.filter(q => /UWV/.test(q.tekst))).toEqual([])
  })
})
