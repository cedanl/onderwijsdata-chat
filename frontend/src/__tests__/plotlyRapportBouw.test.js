// #660: rapporten en dashboards krijgen een Plotly zonder maplibre; de chat houdt de volledige.
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { JSDOM, VirtualConsole } from 'jsdom'
import { beforeAll, describe, expect, it } from 'vitest'
import {
  DEV_URL, KAARTSPOREN, RAPPORTSPOREN, VIRTUEEL_ID, bundelPlotlyRapport, plotlyRapport, plotlyRapportEntry,
} from '../plotlyRapportBouw'
import { inlinePlotly } from '../offlineHtml'

const require = createRequire(import.meta.url)
const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const VOLLEDIG = readFileSync(require.resolve('plotly.js/dist/plotly.min.js'), 'utf8')
const MB = 1_000_000

// Laadt de bundel zoals het rapport dat doet: in de head, voordat er een body is.
const lees = code => {
  const dom = new JSDOM('<!doctype html><head></head>', { runScripts: 'outside-only', virtualConsole: new VirtualConsole() })
  dom.window.document.body.remove()
  dom.window.eval(code)
  return dom.window.Plotly
}

describe('sporenlijst (#660)', () => {
  it('volgt plotly.js/lib/index.js: elk spoor zit in de rapportbundel of is een kaartspoor', () => {
    const index = readFileSync(require.resolve('plotly.js/lib/index.js'), 'utf8')
    const sporen = [...index.matchAll(/require\('\.\/(\w+)'\)/g)].map(m => m[1]).filter(s => s !== 'core')
    expect(sporen.filter(s => !KAARTSPOREN.includes(s))).toEqual(RAPPORTSPOREN)
    expect(KAARTSPOREN.every(s => sporen.includes(s))).toBe(true)
  })

  it('laadt geen kaartspoor en geen maplibre in de entry', () => {
    const entry = plotlyRapportEntry()
    expect(entry).toContain("require('plotly.js/lib/core')")
    for (const s of KAARTSPOREN) expect(entry).not.toContain(`lib/${s}'`)
    expect(entry).not.toContain('maplibre')
  })
})

describe('Vite-plugin plotly-rapport (#660)', () => {
  it('geeft in dev en vitest een eigen pad, zonder te bundelen', async () => {
    const plugin = plotlyRapport()
    plugin.configResolved({ command: 'serve', root: ROOT })
    const id = plugin.resolveId(VIRTUEEL_ID)
    expect(id).toBeTruthy()
    expect(plugin.resolveId('plotly.js')).toBeNull()
    expect(await plugin.load(id)).toBe(`export default ${JSON.stringify(DEV_URL)}`)
    expect(await plugin.load('iets-anders')).toBeNull()
  })

  it('zendt in de build een asset uit met plotly in de naam, en verwijst ernaar', async () => {
    const plugin = plotlyRapport()
    plugin.configResolved({ command: 'build', root: ROOT })
    const uitgezonden = []
    const context = { emitFile: f => (uitgezonden.push(f), 'ref1') }
    expect(await plugin.load.call(context, plugin.resolveId(VIRTUEEL_ID))).toBe('export default import.meta.ROLLUP_FILE_URL_ref1')
    expect(uitgezonden).toHaveLength(1)
    expect(uitgezonden[0]).toMatchObject({ type: 'asset', name: 'plotly-rapport.min.js' })
    expect(uitgezonden[0].source).toContain('Plotly')
  }, 60_000)
})

describe('de rapportbundel (#660)', () => {
  let bundel
  beforeAll(async () => {
    bundel = await bundelPlotlyRapport(ROOT)
  }, 60_000)

  it('heeft geen maplibre en geen cdn.jsdelivr, en is ruim 1 MB kleiner dan de volledige Plotly', () => {
    expect(bundel).not.toContain('cdn.jsdelivr')
    expect(bundel).not.toMatch(/maplibre/i)
    expect(VOLLEDIG).toContain('cdn.jsdelivr')
    expect(bundel.length).toBeLessThan(VOLLEDIG.length - MB)
  })

  it('laadt in de head, vóór de body, en kent de sporen van rapporten en dashboards, niet de kaartsporen', () => {
    const Plotly = lees(bundel)
    const sporen = Object.keys(Plotly.PlotSchema.get().traces)
    for (const s of ['bar', 'scatter', 'histogram', 'pie', 'heatmap', 'scattergeo', 'choropleth']) expect(sporen).toContain(s)
    for (const s of KAARTSPOREN) expect(sporen).not.toContain(s)
    expect(Plotly.version).toBe(lees(VOLLEDIG).version)
    // Twee keer de hele Plotly in jsdom: 1,3 s hier, maar op de CI-runner liep dit tegen de 5 s van vitest (#796).
  }, 30_000)

  it('maakt de download van een rapport met een kaart ruim 1 MB kleiner, zonder cdn.jsdelivr', async () => {
    const html = '<head><script src="/assets/plotly.min-abc.js"></script></head><div id="k"></div>'
      + '<script>Plotly.newPlot("k",[{type:"choroplethmap"},{type:"bar"}])</script>'
    const klein = await inlinePlotly(html, async () => bundel)
    const groot = await inlinePlotly(html, async () => VOLLEDIG)
    expect(klein).not.toContain('cdn.jsdelivr')
    expect(klein).toContain('__kaartAlsSvg=true')
    expect(klein.length).toBeLessThan(groot.length - MB)
  })
})
