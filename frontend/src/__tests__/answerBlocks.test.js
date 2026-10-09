import { describe, it, expect } from 'vitest'
import { answerBlocks, bronnenMarkdown, citatieSamenvatting, metBronnen } from '../answerBlocks'
import { ALLEEN_CITATIES, DUO, TEKST, VIJF_ANTWOORDEN } from './fixtures/vijfAntwoorden'

const kinds = msg => answerBlocks(msg, { settled: true }).map(b => b.kind).join(' · ')
const statussen = msg => answerBlocks(msg, { settled: true }).map(b => `${b.kind}: ${b.status}`).join(', ')

// CH-09 (#416): vijf keer dezelfde vraag, vijf verschillende sets bouwstenen onder het antwoord.
describe('answerBlocks: vaste bouwstenen onder een dataantwoord', () => {
  it('geeft vijf keer dezelfde vraag dezelfde blokken in dezelfde volgorde', () => {
    expect(VIJF_ANTWOORDEN.map(kinds)).toMatchInlineSnapshot(`
      [
        "citaties · telling · export · bronnen",
        "citaties · telling · export · bronnen",
        "citaties · telling · export · bronnen",
        "citaties · telling · export · bronnen",
        "citaties · telling · export · bronnen",
      ]
    `)
  })

  it('zegt per blok of het gevuld is; alleen dat verschilt per run', () => {
    expect(VIJF_ANTWOORDEN.map(statussen)).toMatchInlineSnapshot(`
      [
        "citaties: n.v.t., telling: aanwezig, export: aanwezig, bronnen: aanwezig",
        "citaties: aanwezig, telling: aanwezig, export: aanwezig, bronnen: aanwezig",
        "citaties: aanwezig, telling: n.v.t., export: aanwezig, bronnen: aanwezig",
        "citaties: n.v.t., telling: n.v.t., export: aanwezig, bronnen: aanwezig",
        "citaties: aanwezig, telling: aanwezig, export: aanwezig, bronnen: aanwezig",
      ]
    `)
  })

  it('kent elk blok als n.v.t.', () => {
    expect(statussen(ALLEEN_CITATIES)).toBe('citaties: aanwezig, telling: n.v.t., export: n.v.t., bronnen: n.v.t.')
  })
})

describe('answerBlocks: geen dataantwoord, dus zoals het was', () => {
  const data = VIJF_ANTWOORDEN[1]

  it('niet zolang het antwoord nog loopt', () => {
    expect(answerBlocks(data, { settled: false })).toBeNull()
    expect(answerBlocks(data)).toBeNull()
  })

  it('niet bij een foutmelding', () => {
    expect(answerBlocks({ ...data, isError: true }, { settled: true })).toBeNull()
  })

  it('niet bij een bericht van vóór de bronnenlijst', () => {
    const { bronnen: _weg, ...oud } = data
    expect(answerBlocks(oud, { settled: true })).toBeNull()
    expect(answerBlocks({ ...data, bronnen: 'DUO' }, { settled: true })).toBeNull()
  })

  it('niet bij een ingehouden, geweigerd of leeg antwoord', () => {
    const vast = { role: 'assistant', done: true, content: 'Dit antwoord is ingehouden.', tools: [], bronnen: [] }
    expect(answerBlocks(vast, { settled: true })).toBeNull()
    expect(answerBlocks({ ...vast, citaties: [] }, { settled: true })).toBeNull()
    expect(answerBlocks(null, { settled: true })).toBeNull()
  })
})

describe('citatieSamenvatting', () => {
  it('telt de getallen en noemt die zonder vastgestelde herkomst', () => {
    expect(citatieSamenvatting(VIJF_ANTWOORDEN[2].citaties)).toBe('9 getallen met herkomst')
    expect(citatieSamenvatting(VIJF_ANTWOORDEN[1].citaties)).toBe('9 getallen, waarvan 2 zonder vastgestelde herkomst')
    expect(citatieSamenvatting([{ getal: '7.912', vastgesteld: true }])).toBe('1 getal met herkomst')
  })
})

describe('bronnen in de tekst voor kopiëren en export', () => {
  it('zet de lijst onder het antwoord', () => {
    expect(bronnenMarkdown([DUO])).toBe(`**Bronnen**\n- ${DUO}`)
    expect(metBronnen(TEKST, [DUO])).toBe(`${TEKST}\n\n**Bronnen**\n- ${DUO}`)
  })

  it('laat een antwoord zonder bronnen zoals het is', () => {
    expect(metBronnen(TEKST, [])).toBe(TEKST)
    expect(metBronnen(TEKST, undefined)).toBe(TEKST)
    expect(metBronnen('', [DUO])).toBe('')
  })
})
