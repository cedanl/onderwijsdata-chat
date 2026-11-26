import { readFileSync } from 'node:fs'
import { describe, it, expect } from 'vitest'
import { GEEN_CODE, conversationMarkdown, conversationNotebook, exportBestandsnaam } from '../conversationExport'

// Een gesprek met echte snippets van tools/snippet.py (versiekop, query_data en run_analysis op DUO p02ho1ejrs).
// tests/test_notebook_export.py draait het notebook hieruit in een kernel tegen de bevroren DUO-fixture.
const FIXTURES = new URL('../../../tests/fixtures/notebook/', import.meta.url)
const GESPREK = JSON.parse(readFileSync(new URL('gesprek.json', FIXTURES), 'utf8'))
const DATUM = '26 november 2026'

const nb = (gesprek = GESPREK, opties) => conversationNotebook(gesprek, { datum: DATUM, ...opties })
const tekst = cel => (Array.isArray(cel.source) ? cel.source.join('') : cel.source)
const codecellen = notebook => notebook.cells.filter(c => c.cell_type === 'code')
// Wat elke cel is, kort: m = markdown, c = code, met het begin van de tekst.
const vorm = notebook => notebook.cells.map(c => `${c.cell_type[0]}:${tekst(c).split('\n')[0]}`)

const KOP = '# Gemaakt met onderwijsbronnen 0.3.0, app 2.8.0, commit 7d3488aa.\n' +
  '# Dezelfde versies installeren: pip install "onderwijsbronnen[analyse] @ git+https://example.org/x@7d3488aa#subdirectory=packages/onderwijsbronnen"'
const met = (kop, code) => `${kop}\n\n${code}`

describe('conversationNotebook: nbformat 4 (#1247)', () => {
  it('is een nbformat-4-notebook met een python3-kernel en geldige cellen', () => {
    const notebook = JSON.parse(JSON.stringify(nb()))
    expect(notebook.nbformat).toBe(4)
    expect(notebook.nbformat_minor).toBe(5)
    expect(notebook.metadata.kernelspec).toEqual({ name: 'python3', display_name: 'Python 3', language: 'python' })
    for (const cel of notebook.cells) {
      expect(['markdown', 'code']).toContain(cel.cell_type)
      expect(cel.id).toMatch(/^[a-zA-Z0-9_-]{1,64}$/)
      expect(cel.metadata).toEqual({})
      expect(Array.isArray(cel.source)).toBe(true)
      if (cel.cell_type === 'code') {
        expect(cel.outputs).toEqual([])
        expect(cel.execution_count).toBeNull()
      } else {
        expect(cel).not.toHaveProperty('outputs')
      }
    }
  })

  it('geeft elke cel een vaste id op zijn plaats, zodat dezelfde export hetzelfde bestand is', () => {
    expect(nb().cells.map(c => c.id)).toEqual(nb().cells.map((_, i) => `cel-${i}`))
    expect(JSON.stringify(nb())).toBe(JSON.stringify(nb()))
  })

  it('zet geen gebruikers- of sessiegegevens in de metadata', () => {
    expect(Object.keys(nb().metadata).sort()).toEqual(['kernelspec', 'language_info'])
  })
})

