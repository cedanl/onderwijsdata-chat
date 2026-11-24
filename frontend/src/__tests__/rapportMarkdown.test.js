// @vitest-environment jsdom
// #746: een rapport was alleen als HTML en PDF te bewaren; een gebruiker wilde het aanvullen met eigen bevindingen.
// Besluit 30-10: eerst een Markdown-export van het rapport, geen .docx. Een rapport wordt alleen als HTML bewaard,
// dus de tekst komt uit die HTML (rapportUitHtml.js) en wordt Markdown in de volgorde van het rapport.
import { describe, it, expect } from 'vitest'
import { buildReportHtml } from '../reportHtml'
import { kanMarkdown, rapportUitHtml } from '../rapportUitHtml'
import { rapportMarkdown, GRAFIEK_REGEL } from '../rapportMarkdown'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const figuur = JSON.stringify({ data: [{ type: 'bar', x: ['2023'], y: [475460] }], layout: { meta: { afrondingsnoot: 'Afgerond op tientallen.' } } })

const volledig = {
  title: 'Instroom hbo in Utrecht',
  auteur: 'jansen',
  datum: '30 oktober 2026',
  afwijkingen: ['Je vroeg naar 2025; de laatste cijfers zijn van 2024.'],
  onderzoeksvraag: 'Hoeveel studenten stromen in het hbo in?',
  beantwoordt: ['De instroom per jaar'],
  beantwoordt_niet: ['De reden van de keuze'],
  definities: [
    { begrip: 'Instroom', definitie: 'Eerstejaars in het hoger onderwijs.' },
    { begrip: 'Peildatum', definitie: 'Telling op 1 oktober. Voorlopige cijfers kunnen wijzigen.' },
  ],
  visualisaties: [{
    titel: 'Instroom per jaar',
    figure_json: figuur,
    toelichting: 'De instroom steeg licht.',
    bron: { tekst: 'CBS, Hoger onderwijs (85353NED), 2023', url: 'https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85353NED', bron: 'CBS' },
  }],
  conclusie: '## Kern\nDe instroom is **stabiel**.\n- 2023: 475.460\n- 2024: 476.000\n\nMeer is er niet.',
  bronnen: ['CBS StatLine 85353NED'],
  manifest: { model: 'azure/gpt-4.1', data_as_of: [{ bron: 'cbs', dataset: '85353NED', laatste_update: '2026-10-01' }] },
}

const markdownVan = (spec, opties) => rapportMarkdown(rapportUitHtml(buildReportHtml(spec, opties)))

