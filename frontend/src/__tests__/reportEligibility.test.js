import { describe, it, expect } from 'vitest'
import { hasReportableAnswer, canGenerateReport } from '../reportEligibility'

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

describe('canGenerateReport', () => {
  const figureMessage = { role: 'assistant', content: '', figures: [{ label: 'x', json: '{}' }] }
  const snippetMessage = { role: 'assistant', content: 'c', tools: [{ name: 'get_duo_data', snippet: 'df = ..' }] }
  const plainMessage = { role: 'assistant', content: 'Hoi.' }

  it('is ready when the live session loaded data', () => {
    expect(canGenerateReport([figureMessage], [])).toBe('ready')
    expect(canGenerateReport([snippetMessage], [])).toBe('ready')
  })

  it('is ready when live data exists alongside restored history', () => {
    expect(canGenerateReport([figureMessage], [plainMessage])).toBe('ready')
  })

  it('reports needs_reload when only restored history carries data', () => {
    expect(canGenerateReport([plainMessage], [figureMessage])).toBe('needs_reload')
    expect(canGenerateReport([], [snippetMessage])).toBe('needs_reload')
  })

  it('reports no_data when no reportable answer exists', () => {
    expect(canGenerateReport([plainMessage], [plainMessage])).toBe('no_data')
    expect(canGenerateReport([], [])).toBe('no_data')
  })
})
