// #748: de auteursregel zegt dat het rapport met een AI-assistent is opgesteld ("denk dat het eerlijker is om
// transparant te zijn over gebruik van deze tool"), en "het blok definities mag meer bulletsgewijs".
import { describe, it, expect } from 'vitest'
import { auteursregel, buildReportHtml, definitieDelen } from '../reportHtml.js'

const P02 = 'Eerstejaars ingeschrevenen: alleen de inschrijvingen op de peildatum 1 oktober die voor het eerst in het ' +
  'domein hoger onderwijs voorkomen worden meegenomen. Van deze inschrijvingen worden de hoofdinschrijvingen bepaald ' +
  'en geteld als eerstejaars ingeschrevenen. De master inschrijvingen in het hoger beroepsonderwijs zijn eveneens ' +
  'buiten beschouwing gelaten.'

describe('de auteursregel (#748)', () => {
  it('noemt de gebruiker en de tool', () => {
    expect(auteursregel('jansen')).toBe('Opgesteld door <b>jansen</b> met openEDUdata+ (AI-assistent)')
    const html = buildReportHtml({ title: 'R', auteur: 'jansen' })
    expect(html).toContain('Opgesteld door <b>jansen</b> met openEDUdata+ (AI-assistent)')
    expect(html).not.toContain('Auteur <b>')
  })

  it('zonder naam alleen de tool, niet "onbekend"', () => {
    expect(auteursregel('')).toBe('Opgesteld met openEDUdata+ (AI-assistent)')
    expect(buildReportHtml({ title: 'R' })).not.toContain('onbekend')
  })

  it('ontsnapt de naam', () => {
    expect(auteursregel('<script>x</script>')).toContain('&lt;script&gt;')
  })
})

describe('het definitieblok als opsomming (#748)', () => {
  it('een definitie van meer zinnen wordt een lijst, per zin', () => {
    expect(definitieDelen(P02)).toHaveLength(3)
    const html = buildReportHtml({ title: 'R', definities: [{ begrip: 'Eerstejaars', definitie: P02 }] })
    expect(html).toContain('<ul class="def-lijst"><li>Eerstejaars ingeschrevenen: alleen de inschrijvingen')
    expect((html.match(/<li>/g) || []).length).toBeGreaterThanOrEqual(3)
  })

  it('één zin blijft gewone tekst', () => {
    const html = buildReportHtml({ title: 'R', definities: [{ begrip: 'Instroom', definitie: 'Nieuw ingeschreven studenten.' }] })
    expect(html).toContain('<div class="def-desc">Nieuw ingeschreven studenten.</div>')
    expect(html).not.toContain('def-lijst"><li>')
  })

  it('een afkorting of een datum splitst geen zin', () => {
    expect(definitieDelen('Peildatum 1 okt. van het jaar, o.a. bol en bbl. Daarna volgt de rest.')).toEqual([
      'Peildatum 1 okt. van het jaar, o.a. bol en bbl.',
      'Daarna volgt de rest.',
    ])
  })
})
