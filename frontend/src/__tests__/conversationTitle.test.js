import { describe, it, expect } from 'vitest'
import { conversationTitle } from '../conversationTitle'

describe('conversationTitle', () => {
  it('strips HTML tags', () => {
    expect(conversationTitle('<svg onload=alert(1)>Hoeveel studenten?</svg>')).toBe('Hoeveel studenten?')
  })

  it('collapses whitespace and newlines', () => {
    expect(conversationTitle('  Hoeveel\n\n  mbo-studenten\tin Utrecht?  ')).toBe('Hoeveel mbo-studenten in Utrecht?')
  })

  it('caps the length at 80 characters', () => {
    expect(conversationTitle('a'.repeat(200))).toHaveLength(80)
  })

  it('falls back when nothing readable is left', () => {
    expect(conversationTitle('<img src=x onerror=alert(1)>')).toBe('Nieuw gesprek')
  })
})
