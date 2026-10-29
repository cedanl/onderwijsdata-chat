// #734: "Het veranderen van de onderzoeksvraag had veel prominenter in beeld en als eerste genoemd moeten zijn."
// Een afwijking uit code staat als eerste blok in het rapport, vóór de onderzoeksvraag.
import { describe, it, expect } from 'vitest'
import { buildReportHtml } from '../reportHtml.js'

const REGEL = 'Gevraagd was een prognose; dit rapport toont het verloop tot nu toe, geen prognose.'

describe('de afwijking van de vraag (#734)', () => {
  it('staat vóór de onderzoeksvraag', () => {
    const html = buildReportHtml({ title: 'R', onderzoeksvraag: 'Hoeveel studenten in 2030?', afwijkingen: [REGEL] })
    const afwijking = html.indexOf('<div class="afwijking" role="note">')
    expect(afwijking).toBeGreaterThan(-1)
    expect(afwijking).toBeLessThan(html.indexOf('<div class="vraag">'))
    expect(html).toContain('Afwijking van je vraag')
    expect(html).toContain(`<li>${REGEL}</li>`)
  })

  it('zonder afwijking geen blok, ook bij een ouder rapport zonder het veld', () => {
    expect(buildReportHtml({ title: 'R', afwijkingen: [] })).not.toContain('class="afwijking"')
    expect(buildReportHtml({ title: 'R' })).not.toContain('class="afwijking"')
    expect(buildReportHtml({ title: 'R', afwijkingen: ['', '  ', 3] })).not.toContain('class="afwijking"')
  })

  it('ontsnapt de tekst en heeft een donkere variant', () => {
    const html = buildReportHtml({ title: 'R', afwijkingen: ['<b>x</b>'] })
    expect(html).toContain('&lt;b&gt;x&lt;/b&gt;')
    expect(html).toContain('html.dark .afwijking{')
  })
})