describe('conversationNotebook: de cellen (#1247)', () => {
  it('heeft titel, installcel, en per beurt de vraag-en-antwoordcel met daarna zijn stappen op volgorde', () => {
    expect(vorm(nb())).toEqual([
      'm:# Hoeveel eerstejaars hbo-studenten kozen per studiejaar voor techniek?',
      'c:# Gemaakt met onderwijsbronnen 0.11.2, app 2.8.0, commit 7d3488aa.',
      'm:## Vraag 1',
      'm:Stap 1, "Catalogus doorzocht", heeft geen code: voor die stap maakt de app geen code om zelf na te rekenen.',
      'c:# Stap 2: Data gefilterd',
      'm:## Vraag 2',
      'c:# Stap 1: Analyse uitgevoerd',
    ])
  })

  it('zet de exportdatum in de titelcel', () => {
    expect(tekst(nb().cells[0])).toContain(`Geëxporteerd uit openEDUdata+ op ${DATUM}.`)
  })

  it('geeft een stap zonder snippet de vaste zin van een codeverzoek (#969) en geen codecel', () => {
    const gesprek = [
      { role: 'user', content: 'Wat is het collegegeld?' },
      { role: 'assistant', content: 'Het is 2.601 euro.', done: true, tools: [{ name: 'get_collegegeld', label: 'Collegegeld opgehaald', done: true, snippet: null }] },
    ]
    const notebook = nb(gesprek)
    expect(codecellen(notebook)).toEqual([])
    expect(tekst(notebook.cells.at(-1))).toBe(`Stap 1, "Collegegeld opgehaald", heeft geen code: ${GEEN_CODE}`)
  })

  it('zet het script van run_analysis als codecel, met zijn eigen code (#1247, 4)', () => {
    const analyse = tekst(codecellen(nb()).at(-1))
    expect(analyse).toContain('result = techniek.groupby("STUDIEJAAR"')
    expect(analyse).toContain('df = duo.load("p02ho1ejrs", 0)')
  })

  it('laat mislukte stappen en foutmeldingen weg zoals de Markdown-export, en neemt ze met fouten mee', () => {
    expect(JSON.stringify(nb())).not.toContain('df[df.X == 1]')
    const metFouten = nb(GESPREK, { fouten: true })
    expect(vorm(metFouten)).toContain('c:# Stap 1: Data gefilterd (Kolom bestaat niet)')
    expect(vorm(metFouten)).toContain('c:# Stap 2: Analyse uitgevoerd')

    const fout = [{ role: 'user', content: 'En de HAN?' }, { role: 'assistant', content: 'Er ging iets mis.', isError: true, done: true }]
    expect(JSON.stringify(nb(fout))).not.toContain('Er ging iets mis.')
    expect(vorm(nb(fout))).toEqual(['m:# En de HAN?', 'm:## Vraag 1'])
    expect(JSON.stringify(nb(fout, { fouten: true }))).toContain('Er ging iets mis.')
  })

  it('zet een ingetrokken antwoord alleen geciteerd in de markdowncel, nooit als code (#398)', () => {
    const gesprek = [
      { role: 'user', content: 'Hoeveel eerstejaars?' },
      {
        role: 'assistant', content: 'Het zijn er 36.201.', done: true,
        vervangen: [{ tekst: 'Het zijn er 99.\nDat is veel.', naStap: 1 }],
        tools: [
          { name: 'get_duo_data', label: 'DUO dataset geladen', done: true, snippet: 'df = duo.load("p02ho1ejrs", 0)' },
          { name: 'compute_kpi', label: 'KPI berekend', done: true, snippet: 'print(df.sum())' },
        ],
      },
    ]
    const notebook = nb(gesprek)
    expect(tekst(notebook.cells[1])).toContain('> **Ingetrokken na controle:**\n> Het zijn er 99.\n> Dat is veel.')
    for (const cel of codecellen(notebook)) expect(tekst(cel)).not.toContain('Het zijn er 99.')
    expect(vorm(notebook).slice(2)).toEqual(['c:# Stap 1: DUO dataset geladen', 'c:# Stap 2: KPI berekend (na de correctie)'])
  })

  it('zet bronnen, meldingen, vaste maat en herkomst in de markdowncel zoals in de Markdown-export', () => {
    const gesprek = [
      GESPREK[0],
      { ...GESPREK[1], vaste_maat: { maat: 'ingeschreven_personen_ho', teldefinitie: 'personen', vastgelegd_in: '#188', vastgelegd_op: '2026-10-14' } },
    ]
    const cel = tekst(nb(gesprek).cells[2])
    const markdown = conversationMarkdown(gesprek, { datum: DATUM })
    // De cel is letterlijk het stuk van de Markdown-export vóór de stappen.
    expect(markdown).toContain(`${cel}\n\n#### Stappen`)
    expect(cel).toContain('**Bronnen**\n- DUO · Eerstejaars ingeschrevenen hbo (p02ho1ejrs)')
    expect(cel).toContain('> Let op: de aantallen zijn een ondergrens')
    expect(cel).toContain('Teldefinitie: personen')
    expect(cel).toContain('#### Herkomst')
    expect(cel).toContain('Dataversie: DUO p02ho1ejrs (herladen 26-11-2026)')
  })
})

