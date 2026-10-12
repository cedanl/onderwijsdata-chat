// Plotly voor de HTML van rapporten en dashboards komt van de eigen server (#486, privacy M3/L1):
// de gebundelde plotly.js, door Vite als los asset uitgeleverd (/assets/plotly.min-<hash>.js, een
// jaar cachebaar). Vóór #486 laadde de opgeslagen HTML het script van cdn.plot.ly, waardoor elke
// kijker IP, user-agent en referrer naar een Amerikaanse CDN stuurde; en de CDN-versie moest met
// de hand gelijk blijven aan de gebundelde versie die de figuur-JSON maakt. Oude HTML wordt bij het
// tonen herschreven (metEigenPlotly); de download krijgt Plotly inline (offlineHtml.js).
import plotlyUrl from 'plotly.js/dist/plotly.min.js?url'

export const PLOTLY_URL = plotlyUrl

export const plotlyScript = () => `<script src="${PLOTLY_URL}"></script>`

// Het Plotly-script in opgeslagen HTML: de CDN van vóór #486, of een eerdere eigen build (andere hash).
export const PLOTLY_SCRIPT = /<script src="(?:https:\/\/cdn\.plot\.ly\/plotly-[\d.]+\.min\.js|[^"]*\/plotly[^"]*\.js)"><\/script>/g

export const plotlyScripts = html => String(html ?? '').match(PLOTLY_SCRIPT) || []

// Dezelfde HTML met het Plotly-script van deze build, één keer: oude rapporten noemden de CDN per grafiek.
export function metEigenPlotly(html) {
  if (!html || !plotlyScripts(html).length) return html
  let eerste = true
  return html.replace(PLOTLY_SCRIPT, () => {
    if (!eerste) return ''
    eerste = false
    return plotlyScript()
  })
}
