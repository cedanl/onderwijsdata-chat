// #530: de markering van een verwijderd open gesprek, los van de pagina.
import { describe, it, expect } from 'vitest'
import { isVerwijderd, markeerVerwijderd } from '../verwijderdGesprek'

const vraag = { role: 'user', content: 'vraag', done: true }
const antwoord = { role: 'assistant', content: 'antwoord', done: true }

describe('verwijderd gesprek (#530)', () => {
  it('herkent het gesprek zoals het was bij het verwijderen', () => {
    const m = markeerVerwijderd('c1', [vraag, antwoord])
    expect(isVerwijderd(m, 'c1', [vraag, antwoord])).toBe(true)
  })

  it('ziet een antwoord dat later afrondt nog als hetzelfde gesprek', () => {
    const m = markeerVerwijderd('c1', [vraag, { ...antwoord, content: 'half', done: false }])
    expect(isVerwijderd(m, 'c1', [vraag, antwoord])).toBe(true)
  })

  it('laat los bij een nieuwe vraag', () => {
    const m = markeerVerwijderd('c1', [vraag, antwoord])
    expect(isVerwijderd(m, 'c1', [vraag, antwoord, { ...vraag, content: 'nog een' }])).toBe(false)
  })

  it('geldt alleen voor hetzelfde gesprek, ook als het id een getal is', () => {
    const m = markeerVerwijderd(7, [vraag])
    expect(isVerwijderd(m, '7', [vraag])).toBe(true)
    expect(isVerwijderd(m, 'c2', [vraag])).toBe(false)
  })

  it('blokkeert niets zonder markering', () => {
    expect(isVerwijderd(null, 'c1', [vraag])).toBe(false)
  })
})
