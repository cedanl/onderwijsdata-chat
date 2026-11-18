// De grafieken van een rapport als PNG, voor "Download als Word" (#1038). Het rapport staat in een sandbox-frame met
// een opaque origin (#634): de app komt niet bij Plotly in dat frame. Net als bij afdrukken (WorkbookPrint.jsx) komt
// er daarom na de klik een eigen, onzichtbaar frame, met alleen allow-scripts en dezelfde CSP als de viewer, in het
// lichte thema (useReportFrame().grafiekDoc). Een script van de app, achteraan in dat frame (GRAFIEK_JS), antwoordt op
// een vraag van de app met per visualisatie een PNG van Plotly.toImage, of null. De app neemt alleen een antwoord van
// dat eigen frame, met FRAME_BRON en het id van de vraag, en alleen data-URL's van een PNG. Een script in het rapport
// kan zelf ook antwoorden; dan staan zijn afbeeldingen alleen in het eigen document van de gebruiker, en de server
// neemt alleen een geldige PNG (tools/rapport_docx/afbeeldingen.py).
import { FRAME_BRON } from './reportFrame'
import { PRINT_BREEDTE } from './reportHtml'

export const GRAFIEK_VRAAG = 'grafieken'
// De grenzen van de server (afbeeldingen.py); het hele verzoek moet ook onder MAX_REQUEST_BYTES (4 MiB) blijven.
export const MAX_GRAFIEKEN = 20
export const MAX_GRAFIEK_BYTES = 2 * 1024 * 1024
export const MAX_TOTAAL_BYTES = 3.5 * 1024 * 1024
// Plotly is een paar MB; zonder antwoord binnen deze tijd gaat het document zonder grafieken.
export const GRAFIEK_TIMEOUT_MS = 20000
const MAX_HOOGTE = 900
const PNG_DATA_URL = 'data:image/png;base64,'

// Op de breedte van een A4-kolom, zoals bij afdrukken; scale 2 voor een scherpe afbeelding in Word.
const GRAFIEK_JS = `<script>window.addEventListener('message', function (ev) {
  var d = ev.data
  if (ev.source !== window.parent || !d || d.bron !== '${FRAME_BRON}' || d.vraag !== '${GRAFIEK_VRAAG}') return
  function antwoord(grafieken) { parent.postMessage({ bron: '${FRAME_BRON}', id: d.id, grafieken: grafieken }, '*') }
  function beeld(vis) {
    var e = vis.querySelector('.js-plotly-plot')
    if (!e || !window.Plotly) return null
    var h = Math.min(Math.round(e.getBoundingClientRect().height) || 360, ${MAX_HOOGTE})
    return Plotly.toImage(e, { format: 'png', scale: 2, width: ${PRINT_BREEDTE}, height: h }).catch(function () { return null })
  }
  function maak() {
    Promise.all(Array.prototype.map.call(document.querySelectorAll('.vis'), beeld)).then(antwoord, function () { antwoord([]) })
  }
  if (document.readyState === 'complete') maak(); else window.addEventListener('load', maak)
})</script>`

export const metGrafiekVraag = html => `${html ?? ''}${GRAFIEK_JS}`

// De PNG's uit een bericht van het grafiekframe, of null voor elk ander bericht. Wat geen PNG-data-URL is, wordt null.
export function grafiekAntwoord(event, frameWindow, id) {
  if (!frameWindow || event.source !== frameWindow) return null
  const data = event.data
  if (data?.bron !== FRAME_BRON || data.id !== id || !Array.isArray(data.grafieken)) return null
  return data.grafieken.map(g => (typeof g === 'string' && g.startsWith(PNG_DATA_URL) ? g : null))
}

const nieuwId = () => (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : String(Math.random()).slice(2))

// Vraagt het rapport (`srcDoc`, al met CSP, licht thema en GRAFIEK_JS) om zijn grafieken. Geeft per visualisatie een
// data-URL of null, of [] als het frame niet op tijd antwoordt. Het frame gaat daarna weg.
export function vraagGrafieken(srcDoc, { doc = document, timeoutMs = GRAFIEK_TIMEOUT_MS } = {}) {
  return new Promise(resolve => {
    const win = doc.defaultView
    const id = nieuwId()
    const frame = doc.createElement('iframe')
    frame.setAttribute('sandbox', 'allow-scripts')
    frame.setAttribute('aria-hidden', 'true')
    frame.tabIndex = -1
    // Buiten beeld maar met een maat: Plotly tekent niet in een frame zonder breedte.
    frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1024px;height:768px;border:0'
    let timer = null
    function klaar(grafieken) {
      win.removeEventListener('message', opBericht)
      clearTimeout(timer)
      frame.remove()
      resolve(grafieken)
    }
    function opBericht(event) {
      const grafieken = grafiekAntwoord(event, frame.contentWindow, id)
      if (grafieken) klaar(grafieken)
    }
    win.addEventListener('message', opBericht)
    timer = setTimeout(() => klaar([]), timeoutMs)
    frame.addEventListener('load', () => frame.contentWindow?.postMessage({ bron: FRAME_BRON, vraag: GRAFIEK_VRAAG, id }, '*'))
    frame.srcdoc = srcDoc
    doc.body.appendChild(frame)
  })
}

function pngBlob(dataUrl) {
  try {
    const binair = atob(dataUrl.slice(PNG_DATA_URL.length))
    return new Blob([Uint8Array.from(binair, teken => teken.charCodeAt(0))], { type: 'image/png' })
  } catch {
    return null
  }
}

// Het formulier voor de server: `grafiek-<n>` per visualisatie n, binnen de grenzen van de server. Wat er niet in
// past of niet te lezen is, blijft weg; het document zegt daar "Grafiek niet beschikbaar". `mee` is het aantal dat meegaat.
export function grafiekFormulier(grafieken) {
  const form = new FormData()
  let mee = 0
  let totaal = 0
  grafieken.forEach((dataUrl, i) => {
    const blob = dataUrl ? pngBlob(dataUrl) : null
    if (!blob || mee === MAX_GRAFIEKEN || blob.size > MAX_GRAFIEK_BYTES || totaal + blob.size > MAX_TOTAAL_BYTES) return
    form.append(`grafiek-${i}`, blob, `grafiek-${i}.png`)
    mee += 1
    totaal += blob.size
  })
  return { form, mee }
}
