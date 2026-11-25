// @vitest-environment jsdom
// Eerlijk tonen in UI en exports (#1272): het voorbehoud reist mee (#1257), de regel "Wat is gecontroleerd" (#1260),
// de ondergrens per punt in de tabel (#1261) en het label van een trendbreuk op een smal scherm (#1262).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { kopieerTekst } from '../answerBlocks'
import { conversationMarkdown } from '../conversationExport'
import { figureToCsv } from '../figureCsv'
import { figuurTabel } from '../figuurTabel'
import { metBronregel, figuurNoten } from '../figuurNoot'
import { chatFigureLayout } from '../figureLayout'
import { buildReportHtml } from '../reportHtml'
import { GEEN_GETALLEN, NIET_GECONTROLEERD, controleRegelTekst, controleSamenvatting } from '../controleRegel'
import { metVoorbehoud, voorbehoudAlineas, voorbehoudRegels } from '../voorbehoud'
import ControleRegel from '../components/ControleRegel'
import FiguurTabel from '../components/FiguurTabel'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const UITGANGSPUNT = '**Uitgangspunt:** Hogeschool Utrecht (25DW), alle opleidingsvormen.'
const NIET_MEEGETELD = '**Niet meegeteld:** masterstudenten en extraneï.'
const BRON = '**Bron en definitie:** DUO p01hoinges, ingeschrevenen op 1 oktober.'
const DUO = 'DUO, Ingeschrevenen hbo (p01hoinges)'
const CONTROLES = { getallen: 2, gebonden: 1, jaar_en_instelling: true, niet_gedraaid: 0, ingetrokken: 1, gecorrigeerd: 0 }
const ANTWOORD = {
  role: 'assistant', done: true,
  content: `${UITGANGSPUNT}\n\n${NIET_MEEGETELD}\n\nDe HU had ten minste 38.000 studenten in 2024.\n\n${BRON}`,
  bronnen: [DUO],
  controle: ['2025 staat niet in de data.'],
  controles: CONTROLES,
}

// Een grafiek zoals tools/plot.py haar maakt bij een reeks met een onderdrukte cel in 2020.
const FIGUUR = {
  data: [{ type: 'scatter', mode: 'lines+markers', x: [2019, 2020, 2021], y: [1234, 1100, 1500] }],
  layout: {
    title: { text: 'Studenten per jaar' },
    meta: {
      x: 'STUDIEJAAR', y: 'AANTAL',
      data: [
        { STUDIEJAAR: 2019, AANTAL: 1234, ondergrens: 'nee' },
        { STUDIEJAAR: 2020, AANTAL: 1100, ondergrens: 'ja' },
        { STUDIEJAAR: 2021, AANTAL: 1500, ondergrens: 'nee' },
      ],
      ondergrens_rijen: [1],
      // Zoals tools/plot.py ze zet (tests/test_ondergrens_per_punt.py): de noot over de onderdrukte cel en de kolomregel.
      herkomst: [
        'bron: DUO, dataset p01hoinges, resource 0',
        "1 cellen met DUO-sentinel -1 in 'AANTAL' uitgesloten (onderdrukte cel) — een totaal waarin zo'n cel valt, is daardoor een ondergrens",
        'kolom ondergrens: ja als in die rij een onderdrukte cel valt; het getal is dan ten minste zo groot (een ondergrens), anders nee',
      ],
      bronregel: 'Bron: DUO, dataset p01hoinges, resource 0; ten minste: onderdrukte cellen maken een getal een ondergrens',
      figuurnoten: ['Trendbreuk vanaf 2020 (CBS, tabel X): “Vanaf 2020 telt CBS ook Y mee.”'],
    },
    annotations: [{ name: 'trendbreuk', x: 2020, text: 'definitiebreuk 2020' }],
  },
}

const zonderKop = csv => csv.split('\n').filter(r => !r.startsWith('#')).join('\n')
const kopregels = csv => csv.split('\n').filter(r => r.startsWith('#'))

// ── #1257: het voorbehoud reist mee ──

describe('voorbehoud uit het antwoord (#1257)', () => {
  it('leest Uitgangspunt, Niet meegeteld en Bron en definitie uit de tekst, zonder opmaak', () => {
    expect(voorbehoudAlineas(ANTWOORD.content)).toEqual([
      'Uitgangspunt: Hogeschool Utrecht (25DW), alle opleidingsvormen.',
      'Niet meegeteld: masterstudenten en extraneï.',
      'Bron en definitie: DUO p01hoinges, ingeschrevenen op 1 oktober.',
    ])
  })

  it('zet de "Let op"-regels en de controleregel erachter', () => {
    const regels = voorbehoudRegels(ANTWOORD)
    expect(regels).toContain('Let op: 2025 staat niet in de data.')
    expect(regels.at(-1)).toBe(controleRegelTekst(CONTROLES))
  })

  it('een antwoord zonder voorbehoud geeft geen regels, een CSV blijft dan gelijk', () => {
    expect(voorbehoudRegels({ content: 'Hallo.' })).toEqual([])
    expect(metVoorbehoud('a;b\n1;2', [])).toBe('a;b\n1;2')
  })

  it('zet de regels als #-regels boven de grafiek-CSV; de tabel eronder blijft gelijk', () => {
    const zonder = figureToCsv(FIGUUR)
    const met = figureToCsv(FIGUUR, voorbehoudRegels(ANTWOORD))
    expect(zonderKop(met)).toBe(zonderKop(zonder))
    expect(kopregels(met)[0]).toBe('# Uitgangspunt: Hogeschool Utrecht (25DW), alle opleidingsvormen.')
    expect(zonderKop(met).split('\n')[0]).toBe('STUDIEJAAR;AANTAL;ondergrens')
  })

  it('houdt de BOM van een data-CSV vooraan', () => {
    const csv = metVoorbehoud('﻿# bron: DUO\na;b', ['Uitgangspunt: x'])
    expect(csv).toBe('﻿# Uitgangspunt: x\n# bron: DUO\na;b')
  })
})

