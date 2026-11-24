// #1131: een mislukt verzoek in een dialoog toont geen "Failed to fetch", "API 500" of "Unauthorized", maar wat er
// misging en wat je kunt doen; een tekst die de server voor gebruikers schreef blijft.
import { describe, it, expect } from 'vitest'
import { foutMelding } from '../foutMelding'

const metStatus = (status, tekst) => Object.assign(new Error(tekst), { status })
const TECHNISCH = /Failed to fetch|Load failed|API \d|Unauthorized|\b\d{3}\b/

describe('foutMelding', () => {
  it('geeft bij een netwerkfout een Nederlandse melding met een vervolgstap', () => {
    for (const tekst of ['Failed to fetch', 'Load failed', 'NetworkError when attempting to fetch resource.']) {
      const melding = foutMelding('Feedback niet verstuurd', new TypeError(tekst))
      expect(melding).toBe('Feedback niet verstuurd. De server is niet bereikbaar; controleer je verbinding en probeer het opnieuw.')
    }
  })

  it('noemt bij een 5xx zonder tekst van de server geen statuscode', () => {
    for (const status of [500, 502, 503]) {
      const melding = foutMelding('Titel niet opgeslagen', metStatus(status, `API ${status}`))
      expect(melding).toBe('Titel niet opgeslagen. De server kon het niet verwerken; probeer het over een minuut opnieuw.')
      expect(melding).not.toMatch(TECHNISCH)
    }
  })

  it('noemt bij een 401 geen "Unauthorized" maar zegt dat je opnieuw inlogt', () => {
    const melding = foutMelding('Feedback niet verstuurd', metStatus(401, 'Unauthorized'))
    expect(melding).toBe('Feedback niet verstuurd. Je sessie is verlopen; log opnieuw in en probeer het nog eens.')
  })

  it('laat de tekst staan die de server voor gebruikers schreef', () => {
    const melding = foutMelding('Het Word-document kon niet worden gemaakt', metStatus(404, 'Rapport niet gevonden'))
    expect(melding).toBe('Het Word-document kon niet worden gemaakt: Rapport niet gevonden')
  })

  it('toont een antwoord dat geen JSON was als serverfout, niet de parserfout', () => {
    const melding = foutMelding('Feedback niet verstuurd', new SyntaxError('Unexpected token < in JSON at position 0'))
    expect(melding).not.toMatch(/Unexpected|JSON/)
    expect(melding).toContain('probeer het')
  })

  it('laat een eigen Nederlandse fout zonder status staan en vangt een lege fout op', () => {
    expect(foutMelding('Titel niet opgeslagen', new Error('Rapport is nog niet geladen'))).toBe(
      'Titel niet opgeslagen: Rapport is nog niet geladen',
    )
    expect(foutMelding('Titel niet opgeslagen', new Error(''))).toBe('Titel niet opgeslagen. Probeer het opnieuw.')
    expect(foutMelding('Titel niet opgeslagen', undefined)).toBe('Titel niet opgeslagen. Probeer het opnieuw.')
  })
})
