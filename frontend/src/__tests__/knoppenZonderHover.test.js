// #773: kopiëren, opnieuw sturen en CSV per grafiek bestonden alleen bij muis-hover. jsdom rekent
// geen media queries en geen :hover, dus deze tests leggen de CSS-afspraken vast; het beeld op 390 px
// en de toetsenbordfocus zijn bij de wijziging gemeten (zie de MR).
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

// Zonder commentaar: anders hoort de tekst erboven bij de kiezer van de regel eronder.
const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

const regels = [...css.matchAll(/([^{}]+){([^{}]*)}/g)].map(([, kiezer, body]) => ({ kiezer: kiezer.trim(), body }))
const zichtbaar = body => /opacity:\s*1\b/.test(body)

// De knop en de container waarin hij met de muis verschijnt.
const KNOPPEN = [
  ['.message.user', '.resend-btn'],
  ['.plotly-figure-wrap', '.csv-download-btn'],
  ['.message-bubble-assistant', '.copy-btn-message'],
  ['.message.user .message-bubble', '.copy-btn-message'],
  ['.code-block-wrap', '.copy-btn-code'],
]

const ZONDER_HOVER = '@media (hover: none), (max-width: 768px)'

function zonderHoverBlokken() {
  const blokken = []
  let i = css.indexOf(ZONDER_HOVER)
  while (i !== -1) {
    const open = css.indexOf('{', i)
    let diepte = 0
    let eind = open
    for (; eind < css.length; eind++) {
      if (css[eind] === '{') diepte++
      if (css[eind] === '}' && --diepte === 0) break
    }
    blokken.push({ start: i, tekst: css.slice(open + 1, eind) })
    i = css.indexOf(ZONDER_HOVER, eind)
  }
  return blokken
}

describe('knoppen die niet alleen bij hover bestaan (#773)', () => {
  it.each(KNOPPEN)('%s %s verschijnt ook als er focus in de container staat', (container, knop) => {
    const regel = regels.find(r => r.kiezer.split(',').map(s => s.trim()).includes(`${container}:focus-within ${knop}`))
    expect(regel, `${container}:focus-within ${knop}`).toBeDefined()
    expect(zichtbaar(regel.body)).toBe(true)
  })

  it.each(['.resend-btn', '.csv-download-btn', '.copy-btn'])('%s staat altijd zichtbaar zonder hover en in een smal venster', knop => {
    const blok = zonderHoverBlokken().find(b => [...b.tekst.matchAll(/([^{}]+){([^{}]*)}/g)]
      .some(([, kiezer, body]) => kiezer.split(',').map(s => s.trim()).includes(knop) && zichtbaar(body)))
    expect(blok, knop).toBeDefined()
    // Later in het bestand dan de basisregel met opacity 0, anders wint die bij gelijke specificiteit.
    const basis = css.search(new RegExp(`\\n\\${knop}\\s*{[^}]*opacity:\\s*0`))
    expect(basis).toBeGreaterThan(-1)
    expect(blok.start).toBeGreaterThan(basis)
  })

  it('de vaste kopieerknop houdt de eerste regel van een vraag vrij', () => {
    const regel = zonderHoverBlokken().flatMap(b => [...b.tekst.matchAll(/([^{}]+){([^{}]*)}/g)])
      .find(([, kiezer]) => kiezer.trim() === '.message.user .message-bubble::before')
    expect(regel).toBeDefined()
    expect(regel[2]).toMatch(/float:\s*right/)
    expect(regel[2]).toMatch(/height:\s*1lh/)
  })

  it('met een muis op een breed scherm blijven de knoppen verborgen tot hover', () => {
    for (const knop of ['.resend-btn', '.csv-download-btn', '.copy-btn']) {
      const basis = regels.find(r => r.kiezer === knop)
      expect(basis?.body, knop).toMatch(/opacity:\s*0\b/)
    }
  })
})
