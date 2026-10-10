import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

// Top-level rules and @media blocks in file order: { media, selectors, body, index }.
function parseRules(text) {
  const rules = []
  let i = 0
  while (i < text.length) {
    const open = text.indexOf('{', i)
    if (open === -1) break
    const prelude = text.slice(i, open).trim()
    let depth = 1
    let j = open + 1
    while (depth > 0 && j < text.length) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') depth--
      j++
    }
    const inner = text.slice(open + 1, j - 1)
    if (prelude.startsWith('@media')) {
      for (const rule of parseRules(inner)) rules.push({ ...rule, media: prelude, index: rules.length })
    } else if (!prelude.startsWith('@')) {
      rules.push({ media: null, selectors: prelude.split(',').map(s => s.trim()), body: inner, index: rules.length })
    }
    i = j
  }
  return rules
}

const rules = parseRules(css)
const TOUCH = '@media (pointer: coarse), (max-width: 1024px)'
const touchRules = rules.filter(r => r.media === TOUCH)
const declares = (body, prop, value) => new RegExp(`(?:^|[;\\s])${prop}:\\s*${value.replace(/[()]/g, '\\$&')}\\s*(?:;|$)`).test(body)
// [declaration, value] for every property matching `props` (a regex source) in a rule body.
const sizes = (body, props) => body.matchAll(new RegExp(`(?:^|[;\\s])(?:${props}):\\s*([^;]+?)\\s*(?:;|$)`, 'g'))

// A size on a named target must stay at or above 44px: px, or rem at 16px. Keywords that do not cap
// the box pass; em, %, calc() and other tokens cannot be checked from the CSS, so they fail.
const REM_PX = 16
function expectAtLeastTouch(value, selector) {
  if (/^(auto|none|var\(--tap-min\))$/.test(value)) return
  const size = /^([\d.]+)(px|rem)$/.exec(value)
  expect(size, `${selector}: ${value} is not checkable, use px, rem or var(--tap-min)`).not.toBeNull()
  const px = Number(size[1]) * (size[2] === 'rem' ? REM_PX : 1)
  expect(px, `${selector}: ${value}`).toBeGreaterThanOrEqual(44)
}

// The targets the UX review measured too small on phones (#490), plus every button in
// the sidebar and the settings dialog.
const NAMED = [
  '.resend-btn', '.copy-btn', '.modal-close', '.modal-overlay-close', '.answer-feedback-btn',
  '.scroll-to-bottom-btn', '.message-continue', '.data-export-btn',
  '.chat-sidebar button', '.settings-modal button',
]

describe('tap target tokens', () => {
  it('defines the AA minimum and the touch minimum in :root', () => {
    const root = rules.find(r => r.selectors.includes(':root') && !r.media)
    expect(root.body).toMatch(/--tap-min-aa:\s*24px/)
    expect(root.body).toMatch(/--tap-min:\s*44px/)
  })
})

describe('AA baseline (WCAG 2.2 2.5.8)', () => {
  const baseline = rules.find(r => !r.media && r.selectors.some(s => s.includes('button')) &&
    declares(r.body, 'min-height', 'var(--tap-min-aa)'))

  it('gives every button, link and role=button 24x24 outside any media query', () => {
    expect(baseline).toBeDefined()
    const selector = baseline.selectors.join(',')
    for (const part of ['button', 'a[href]', '[role=button]']) expect(selector).toContain(part)
    expect(declares(baseline.body, 'min-width', 'var(--tap-min-aa)')).toBe(true)
  })

  it('leaves numbers in a sentence alone (inline exception)', () => {
    expect(baseline.selectors.join(',')).toMatch(/button:not\(\.citatie-getal\)/)
  })

  it('has zero specificity, so a component size still wins', () => {
    expect(baseline.selectors.join(',')).toMatch(/^:where\(/)
  })
})

describe('touch block', () => {
  it('uses the token instead of a literal 44px', () => {
    expect(touchRules.length).toBeGreaterThan(0)
    expect(touchRules.map(r => r.body).join(';')).not.toMatch(/\b44px/)
  })

  it.each(NAMED)('gives %s a 44x44 tap target', selector => {
    const own = touchRules.filter(r => r.selectors.includes(selector))
    expect(own.some(r => declares(r.body, 'min-width', 'var(--tap-min)'))).toBe(true)
    expect(own.some(r => declares(r.body, 'min-height', 'var(--tap-min)'))).toBe(true)
  })

  it.each(NAMED)('has no later rule that lowers %s again', selector => {
    const setters = touchRules.filter(r => r.selectors.includes(selector) && declares(r.body, 'min-height', 'var(--tap-min)'))
    const last = Math.max(...setters.map(r => r.index))
    const later = rules.filter(r => r.index > last && r.selectors.some(s => s.includes(selector)))
    for (const rule of later) {
      for (const [, value] of sizes(rule.body, '(?:min-)?(?:height|width)')) expectAtLeastTouch(value, selector)
    }
  })

  it.each(NAMED)('has no max-height or max-width under the token for %s anywhere', selector => {
    for (const rule of rules.filter(r => r.selectors.some(s => s.includes(selector)))) {
      for (const [, value] of sizes(rule.body, 'max-(?:height|width)')) expectAtLeastTouch(value, selector)
    }
  })
})

describe('size check helpers', () => {
  it.each(['1.5rem', '2em', '30px', '50%', 'calc(100% - 4px)', 'var(--tap-min-aa)'])('rejects %s', value => {
    expect(() => expectAtLeastTouch(value, '.x')).toThrow()
  })
  it.each(['44px', '2.75rem', '3rem', 'var(--tap-min)', 'auto', 'none'])('accepts %s', value => {
    expect(() => expectAtLeastTouch(value, '.x')).not.toThrow()
  })
})

describe('copy button on touch', () => {
  it('paints every child above the ::before frame, so "Gekopieerd" (#492) stays visible', () => {
    const children = touchRules.find(r => r.selectors.includes('.copy-btn > *'))
    expect(children).toBeDefined()
    expect(declares(children.body, 'position', 'relative')).toBe(true)
  })

  it('keeps space between the frame and the copied label', () => {
    const copied = touchRules.find(r => r.selectors.includes('.copy-btn[data-copied]'))
    expect(copied.body).toMatch(/padding-inline:[^;]*8px[^;]*var\(--tap-min\)[^;]*28px/)
  })
})

describe('icons stay small', () => {
  it('keeps the history action icons at 13px', () => {
    const icon = rules.find(r => !r.media && r.selectors.includes('.history-action-icon svg'))
    expect(icon.body).toMatch(/width:\s*13px/)
    expect(icon.body).toMatch(/height:\s*13px/)
  })

  it('draws the copy frame at 28px inside the larger touch box', () => {
    const frame = touchRules.find(r => r.selectors.includes('.copy-btn::before'))
    expect(frame.body).toMatch(/inset:[^;]*var\(--tap-min\)[^;]*28px/)
  })
})
