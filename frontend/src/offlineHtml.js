// A downloaded report or dashboard must open without a network (#405, UX N11). The
// stored HTML loads Plotly from the CDN, which keeps it small enough for storage; the
// download gets Plotly inline instead, loaded only when the user downloads.
const CDN_SCRIPT = /<script src="https:\/\/cdn\.plot\.ly\/plotly-[\d.]+\.min\.js"><\/script>/g

const bundledPlotly = () => import('plotly.js/dist/plotly.min.js?raw').then(m => m.default)

export async function inlinePlotly(html, loadPlotly = bundledPlotly) {
  if (!html?.includes('cdn.plot.ly/plotly-')) return html
  // Inside an inline script, '</script' would end the element early.
  const source = (await loadPlotly()).replace(/<\/script/gi, '<\\/script')
  let first = true
  return html.replace(CDN_SCRIPT, () => {
    if (!first) return ''
    first = false
    return `<script>${source}</script>`
  })
}
