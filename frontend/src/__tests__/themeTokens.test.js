import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(__dirname, '..')
const css = readFileSync(join(SRC, 'styles.css'), 'utf8')

function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    if (e.name === '__tests__') return []
    const path = join(dir, e.name)
    return e.isDirectory() ? sources(path) : /\.(css|jsx?)$/.test(e.name) ? [path] : []
  })
}

describe('theme tokens', () => {
  it('keeps --on-color white in the dark theme', () => {
    expect([...css.matchAll(/--on-color\s*:\s*([^;]+);/g)].map(m => m[1].trim())).toEqual(['#FFFFFF'])
  })

  // The dark theme turns --white into a dark surface colour; as text colour it is only right
  // where the background flips along with it.
  it('uses --white as text colour only on surfaces that flip with it', () => {
    const rules = [...css.matchAll(/([^{}]+)\{[^}]*[^-]color:\s*var\(--white\)/g)].map(m => m[1].trim())
    expect(rules).toEqual(['.toast.info'])
  })

  // Both stay below 4.5:1 as text (gray-400 on white, blue-600 on the dark background).
  it('uses the text tokens instead of --gray-400 and --blue-600 for text', () => {
    const offenders = sources(SRC).flatMap(file =>
      [...readFileSync(file, 'utf8').matchAll(/(?<![\w-])color:\s*'?var\(--(gray-400|blue-600)\)/g)]
        .map(m => `${file.split('/src/')[1]}: ${m[1]}`))
    expect(offenders).toEqual([])
  })
})

// #1174: de rand die een invoerveld herkenbaar maakt vraagt 3:1 tegen zijn achtergrond (WCAG 1.4.11). --gray-200
// haalde 1.24:1 (licht) en 1.37:1 (donker); --gray-500 is een Npuls-neutraal token met ruime marge.
describe('rand van invoervelden', () => {
  const VELDEN = ['.login-input', '.instelling-search', '.history-search', '.chat-input-wrap', '.onderzoeksvraag-veld']
  const blok = kop => css.slice(css.indexOf(kop)).match(/\{([^}]*)\}/)[1]
  const token = (tekst, naam) => tekst.match(new RegExp(`${naam}:\\s*(#[0-9A-Fa-f]{6})`))[1]
  const luminantie = hex => {
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const verhouding = (a, b) => {
    const [licht, donker] = [luminantie(a), luminantie(b)].sort((x, y) => y - x)
    return (licht + 0.05) / (donker + 0.05)
  }

  it.each(VELDEN)('%s tekent zijn rand met --gray-500', veld => {
    const regel = css.match(new RegExp(`\\n${veld.replace('.', '\\.')} \\{([^}]*)\\}`))[1]
    expect(regel).toMatch(/border:\s*[\d.]+px solid var\(--gray-500\)/)
  })

  it.each([
    ['licht', ':root {'],
    ['donker', 'html.dark {'],
  ])('--gray-500 haalt 3:1 tegen --white in het %s thema', (_, kop) => {
    const tokens = blok(kop)
    expect(verhouding(token(tokens, '--gray-500'), token(tokens, '--white'))).toBeGreaterThanOrEqual(3)
  })
})

