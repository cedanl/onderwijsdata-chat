// #486: Plotly voor rapporten en dashboards komt van de eigen server, niet van cdn.plot.ly.
import { describe, it, expect } from 'vitest'
import { PLOTLY_URL, metEigenPlotly, plotlyScript, plotlyScripts } from '../plotlyBron'

const CDN = '<script src="https://cdn.plot.ly/plotly-4.1.0.min.js"></script>'

describe('plotlyBron (#486)', () => {
  it('wijst naar een pad op de eigen server, niet naar een derde partij', () => {
    expect(PLOTLY_URL).toMatch(/^\//)
    expect(PLOTLY_URL).not.toMatch(/^https?:/)
    expect(PLOTLY_URL).toMatch(/plotly.*\.js$/)
    expect(plotlyScript()).toBe(`<script src="${PLOTLY_URL}"></script>`)
  })

  it('herkent het script van de CDN en dat van een eigen build', () => {
    expect(plotlyScripts(`<head>${CDN}</head>`)).toHaveLength(1)
    expect(plotlyScripts('<script src="/assets/plotly.min-abc123.js"></script>')).toHaveLength(1)
    expect(plotlyScripts('<script src="/assets/index-abc123.js"></script><p>tekst</p>')).toHaveLength(0)
    expect(plotlyScripts(null)).toHaveLength(0)
  })

  it('herschrijft een oud rapport naar de eigen Plotly, één keer, op de plek van de eerste', () => {
    const oud = `<body>${CDN}<div id="rp0"></div><script>Plotly.newPlot('rp0')</script>${CDN}<div id="rp1"></div></body>`
    const nieuw = metEigenPlotly(oud)
    expect(nieuw).not.toContain('cdn.plot.ly')
    expect(nieuw.match(/<script src=/g)).toHaveLength(1)
    expect(nieuw.indexOf(PLOTLY_URL)).toBeLessThan(nieuw.indexOf("Plotly.newPlot('rp0')"))
    expect(nieuw).toContain('<div id="rp1"></div>')
  })

  it('laat HTML zonder Plotly en HTML van deze build met rust', () => {
    expect(metEigenPlotly('<p>alleen tekst</p>')).toBe('<p>alleen tekst</p>')
    expect(metEigenPlotly(null)).toBeNull()
    const eigen = `<head>${plotlyScript()}</head>`
    expect(metEigenPlotly(eigen)).toBe(eigen)
  })
})
