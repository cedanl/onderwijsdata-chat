// Plotly voor de HTML van rapporten en dashboards, zonder maplibre (#660). Een kaart in een rapport tekent sinds
// #642/#648 als SVG (kaartRapport.js zet `choroplethmap` om naar `choropleth`), dus de drie sporen op maplibre zijn
// daar dood gewicht: ongeveer 1,5 MB en een verwijzing naar cdn.jsdelivr.net (privacy F8, #486). De chat
// (LazyPlot.jsx) houdt de volledige Plotly. Deze Vite-plugin bundelt bij `vite build` met esbuild een los asset uit
// plotly.js/lib, met de aliassen en defines van plotly's eigen esbuild-config.js (de glsl- en css-plugins daaruit
// zijn niet nodig: deze sporen laden geen .glsl, en de enige CSS is die van maplibre); in dev serveert hij het op
// DEV_URL. package.json zet `to-px` op 1.0.1 (overrides), zoals plotly zelf: 1.1.0 meet bij het laden in
// document.body, en het rapport laadt Plotly in de head, vóór de body er is.
// Draait in Node (vite.config.js), niet in de browser; staat onder src/ omdat de Dockerfile alleen dat meekopieert.

// De sporen van plotly.js/lib/index.js, in die volgorde, zonder KAARTSPOREN. Een test houdt de lijst gelijk aan
// lib/index.js, zodat een nieuwe Plotly-versie met een nieuw spoor opvalt.
export const RAPPORTSPOREN = [
  'bar', 'box', 'heatmap', 'histogram', 'histogram2d', 'histogram2dcontour', 'contour', 'scatterternary', 'violin',
  'funnel', 'waterfall', 'image', 'pie', 'sunburst', 'treemap', 'icicle', 'funnelarea', 'scatter3d', 'surface',
  'isosurface', 'volume', 'mesh3d', 'cone', 'streamtube', 'scattergeo', 'choropleth', 'scattergl', 'splom',
  'parcoords', 'parcats', 'sankey', 'indicator', 'table', 'carpet', 'scattercarpet', 'contourcarpet', 'ohlc',
  'candlestick', 'scatterpolar', 'scatterpolargl', 'barpolar', 'scattersmith', 'quiver', 'calendars',
]

// Tekenen met maplibre: een worker vanaf een blob:-URL, die in de sandbox en vanaf schijf niet start (#642).
export const KAARTSPOREN = ['scattermap', 'choroplethmap', 'densitymap']

export const VIRTUEEL_ID = 'virtual:plotly-rapport'
export const DEV_URL = '/@plotly-rapport/plotly-rapport.min.js'
const OPGELOST_ID = `\0${VIRTUEEL_ID}`

export const plotlyRapportEntry = () => `var Plotly = require('plotly.js/lib/core');
Plotly.register([${RAPPORTSPOREN.map(s => `require('plotly.js/lib/${s}')`).join(', ')}]);
module.exports = Plotly;`

// registry.js laadt de CSS van maplibre bij het registreren van een kaartspoor; de bundel heeft die niet nodig.
const geenMaplibreCss = {
  name: 'geen-maplibre-css',
  setup(build) {
    build.onResolve({ filter: /^maplibre-gl\/dist\/maplibre-gl\.css$/ }, () => ({ path: 'leeg', namespace: 'leeg' }))
    build.onLoad({ filter: /.*/, namespace: 'leeg' }, () => ({ contents: '', loader: 'js' }))
  },
}

// De minified Plotly voor rapporten, als tekst. `resolveDir` is de map met node_modules (frontend/).
export async function bundelPlotlyRapport(resolveDir) {
  const { build } = await import('esbuild')
  const resultaat = await build({
    stdin: { contents: plotlyRapportEntry(), resolveDir, loader: 'js', sourcefile: 'plotly-rapport.js' },
    bundle: true,
    write: false,
    minify: true,
    format: 'iife',
    globalName: 'Plotly',
    target: 'es2016',
    legalComments: 'none',
    plugins: [geenMaplibreCss],
    alias: { regl: '@plotly/regl', stream: 'stream-browserify' },
    define: { global: 'window', 'define.amd': 'false', 'process.env.NODE_DEBUG': 'false' },
    logLevel: 'silent',
  })
  return resultaat.outputFiles[0].text
}

// `import url from 'virtual:plotly-rapport'`: in de build de URL van het asset (assets/plotly-rapport.min-<hash>.js,
// een jaar cachebaar), in dev en vitest DEV_URL. Vitest bundelt niets; dev pas bij de eerste aanvraag. De root van
// Vite (frontend/) is de map met node_modules.
export function plotlyRapport() {
  let bouw = false
  let root = null
  let dev = null
  return {
    name: 'plotly-rapport',
    configResolved(config) {
      bouw = config.command === 'build'
      root = config.root
    },
    resolveId(id) {
      return id === VIRTUEEL_ID ? OPGELOST_ID : null
    },
    async load(id) {
      if (id !== OPGELOST_ID) return null
      if (!bouw) return `export default ${JSON.stringify(DEV_URL)}`
      const ref = this.emitFile({ type: 'asset', name: 'plotly-rapport.min.js', source: await bundelPlotlyRapport(root) })
      return `export default import.meta.ROLLUP_FILE_URL_${ref}`
    },
    configureServer(server) {
      server.middlewares.use(DEV_URL, (_req, res, next) => {
        dev ??= bundelPlotlyRapport(root)
        dev.then(code => {
          res.setHeader('Content-Type', 'text/javascript')
          res.end(code)
        }, fout => {
          dev = null
          next(fout)
        })
      })
    },
  }
}
