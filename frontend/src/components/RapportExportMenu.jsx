import { useEffect, useId, useRef, useState } from 'react'
import WorkbookDownload from './WorkbookDownload'
import WorkbookMarkdown from './WorkbookMarkdown'
import WorkbookPrint, { kanAfdrukken } from './WorkbookPrint'
import WorkbookWord from './WorkbookWord'
import { kanMarkdown } from '../rapportUitHtml'
import { useEscape } from '../hooks/useEscape'

// De exportformaten van een geopend rapport in de kopbalk op desktop: één knop "Downloaden" met een paneel in plaats
// van vier knoppen naast elkaar (HTML, Markdown, Word, PDF). Op een telefoon staan ze in het ⋯-menu
// (RapportNavActies). Disclosure-patroon, geen ARIA-menu: de formaten zijn gewone knoppen in tabvolgorde. Escape en
// een klik ernaast sluiten het paneel; een keuze niet, zodat "Word-document maken…" en een melding zichtbaar blijven.
// Het paneel blijft gemount (hidden): sluit iemand het tijdens een Word-download, dan blijft die en haar melding.
// printDoc: het rapport voor "Opslaan als PDF" (useReportFrame().printDoc); grafiekDoc: de grafieken voor Word.
export function heeftExport(workbook, printDoc) {
  return !workbook.builtin || kanMarkdown(String(workbook.htmlContent ?? '')) || kanAfdrukken(printDoc)
}

export default function RapportExportMenu({ workbook, save, printDoc = null, grafiekDoc = null }) {
  const [open, setOpen] = useState(false)
  const knopRef = useRef(null)
  const houderRef = useRef(null)
  const paneelId = useId()
  useEscape(open, () => { setOpen(false); knopRef.current?.focus() })

  useEffect(() => {
    if (!open) return
    function buiten(e) {
      if (!houderRef.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', buiten)
    return () => document.removeEventListener('mousedown', buiten)
  }, [open])

  if (!heeftExport(workbook, printDoc)) return null
  return (
    <div className="wb-export" ref={houderRef}>
      <button
        type="button" ref={knopRef} className="wb-download-btn wb-export-knop"
        aria-haspopup="true" aria-expanded={open} aria-controls={paneelId}
        onClick={() => setOpen(o => !o)}
      >
        Downloaden
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <div className="wb-export-paneel" id={paneelId} hidden={!open}>
        <WorkbookDownload workbook={workbook} save={save} />
        <WorkbookMarkdown workbook={workbook} save={save} />
        <WorkbookWord workbook={workbook} save={save} grafiekDoc={grafiekDoc} />
        <WorkbookPrint html={printDoc} />
      </div>
    </div>
  )
}
