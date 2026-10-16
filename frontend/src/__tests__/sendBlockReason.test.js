// #585 (mobiel B10), eerder #241: waarom een vraag nu niet weg kan, als één korte reden.
import { describe, it, expect } from 'vitest'
import { chatBlockReason, refusalReason, sendBlockReason } from '../sendBlockReason'

const KLAAR = { text: 'Hoeveel mbo-studenten?', over: false, connected: true, busy: false, resetting: false, reporting: false, atContextLimit: false }
const tekst = staat => sendBlockReason({ ...KLAAR, ...staat })?.text ?? null

describe('sendBlockReason (#585)', () => {
  it('geeft null als de vraag weg kan', () => {
    expect(sendBlockReason(KLAAR)).toBeNull()
  })

  it.each([
    ['een leeg concept', { text: '' }, 'Typ eerst een vraag'],
    ['een concept van alleen spaties', { text: '  \n ' }, 'Typ eerst een vraag'],
    ['geen verbinding', { connected: false }, 'Geen verbinding'],
    ['een te lang bericht', { over: true }, 'Bericht te lang'],
    ['een lopend antwoord', { busy: true }, 'Even wachten: het vorige antwoord is nog bezig'],
    ['een rapport dat wordt gemaakt', { reporting: true }, 'Even wachten: er wordt een rapport gemaakt'],
    ['een nieuw gesprek dat start', { resetting: true }, 'Even wachten: het nieuwe gesprek wordt gestart'],
    ['een volle chat', { atContextLimit: true }, 'Chat is vol: begin een nieuw gesprek'],
  ])('noemt %s', (_naam, staat, verwacht) => {
    expect(tekst(staat)).toBe(verwacht)
  })

  it('noemt eerst wat aan de chat ligt, dan wat aan het concept', () => {
    const alles = { text: '', over: true, connected: false, busy: true, resetting: true, reporting: true, atContextLimit: true }
    const volgorde = []
    let staat = { ...alles }
    for (const veld of ['busy', 'reporting', 'resetting', 'connected', 'atContextLimit', 'text', 'over']) {
      volgorde.push(sendBlockReason(staat).key)
      staat = { ...staat, [veld]: KLAAR[veld] }
    }
    expect(volgorde).toEqual(['busy', 'reporting', 'resetting', 'offline', 'full', 'empty', 'over'])
    expect(sendBlockReason(staat)).toBeNull()
  })

  it('laat elke tijdelijke reden beginnen met "Even wachten:"', () => {
    for (const staat of [{ busy: true }, { reporting: true }, { resetting: true }]) {
      expect(tekst(staat)).toMatch(/^Even wachten: /)
    }
  })

  it('verdraagt een ontbrekend concept', () => {
    expect(sendBlockReason({ connected: true })?.key).toBe('empty')
  })
})

describe('chatBlockReason en refusalReason (#585)', () => {
  it('kijkt niet naar het concept', () => {
    expect(chatBlockReason({ connected: true })).toBeNull()
    expect(chatBlockReason({ connected: false }).text).toBe('Geen verbinding')
  })

  it('geeft bij een geweigerde vraag de reden van de chat, of een algemene tijdelijke', () => {
    expect(refusalReason({ connected: true, resetting: true }).text).toBe('Even wachten: het nieuwe gesprek wordt gestart')
    expect(refusalReason({ connected: true })).toEqual({ key: 'refused', text: 'Even wachten: probeer het zo opnieuw' })
  })
})
