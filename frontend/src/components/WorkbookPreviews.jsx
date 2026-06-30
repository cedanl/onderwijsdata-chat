import { useState, useRef, useEffect } from 'react'

function UserWorkbookPreview({ wb }) {
  const answer = wb.messages?.find(m => m.role === 'assistant' && m.content)?.content || ''
  const preview = answer.replace(/[#*`|]/g, '').replace(/\n+/g, ' ').trim().slice(0, 180)
  const hasFigures = (wb.figures?.length ?? 0) > 0
  return (
    <div className="wb-user-preview">
      <div className="wb-user-preview-bars">
        {[40, 65, 55, 80, 70, 50].map((h, i) => (
          <div key={i} className="wb-user-preview-bar" style={{ height: `${h}%`, opacity: 0.15 + i * 0.1 }} />
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

export function BuiltinPreview() {
  const bars = [55, 70, 82, 88, 100]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#EFF6FF', '#F0FDFA', '#F0FDF4', '#FFF7ED'].map((c, i) => (
          <div key={i} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#2563EB','#0D9488','#22C55E','#F59E0B'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, i) => (
            <div key={i} className="wb-mini-bar" style={{ height: `${h}%` }} />
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

export function ArbeidsmarktPreview() {
  const bars = [42, 58, 72, 90, 68]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#FFF7ED', '#F0FDFA', '#EFF6FF', '#F0FDF4'].map((c, i) => (
          <div key={i} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#F59E0B','#0D9488','#2563EB','#22C55E'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, i) => (
            <div key={i} className="wb-mini-bar" style={{ height: `${h}%`, background: ['#F59E0B','#0D9488','#2563EB','#22C55E','#8B5CF6'][i] }} />
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

export default function WorkbookPreview({ wb }) {
  const [loaded, setLoaded] = useState(false)
  const wrapRef = useRef(null)
  const [scale, setScale] = useState(0.25)

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

  if (wb.builtin) return wb.id === '__builtin_arbeidsmarkt__' ? <ArbeidsmarktPreview /> : <BuiltinPreview />

  if (wb.messages) return <UserWorkbookPreview wb={wb} />

  return (
    <div ref={wrapRef} className="wb-preview-wrap">
      {!loaded && <div className="wb-preview-shimmer" />}
      <div
        className="wb-preview-frame-outer"
        style={{ transform: `scale(${scale})`, height: Math.ceil(155 / scale) }}
      >
        <iframe
          srcDoc={wb.htmlContent}
          sandbox="allow-scripts"
          onLoad={() => setLoaded(true)}
          style={{ width: 960, height: '100%', border: 'none' }}
          title={wb.title}
        />
      </div>
    </div>
  )
}
