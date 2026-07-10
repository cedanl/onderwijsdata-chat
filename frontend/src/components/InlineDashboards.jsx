import { useState, useEffect } from 'react'
import { CHART_COLORS } from '../constants'
import { Bar, Line, Doughnut } from 'react-chartjs-2'

function useDarkMode() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains('dark'))
    )
    obs.observe(document.documentElement, { attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

function chartOpts(dark) {
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  const tick = dark ? '#9CA3AF' : '#6B7280'
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: { grid: { color: grid }, ticks: { color: tick } },
    },
  }
}
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

// ─── Chart constants ─────────────────────────────────────────────────────────

export const CHART_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { display: false } }, y: { grid: { color: '#F3F4F6' } } },
}

export const SECTOR_LABELS = {
  ECONOMIE: 'Economie',
  GEZONDHEIDSZORG: 'Gezondheidszorg',
  TECHNIEK: 'Techniek',
  ONDERWIJS: 'Onderwijs',
  GEDRAG_EN_MAATSCHAPPIJ: 'Gedrag & Mij.',
  TAAL_EN_CULTUUR: 'Taal & Cultuur',
  SECTOROVERSTIJGEND: 'Sectoroverstijgend',
}
// Semantic: each color is fixed to a named sector (Economie→blauw, Gezondheidszorg→teal, …).
// Not a generic sequential palette, so not replaced by CHART_COLORS.
export const SECTOR_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8']

export function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}

// ─── Data hook ───────────────────────────────────────────────────────────────

