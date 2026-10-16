// #589 (mobiel B7): de aankondiging van een antwoord voor een schermlezer is platte tekst, zonder de
// markdowntekens die op het scherm opmaak worden.
import { describe, it, expect } from 'vitest'
import { platteTekst } from '../platteTekst'

const GEEN_OPMAAKTEKENS = /[*|#`]/

const tabel = [
  '| Jaar | Aantal |',
  '| --- | --- |',
  '| 2023 | 518.940 |',
  '| 2024 | 475.460 |',
].join('\n')

const GEVALLEN = [
  ['vet', '**Onderzoeksvraag:** x', 'Onderzoeksvraag: x'],
  ['kop', '# Kop', 'Kop.'],
  ['kop van niveau 3 met sluitende hekjes', '### Kop ###', 'Kop.'],
  ['lijsten', '- a\n* b\n1. c', 'a.\nb.\nc.'],
  ['tabel', tabel, 'Jaar, Aantal.\n2023, 518.940.\n2024, 475.460.'],
  ['codeblok', 'Voor\n```python\nprint(1)\n```\nNa', 'Voor\nNa'],
  ['inline code', 'Gebruik `data_key` hier', 'Gebruik data_key hier'],
  ['link', '[tekst](https://x)', 'tekst'],
  ['afbeelding', '![alt](u)', 'alt'],
  ['citaat', '> q', 'q'],
  ['scheidingslijn', 'boven\n---\nonder', 'boven\nonder'],
  ['doorgehaald', '~~x~~', 'x'],
  ['cursief met sterretjes', '*i*', 'i'],
  ['cursief met underscores', '_i_', 'i'],
  ['underscore in een woord', 'data_key', 'data_key'],
]

describe('platteTekst (#589)', () => {
  it.each([[''], [null], [undefined], ['   \n\t ']])('geeft lege tekst voor %j', invoer => {
    expect(platteTekst(invoer)).toBe('')
  })

  it.each(GEVALLEN)('%s', (_naam, invoer, verwacht) => {
    expect(platteTekst(invoer)).toBe(verwacht)
  })

  it.each(GEVALLEN)('%s: geen *, |, # of ` in de uitkomst', (_naam, invoer) => {
    expect(platteTekst(invoer)).not.toMatch(GEEN_OPMAAKTEKENS)
  })

  it('laat een tabelrij zonder scheidingsregel voorlezen als cellen met komma\'s', () => {
    expect(platteTekst(tabel).split('\n')).not.toContain(expect.stringMatching(/---/))
    expect(platteTekst(tabel).split('\n')[0]).toBe('Jaar, Aantal.')
  })

  it('zet geen extra punt achter een kop, item of rij die al met een leesteken eindigt', () => {
    expect(platteTekst('## Wat zie je?')).toBe('Wat zie je?')
    expect(platteTekst('- Let op!')).toBe('Let op!')
    expect(platteTekst('1. Bron:')).toBe('Bron:')
    expect(platteTekst('- eerst; daarna')).toBe('eerst; daarna.')
    expect(platteTekst('| a | klaar. |')).toBe('a, klaar.')
  })

  it('laat een gewone alinea staan zoals hij is geschreven', () => {
    expect(platteTekst('Er zijn 518.940 studenten')).toBe('Er zijn 518.940 studenten')
  })

  it('laat een vet stuk midden in een zin lezen zonder sterretjes', () => {
    expect(platteTekst('Het aantal is **518.940** in 2023.')).toBe('Het aantal is 518.940 in 2023.')
  })

  it.each(['[', '*', '|'])('is snel bij 100 000 keer "%s" (geen catastrofale backtracking)', teken => {
    const start = performance.now()
    platteTekst(teken.repeat(100_000))
    expect(performance.now() - start).toBeLessThan(1000)
  })
})
