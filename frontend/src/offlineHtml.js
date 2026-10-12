// A downloaded report or dashboard must open without a network (#405, UX N11). The
// stored HTML loads Plotly from our own server (#486), which keeps it small enough for
// storage; the download gets Plotly inline instead, fetched from that same asset only
// when the user downloads, so the build carries Plotly once.
import { PLOTLY_SCRIPT, PLOTLY_URL, plotlyScripts } from './plotlyBron'

const bundledPlotly = () => fetch(PLOTLY_URL).then(r => {
  if (!r.ok) throw new Error(`Plotly niet geladen (${r.status})`)
  return r.text()
})

export async function inlinePlotly(html, loadPlotly = bundledPlotly) {
  if (!plotlyScripts(html).length) return html
  // Inside an inline script, '</script' would end the element early.
  const source = (await loadPlotly()).replace(/<\/script/gi, '<\\/script')
  let first = true
  return html.replace(PLOTLY_SCRIPT, () => {
    if (!first) return ''
    first = false
    return `<script>${source}</script>`
  })
}
