import { useState, useRef, useEffect } from 'react'
import { Bar, Line, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { BUILTIN, getWorkbooks, deleteWorkbook } from '../workbooks'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function DashboardPage({ setPage }) {
  const [userWorkbooks, setUserWorkbooks] = useState(getWorkbooks)
  const [selected, setSelected] = useState(null)

  const all = [BUILTIN, ...userWorkbooks]

  const handleDelete = (id) => {
    deleteWorkbook(id)
    setUserWorkbooks(getWorkbooks())
    if (selected?.id === id) setSelected(null)
  }

  if (selected) {
    return (
      <div className="wb-viewer">
        <div className="wb-viewer-bar">
          <button className="wb-back-btn" onClick={() => setSelected(null)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Werkboeken
          </button>
          <span className="wb-viewer-title">{selected.title}</span>
          <div />
        </div>
        <div className="wb-viewer-content">
          {selected.builtin
            ? <InlineDashboard />
            : <iframe className="wb-iframe" srcDoc={selected.htmlContent} title={selected.title} sandbox="allow-scripts" />
          }
        </div>
      </div>
    )
  }

  return (
    <div className="wb-gallery-page">
      <div className="wb-gallery-header">
        <div>
          <div className="wb-gallery-title">Werkboeken</div>
          <div className="wb-gallery-sub">{all.length} werkboek{all.length !== 1 ? 'en' : ''}</div>
        </div>
        {setPage && (
          <button className="btn-primary" onClick={() => setPage('chat')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Genereer vanuit chat
          </button>
        )}
      </div>

      <div className="wb-grid">
        {all.map(wb => (
          <div key={wb.id} className="wb-card" onClick={() => setSelected(wb)}>
            <div className="wb-card-thumb">
              <WorkbookPreview wb={wb} />
              {wb.builtin && <span className="wb-builtin-badge">Voorbeeld</span>}
            </div>
            <div className="wb-card-body">
              <div className="wb-card-title">{wb.title}</div>
              <div className="wb-card-desc">{wb.description}</div>
              <div className="wb-card-footer">
                <span className="wb-card-date">{formatDate(wb.createdAt)}</span>
                {!wb.builtin && (
                  <button
                    className="wb-delete-btn"
                    title="Verwijder"
                    onClick={e => { e.stopPropagation(); handleDelete(wb.id) }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {setPage && (
          <button className="wb-new-card" onClick={() => setPage('chat')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Nieuw werkboek</span>
            <small>Genereer vanuit een gesprek</small>
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Workbook preview thumbnails ──────────────────────────────────────────────

function WorkbookPreview({ wb }) {
  const [loaded, setLoaded] = useState(false)
  const wrapRef = useRef(null)
  const [scale, setScale] = useState(0.25)

  // Recalculate scale when the container resizes so the iframe fills the width
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

  if (wb.builtin) return <BuiltinPreview />

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

function BuiltinPreview() {
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

// ─── Builtin demo dashboard ────────────────────────────────────────────────────

const CHART_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { display: false } }, y: { grid: { color: '#F3F4F6' } } },
}

function InlineDashboard() {
  const KPI_DATA = [
    { label: 'Totaal inschrijvingen', value: '4.832', trend: '+6,3%', color: '#EFF6FF', iconColor: '#2563EB' },
    { label: 'Diplomarendement 4jr', value: '71,4%', trend: '+2,1 pp', color: '#F0FDFA', iconColor: '#0D9488' },
    { label: 'VSV-percentage', value: '3,8%', trend: '-0,4 pp', color: '#F0FDF4', iconColor: '#22C55E' },
    { label: 'Arbeidsmarktplaatsing', value: '84,2%', trend: '+1,8 pp', color: '#FFF7ED', iconColor: '#F59E0B' },
  ]
  const instroom = {
    labels: ['2020', '2021', '2022', '2023', '2024'],
    datasets: [{ data: [3912, 4087, 4398, 4545, 4832], backgroundColor: '#2563EB', borderRadius: 6 }],
  }
  const rendement = {
    labels: ['Informatica', 'Verpleegkunde', 'Bedrijfskunde', 'Werktuigbouw', 'Communicatie'],
    datasets: [
      { label: 'Uw instelling', data: [68.3, 74.2, 64.8, 71.4, 72.1], backgroundColor: '#2563EB', borderRadius: 4 },
      { label: 'Regionaal gem.', data: [65.1, 71.8, 67.3, 69.2, 70.4], backgroundColor: '#DBEAFE', borderRadius: 4 },
    ],
  }
  const herkomst = {
    labels: ['Groot-Amsterdam', 'Noord-Holland', 'Flevoland', 'Utrecht', 'Buitenland'],
    datasets: [{ data: [52.4, 21.3, 11.2, 8.7, 6.4], backgroundColor: ['#2563EB', '#3B82F6', '#93C5FD', '#DBEAFE', '#EFF6FF'], borderWidth: 0 }],
  }
  const trend = {
    labels: ['2020', '2021', '2022', '2023', '2024'],
    datasets: [
      { label: 'Voltijd', data: [3241, 3389, 3618, 3724, 3901], borderColor: '#2563EB', backgroundColor: 'rgba(37,99,235,.08)', fill: true, tension: 0.3, pointRadius: 4 },
      { label: 'Deeltijd', data: [487, 501, 538, 561, 612], borderColor: '#14B8A6', backgroundColor: 'transparent', fill: false, tension: 0.3, pointRadius: 4 },
    ],
  }

  return (
    <div className="dashboard-content" style={{ padding: 24 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <span className="meta-badge live">● Live</span>
        <span className="meta-badge date">Peildatum: 1 okt 2024</span>
        <span className="meta-badge date">Demo data — niet op beleid baseren</span>
      </div>
      <div className="kpi-grid">
        {KPI_DATA.map(k => (
          <div key={k.label} className="kpi-card">
            <div className="kpi-card-header">
              <span className="kpi-label">{k.label}</span>
              <div className="kpi-icon" style={{ background: k.color }}>
                <svg viewBox="0 0 24 24" fill="none" stroke={k.iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
                </svg>
              </div>
            </div>
            <div className="kpi-value">{k.value}</div>
            <div className="kpi-trend up">↑ {k.trend} t.o.v. vorig jaar</div>
          </div>
        ))}
      </div>
      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-header"><div><div className="chart-title">Instroom per jaar</div><div className="chart-sub">Totaal inschrijvingen 2020–2024</div></div></div>
          <div style={{ height: 200 }}><Bar data={instroom} options={CHART_OPTS} /></div>
        </div>
        <div className="chart-card">
          <div className="chart-header"><div><div className="chart-title">Herkomst instroom</div><div className="chart-sub">Regio van herkomst 2024</div></div></div>
          <div style={{ height: 200 }}><Doughnut data={herkomst} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } } }} /></div>
        </div>
        <div className="chart-card">
          <div className="chart-header"><div><div className="chart-title">Diplomarendement per opleiding</div><div className="chart-sub">Binnen 4 jaar, cohort 2020</div></div></div>
          <div style={{ height: 200 }}><Bar data={rendement} options={{ ...CHART_OPTS, plugins: { legend: { display: true, position: 'top' } } }} /></div>
        </div>
        <div className="chart-card">
          <div className="chart-header"><div><div className="chart-title">Deelname voltijd vs. deeltijd</div><div className="chart-sub">Ontwikkeling 2020–2024</div></div></div>
          <div style={{ height: 200 }}><Line data={trend} options={{ ...CHART_OPTS, plugins: { legend: { display: true, position: 'top' } } }} /></div>
        </div>
      </div>
    </div>
  )
}