// Elk exportpad van een antwoord met een ondergrens en een "Niet meegeteld" (#1257-4): faalt als één pad het
// voorbehoud mist.
describe('elk exportpad draagt het voorbehoud (#1257)', () => {
  afterEach(() => vi.unstubAllGlobals())

  const NIET = 'Niet meegeteld: masterstudenten'
  const paden = {
    kopie: () => kopieerTekst(ANTWOORD).replace(/\*\*/g, ''),
    gespreksexport: () => conversationMarkdown([{ role: 'user', content: 'Hoeveel?' }, ANTWOORD], { datum: 'vandaag' })
      .replace(/\*\*/g, ''),
    'grafiek-CSV': () => figureToCsv(FIGUUR, voorbehoudRegels(ANTWOORD)),
  }

  for (const [pad, maak] of Object.entries(paden)) {
    it(`${pad}: Niet meegeteld, ten minste, Let op en wat niet gecontroleerd is`, () => {
      const tekst = maak()
      expect(tekst).toContain(NIET)
      expect(tekst).toContain('ten minste')
      expect(tekst).toContain('Let op: 2025 staat niet in de data.')
      expect(tekst).toContain(NIET_GECONTROLEERD)
    })
  }

  it('data-CSV: de regels van het antwoord boven die van de server', async () => {
    const { downloadDataCsv } = await import('../api')
    const server = '﻿# bron: DUO, dataset p01hoinges, resource 0\n# kolom ondergrens: ja als ...\nSTUDIEJAAR;AANTAL;ondergrens\n2020;1100;ja'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(server, {
      headers: { 'Content-Disposition': 'attachment; filename="x.csv"' },
    })))
    let blob
    URL.createObjectURL = vi.fn(b => { blob = b; return 'blob:x' })
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await downloadDataCsv('k', voorbehoudRegels(ANTWOORD))
    click.mockRestore()
    const tekst = await blob.text()
    expect(tekst).toContain(`# ${NIET}`)
    expect(tekst).toContain('# Let op: 2025 staat niet in de data.')
    expect(tekst).toContain(NIET_GECONTROLEERD)
    expect(tekst.split('\n').filter(r => !r.startsWith('#') && !r.startsWith('﻿#'))).toEqual(['STUDIEJAAR;AANTAL;ondergrens', '2020;1100;ja'])
  })

  for (const pad of ['Word', 'PDF-afdruk']) {
    it(`${pad}: de figuur in het rapport draagt de bronregel met "ten minste", de noot staat eronder`, () => {
      // Word maakt zijn PNG's uit deze figuur (rapportGrafieken.js), afdrukken drukt dezelfde pagina af.
      const html = buildReportHtml({ titel: 'R', visualisaties: [{ titel: 'Studenten per jaar', figure_json: JSON.stringify(FIGUUR) }] })
      expect(html).toContain('"name":"bronregel"')
      expect(html).toContain('ten minste: onderdrukte cellen maken een getal een ondergrens')
      expect(html).toContain('<p class="vis-noot">Trendbreuk vanaf 2020')
    })
  }

  it('op het scherm in de chat staat de bronregel niet in de figuur (#651)', () => {
    expect((chatFigureLayout(FIGUUR, false, 800).annotations || []).map(a => a.name)).not.toContain('bronregel')
    expect(metBronregel(FIGUUR).figure.layout.annotations.at(-1).text).toContain('ten minste')
    expect(metBronregel({ layout: {} }).extraBoven).toBe(0)
  })
})

// ── #1260: "Wat is gecontroleerd" ──

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
  return container
}

function opruimen() {
  if (!root) return
  act(() => root.unmount())
  container.remove()
  root = null
}

const VERBODEN = /geverifieerd|juist|betrouwbaar|[✓✔☑✅]/i

