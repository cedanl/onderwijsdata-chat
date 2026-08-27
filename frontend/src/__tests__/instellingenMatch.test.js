import { describe, it, expect } from 'vitest'
import { buildInstellingenLookup, matchKnownInstelling } from '../instellingenMatch'

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