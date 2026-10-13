import { describe, it, expect } from 'vitest'
import { buildInstellingenLookup, matchKnownInstelling, instellingType, suggereerInstellingen } from '../instellingenMatch'

const INSTELLINGEN = [
  { naam: 'Hogeschool Utrecht', aliassen: ['HU'], domeinen: ['hu.nl'] },
  { naam: 'Vrije Universiteit Amsterdam', aliassen: ['VU', 'Vrije Universiteit'], domeinen: ['vu.nl'] },
  { naam: 'ROC Midden Nederland', aliassen: ['ROC MN'], domeinen: [] },
]

describe('matchKnownInstelling', () => {
  it('matches the canonical name case-insensitively', () => {
    expect(matchKnownInstelling(['hogeschool utrecht'], INSTELLINGEN)).toBe('Hogeschool Utrecht')
  })

  it('matches via an alias', () => {
    expect(matchKnownInstelling(['HU'], INSTELLINGEN)).toBe('Hogeschool Utrecht')
    expect(matchKnownInstelling(['vu'], INSTELLINGEN)).toBe('Vrije Universiteit Amsterdam')
  })

  it('matches via an email domain', () => {
    expect(matchKnownInstelling(['j.vermeer@hu.nl'], INSTELLINGEN)).toBe('Hogeschool Utrecht')
    expect(matchKnownInstelling(['hu.nl'], INSTELLINGEN)).toBe('Hogeschool Utrecht')
    expect(matchKnownInstelling(['bar@vu.nl'], INSTELLINGEN)).toBe('Vrije Universiteit Amsterdam')
  })

  it('matches via a SRAM short name', () => {
    expect(matchKnownInstelling(['hu'], INSTELLINGEN)).toBe('Hogeschool Utrecht')
  })

  it('matches when only one candidate matches', () => {
    expect(matchKnownInstelling(['not-an-instelling', 'ROC MN'], INSTELLINGEN)).toBe('ROC Midden Nederland')
  })

  it('returns null when nothing matches', () => {
    expect(matchKnownInstelling(['surf-ram'], INSTELLINGEN)).toBeNull()
    expect(matchKnownInstelling(['sram.surf.nl'], INSTELLINGEN)).toBeNull()
    expect(matchKnownInstelling(['someone@sram.surf.nl'], INSTELLINGEN)).toBeNull()
    expect(matchKnownInstelling([], INSTELLINGEN)).toBeNull()
    expect(matchKnownInstelling(null, INSTELLINGEN)).toBeNull()
    expect(matchKnownInstelling(['HU'], [])).toBeNull()
  })

  it('returns null without a list', () => {
    expect(matchKnownInstelling(['HU'], null)).toBeNull()
  })
})

describe('buildInstellingenLookup', () => {
  it('maps names and aliases to the canonical name', () => {
    const lookup = buildInstellingenLookup(INSTELLINGEN)
    expect(lookup.get('hu')).toBe('Hogeschool Utrecht')
    expect(lookup.get('hogeschool utrecht')).toBe('Hogeschool Utrecht')
    expect(lookup.get('nope')).toBeUndefined()
  })
})
// The sector decides which suggested questions the data can answer (#447).
describe('instellingType', () => {
  const TYPED = [
    { naam: 'Hogeschool Utrecht', type: 'hbo', aliassen: ['HU'] },
    { naam: 'ROC Midden Nederland', type: 'mbo', aliassen: [] },
  ]

  it('gives the type of a known name or alias, case-insensitively', () => {
    expect(instellingType('Hogeschool Utrecht', TYPED)).toBe('hbo')
    expect(instellingType(' hu ', TYPED)).toBe('hbo')
    expect(instellingType('roc midden nederland', TYPED)).toBe('mbo')
  })

  it('does not guess for free text, an empty profile or a list that has not loaded', () => {
    expect(instellingType('Hogeschool', TYPED)).toBeNull()
    expect(instellingType('', TYPED)).toBeNull()
    expect(instellingType('Hogeschool Utrecht', [])).toBeNull()
  })
})

// "Bedoel je …?" (#496 F04, #533): een zoekterm van meer woorden telt per woord, met typefouten.
describe('suggereerInstellingen', () => {
  const LIJST = [
    { naam: 'Hogeschool Utrecht', aliassen: ['HU'] },
    { naam: 'Hogeschool van Amsterdam', aliassen: ['HvA'] },
    { naam: 'Universiteit van Amsterdam', aliassen: ['UvA'] },
    { naam: 'Vrije Universiteit Amsterdam', aliassen: ['VU', 'Vrije Universiteit'] },
    { naam: 'Universiteit Leiden', aliassen: [] },
    { naam: 'Universiteit Utrecht', aliassen: ['UU'] },
    { naam: 'Erasmus Universiteit Rotterdam', aliassen: ['EUR'] },
  ]
  const namen = (term, max) => suggereerInstellingen(term, LIJST, max).map(i => i.naam)

  it('stelt bij "universiteit vam" de Amsterdamse universiteiten voor', () => {
    expect(namen('universiteit vam')).toEqual(['Universiteit van Amsterdam', 'Vrije Universiteit Amsterdam'])
  })

  it('verdraagt een typefout per woord, in elke volgorde', () => {
    expect(namen('universiteit amsterdm')).toEqual(['Universiteit van Amsterdam', 'Vrije Universiteit Amsterdam'])
    expect(namen('amsterdm universiteit').sort()).toEqual(['Universiteit van Amsterdam', 'Vrije Universiteit Amsterdam'])
    expect(namen('hogescool van utrect')).toEqual(['Hogeschool Utrecht'])
  })

  it('laat een vulwoord dat niet in de naam staat buiten beschouwing', () => {
    expect(namen('universiteit van leidn')).toEqual(['Universiteit Leiden'])
  })

  it('vraagt dat elk ander woord een woord van de naam raakt', () => {
    expect(namen('universiteit groningen')).toEqual([])
    expect(namen('xyz qwerty')).toEqual([])
    expect(namen('van de')).toEqual([])
  })

  it('noemt hoogstens max namen, de dichtstbijzijnde eerst', () => {
    expect(namen('universiteit amsterdm', 1)).toEqual(['Universiteit van Amsterdam'])
  })

  it('houdt een enkel woord tegen de naam en elk woord ervan, zoals voorheen', () => {
    expect(namen('Hogescool')).toEqual(['Hogeschool Utrecht', 'Hogeschool van Amsterdam'])
    expect(namen('hogeschool utrecth')).toEqual(['Hogeschool Utrecht'])
    expect(namen('Sorbonne')).toEqual([])
    expect(namen('hu')).toEqual([])
  })
})

describe('suggereerInstellingen bij een gelijkspel', () => {
  it('zet de naam die als geheel het dichtst bij de zoekterm ligt voorop', () => {
    const lijst = [
      { naam: 'Theologische Universiteit Utrecht', aliassen: [] },
      { naam: 'Universiteit Utrecht', aliassen: ['UU'] },
    ]
    expect(suggereerInstellingen('universiteit utrect', lijst).map(i => i.naam))
      .toEqual(['Universiteit Utrecht', 'Theologische Universiteit Utrecht'])
  })
})
