import { PRINT_BERICHT } from '../reportHtml'

// "Opslaan als PDF" (#622): de browser drukt het rapport af (en biedt daar "Opslaan als PDF"); het rapport zelf
// zorgt voor A4, licht thema en passende grafieken (reportHtml.js, PRINT_CSS/PRINT_JS). Het frame heeft een
// opaque origin, dus de app stuurt een bericht en het rapport roept print() aan. Alleen voor een rapport dat
// het bericht kent; een ouder rapport krijgt geen knop (de browser kan het nog wel zelf afdrukken).
export function kanAfdrukken(html) {
  return typeof html === 'string' && html.includes(PRINT_BERICHT)
}

export function stuurAfdrukken(frame) {
  frame?.contentWindow?.postMessage(PRINT_BERICHT, '*')
}

export default function WorkbookPrint({ frameRef, html, className = 'wb-download-btn' }) {
  if (!kanAfdrukken(html)) return null
  return (
    <button type="button" className={className} onClick={() => stuurAfdrukken(frameRef?.current)}>
      Opslaan als PDF
    </button>
  )
}