export function useDashboardData(instelling) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!instelling) return
    setLoading(true)
    setData(null)
    setError(null)
    fetch(`/api/dashboard/instroom?instelling=${encodeURIComponent(instelling)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [instelling])

  return { data, loading, error }
}

// ─── Shell ───────────────────────────────────────────────────────────────────

export function DashboardShell({ instelling, children, loading, data, error }) {
  if (loading) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Data laden&hellip;</span>
        </div>
        <div className="db-skeleton-grid">
          {[1,2,3,4].map(i => <div key={i} className="db-skeleton-kpi" />)}
        </div>
        <div className="db-skeleton-grid" style={{ marginTop: 16 }}>
          {[1,2,3,4].map(i => <div key={i} className="db-skeleton-chart" />)}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <div style={{ fontSize: '.85rem', color: '#991B1B' }}>
            Kon geen data ophalen voor <strong>{instelling}</strong>. {error}
          </div>
        </div>
      </div>
    )
  }

  if (!data.gevonden) {
    const suggesties = data.beschikbare_instellingen || []
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
          <div style={{ fontSize: '.85rem', color: '#92400E', lineHeight: 1.6 }}>
            <strong>&ldquo;{instelling}&rdquo;</strong> niet gevonden in DUO-data.
            {suggesties.length > 0 && (
              <> Bedoel je misschien: {suggesties.slice(0,5).join(', ')}?</>
            )}
            <br />Pas de naam aan via <strong>Instellingen</strong>.
          </div>
        </div>
      </div>
    )
  }

  return children
}

// ─── Chart data builders ─────────────────────────────────────────────────────

function buildBarChartData(dict, label, color) {
  if (!dict) return null
  const entries = Object.entries(dict).sort((a, b) => a[0] - b[0])
  return {
    labels: entries.map(([y]) => String(y)),
    datasets: [{ label, data: entries.map(([, v]) => v), backgroundColor: color, borderRadius: 6 }],
  }
}

function buildLineChartData(dict, label, borderColor, bgColor) {
  if (!dict) return null
  const entries = Object.entries(dict).sort((a, b) => a[0] - b[0])
  return {
    labels: entries.map(([y]) => String(y)),
    datasets: [{ label, data: entries.map(([, v]) => v), borderColor, backgroundColor: bgColor, fill: true, tension: 0.3, pointRadius: 4 }],
  }
}

function buildSectorChartData(sectoren, { type = 'doughnut' } = {}) {
  if (!sectoren) return null
  const entries = Object.entries(sectoren).sort((a, b) => b[1] - a[1]).slice(0, 7)
  const dataset = { data: entries.map(([, v]) => v), backgroundColor: SECTOR_COLORS, borderWidth: 0 }
  if (type === 'bar') {
    dataset.label = 'Ingeschrevenen'
    dataset.borderRadius = 6
  }
  return {
    labels: entries.map(([k]) => SECTOR_LABELS[k] || k),
    datasets: [dataset],
  }
}

function sortedEntries(dict) {
  if (!dict) return []
  return Object.entries(dict).sort((a, b) => a[0] - b[0])
}

function yearOverYearDelta(entries) {
  const last = entries.at(-1)
  const prev = entries.at(-2)
  return last && prev ? last[1] - prev[1] : null
}

// ─── InlineDashboard ─────────────────────────────────────────────────────────

export function InlineDashboard({ instelling }) {
  const { data, loading, error } = useDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)

  const ingesChartData = buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])
  const eerstejaarsChartData = buildBarChartData(data?.eerstejaars, 'Eerstejaars', '#0D9488')
  const gediplChartData = buildLineChartData(data?.gediplomeerden, 'Gediplomeerden', CHART_COLORS[5], 'rgba(34,197,94,.08)')
  const sectorChartData = buildSectorChartData(data?.sectoren)

  const ingesEntries = sortedEntries(data?.ingeschrevenen)
  const lastInges = ingesEntries.at(-1)
  const ingesDelta = yearOverYearDelta(ingesEntries)

  const diplEntries = sortedEntries(data?.gediplomeerden)
  const lastDipl = diplEntries.at(-1)
  const diplDelta = yearOverYearDelta(diplEntries)

  const lastEj = sortedEntries(data?.eerstejaars).at(-1)

  const vrouw = data?.geslacht?.VROUW || 0
  const man = data?.geslacht?.MAN || 0
  const totaalGeslacht = vrouw + man
  const pctVrouw = totaalGeslacht > 0 ? ((vrouw / totaalGeslacht) * 100).toFixed(1) : null

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>
        <div className="kpi-grid">
          {lastInges && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Ingeschrevenen {lastInges[0]}&ndash;{Number(lastInges[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastInges[1])}</div>
              {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {lastEj && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Eerstejaars {lastEj[0]}&ndash;{Number(lastEj[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastEj[1])}</div>
            </div>
          )}
          {pctVrouw != null && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Aandeel vrouw {data.laatste_jaar}</span>
                <div className="kpi-icon" style={{ background: '#FFF7ED' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{pctVrouw}%</div>
              <div className="kpi-trend">van {fmt(totaalGeslacht)} ingeschrevenen</div>
            </div>
          )}
        </div>
        <div className="charts-grid">
          {ingesChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per jaar</div><div className="chart-sub">{instelling} (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Bar data={ingesChartData} options={opts} /></div>
            </div>
          )}
          {sectorChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={sectorChartData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 } } } } }} /></div>
            </div>
          )}
          {eerstejaarsChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Eerstejaars instroom per jaar</div><div className="chart-sub">{instelling} (DUO p02ho1ejrs)</div></div></div>
              <div style={{ height: 200 }}><Bar data={eerstejaarsChartData} options={opts} /></div>
            </div>
          )}
          {gediplChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">{instelling} (DUO p04hogdipl)</div></div></div>
              <div style={{ height: 200 }}><Line data={gediplChartData} options={{ ...opts, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
        </div>
        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/ingeschrevenen-wo-hbo/" target="_blank" rel="noreferrer">DUO &mdash; Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/eerstejaars-wo-hbo/" target="_blank" rel="noreferrer">DUO &mdash; Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/gediplomeerden-wo-hbo/" target="_blank" rel="noreferrer">DUO &mdash; Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

// ─── InlineDashboardArbeidsmarkt ─────────────────────────────────────────────

export function InlineDashboardArbeidsmarkt({ instelling }) {
  const { data, loading, error } = useDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)

  const gediplChartData = buildLineChartData(data?.gediplomeerden, 'Gediplomeerden', '#0D9488', 'rgba(13,148,136,.08)')
  const sectorChartData = buildSectorChartData(data?.sectoren, { type: 'bar' })

  const diplEntries = sortedEntries(data?.gediplomeerden)
  const lastDipl = diplEntries.at(-1)
  const diplDelta = yearOverYearDelta(diplEntries)

  const sectorEntries = data?.sectoren ? Object.entries(data.sectoren).sort((a, b) => b[1] - a[1]) : []
  const kpiColors = ['#EFF6FF','#FFF7ED','#F0FDF4']
  // Icon stroke colors: drawn from CHART_COLORS (indices 0, 2, 5)
  const kpiIconColors = [CHART_COLORS[0], CHART_COLORS[2], CHART_COLORS[5]]

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>
        <div className="kpi-grid">
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {sectorEntries.slice(0, 3).map(([key, val], i) => (
            <div key={key} className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">{SECTOR_LABELS[key] || key} {data.laatste_jaar}</span>
                <div className="kpi-icon" style={{ background: kpiColors[i] }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke={kpiIconColors[i]} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(val)}</div>
              <div className="kpi-trend">{i === 0 ? 'grootste sector' : i === 1 ? '2e sector' : '3e sector'}</div>
            </div>
          ))}
        </div>
        <div className="charts-grid">
          {gediplChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">{instelling} (DUO p04hogdipl)</div></div></div>
              <div style={{ height: 200 }}><Line data={gediplChartData} options={{ ...opts, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
          {sectorChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per sector {data.laatste_jaar}</div><div className="chart-sub">Verdeling naar onderdeel (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Bar data={sectorChartData} options={{ ...opts, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
        </div>
        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/ingeschrevenen-wo-hbo/" target="_blank" rel="noreferrer">DUO &mdash; Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/gediplomeerden-wo-hbo/" target="_blank" rel="noreferrer">DUO &mdash; Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
