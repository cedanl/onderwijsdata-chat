import { describe, it, expect } from 'vitest'
import { SUGGESTED } from '../constants'
import { personalizeQuestion } from '../suggestions'

const all = SUGGESTED.flatMap(c => c.questions)

describe('personalizeQuestion', () => {
  it('names the institution in every suggested question', () => {
    const generic = all.filter(q => !personalizeQuestion(q, 'Hogeschool Utrecht').includes('Hogeschool Utrecht'))
    expect(generic).toEqual([])
  })

  it('leaves questions alone without an institution', () => {
    for (const q of all) expect(personalizeQuestion(q, '')).toBe(q)
  })

  it('reads naturally', () => {
    expect(personalizeQuestion('Wat is in mijn regio het opleidingsniveau van werkzoekenden?', 'ROC Midden Nederland'))
      .toBe('Wat is in de regio van ROC Midden Nederland het opleidingsniveau van werkzoekenden?')
  })
})
