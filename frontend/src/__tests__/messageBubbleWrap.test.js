// #606: jsdom does no layout, so this pins the CSS that keeps a long word inside the chat bubble.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
// Every innermost rule with its selectors and body, rules inside @media blocks included, in file order. Selectors
// split at top-level commas only, so `:is(th, td)` stays whole.
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, prelude, body], index) => ({
  selectors: prelude.split(/,(?![^()]*\))/).map(s => s.trim()), body, index,
}))
// A selector whose last compound is the bubble itself (also as the assistant or error bubble), not a child of it.
const onBubble = selector => /\.message-bubble(?:-assistant|-error)?(?![\w-])[^\s>+~]*$/.test(selector)

describe('long word in a chat bubble (#606)', () => {
  const base = rules.find(r => r.selectors.includes('.message-bubble'))

  it('lets the bubble break a word anywhere, so its min-content width drops too', () => {
    expect(base.body).toMatch(/(?:^|[;\s])overflow-wrap:\s*anywhere\s*(?:;|$)/)
  })

  it('has no later rule on the bubble that undoes it', () => {
    const later = rules.filter(r => r.index > base.index && r.selectors.some(onBubble))
    expect(later.length).toBeGreaterThan(0)
    for (const rule of later) {
      expect(rule.body, rule.selectors.join(', ')).not.toMatch(/(?:overflow-wrap|word-wrap):\s*(?!anywhere)/)
      expect(rule.body, rule.selectors.join(', ')).not.toMatch(/white-space:\s*(?:nowrap|pre)\s*(?:;|$)/)
      expect(rule.body, rule.selectors.join(', ')).not.toMatch(/word-break:\s*keep-all/)
    }
  })

  // A table wider than the bubble would squeeze its columns below a word and break a figure mid-number.
  it('keeps the old wrapping in table cells, so a figure in a table never breaks', () => {
    const cells = rules.filter(r => r.index > base.index && r.selectors.includes('.message-bubble :is(th, td)'))
    expect(cells.some(r => /(?:^|[;\s])overflow-wrap:\s*normal\s*(?:;|$)/.test(r.body))).toBe(true)
  })

  it('recognises the bubble selectors it guards', () => {
    expect(onBubble('.message.user .message-bubble')).toBe(true)
    expect(onBubble('.message-bubble-assistant')).toBe(true)
    expect(onBubble('html.dark .message-bubble-error')).toBe(true)
    expect(onBubble('.message-bubble p')).toBe(false)
    expect(onBubble('.message-bubble-assistant .copy-btn-message')).toBe(false)
  })
})
