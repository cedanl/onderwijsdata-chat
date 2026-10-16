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
