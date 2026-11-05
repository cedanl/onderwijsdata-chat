import { useState, useRef, useEffect, useMemo } from 'react'
import { getWorkbookType, isVolledig, loadWorkbook } from '../workbooks'
import { useInBeeld, useMiniatuurSchaal, MINIATUUR_BREEDTE, MINIATUUR_HOOGTE } from '../hooks/useMiniatuur'
import { metThema } from '../reportThema'
import { zonderScripts } from '../zonderScripts'

function UserWorkbookPreview({ wb }) {
  const answer = wb.messages?.find(m => m.role === 'assistant' && m.content)?.content || ''
  const preview = answer.replace(/[#*`|]/g, '').replace(/\n+/g, ' ').trim().slice(0, 180)
  const hasFigures = (wb.figures?.length ?? 0) > 0
  return (
    <div className="wb-user-preview">
      <div className="wb-user-preview-bars">
        {[40, 65, 55, 80, 70, 50].map((h, i) => (
          <div key={h} className="wb-user-preview-bar" style={{ height: `${h}%`, opacity: 0.15 + i * 0.1 }} />
        ))}
      </div>
      {hasFigures && (
        <div className="wb-user-preview-chart-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
      )}
      <p className="wb-user-preview-text">{preview}</p>
    </div>
  )
}

// The report's HTML for a thumbnail on screen: from the workbook when it has it, else fetched (#633).
function useRapportHtml(wb, inBeeld) {
  const eigen = isVolledig(wb) ? wb.htmlContent : null
  const [geladen, setGeladen] = useState(null)
  useEffect(() => {
    if (!inBeeld || eigen != null || geladen?.id === wb.id) return
    let weg = false
    loadWorkbook(wb.id).then(full => { if (!weg) setGeladen({ id: wb.id, html: full.htmlContent }) }).catch(() => {})
    return () => { weg = true }
  }, [inBeeld, eigen, geladen, wb.id])
  return eigen ?? (geladen?.id === wb.id ? geladen.html : null)
}

// mode: the app's theme choice; a report thumbnail follows it like the report itself (#568).
export default function WorkbookPreview({ wb, mode }) {
  const [loaded, setLoaded] = useState(false)
  const wrapRef = useRef(null)
  const isRapport = !wb.messages && getWorkbookType(wb) === 'report'
  const inBeeld = useInBeeld(wrapRef, isRapport)
  const scale = useMiniatuurSchaal(wrapRef, isRapport)
  const html = useRapportHtml(wb, isRapport && inBeeld)
  // Once per report and theme, not on every render of a long gallery.
  const srcDoc = useMemo(() => metThema(zonderScripts(html), mode), [html, mode])
  const toon = inBeeld && html != null
  // A frame scrolled out and back in is a new frame: the shimmer stays until it has loaded again.
  useEffect(() => { if (!toon) setLoaded(false) }, [toon])

  if (wb.messages) return <UserWorkbookPreview wb={wb} />

  // Only a card on or near the screen holds an iframe (#633): `loading="lazy"` does nothing for a
  // srcdoc frame, and 81 of them at once crashed the tab. Off screen the card keeps its shimmer.
  return (
    <div ref={wrapRef} className="wb-preview-wrap">
      {!(toon && loaded) && isRapport && <div className="wb-preview-shimmer" />}
      {toon && (
        <div
          className="wb-preview-frame-outer"
          style={{ transform: `scale(${scale})`, height: Math.ceil(MINIATUUR_HOOGTE / scale) }}
        >
          {/* No scripts in a thumbnail (#427): each report would load and draw Plotly once per
              card, and with a hundred cards some stayed blank. The top of a report is static.
              sandbox="" blocks them; the srcdoc leaves them out too, so the console stays free of
              "Blocked script execution" lines (#654). */}
          <iframe
            srcDoc={srcDoc}
            sandbox=""
            loading="lazy"
            onLoad={() => setLoaded(true)}
            style={{ width: MINIATUUR_BREEDTE, height: '100%', border: 'none' }}
            title={wb.title}
          />
        </div>
      )}
    </div>
  )
}
