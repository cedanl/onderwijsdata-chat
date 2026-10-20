import { useState, useRef, useEffect } from 'react'
import { BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL, getWorkbookType, isVolledig, loadWorkbook } from '../workbooks'
import { metThema } from '../reportThema'

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

function BuiltinPreview() {
  const bars = [55, 70, 82, 88, 100]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#EFF6FF', '#F0FDFA', '#F0FDF4', '#FFF7ED'].map((c, i) => (
          <div key={c} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#2563EB','#0D9488','#22C55E','#F59E0B'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, _i) => (
            <div key={h} className="wb-mini-bar" style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="wb-mini-line">
          <svg viewBox="0 0 60 40" preserveAspectRatio="none">
            <polyline points="0,38 15,30 30,18 45,10 60,4" fill="rgba(37,99,235,.12)" stroke="#2563EB" strokeWidth="2" />
            <polyline points="0,38 15,34 30,28 45,22 60,16" fill="none" stroke="#14B8A6" strokeWidth="1.5" strokeDasharray="3,2" />
          </svg>
        </div>
        <div className="wb-mini-donut-wrap">
          <div className="wb-mini-donut" />
        </div>
      </div>
    </div>
  )
}

function ArbeidsmarktPreview() {
  const bars = [42, 58, 72, 90, 68]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#FFF7ED', '#F0FDFA', '#EFF6FF', '#F0FDF4'].map((c, i) => (
          <div key={c} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#F59E0B','#0D9488','#2563EB','#22C55E'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, i) => (
            <div key={h} className="wb-mini-bar" style={{ height: `${h}%`, background: ['#F59E0B','#0D9488','#2563EB','#22C55E','#8B5CF6'][i] }} />
          ))}
        </div>
        <div className="wb-mini-line">
          <svg viewBox="0 0 60 40" preserveAspectRatio="none">
            <polyline points="0,32 15,28 30,20 45,14 60,10" fill="rgba(245,158,11,.12)" stroke="#F59E0B" strokeWidth="2" />
            <polyline points="0,36 15,33 30,29 45,25 60,22" fill="none" stroke="#0D9488" strokeWidth="1.5" strokeDasharray="3,2" />
          </svg>
        </div>
        <div className="wb-mini-donut-wrap">
          <div className="wb-mini-donut" style={{ background: 'conic-gradient(#F59E0B 0% 35%, #0D9488 35% 60%, #2563EB 60% 85%, #22C55E 85% 100%)' }} />
        </div>
      </div>
    </div>
  )
}

function NationaalPreview() {
  const bars = [100, 85, 72, 60, 48]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#EFF6FF','#F0FDF4','#FFF7ED'].map((c, i) => (
          <div key={c} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#2563EB','#22C55E','#F59E0B'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts" style={{ flexDirection: 'column', gap: 3, justifyContent: 'center' }}>
        {bars.map((w, i) => (
          <div key={i} style={{ height: 5, borderRadius: 2, background: `rgba(37,99,235,${0.3 + i * 0.12})`, width: `${w}%` }} />
        ))}
      </div>
    </div>
  )
}

// Near the viewport: a card this close to the screen loads its thumbnail before it scrolls in.
const IN_BEELD_MARGE = '300px'

// True while the element is on or near the screen. Without IntersectionObserver (old browser, tests)
// everything counts as in view, as before #633.
function useInBeeld(ref, aan) {
  const [inBeeld, setInBeeld] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (!aan || !el || typeof IntersectionObserver === 'undefined') return
    const obs = new IntersectionObserver(([entry]) => setInBeeld(entry.isIntersecting), { rootMargin: IN_BEELD_MARGE })
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref, aan])
  return inBeeld
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
  const [scale, setScale] = useState(0.25)
  const isRapport = !wb.builtin && !wb.messages && getWorkbookType(wb) === 'report'
  const inBeeld = useInBeeld(wrapRef, isRapport)
  const html = useRapportHtml(wb, isRapport && inBeeld)
  const toon = inBeeld && html != null
  // A frame scrolled out and back in is a new frame: the shimmer stays until it has loaded again.
  useEffect(() => { if (!toon) setLoaded(false) }, [toon])

  useEffect(() => {
    if (wb.builtin) return
    const el = wrapRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      setScale(entry.contentRect.width / 960)
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [wb.builtin])

  if (wb.builtin) {
    if (wb.id === BUILTIN_ARBEIDSMARKT.id) return <ArbeidsmarktPreview />
    if (wb.id === BUILTIN_NATIONAAL.id) return <NationaalPreview />
    return <BuiltinPreview />
  }

  if (wb.messages) return <UserWorkbookPreview wb={wb} />

  // Only a card on or near the screen holds an iframe (#633): `loading="lazy"` does nothing for a
  // srcdoc frame, and 81 of them at once crashed the tab. Off screen the card keeps its shimmer.
  return (
    <div ref={wrapRef} className="wb-preview-wrap">
      {!(toon && loaded) && isRapport && <div className="wb-preview-shimmer" />}
      {toon && (
        <div
          className="wb-preview-frame-outer"
          style={{ transform: `scale(${scale})`, height: Math.ceil(155 / scale) }}
        >
          {/* No scripts in a thumbnail (#427): each report would load and draw Plotly once per
              card, and with a hundred cards some stayed blank. The top of a report is static. */}
          <iframe
            srcDoc={metThema(html, mode)}
            sandbox=""
            loading="lazy"
            onLoad={() => setLoaded(true)}
            style={{ width: 960, height: '100%', border: 'none' }}
            title={wb.title}
          />
        </div>
      )}
    </div>
  )
}
