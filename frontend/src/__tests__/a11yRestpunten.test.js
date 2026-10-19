// #517: a11y-restpunten uit de her-audit van 10 okt (A2, A4, A5). jsdom rekent geen
// layout, dus deze tests leggen de CSS-afspraken vast; de maten zelf zijn bij de
// wijziging gemeten (zie de MR).
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

describe('a11y-restpunten (#517)', () => {
  it('A2: het citaatgetal heeft een klikvlak van minstens 24 px hoog', () => {
    const hitArea = css.match(/\.citatie-getal::before\s*{[^}]*}/s)?.[0]
    expect(hitArea).toBeDefined()
    expect(hitArea).toContain('height: 24px')
    expect(hitArea).toContain('width: max(100%, 24px)')
  })

  it('A4: de focusring is een eigen token, geen browserdefault', () => {
    expect(css).toMatch(/:focus-visible\s*{\s*outline: 2px solid var\(--focus-ring\)/)
    expect(css).toContain('--focus-ring:')
  })

  it('A4: geen focusregel gebruikt de te lichte --blue-400 (2,5:1 op wit)', () => {
    const regels = [...css.matchAll(/([^{}]+){([^{}]*)}/g)]
    const focusRegels = regels.filter(([, kiezer]) => kiezer.includes(':focus'))
    expect(focusRegels.length).toBeGreaterThan(5)
    for (const [, kiezer, body] of focusRegels) {
      expect(body, kiezer.trim()).not.toContain('--blue-400')
    }
  })

  it('A5: reduced motion zet transities en animaties uit', () => {
    const blok = css.match(/@media \(prefers-reduced-motion: reduce\)\s*{[\s\S]*?\n}/)?.[0]
    expect(blok).toBeDefined()
    expect(blok).toContain('transition-duration: .01ms !important')
    expect(blok).toContain('animation-duration: .01ms !important')
  })

  it('A5: laad- en activiteitsindicatoren blijven rustig doorlopen bij reduced motion', () => {
    const blok = css.match(/@media \(prefers-reduced-motion: reduce\)\s*{[\s\S]*?\n}/)?.[0]
    const regel = blok.match(/\n {2}\.spinner,[^{]*{[^}]*}/)?.[0]
    expect(regel).toBeDefined()
    for (const kiezer of ['.spinner', '.ai-typing span', '.ws-dot', '.tool-step-dot:not(.done)']) {
      expect(regel).toContain(kiezer)
    }
    expect(regel).toContain('animation-duration: 2.4s !important')
    expect(regel).toContain('animation-iteration-count: infinite !important')
  })
})

// #598: the 24 px hit area of #517 is the floor; on touch the figure gets 44 px (WCAG 2.5.5).
describe('citaatgetal op touch (#598)', () => {
  const touchBlok = css.slice(css.indexOf('@media (pointer: coarse), (max-width: 1024px)'))
  const hitArea = touchBlok.match(/\.citatie-getal::before\s*{[^}]*}/s)?.[0]

  it('het klikvlak is op touch en smalle schermen 44 px hoog', () => {
    expect(hitArea).toBeDefined()
    expect(hitArea).toContain('height: var(--tap-min)')
    expect(hitArea).toContain('width: max(100%, var(--tap-min))')
  })

  it('de zichtbare regel verandert niet: het vlak blijft een onzichtbare ::before', () => {
    expect(touchBlok).not.toMatch(/\.citatie-getal\s*{[^}]*(padding|min-height|line-height)/s)
  })
})

// #611: the hit area of a later figure (its ::before) covered the lower half of the figure above it in a list or
// table. The figure's own box (::after) now lies above every hit area, and below the open explanation and the copy
// button. jsdom does no hit testing; tests/e2e/mobiel-tikvlakken.spec.js measures it in the browser.
describe('citaatgetal tussen gestapelde getallen (#611)', () => {
  const zonderCommentaar = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const escape = tekst => tekst.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regels = kiezer => [...zonderCommentaar.matchAll(new RegExp(`(?:^|[},])\\s*${escape(kiezer)}\\s*{([^}]*)}`, 'gm'))]
    .map(m => m[1])
  const zIndex = body => body.match(/z-index:\s*(-?\d+|auto)/)?.[1]
  const [eigenVak] = regels('.citatie-getal::after')

  it('het eigen vak is een onzichtbare laag precies over de knop, rand onderaan inbegrepen', () => {
    expect(eigenVak).toBeDefined()
    expect(eigenVak).toMatch(/content:\s*''/)
    expect(eigenVak).toMatch(/position:\s*absolute/)
    expect(eigenVak).toMatch(/inset:\s*0 0 -1px/)
    expect(eigenVak).not.toMatch(/background|border|transform/)
  })

  it('ligt boven de klikvlakken van andere getallen: die houden z-index auto', () => {
    expect(Number(zIndex(eigenVak))).toBeGreaterThan(0)
    for (const vlak of regels('.citatie-getal::before')) expect(zIndex(vlak) ?? 'auto').toBe('auto')
  })

  it('de knop zelf maakt geen stapelcontext, dus vak en vlakken van alle getallen liggen in dezelfde', () => {
    for (const knop of regels('.citatie-getal')) {
      expect(knop).toMatch(/position:\s*relative/)
      expect(zIndex(knop)).toBeUndefined()
    }
    for (const omhulsel of regels('.citatie')) expect(zIndex(omhulsel)).toBeUndefined()
  })

  it('blijft onder een open uitleg en onder de kopieerknop', () => {
    const [uitleg] = regels('.citatie-uitleg')
    const [kopieer] = regels('.copy-btn')
    expect(Number(zIndex(eigenVak))).toBeLessThan(Number(zIndex(uitleg)))
    expect(Number(zIndex(eigenVak))).toBeLessThan(Number(zIndex(kopieer)))
  })
})
