// #493: verwijderen krijgt acht seconden bedenktijd; pas daarna gaat de DELETE.
import { describe, it, expect, vi } from 'vitest'
import { uitgesteldeVerwijdering, terugInLijst, UITSTEL_MS } from '../verwijderenMetUitstel'

const conv = (id) => ({ id, title: `gesprek ${id}`, timestamp: 1 })

function maak() {
  vi.useFakeTimers()
  const voerUit = vi.fn()
  const v = uitgesteldeVerwijdering({ voerUit })
  return { v, voerUit }
}

describe('uitgesteldeVerwijdering', () => {
  it('voert de verwijdering pas uit als de wachttijd om is', () => {
    const { v, voerUit } = maak()
    v.plan(conv('a'), 0)
    expect(v.lopend.id).toBe('a')
    vi.advanceTimersByTime(UITSTEL_MS - 1)
    expect(voerUit).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(voerUit).toHaveBeenCalledWith(conv('a'))
    expect(v.lopend).toBeNull()
    vi.useRealTimers()
  })

  it('ongedaan maken geeft het gesprek met zijn plaats terug en laat de server met rust', () => {
    const { v, voerUit } = maak()
    v.plan(conv('a'), 2)
    expect(v.ongedaan()).toEqual({ conv: conv('a'), index: 2 })
    vi.advanceTimersByTime(UITSTEL_MS * 2)
    expect(voerUit).not.toHaveBeenCalled()
    expect(v.ongedaan()).toBeNull()
    vi.useRealTimers()
  })

  it('een tweede verwijdering voert de eerste direct uit', () => {
    const { v, voerUit } = maak()
    v.plan(conv('a'), 0)
    v.plan(conv('b'), 0)
    expect(voerUit).toHaveBeenCalledTimes(1)
    expect(voerUit).toHaveBeenCalledWith(conv('a'))
    expect(v.lopend.id).toBe('b')
    vi.useRealTimers()
  })

  it('"nu" voert een geplande verwijdering meteen uit, bijvoorbeeld bij het sluiten van de tab', () => {
    const { v, voerUit } = maak()
    expect(v.nu()).toBeNull()
    v.plan(conv('a'), 0)
    expect(v.nu()).toEqual(conv('a'))
    expect(voerUit).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(UITSTEL_MS)
    expect(voerUit).toHaveBeenCalledOnce()
    vi.useRealTimers()
  })
})

describe('terugInLijst', () => {
  it('zet het gesprek terug op zijn oude plaats, ook als de lijst intussen korter is', () => {
    const lijst = [conv('a'), conv('c')]
    expect(terugInLijst(lijst, conv('b'), 1).map(c => c.id)).toEqual(['a', 'b', 'c'])
    expect(terugInLijst(lijst, conv('z'), 9).map(c => c.id)).toEqual(['a', 'c', 'z'])
    expect(terugInLijst([conv('b')], conv('b'), 0).map(c => c.id)).toEqual(['b'])
  })
})