describe('een rapport als Markdown', () => {
  const md = markdownVan(volledig, { instelling: 'Hogeschool Utrecht' })

  it('volgt de volgorde van het rapport', () => {
    const koppen = [
      '# Instroom hbo in Utrecht', '## Afwijking van je vraag', '## Onderzoeksvraag', '## Reikwijdte',
      '### Wat dit rapport wel beantwoordt', '### Wat dit rapport niet beantwoordt', '## Gekozen definities',
      '## Visualisaties', '### Instroom per jaar', '## Conclusie', '## Bronnen', '## Herkomst',
    ]
    const plekken = koppen.map(k => md.indexOf(`${k}\n`))
    expect(plekken.every(p => p >= 0)).toBe(true)
    expect([...plekken].sort((a, b) => a - b)).toEqual(plekken)
  })

  it('zet datum, auteursregel en instelling onder de titel', () => {
    expect(md).toContain('# Instroom hbo in Utrecht\n\nGegenereerd op 30 oktober 2026 · Opgesteld door jansen met openEDUdata+ (AI-assistent) · Instelling: Hogeschool Utrecht\n')
  })

  it('neemt per visualisatie titel, noot, bron met link en toelichting, en zegt dat er een grafiek stond', () => {
    expect(md).toContain([
      '### Instroom per jaar', GRAFIEK_REGEL, 'Afgerond op tientallen.',
      'Bron: CBS, Hoger onderwijs (85353NED), 2023 · [Bekijk de bron bij CBS](https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85353NED)',
      'De instroom steeg licht.',
    ].join('\n\n'))
    expect(md).not.toContain('475460')
    expect(md).not.toContain('Plotly')
  })

  it('zet definities van meer zinnen als opsomming onder het begrip (#748)', () => {
    expect(md).toContain('- **Instroom**: Eerstejaars in het hoger onderwijs.\n- **Peildatum**\n  - Telling op 1 oktober.\n  - Voorlopige cijfers kunnen wijzigen.')
  })

  it('geeft de conclusie terug als Markdown: kop, vet en opsomming', () => {
    expect(md).toContain('## Conclusie\n\n### Kern\n\nDe instroom is **stabiel**.\n\n- 2023: 475.460\n- 2024: 476.000\n\nMeer is er niet.\n')
  })

  it('neemt bronnen genummerd en de herkomst met de dataversie', () => {
    expect(md).toContain('## Bronnen\n\n1. CBS StatLine 85353NED')
    expect(md).toMatch(/## Herkomst\n\nVerantwoording: model gpt-4\.1\n\nDataversie: CBS 85353NED \(bijgewerkt 2026-10-01\)\n$/)
  })

  it('neemt de commit uit de verantwoordingsregel ongewijzigd over (#1123)', () => {
    const met = markdownVan({ ...volledig, manifest: { ...volledig.manifest, app: '2.8.0', commit: '7d3488aa' } })
    expect(met).toContain('Verantwoording: model gpt-4.1 · app 2.8.0 (commit 7d3488aa)\n')
  })

  it('bevat geen HTML-tags', () => {
    expect(md).not.toMatch(/<\/?[a-z][^>]*>/i)
  })

  it('laat lege secties weg', () => {
    const kaal = markdownVan({ title: 'Kort', datum: '30 oktober 2026', onderzoeksvraag: 'Hoe?', conclusie: 'Zo.' })
    expect(kaal).toBe('# Kort\n\nGegenereerd op 30 oktober 2026 · Opgesteld met openEDUdata+ (AI-assistent)\n\n## Onderzoeksvraag\n\nHoe?\n\n## Conclusie\n\nZo.\n')
  })

  it('is deterministisch', () => {
    expect(markdownVan(volledig)).toBe(markdownVan(volledig))
  })
})

describe('de tekst uit een bewaard rapport', () => {
  it('maakt van een link die geen http(s)-adres is geen Markdown-link', () => {
    const html = '<div class="vraag"><div class="vraag-text">Hoe?</div></div><div class="vis"><h3 class="vis-title">G</h3><p class="vis-bron">Bron: X · <a href="javascript:alert(1)">Bekijk de bron</a></p></div>'
    const md = rapportMarkdown(rapportUitHtml(html))
    expect(md).toContain('Bron: X\n')
    expect(md).not.toContain('javascript:')
  })

  it('codeert haakjes in een adres, zodat de link heel blijft', () => {
    const html = '<div class="vraag"></div><div class="vis"><p class="vis-bron">Bron: X · <a href="https://example.org/a_(b) c">Bekijk de bron</a></p></div>'
    expect(rapportMarkdown(rapportUitHtml(html))).toContain('[Bekijk de bron](https://example.org/a_%28b%29%20c)')
  })

  it('laat geen script uit het rapport lopen', () => {
    rapportUitHtml('<div class="vraag"></div><script>window.__rapportScript = true</script><img src=x onerror="window.__rapportScript = true">')
    expect(window.__rapportScript).toBeUndefined()
  })

  it('herkent een rapport aan zijn onderzoeksvraag', () => {
    expect(kanMarkdown(buildReportHtml(volledig))).toBe(true)
    expect(kanMarkdown('<p>rapport</p>')).toBe(false)
    expect(kanMarkdown(undefined)).toBe(false)
  })
})

// #1075: de conclusie heeft nu echte <table>, <ol> en <ul>; de Markdown krijgt de pipetabel en de lijstregels terug.
// tests/test_rapport_docx_uit_html.py leest dezelfde HTML met de Python-tweeling.
describe('een conclusie met tabel en lijsten terug naar Markdown (#1075)', () => {
  const fixture = naam => readFileSync(join(__dirname, '..', '..', '..', 'tests', 'fixtures', 'rapport_docx', naam), 'utf-8')
  const terug = fixture('conclusie-tabel.terug.md').trimEnd()

  it('geeft de pipetabel, 1./2. en - regels terug', () => {
    const conclusie = fixture('conclusie-tabel.md').trimEnd()
    expect(rapportUitHtml(buildReportHtml({ title: 'T', onderzoeksvraag: 'Hoe?', conclusie })).conclusie).toBe(terug)
  })

  it('leest de vaste HTML zoals de Python-tweeling', () => {
    const html = `<div class="vraag"></div><div class="card conf"><div class="prose">${fixture('conclusie-tabel.html').trimEnd()}</div></div>`
    expect(rapportUitHtml(html).conclusie).toBe(terug)
  })

  it('zet de tabel in de Markdown-download, zonder HTML-tags', () => {
    const md = markdownVan({ title: 'T', datum: '1 december 2026', onderzoeksvraag: 'Hoe?', conclusie: fixture('conclusie-tabel.md') })
    expect(md).toContain('| Sector | Instroom |\n|---|---:|\n| Economie | **1.200** |')
    expect(md).toContain('1. Eerst economie\n2. Dan zorg\n\n- Een punt\n- Nog een <script>')
    expect(md).not.toMatch(/<\/?(table|tr|td|th|ol|ul|li|p|div)\b/i)
  })
})
