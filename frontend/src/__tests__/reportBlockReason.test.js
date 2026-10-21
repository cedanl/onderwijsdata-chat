// #648: waarom "Genereer rapport" nu niet kan starten, als één korte Nederlandse reden; null als het kan.
import { describe, it, expect } from 'vitest'
import { reportBlockReason } from '../reportBlockReason'

const KLAAR = { connected: true, open: false, reporting: false, resetting: false }
const reden = staat => reportBlockReason({ ...KLAAR, ...staat })

describe('reportBlockReason (#648)', () => {
  it('geeft null als het rapport kan starten', () => {
    expect(reportBlockReason(KLAAR)).toBeNull()
  })

  it.each([
    ['een lopend antwoord', { open: true }, 'open', 'Wacht tot het antwoord klaar is'],
    ['een rapport dat al wordt gemaakt', { reporting: true }, 'reporting', 'Er wordt al een rapport gemaakt'],
    ['een nieuw gesprek dat start', { resetting: true }, 'resetting', 'Even wachten: het nieuwe gesprek wordt gestart'],
  ])('noemt %s', (_naam, staat, key, tekst) => {
    expect(reden(staat)).toEqual({ key, text: tekst })
  })

  it('noemt de verbinding als die er niet is', () => {
    const { key, text } = reden({ connected: false })
    expect(key).toBe('offline')
    expect(text).toMatch(/^Geen verbinding/)
    expect(text).toContain('verbinding')
  })

  it('noemt eerst het lopende rapport, dan het antwoord, dan het nieuwe gesprek, dan de verbinding', () => {
    let staat = { connected: false, open: true, reporting: true, resetting: true }
    const volgorde = []
    for (const veld of ['reporting', 'open', 'resetting', 'connected']) {
      volgorde.push(reden(staat).key)
      staat = { ...staat, [veld]: veld === 'connected' }
    }
    expect(volgorde).toEqual(['reporting', 'open', 'resetting', 'offline'])
    expect(reden(staat)).toBeNull()
  })
})
