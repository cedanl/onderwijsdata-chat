import { describe, it, expect } from 'vitest'
import { buildReportHtml } from '../reportHtml.js'

const fullSpec = {
  title: 'Instroom ROC van Flevoland 2018–2024',
  onderzoeksvraag: 'Hoe ontwikkelt de eerstejaars instroom van ROC van Flevoland zich over de jaren?',
  definities: [
    { begrip: 'Eerstejaars', definitie: 'Student die voor het eerst staat ingeschreven bij een opleiding' },
    { begrip: 'Instroom', definitie: 'Aantal nieuw ingeschreven studenten in een kalenderjaar' },
  ],
  beantwoordt: ['De jaarlijkse ontwikkeling van de instroom', 'Het aantal mbo-studenten per sector'],
  beantwoordt_niet: ['De internationale studentenmigratie', 'De arbeidsmarktuitstroom van gediplomeerden'],
  visualisaties: [
    {
      titel: 'Instroom per jaar',
      toelichting: 'De instroom stijgt gestaag, met een uitschieter in 2022.',
      figure_json: '{"data":[],"layout":{"title":"x"}}',
    },
  ],
  conclusie: 'De instroom is tussen 2018 en 2024 met **18%** gestegen.',
  bronnen: ['DUO — Instroom in het mbo (p01hoinges)', 'CBS — Regionale arbeidsmarktcijfers'],
  auteur: 'jansen',
  datum: '1 september 2026',
}

describe('buildReportHtml', () => {
  it('returns valid HTML with doctype and title', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<title>Instroom ROC van Flevoland 2018–2024</title>')
  })

  it('shows the research question prominently at the top', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Onderzoeksvraag')
    expect(html).toContain('Hoe ontwikkelt de eerstejaars instroom')
  })

  it('lists the chosen definitions', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Gekozen definities')
    expect(html).toContain('Eerstejaars')
    expect(html).toContain('Student die voor het eerst staat ingeschreven')
  })

  it('shows what the report does and does not answer', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Wat dit rapport wel beantwoordt')
    expect(html).toContain('De jaarlijkse ontwikkeling van de instroom')
    expect(html).toContain('Wat dit rapport niet beantwoordt')
    expect(html).toContain('De internationale studentenmigratie')
  })

  it('embeds visualisations with title, explanation and plotly figure', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Instroom per jaar')
    expect(html).toContain('De instroom stijgt gestaag')
    expect(html).toContain('plotly')
    expect(html).toContain('rp0')
  })

  it('renders a Conclusie heading with markdown', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Conclusie')
    expect(html).toContain('18%')
    expect(html).toContain('<strong>18%</strong>')
  })

  it('lists the sources', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('Bronnen')
    expect(html).toContain('DUO — Instroom in het mbo (p01hoinges)')
  })

  it('shows generation date and author', () => {
    const html = buildReportHtml(fullSpec)
    expect(html).toContain('1 september 2026')
    expect(html).toContain('jansen')
  })

  it('includes the instelling badge when provided', () => {
    const html = buildReportHtml(fullSpec, { instelling: 'Hogeschool Utrecht' })
    expect(html).toContain('Hogeschool Utrecht')
  })

  it('handles an empty spec gracefully', () => {
    const html = buildReportHtml({})
    expect(html).toContain('<!DOCTYPE html>')
  })

  it('escapes HTML to prevent XSS', () => {
    const evil = {
      title: '<img onerror=alert(1)>',
      onderzoeksvraag: '<script>alert("x")</script>',
      conclusie: 'nog <b>vet</b>',
      beantwoordt: ['<i>cursief</i>'],
      bronnen: ['<svg onload=alert(2)>'],
    }
    const html = buildReportHtml(evil, { instelling: '<b>evil</b>' })
    expect(html).not.toContain('<img onerror=alert(1)>')
    expect(html).not.toContain('<script>alert')
    expect(html).not.toContain('<svg onload=alert(2)>')
    expect(html).not.toContain('<b>evil</b>')
    expect(html).toContain('&lt;img onerror=alert(1)&gt;')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('&lt;svg onload=alert(2)&gt;')
    expect(html).toContain('&lt;b&gt;evil&lt;/b&gt;')
  })
})