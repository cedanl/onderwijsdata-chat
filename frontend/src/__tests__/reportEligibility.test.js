import { describe, it, expect } from 'vitest'
import { hasReportableAnswer } from '../reportEligibility'

describe('hasReportableAnswer', () => {
  it('is false for a greeting or definition answer without data', () => {
    expect(hasReportableAnswer([
      { role: 'user', content: 'Waar staat DUO voor?' },
      { role: 'assistant', content: 'Dienst Uitvoering Onderwijs.', tools: [] },
    ])).toBe(false)
  })

  it('is false when only a clarification question was asked', () => {
    expect(hasReportableAnswer([
      { role: 'assistant', content: 'Welk niveau bedoel je?', clarification: ['Gemeente', 'Provincie'] },
    ])).toBe(false)
  })

  it('is true once a data tool produced a snippet', () => {
    expect(hasReportableAnswer([
      { role: 'assistant', content: 'Er zijn 27.441 studenten.', tools: [{ name: 'get_duo_data', snippet: 'df = ...' }] },
    ])).toBe(true)
  })

  it('is true when a figure was shown', () => {
    expect(hasReportableAnswer([
      { role: 'assistant', content: '', figures: [{ label: 'x', json: '{}' }] },
    ])).toBe(true)
  })

  it('ignores error messages', () => {
    expect(hasReportableAnswer([
      { role: 'assistant', content: 'fout', isError: true, figures: [{ label: 'x', json: '{}' }] },
    ])).toBe(false)
  })
})
