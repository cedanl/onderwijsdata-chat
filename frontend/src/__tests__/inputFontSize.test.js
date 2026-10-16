// #590: Safari on an iPhone zooms the page in when a field under 16px gets focus. The root is 15px, so
// 1rem is 15px and does not help: on a phone every field needs an explicit px size of at least 16.
// jsdom does no layout, so this pins the CSS agreement (same parsing approach as tapTargets.test.js).
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
const PHONE_WIDTH = 390
const MIN_PX = 16

// Can this media query hold on a 390px touch phone? A feature the check does not know counts as yes
// (dark mode, reduced motion), so an override cannot hide behind it.
function appliesOnPhone(media) {
  if (!media) return true
  return media.replace(/^@media\s*/, '').split(',').some(query =>
    [...query.matchAll(/\(([^)]+)\)/g)].every(([, feature]) => {
      const [name, value = ''] = feature.split(':').map(s => s.trim())
      if (name === 'max-width') return parseFloat(value) >= PHONE_WIDTH
      if (name === 'min-width') return parseFloat(value) <= PHONE_WIDTH
      if (name === 'pointer') return value === 'coarse'
      if (name === 'hover') return value === 'none'
      return true
    }))
}

// [ids, classes + attributes + pseudo-classes, types]; :where() counts zero, :not()/:is()/:has() count their argument.
function specificity(selector) {
  const s = selector.replace(/:where\((?:[^()]|\([^()]*\))*\)/g, '').replace(/:(?:not|is|has)(?=\()/g, '')
  return [
    (s.match(/#[\w-]+/g) || []).length,
    (s.match(/\.[\w-]+|\[[^\]]*\]|:[\w-]+/g) || []).length,
    (s.match(/(?:^|[\s>+~(])[a-z][\w-]*/gi) || []).length,
  ]
}
const compare = (a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]

// Does this selector style the field element itself (pseudo-classes allowed, pseudo-elements not)?
function hitsField(selector, field) {
  if (selector.includes('::')) return false
  return selector.replace(/(?::[\w-]+(?:\([^)]*\))?)+$/, '').endsWith(field)
}

// The value of the last declaration of `prop` in a rule body, or undefined.
function lastValue(body, prop) {
  const values = [...body.matchAll(new RegExp(`(?:^|[;\\s{])${prop}:\\s*([^;]+?)\\s*(?:;|$)`, 'g'))]
  return values.at(-1)?.[1]
}
// font-size, or `font` when the shorthand comes after it in the same body (it resets the size).
function fontValue(body) {
  const decls = [...body.matchAll(/(?:^|[;\s{])(font|font-size):\s*([^;]+?)\s*(?:;|$)/g)]
  const last = decls.at(-1)
  return last && { prop: last[1], value: last[2] }
}

// The rule whose `prop` a 390px touch phone uses for the element: highest specificity, then the last in the file.
function winner(selectors, read) {
  const candidates = []
  for (const rule of rules.filter(r => appliesOnPhone(r.media) && read(r.body))) {
    for (const sel of rule.selectors.filter(s => selectors.some(field => hitsField(s, field)))) {
      candidates.push({ rule, spec: specificity(sel) })
    }
  }
  candidates.sort((a, b) => compare(a.spec, b.spec) || a.rule.index - b.rule.index)
  return candidates.at(-1)?.rule
}

// Each entry: the selectors that style one field element on a phone.
const FIELDS = [
  ['.chat-input'],
  ['.login-input'],
  ['.instelling-search'],
  ['.history-search'],
  ['.dc-textarea'],
  ['.answer-feedback-form textarea'],
  ['.feedback-question textarea'],
  ['.model-picker select'],
  // Inline rename in the history list, and of a report title (it also carries .wb-viewer-title).
  ['.title-edit-input'],
  ['.wb-viewer-title', '.title-edit-input'],
  // Already 16px everywhere (#562); kept in the list so it does not drop again.
  ['.wb-gallery-search-input'],
]

describe('form fields on a phone (#590)', () => {
  it.each(FIELDS.map(f => [f.join(' + '), f]))('gives %s a font-size of at least 16px, in px', (_, selectors) => {
    const rule = winner(selectors, fontValue)
    expect(rule, `no font-size for ${selectors}`).toBeDefined()
    const { prop, value } = fontValue(rule.body)
    expect(prop, `${selectors}: the winning rule sets the font shorthand, set font-size in px`).toBe('font-size')
    const px = /^([\d.]+)px$/.exec(value)
    expect(px, `${selectors}: ${value} (rem and em follow the 15px root)`).not.toBeNull()
    expect(Number(px[1])).toBeGreaterThanOrEqual(MIN_PX)
  })

  it('sets no field size in rem or em inside a phone media block', () => {
    const fields = FIELDS.flat()
    const phoneRules = rules.filter(r => r.media && appliesOnPhone(r.media))
    for (const rule of phoneRules) {
      if (!rule.selectors.some(s => fields.some(field => hitsField(s, field)))) continue
      const size = lastValue(rule.body, 'font-size')
      if (size) expect(size, `${rule.selectors.join(', ')} in ${rule.media}`).not.toMatch(/r?em$/)
    }
  })

  // 15px x 1.6 was 24px; 16px x 1.6 would add 1.6px to the compact input area.
  it('keeps one row of the chat input at 24px, as before (#527)', () => {
    const size = parseFloat(fontValue(winner(['.chat-input'], fontValue).body).value)
    const lineHeight = Number(lastValue(winner(['.chat-input'], b => lastValue(b, 'line-height')).body, 'line-height'))
    expect(size, 'font-size in px').toBeGreaterThanOrEqual(MIN_PX)
    expect(size * lineHeight).toBeLessThanOrEqual(24)
  })
})

describe('desktop keeps its sizes', () => {
  const desktop = rules.filter(r => !r.media)
  it.each([['.chat-input', '.95rem'], ['.history-search', '.8rem'], ['.login-input', '.9rem']])(
    'leaves %s at %s outside the phone block', (field, size) => {
      const own = desktop.filter(r => r.selectors.includes(field) && lastValue(r.body, 'font-size'))
      expect(lastValue(own.at(-1).body, 'font-size')).toBe(size)
    })
})

describe('checks of the parser itself', () => {
  it.each([
    ['@media (pointer: coarse), (max-width: 1024px)', true],
    ['@media (max-width: 640px)', true],
    ['@media(max-width:640px)', true],
    ['@media (pointer: coarse) and (max-width: 1024px)', true],
    ['@media (min-width: 1025px)', false],
    ['@media (max-width: 360px)', false],
    ['@media (pointer: fine) and (hover: hover)', false],
  ])('%s applies on a phone: %s', (media, expected) => {
    expect(appliesOnPhone(media)).toBe(expected)
  })

  it('ranks a more specific selector above a later, plainer one', () => {
    expect(compare(specificity('.answer-feedback-form textarea'), specificity('.answer-feedback-form'))).toBeGreaterThan(0)
    expect(compare(specificity(':where(.x) textarea'), specificity('textarea'))).toBe(0)
  })

  it('matches the field, not a longer class or a pseudo-element', () => {
    expect(hitsField('.chat-input:focus', '.chat-input')).toBe(true)
    expect(hitsField('.wb-viewer-title.title-edit-input', '.title-edit-input')).toBe(true)
    expect(hitsField('.chat-input-wrap', '.chat-input')).toBe(false)
    expect(hitsField('.chat-input::placeholder', '.chat-input')).toBe(false)
  })
})
