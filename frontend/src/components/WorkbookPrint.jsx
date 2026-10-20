import { PRINT_BERICHT } from '../reportHtml'

// "Opslaan als PDF" (#622): de browser drukt het rapport af (en biedt daar "Opslaan als PDF"); het rapport zelf
// zorgt voor A4, licht thema en passende grafieken (reportHtml.js, PRINT_CSS/PRINT_JS). Alleen voor een rapport dat
// het printbericht kent; een ouder rapport krijgt geen knop (de browser kan het nog wel zelf afdrukken).
//
// print() vraagt allow-modals, en dat geeft het rapport ook alert, confirm en prompt (#634). Het frame in de viewer
// krijgt het daarom niet: pas na een klik op de knop komt er een eigen, onzichtbaar printframe met allow-modals,
// zonder pop-ups en zonder de andere dialogen (`html` is useReportFrame().printDoc). Het frame heeft een opaque
// origin, dus de app stuurt het een bericht en het rapport drukt zelf af.
const PRINTFRAME_ID = 'edudata-printframe'

export function kanAfdrukken(html) {
  return typeof html === 'string' && html.includes(PRINT_BERICHT)
}

export function ruimPrintframeOp(doc = document) {
  doc.getElementById(PRINTFRAME_ID)?.remove()
}

export function stuurAfdrukken(html, doc = document) {
  if (!kanAfdrukken(html)) return null
  ruimPrintframeOp(doc)
  const frame = doc.createElement('iframe')
  frame.id = PRINTFRAME_ID
  frame.setAttribute('sandbox', 'allow-scripts allow-modals')
  frame.setAttribute('aria-hidden', 'true')
  frame.tabIndex = -1
  // Buiten beeld maar met een maat: Plotly tekent niet in een frame zonder breedte.
  frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1024px;height:768px;border:0'
  frame.addEventListener('load', () => frame.contentWindow?.postMessage(PRINT_BERICHT, '*'))
  frame.srcdoc = html
  doc.body.appendChild(frame)
  return frame
}

// De knop staat ook in het ⋯-menu op een telefoon, dat na de klik sluit: de viewer ruimt het printframe op.
export default function WorkbookPrint({ html, className = 'wb-download-btn' }) {
  if (!kanAfdrukken(html)) return null
  return (
    <button type="button" className={className} onClick={() => stuurAfdrukken(html)}>
      Opslaan als PDF
    </button>
  )
}
