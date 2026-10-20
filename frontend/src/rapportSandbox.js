// Opgeslagen rapport-HTML is onvertrouwd (#634): de server bewaart wat de client stuurt, en op een gedeeld account
// opent iedereen elkaars rapporten (#488). De app zet daarom zelf de grenzen om elk rapport, ook om een oud rapport:
// - het frame in de viewer heeft alleen allow-scripts (WorkbookViewer.jsx): geen dialogen, geen pop-ups;
// - een Content-Security-Policy vooraan in de HTML, in het frame én in de download: scripts alleen inline of van de
//   eigen server (Plotly, #486), geen verbindingen, formulieren of frames;
// - een link in het rapport gaat via de app (LINK_JS, openRapportLink), want het frame mag zelf geen tab openen;
// - afdrukken gebeurt in een eigen frame met allow-modals, zonder alert/confirm/prompt (WorkbookPrint.jsx).
import { FRAME_BRON } from './reportFrame'

export function rapportCsp(scriptBron = '') {
  return [
    "default-src 'none'",
    `script-src 'unsafe-inline'${scriptBron ? ` ${scriptBron}` : ''}`,
    "style-src 'unsafe-inline'",
    'img-src data: blob:',
    'font-src data:',
    "connect-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
    "frame-src 'none'",
    "child-src 'none'",
  ].join('; ')
}

const DOCTYPE = /^\s*<!doctype[^>]*>/i

// De policy staat vóór alles wat het rapport zelf meebrengt: een script dat eerder stond, liep anders al vrij. Een
// <meta> vóór <html> komt in <head>, en de klasse op het latere <html> (reportThema.js) blijft gewoon staan.
// `vooraf` is HTML van de app die direct na de policy moet lopen (GEEN_DIALOGEN_JS).
export function metCsp(html, { scriptBron = '', vooraf = '' } = {}) {
  if (!html) return html
  const meta = `<meta http-equiv="Content-Security-Policy" content="${rapportCsp(scriptBron)}">`
  return `<!DOCTYPE html>${meta}${vooraf}${String(html).replace(DOCTYPE, '')}`
}

// Het frame mag geen tab openen; een klik op een link vraagt het de app. Achteraan, zoals de probe in reportFrame.js.
const LINK_JS = `<script>document.addEventListener('click', function (ev) {
  var a = ev.target && ev.target.closest && ev.target.closest('a[href]')
  if (!a || a.getAttribute('href').charAt(0) === '#') return
  ev.preventDefault()
  parent.postMessage({ bron: '${FRAME_BRON}', link: a.href }, '*')
}, true)</script>`

export const metLinkDoorgifte = html => `${html ?? ''}${LINK_JS}`

// Opent de link uit een bericht van het rapportframe, als het een gewone webadres is en de gebruiker net klikte: een
// script in het rapport dat zelf berichten stuurt, opent zo geen tabs (de klik in het frame activeert ook de app).
// Geeft true als het bericht een linkvraag was.
export function openRapportLink(event, frameWindow, open = window.open) {
  if (!frameWindow || event.source !== frameWindow) return false
  const data = event.data
  if (data?.bron !== FRAME_BRON || typeof data.link !== 'string') return false
  let url
  try { url = new URL(data.link) } catch { return true }
  if (!['https:', 'http:'].includes(url.protocol)) return true
  if (navigator.userActivation && !navigator.userActivation.isActive) return true
  open(url.href, '_blank', 'noopener,noreferrer')
  return true
}

// Voor het printframe, dat allow-modals nodig heeft voor print(): de andere dialogen bestaan daar niet. Niet te
// overschrijven of te wissen; een kindframe om ze terug te halen houdt frame-src 'none' tegen.
export const GEEN_DIALOGEN_JS = `<script>['alert', 'confirm', 'prompt'].forEach(function (k) {
  Object.defineProperty(window, k, { value: function () { return k === 'confirm' ? false : null }, writable: false, configurable: false })
})</script>`
