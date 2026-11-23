// #1124, #1125: één naamregel voor de rapportdownloads, in de browser en op de server. tests/fixtures/bestandsnamen.json
// is de gedeelde verwachting: tests/test_bestandsnaam.py (core/bestandsnaam.py) leest hetzelfde bestand.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { bestandsdeel, rapportdeel, RAPPORT_MAX } from '../bestandsnaam'
import { workbookFilename } from '../workbookHtml'

const GEVALLEN = JSON.parse(readFileSync(join(__dirname, '..', '..', '..', 'tests', 'fixtures', 'bestandsnamen.json'), 'utf-8'))

describe('rapportdeel', () => {
  it('noemt hetzelfde maximum als de server', () => {
    expect(RAPPORT_MAX).toBe(GEVALLEN.maximum)
  })

  it.each(GEVALLEN.gevallen.map(g => [g.titel.slice(0, 30) || 'leeg', g]))('volgt het gedeelde geval %s', (_naam, geval) => {
    expect(rapportdeel(geval.titel)).toBe(geval.deel)
  })
})

describe('workbookFilename', () => {
  it('geeft "Commerciële opleidingen" in HTML, Markdown en Word dezelfde naam, met een e', () => {
    const naam = workbookFilename({ title: 'Commerciële opleidingen' })
    expect(naam).toBe('Commerciele_opleidingen.html')
    expect(naam.replace(/\.html$/, '.md')).toBe('Commerciele_opleidingen.md')
    expect(naam.replace(/\.html$/, '.docx')).toBe('Commerciele_opleidingen.docx')
  })

  it('geeft een emoji hooguit één streepje', () => {
    expect(workbookFilename({ title: '🎓📊 studenten 📊🎓 en meer' })).not.toContain('__')
  })

  it('houdt een titel van 300 tekens onder de grens van een bestandssysteem, op een woordgrens', () => {
    const titel = 'Commerciële opleidingen in het hoger onderwijs '.repeat(7)
    const naam = workbookFilename({ title: titel })
    expect(titel.length).toBeGreaterThan(300)
    expect(naam.length - '.html'.length).toBeLessThanOrEqual(RAPPORT_MAX)
    expect(naam.endsWith('_opleidingen_in.html')).toBe(true)
  })
})

describe('bestandsdeel', () => {
  it('kapt een gegeven maximum op een woordgrens af', () => {
    expect(bestandsdeel('aaa bbb ccc', 9)).toBe('aaa_bbb')
    expect(bestandsdeel('aaa bbb ccc', 7)).toBe('aaa_bbb')
    expect(bestandsdeel('aaabbbccc', 4)).toBe('aaab')
  })
})
