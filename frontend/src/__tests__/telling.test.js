import { describe, it, expect } from 'vitest'
import { splitsTelling } from '../telling'

const BLOK = '**Telling**\n- p01hoinges (Ingeschrevenen hoger onderwijs): Ingeschrevenen: hoofdinschrijvingen op 1 oktober. Een hbo-inschrijving telt niet ook in het wo.\n- Ondergrens: cellen met -1 uitgesloten.'

// Een kort telling-blok met uitklap naar de volledige brontekst (#402).
describe('splitsTelling', () => {
  it('splits the answer from the telling block', () => {
    const { antwoord, telling } = splitsTelling(`De HU had 36.201 studenten.\n\n${BLOK}`)
    expect(antwoord).toBe('De HU had 36.201 studenten.')
    expect(telling).toContain('Een hbo-inschrijving telt niet ook in het wo.')
    expect(telling).toContain('Ondergrens')
  })

  it('summarises with the first sentence of the first definition', () => {
    expect(splitsTelling(`Antwoord.\n\n${BLOK}`).samenvatting).toBe('Ingeschrevenen: hoofdinschrijvingen op 1 oktober.')
  })

  it('leaves an answer without a telling block as it is', () => {
    expect(splitsTelling('Alleen tekst. **Telling** midden in een zin.')).toEqual({
      antwoord: 'Alleen tekst. **Telling** midden in een zin.', telling: null, samenvatting: null,
    })
  })
})
