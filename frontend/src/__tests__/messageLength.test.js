import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { messageLengthState, resolveMaxMessageChars } from '../messageLength'
import { MAX_MESSAGE_CHARS } from '../constants'

// #481: the composer keeps new input within the server's MAX_MESSAGE_CHARS.
describe('messageLengthState', () => {
  it('telt de tekst zonder witruimte aan begin en eind, zoals de server', () => {
    expect(messageLengthState('  abc \n', 10)).toEqual({ count: 3, max: 10, atLimit: false, over: false, showCounter: false })
  })

  it('toont de teller vanaf 80% van het maximum', () => {
    expect(messageLengthState('x'.repeat(7), 10).showCounter).toBe(false)
    expect(messageLengthState('x'.repeat(8), 10).showCounter).toBe(true)
    expect(messageLengthState('x'.repeat(3199), 4000).showCounter).toBe(false)
    expect(messageLengthState('x'.repeat(3200), 4000).showCounter).toBe(true)
  })

  it('staat precies op het maximum aan de grens, maar niet erover', () => {
    const state = messageLengthState('x'.repeat(10), 10)
    expect(state.atLimit).toBe(true)
    expect(state.over).toBe(false)
  })

  it('is boven het maximum te lang', () => {
    const state = messageLengthState('x'.repeat(11), 10)
    expect(state).toMatchObject({ count: 11, atLimit: true, over: true, showCounter: true })
  })

  it('gebruikt standaard MAX_MESSAGE_CHARS', () => {
    expect(messageLengthState('').max).toBe(MAX_MESSAGE_CHARS)
    expect(messageLengthState('x'.repeat(MAX_MESSAGE_CHARS + 1)).over).toBe(true)
  })
})

describe('resolveMaxMessageChars', () => {
  it('neemt een positief geheel getal van de server over (#501)', () => {
    expect(resolveMaxMessageChars(50)).toBe(50)
    expect(resolveMaxMessageChars(1234)).toBe(1234)
  })

  it.each([undefined, null, 0, -1, 1.5, 'abc', '50', NaN, Infinity])('valt bij %s terug op MAX_MESSAGE_CHARS', value => {
    expect(resolveMaxMessageChars(value)).toBe(MAX_MESSAGE_CHARS)
  })
})

// The server publishes the real limit via /api/config (#501); the constant is only the fallback
// when that fails, so it must match the server's default.
describe('MAX_MESSAGE_CHARS als terugvalwaarde', () => {
  it('is gelijk aan de standaard in core/config.py', () => {
    const config = readFileSync(join(__dirname, '..', '..', '..', 'core', 'config.py'), 'utf8')
    const match = config.match(/MAX_MESSAGE_CHARS = int\(os\.getenv\("MAX_MESSAGE_CHARS", "(\d+)"\)\)/)
    expect(match).not.toBeNull()
    expect(MAX_MESSAGE_CHARS).toBe(Number(match[1]))
  })
})
