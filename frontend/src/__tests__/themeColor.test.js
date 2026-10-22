// @vitest-environment jsdom
// #672: de statusbalk van een geïnstalleerde app krijgt de kleur van de navbar in het thema dat de gebruiker koos.
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { applyMode, THEME_COLOR } from '../theme'

const kleuren = () => [...document.querySelectorAll('meta[name="theme-color"]')].map(m => m.getAttribute('content'))

beforeEach(() => {
  document.head.innerHTML = `
    <meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
    <meta name="theme-color" content="#1A1F2E" media="(prefers-color-scheme: dark)">`
  window.matchMedia = q => ({ matches: false, media: q })
})

describe('theme-color', () => {
  it('geeft bij een gekozen donker thema beide metas de donkere navbarkleur, ook op een licht apparaat', () => {
    applyMode('dark')
    expect(kleuren()).toEqual([THEME_COLOR.dark, THEME_COLOR.dark])
  })

  it('geeft bij een gekozen licht thema beide metas de lichte kleur, ook op een donker apparaat', () => {
    window.matchMedia = q => ({ matches: q.includes('dark'), media: q })
    applyMode('light')
    expect(kleuren()).toEqual([THEME_COLOR.light, THEME_COLOR.light])
  })

  it('zet in systeemmodus elke meta terug op zijn eigen kleur, zodat het apparaat beslist', () => {
    applyMode('dark')
    applyMode('system')
    expect(kleuren()).toEqual([THEME_COLOR.light, THEME_COLOR.dark])
  })

  it('gebruikt dezelfde donkere kleur als de navbar in styles.css', () => {
    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
    expect(css.match(/html\.dark \{[^}]*--white:\s*(#[0-9A-Fa-f]{6})/s)[1].toUpperCase()).toBe(THEME_COLOR.dark)
    const html = readFileSync(join(__dirname, '..', '..', 'index.html'), 'utf8')
    expect(html).toContain(`content="${THEME_COLOR.dark}" media="(prefers-color-scheme: dark)"`)
  })
})
