// #798: op 320 px scrolde de pagina horizontaal (WCAG 1.4.10): op /chat door de navigatiebalk, op /dashboards (en
// /rapporten met rapporten) door een kaart van minstens 280 px. jsdom rekent geen media queries en geen layout, dus
// deze test legt de CSS-afspraken vast; de breedtes 320–390 px zijn bij de wijziging gemeten (zie de MR).
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
const SMAL = '@media (max-width: 359px)'

function blok(kop) {
  const start = css.indexOf(kop)
  if (start === -1) return null
  const open = css.indexOf('{', start)
  let diepte = 0
  for (let eind = open; eind < css.length; eind++) {
    if (css[eind] === '{') diepte++
    if (css[eind] === '}' && --diepte === 0) return css.slice(open + 1, eind)
  }
  return null
}

describe('het woordmerk in een smalle navigatiebalk', () => {
  it('verdwijnt onder 360 px alleen uit beeld, niet voor de schermlezer', () => {
    const regel = /\.navbar \.navbar-name\s*{([^}]*)}/.exec(blok(SMAL) ?? '')
    expect(regel).not.toBeNull()
    expect(regel[1]).toMatch(/clip-path:\s*inset\(50%\)/)
    expect(regel[1]).toMatch(/position:\s*absolute/)
    expect(regel[1]).not.toMatch(/display:\s*none|visibility:\s*hidden/)
  })

  it('geldt alleen in de navigatiebalk: de voettekst van Home houdt het woordmerk', () => {
    const smal = blok(SMAL) ?? ''
    const kiezers = [...smal.matchAll(/([^{}]+){/g)].map(([, kiezer]) => kiezer.trim())
    expect(kiezers).toEqual(['.navbar .navbar-name'])
  })
})

describe('de kaarten van de galerij', () => {
  it('zijn minstens 280 px, maar nooit breder dan de galerij', () => {
    const regel = /(?:^|})\s*\.wb-grid\s*{([^}]*)}/.exec(css)
    expect(regel).not.toBeNull()
    expect(regel[1]).toMatch(/grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(min\(280px,\s*100%\),\s*1fr\)\)/)
  })
})