describe('de regel "Wat is gecontroleerd" (#1260)', () => {
  afterEach(opruimen)

  it('is ingeklapt en zegt het bij een antwoord zonder getallen', async () => {
    const el = await render(createElement(ControleRegel, { controles: { getallen: 0, per_controle: {} } }))
    const details = el.querySelector('details.controle-regel')
    expect(details).not.toBeNull()
    expect(details.open).toBe(false)
    expect(details.querySelector('summary').textContent).toBe(`Wat is gecontroleerd: ${GEEN_GETALLEN}`)
  })

  const varianten = [
    { getallen: 0 },
    { getallen: 1, jaar_en_instelling: true },
    CONTROLES,
    { getallen: 4, gebonden: 4, niet_gedraaid: 2, ingetrokken: 0, gecorrigeerd: 3 },
  ]
  for (const controles of varianten) {
    it(`toont altijd de vaste zin en nooit een woord dat meer belooft (${JSON.stringify(controles)})`, async () => {
      const el = await render(createElement(ControleRegel, { controles }))
      const tekst = el.textContent
      expect(tekst).toContain(NIET_GECONTROLEERD)
      expect(tekst).not.toMatch(VERBODEN)
      expect(el.querySelector('svg, img')).toBeNull()
      expect(controleRegelTekst(controles)).toContain(NIET_GECONTROLEERD)
      expect(controleRegelTekst(controles)).not.toMatch(VERBODEN)
    })
  }

  it('noemt het aantal correcties van een ingetrokken en een gecorrigeerd antwoord', () => {
    expect(controleSamenvatting({ getallen: 2, ingetrokken: 1 }).details.join(' ')).toContain('één correctie')
    expect(controleSamenvatting({ getallen: 2, ingetrokken: 1, gecorrigeerd: 2 }).details.join(' ')).toContain('3 correcties')
  })

  it('zonder veld (een antwoord van vóór #1260) geen regel', async () => {
    expect(controleSamenvatting(undefined)).toBeNull()
    expect(controleSamenvatting([1])).toBeNull()
    const el = await render(createElement(ControleRegel, { controles: null }))
    expect(el.querySelector('details')).toBeNull()
  })

  it('staat in de gespreksexport en in de kopie', () => {
    const md = conversationMarkdown([{ role: 'user', content: 'Hoeveel?' }, ANTWOORD], { datum: 'vandaag' })
    expect(md).toContain(`> ${controleRegelTekst(CONTROLES)}`)
    expect(kopieerTekst(ANTWOORD)).toContain(controleRegelTekst(CONTROLES))
  })
})

// ── #1261: de ondergrens in de tabel ──

describe('ondergrens per punt in de tabel (#1261)', () => {
  afterEach(opruimen)

  it('markeert alleen de cel van het punt met een onderdrukte cel, en verbergt de kolom ondergrens', () => {
    const tabel = figuurTabel(FIGUUR)
    expect(tabel.kolommen).toEqual(['STUDIEJAAR', 'AANTAL'])
    expect([...tabel.ondergrens]).toEqual(['1:1'])
  })

  it('markeert de cel van de juiste reeks bij meer reeksen', () => {
    const figuur = {
      data: [],
      layout: {
        meta: {
          x: 'jaar', y: 'n',
          data: [{ reeks: 'A', jaar: 2020, n: 5 }, { reeks: 'B', jaar: 2020, n: 7 }, { reeks: 'A', jaar: 2021, n: 6 }],
          ondergrens_rijen: [1],
        },
      },
    }
    const tabel = figuurTabel(figuur)
    expect(tabel.kolommen).toEqual(['jaar', 'A', 'B'])
    expect([...tabel.ondergrens]).toEqual(['0:2'])
  })

  it('toont "≥ 1.100" in de cel en de andere waarden gewoon', async () => {
    const el = await render(createElement(FiguurTabel, { tabel: figuurTabel(FIGUUR) }))
    const cellen = [...el.querySelectorAll('tbody td.getal')].map(td => td.textContent)
    expect(cellen).toEqual(['1.234', '≥ 1.100', '1.500'])
  })

  it('een figuur zonder ondergrens heeft geen markering', () => {
    const { ondergrens_rijen: _, ...meta } = FIGUUR.layout.meta
    expect(figuurTabel({ ...FIGUUR, layout: { ...FIGUUR.layout, meta } }).ondergrens).toBeUndefined()
  })
})

// ── #1262: het label van een trendbreuk op een smal scherm ──

describe('trendbreuk op een smal scherm (#1262)', () => {
  it('haalt het label op 320 px uit de figuur; de noot eronder blijft', () => {
    expect(chatFigureLayout(FIGUUR, false, 320).annotations).toEqual([])
    expect(figuurNoten(FIGUUR)).toEqual(FIGUUR.layout.meta.figuurnoten)
  })

  it('houdt het label op een breed scherm', () => {
    expect(chatFigureLayout(FIGUUR, false, 800).annotations).toEqual(FIGUUR.layout.annotations)
  })

  it('het rapport haalt het label op een telefoon ook weg', () => {
    const html = buildReportHtml({ titel: 'R', visualisaties: [{ titel: 'V', figure_json: JSON.stringify(FIGUUR) }] })
    expect(html).toContain("a.name!=='trendbreuk'")
  })
})
