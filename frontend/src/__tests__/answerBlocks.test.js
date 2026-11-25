import { describe, it, expect } from 'vitest'
import { answerBlocks, bronnenMarkdown, bronnenTekst, citatieSamenvatting, kopieerTekst, metBronnen } from '../answerBlocks'
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

  it('kent elk blok als n.v.t.; export is er bij elk dataantwoord, met zijn bewijsbestand (#544, #1244)', () => {
    expect(statussen(ALLEEN_CITATIES)).toBe('citaties: aanwezig, telling: n.v.t., export: aanwezig, bronnen: n.v.t.')
    // Zonder getal met herkomst geen CSV, maar wel "Bewijs (JSON)" (#1244): de export blijft aanwezig.
    const zonder_herkomst = { ...ALLEEN_CITATIES, citaties: [{ getal: '7.912', vastgesteld: false }] }
    expect(statussen(zonder_herkomst)).toBe('citaties: aanwezig, telling: n.v.t., export: aanwezig, bronnen: n.v.t.')
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

  it('neemt alleen bronnen die tekst zijn', () => {
    expect(bronnenMarkdown([{ titel: DUO }, DUO, null, 3, ' '])).toBe(`**Bronnen**\n- ${DUO}`)
    expect(metBronnen(TEKST, [{ titel: DUO }])).toBe(TEKST)
  })
})

// #1108: wat een journalist plakt, zegt ook dat de controle iets uit het antwoord haalde.
describe('kopieerTekst: het antwoord met de controlemelding en de bronnen', () => {
  const melding = 'Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten.'

  it('zet elke controlemelding als "Let op" vóór de bronnen', () => {
    const msg = { content: TEKST, bronnen: [DUO], controle: [melding, '92.600 hoort bij 2024/25.'] }
    expect(kopieerTekst(msg)).toBe(
      `${TEKST}\n\nLet op: ${melding}\n\nLet op: 92.600 hoort bij 2024/25.\n\n**Bronnen**\n- ${DUO}`,
    )
  })

  it('kopieert van een ingehouden antwoord de melding en de redenen', () => {
    const msg = { content: 'Dit antwoord is ingehouden.', controle: ['Hieronder staat wat er niet klopte.', '5 klopt niet.'] }
    expect(kopieerTekst(msg)).toBe('Dit antwoord is ingehouden.\n\nLet op: Hieronder staat wat er niet klopte.\n\nLet op: 5 klopt niet.')
  })

  it('laat een antwoord zonder controlemelding zoals metBronnen het geeft', () => {
    expect(kopieerTekst({ content: TEKST, bronnen: [DUO] })).toBe(metBronnen(TEKST, [DUO]))
    expect(kopieerTekst({ content: TEKST, controle: [] })).toBe(TEKST)
  })
})

// Een bericht uit localStorage of de gespreksopslag kan in bronnen iets anders dan tekst hebben.
describe('bronnen die geen tekst zijn', () => {
  const data = VIJF_ANTWOORDEN[1]

  it('tellen niet mee', () => {
    expect(bronnenTekst([DUO, { titel: 'x' }, null, 3, '', ' '])).toEqual([DUO])
    expect(bronnenTekst(undefined)).toEqual([])
    expect(statussen({ ...data, bronnen: [{ titel: DUO }] })).toContain('bronnen: n.v.t.')
    expect(answerBlocks({ ...ALLEEN_CITATIES, citaties: [], bronnen: [{ titel: DUO }] }, { settled: true })).toBeNull()
  })
})