describe('conversationNotebook: de installcel (#1247, 3)', () => {
  it('haalt de versiekop uit de snippets naar één cel bovenaan, met alle pakketten', () => {
    const notebook = nb()
    expect(tekst(notebook.cells[1]).split('\n')).toEqual([
      '# Gemaakt met onderwijsbronnen 0.11.2, app 2.8.0, commit 7d3488aa.',
      '# Dezelfde versies installeren:',
      '%pip install "onderwijsbronnen[analyse] @ git+https://github.com/cedanl/onderwijsdata-chat@7d3488aa0c1e5b2f9a64d3e8b1c07f25e9a4d6b3#subdirectory=packages/onderwijsbronnen" plotly',
    ])
    const stappen = codecellen(notebook).slice(1)
    expect(stappen).toHaveLength(2)
    for (const cel of stappen) expect(tekst(cel)).not.toContain('pip install')
    expect(tekst(stappen[0]).split('\n').slice(0, 3)).toEqual(['# Stap 2: Data gefilterd', 'import pandas as pd', 'from onderwijsbronnen import duo'])
  })

  it('heeft geen installcel als geen stap een snippet heeft', () => {
    const gesprek = [
      { role: 'user', content: 'Welke datasets?' },
      { role: 'assistant', content: 'Deze.', done: true, tools: [{ name: 'search_catalog', label: 'Catalogus doorzocht', done: true, snippet: null }] },
    ]
    expect(codecellen(nb(gesprek))).toEqual([])
  })

  it('houdt de databewerking boven de code en de kop van een andere versie in zijn eigen cel', () => {
    const ander = KOP.replaceAll('7d3488aa', '1234abcd').replace('0.3.0', '0.4.0')
    const gesprek = [
      { role: 'user', content: 'Hoeveel?' },
      {
        role: 'assistant', content: 'Zoveel.', done: true,
        tools: [
          { name: 'query_data', label: 'Data gefilterd', done: true, snippet: `# Databewerking in de app:\n# - leeg filter\n\n${met(KOP, 'print(1)')}` },
          { name: 'query_data', label: 'Data gefilterd', done: true, snippet: met(ander, 'print(2)') },
        ],
      },
    ]
    const [install, eerste, tweede] = codecellen(nb(gesprek)).map(tekst)
    expect(install).toContain('commit 7d3488aa.')
    expect(install).not.toContain('1234abcd')
    expect(eerste).toBe('# Stap 1: Data gefilterd\n# Databewerking in de app:\n# - leeg filter\n\nprint(1)')
    expect(tweede).toBe(`# Stap 2: Data gefilterd\n${met(ander, 'print(2)')}`)
  })

  it('zegt bij een snippet zonder commit dat hij de nieuwste versie installeert', () => {
    const zonder = '# Gemaakt met onderwijsbronnen 0.3.0.\n# Commit onbekend, dus de nieuwste versie installeren: pip install "x @ git+https://example.org/x"'
    const gesprek = [
      { role: 'user', content: 'Hoeveel?' },
      { role: 'assistant', content: 'Zoveel.', done: true, tools: [{ name: 'query_data', label: 'Data gefilterd', done: true, snippet: met(zonder, 'print(1)') }] },
    ]
    expect(tekst(codecellen(nb(gesprek))[0]).split('\n')).toEqual([
      '# Gemaakt met onderwijsbronnen 0.3.0.',
      '# Commit onbekend, dus de nieuwste versie installeren:',
      '%pip install "x @ git+https://example.org/x"',
    ])
  })
})

describe('exportBestandsnaam (#478, #1247)', () => {
  it('neemt alleen letters, cijfers en _ uit de titel, voor .md en .ipynb gelijk', () => {
    const gesprek = [{ role: 'user', content: 'Mail jan@hu.nl: hoeveel studenten / 2024?' }]
    const md = exportBestandsnaam(gesprek, '.md')
    const ipynb = exportBestandsnaam(gesprek, '.ipynb')
    expect(md.replace(/\.md$/, '')).toMatch(/^[a-zA-Z0-9_]+$/)
    expect(ipynb).toBe(md.replace(/\.md$/, '.ipynb'))
    expect(ipynb).not.toContain('@')
  })
})

// De fixture van tests/test_notebook_export.py is dit notebook zelf: wijkt de export af, dan faalt deze test.
// Na een bewuste wijziging: `npx vitest run -u src/__tests__/conversationNotebook.test.js` en commit de fixture.
describe('notebookfixture voor de kerneltest (#1247, 5)', () => {
  it('is wat conversationNotebook van het fixturegesprek maakt', async () => {
    await expect(JSON.stringify(nb(), null, 1) + '\n').toMatchFileSnapshot('../../../tests/fixtures/notebook/gesprek.ipynb')
  })
})
