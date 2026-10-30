import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { MAX_CHAT_TURNS, MAX_FEEDBACK_CHARS, MAX_HISTORY } from '../constants'
import { resolveMaxChatTurns, resolveMaxHistory, trimHistory, warnChatTurns } from '../contextLimits'
import { buildHistory } from '../hooks/useChat'

// Six questions with their answers: user 0, assistant 0, …, user 5, assistant 5.
const gesprek = Array.from({ length: 6 }, (_, i) => [
  { id: 2 * i, role: 'user', content: `user ${i}` },
  { id: 2 * i + 1, role: 'assistant', content: `assistant ${i}`, done: true },
]).flat()
const kaal = m => ({ role: m.role, content: m.content })

// #789: the client cuts like agent/history.py trim (and so like a reopened conversation on the server):
// the first question stays, it is the subject of report and dashboard. slice(-40) dropped it.
describe('inkorten met behoud van de eerste vraag (#789)', () => {
  it('buildHistory houdt de eerste vraag vóór de jongste berichten', () => {
    const history = buildHistory(gesprek, 6)
    expect(history[0]).toEqual({ role: 'user', content: 'user 0' })
    // The same cut as tests/test_ws_acties.py: the first question plus the last five messages.
    expect(history).toEqual([gesprek[0], ...gesprek.slice(-5)].map(kaal))
  })

  it('laat een gesprek binnen de grens heel', () => {
    expect(buildHistory(gesprek, 12)).toEqual(gesprek.map(kaal))
  })

  it('zet de eerste vraag niet dubbel als ze nog in de staart zit', () => {
    const welkom = { role: 'assistant', content: 'welkom' }
    const history = [welkom, welkom, ...gesprek.slice(0, 2).map(kaal)]
    expect(trimHistory(history, 3)).toEqual(history.slice(-2))
  })

  it('valt zonder grens terug op MAX_HISTORY', () => {
    const lang = Array.from({ length: MAX_HISTORY + 2 }, (_, i) => ({ role: i % 2 ? 'assistant' : 'user', content: `${i}` }))
    const history = trimHistory(lang)
    expect(history).toHaveLength(MAX_HISTORY)
    expect(history[0]).toBe(lang[0])
  })
})

describe('de contextlimieten van de server (#789)', () => {
  it('neemt een positief geheel getal over', () => {
    expect(resolveMaxChatTurns(5)).toBe(5)
    expect(resolveMaxHistory(10)).toBe(10)
  })

  it.each([undefined, null, 0, -1, 1.5, '20', NaN])('valt bij %s terug op de constante', value => {
    expect(resolveMaxChatTurns(value)).toBe(MAX_CHAT_TURNS)
    expect(resolveMaxHistory(value)).toBe(MAX_HISTORY)
  })

  it('waarschuwt vanaf 80% van de vragen', () => {
    expect(warnChatTurns(20)).toBe(16)
    expect(warnChatTurns(5)).toBe(4)
  })
})

// The constants are only fallbacks for a failed /api/config, so they must match the server's defaults.
describe('terugvalwaarden gelijk aan de server (#789)', () => {
  const backend = (...pad) => readFileSync(join(__dirname, '..', '..', '..', ...pad), 'utf8')

  it('MAX_HISTORY en MAX_CHAT_TURNS volgen core/config.py', () => {
    const config = backend('core', 'config.py')
    const match = config.match(/MAX_HISTORY = int\(os\.getenv\("MAX_HISTORY", "(\d+)"\)\)/)
    expect(match).not.toBeNull()
    expect(MAX_HISTORY).toBe(Number(match[1]))
    expect(config).toContain('MAX_CHAT_TURNS = max(1, MAX_HISTORY // 2)')
    expect(MAX_CHAT_TURNS).toBe(Math.max(1, Math.floor(MAX_HISTORY / 2)))
  })

  it('MAX_FEEDBACK_CHARS is MAX_TEKST uit core/algemene_feedback.py', () => {
    const match = backend('core', 'algemene_feedback.py').match(/^MAX_TEKST = (\d+)$/m)
    expect(match).not.toBeNull()
    expect(MAX_FEEDBACK_CHARS).toBe(Number(match[1]))
  })
})
