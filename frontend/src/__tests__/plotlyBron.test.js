// #486: Plotly voor rapporten en dashboards komt van de eigen server, niet van cdn.plot.ly.
import { describe, it, expect } from 'vitest'
import { PLOTLY_URL, metEigenPlotly, plotlyScript, plotlyScripts } from '../plotlyBron'
import { kaartAlsSvgScript } from '../kaartRapport'

const CDN = '<script src="https://cdn.plot.ly/plotly-4.1.0.min.js"></script>'

describe('plotlyBron (#486)', () => {
  it('wijst naar een pad op de eigen server, niet naar een derde partij', () => {
    expect(PLOTLY_URL).toMatch(/^\//)
    expect(PLOTLY_URL).not.toMatch(/^https?:/)
    expect(PLOTLY_URL).toMatch(/plotly.*\.js$/)
    // Met het script dat een kaart zonder maplibre-worker tekent erachter (#642).
    expect(plotlyScript()).toBe(`<script src="${PLOTLY_URL}"></script>${kaartAlsSvgScript()}`)
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
    expect(nieuw.split('__kaartAlsSvg=true')).toHaveLength(2)
    expect(nieuw.indexOf(PLOTLY_URL)).toBeLessThan(nieuw.indexOf("Plotly.newPlot('rp0')"))
    expect(nieuw).toContain('<div id="rp1"></div>')
  })

  it('herschrijft een rapport met de volledige Plotly van een eerdere build naar die zonder maplibre (#660)', () => {
    expect(PLOTLY_URL).toContain('plotly-rapport')
    const kaartscript = kaartAlsSvgScript()
    const naKaart = `<head><script src="/assets/plotly.min-Ab12Cd34.js"></script>${kaartscript}</head><div id="k"></div>`
    const nieuw = metEigenPlotly(naKaart)
    expect(nieuw).not.toContain('plotly.min-Ab12Cd34')
    expect(nieuw).toBe(`<head><script src="${PLOTLY_URL}"></script>${kaartscript}</head><div id="k"></div>`)
    // Van vóór #642: nog zonder kaartscript; dat komt er één keer achter.
    const voorKaart = metEigenPlotly('<head><script src="/assets/plotly.min-Ab12Cd34.js"></script></head>')
    expect(voorKaart).toBe(`<head>${plotlyScript()}</head>`)
    expect(voorKaart.split(PLOTLY_URL)).toHaveLength(2)
    expect(voorKaart.split('__kaartAlsSvg=true')).toHaveLength(2)
  })

  it('laat HTML zonder Plotly en HTML van deze build met rust', () => {
    expect(metEigenPlotly('<p>alleen tekst</p>')).toBe('<p>alleen tekst</p>')
    expect(metEigenPlotly(null)).toBeNull()
    const eigen = `<head>${plotlyScript()}</head>`
    expect(metEigenPlotly(eigen)).toBe(eigen)
  })
})
