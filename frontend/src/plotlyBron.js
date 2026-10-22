// Plotly voor de HTML van rapporten en dashboards komt van de eigen server (#486, privacy M3/L1):
// een eigen build van plotly.js zonder maplibre, door Vite als los asset uitgeleverd
// (/assets/plotly-rapport.min-<hash>.js, een jaar cachebaar; plotlyRapportBouw.js, #660). Vóór #486
// laadde de opgeslagen HTML het script van cdn.plot.ly, waardoor elke kijker IP, user-agent en
// referrer naar een Amerikaanse CDN stuurde; en de CDN-versie moest met de hand gelijk blijven aan
// de gebundelde versie die de figuur-JSON maakt. Oude HTML (CDN of een eerdere eigen build) wordt
// bij het tonen herschreven (metEigenPlotly); de download krijgt Plotly inline (offlineHtml.js).
import plotlyUrl from 'virtual:plotly-rapport'
import { heeftKaartAlsSvg, kaartAlsSvgScript } from './kaartRapport'

export const PLOTLY_URL = plotlyUrl

// Met daarachter het script dat een kaart zonder maplibre-worker tekent (kaartRapport.js, #642).
export const plotlyScript = () => `<script src="${PLOTLY_URL}"></script>${kaartAlsSvgScript()}`

// Het Plotly-script in opgeslagen HTML: de CDN van vóór #486, of een eerdere eigen build (andere hash).
export const PLOTLY_SCRIPT = /<script src="(?:https:\/\/cdn\.plot\.ly\/plotly-[\d.]+\.min\.js|[^"]*\/plotly[^"]*\.js)"><\/script>/g

export const plotlyScripts = html => String(html ?? '').match(PLOTLY_SCRIPT) || []

// Dezelfde HTML met het Plotly-script van deze build, één keer: oude rapporten noemden de CDN per grafiek.
export function metEigenPlotly(html) {
  if (!html || !plotlyScripts(html).length) return html
  let eerste = true
  const script = heeftKaartAlsSvg(html) ? `<script src="${PLOTLY_URL}"></script>` : plotlyScript()
  return html.replace(PLOTLY_SCRIPT, () => {
    if (!eerste) return ''
    eerste = false
    return script
  })
}
