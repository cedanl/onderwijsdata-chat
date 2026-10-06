import { describe, it, expect } from 'vitest'
import { conversationMarkdown } from '../conversationExport'

const SNIPPET = "import pandas as pd\ndf = pd.read_csv('https://duo.nl/p01hoinges.csv')"

const GESPREK = [
  { role: 'user', content: 'Hoeveel studenten heeft de HU?' },
  {
    role: 'assistant', content: 'De HU had **38.000** studenten.', done: true,
    tussentekst: ['We need to capture the result from previous run_analysis.'],
    controle: ['het jaar 2025 staat niet in de data'],
    tools: [
      { name: 'get_duo_data', label: 'Data opgehaald', done: true, snippet: SNIPPET },
      { name: 'query_data', label: 'Data gefilterd', done: true, status: 'empty', statusLabel: 'Filter leverde 0 rijen op', snippet: 'df[df.X == 1]' },
      { name: 'search_catalog', label: 'Catalogus doorzocht', done: true, snippet: null },
    ],
  },
  { role: 'assistant', content: '', figures: [{ label: 'Studenten per jaar', json: '{}' }], done: true },
  { role: 'user', content: 'En de HAN?' },
  { role: 'assistant', content: 'Er ging iets mis.', isError: true, done: true },
]

const md = opties => conversationMarkdown(GESPREK, { datum: '5 oktober 2026', ...opties })

describe('conversationMarkdown (#366)', () => {
  it('begint met de titel uit de eerste vraag en de exportdatum', () => {
    const [titel, , datum] = md().split('\n')
    expect(titel).toBe('# Hoeveel studenten heeft de HU?')
    expect(datum).toBe('Geëxporteerd uit EDUdata op 5 oktober 2026.')
  })

  it('zet vraag en antwoord onder elkaar, het antwoord als markdown', () => {
    const tekst = md()
    expect(tekst).toContain('## Vraag 1\n\nHoeveel studenten heeft de HU?')
    expect(tekst).toContain('### Antwoord\n\nDe HU had **38.000** studenten.')
    expect(tekst).toContain('## Vraag 2\n\nEn de HAN?')
  })

  it('laat tekst uit de toolronden buiten het antwoord (#393)', () => {
    expect(md()).not.toContain('We need to capture')
  })

  it('geeft per stap het label en de code die hem reproduceert', () => {
    const tekst = md()
    expect(tekst).toContain('1. Data opgehaald')
    expect(tekst).toContain('```python\n' + SNIPPET + '\n```')
    expect(tekst).toContain('Catalogus doorzocht')
  })

  it('laat de snippets weg als dat gevraagd is', () => {
    const tekst = md({ snippets: false })
    expect(tekst).toContain('1. Data opgehaald')
    expect(tekst).not.toContain('```python')
  })

  it('houdt de controle van de server en de grafieken erin', () => {
    const tekst = md()
    expect(tekst).toContain('> Let op: het jaar 2025 staat niet in de data')
    expect(tekst).toContain('_Grafiek: Studenten per jaar_')
  })

  it('laat mislukte stappen en foutmeldingen standaard weg', () => {
    const tekst = md()
    expect(tekst).not.toContain('Data gefilterd')
    expect(tekst).not.toContain('Er ging iets mis.')
  })

  it('neemt ze op met de foutentoggle, met wat er misging', () => {
    const tekst = md({ fouten: true })
    expect(tekst).toContain('Data gefilterd (Filter leverde 0 rijen op)')
    expect(tekst).toContain('Er ging iets mis.')
  })

  it('nummert de stappen door zonder gat als er een wegvalt', () => {
    const stappen = md({ snippets: false }).split('\n').filter(r => /^\d+\. /.test(r))
    expect(stappen).toEqual(['1. Data opgehaald', '2. Catalogus doorzocht'])
  })
})

describe('conversationMarkdown na een correctie (#398)', () => {
  const GECORRIGEERD = [
    { role: 'user', content: 'Hoeveel eerstejaars?' },
    {
      role: 'assistant', content: 'Het zijn er 36.201.', done: true,
      vervangen: [{ tekst: 'Het zijn er 99.\nDat is veel.', naStap: 2 }],
      tools: [
        { name: 'search_catalog', label: 'Catalogus doorzocht', done: true },
        { name: 'get_duo_data', label: 'Data opgehaald', done: true },
        { name: 'compute_kpi', label: 'KPI berekend', done: true },
      ],
    },
  ]
  const tekst = conversationMarkdown(GECORRIGEERD, { datum: '6 oktober 2026', snippets: false })

  it('neemt de ingetrokken tekst op, gemarkeerd', () => {
    expect(tekst).toContain('> **Ingetrokken na controle:**\n> Het zijn er 99.\n> Dat is veel.')
    expect(tekst.indexOf('Ingetrokken')).toBeLessThan(tekst.indexOf('### Antwoord'))
  })

  it('houdt de oorspronkelijke stappen en markeert wat na de correctie kwam', () => {
    const stappen = tekst.split('\n').filter(r => /^\d+\. /.test(r))
    expect(stappen).toEqual(['1. Catalogus doorzocht', '2. Data opgehaald', '3. KPI berekend (na de correctie)'])
  })
})
