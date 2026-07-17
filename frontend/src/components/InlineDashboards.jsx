import { useState, useEffect } from 'react'
import { CHART_COLORS } from '../constants'
import { Bar, Line, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

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

function buildIndexChartOpts(dark) {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 }, boxWidth: 20 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y
            return `${ctx.dataset.label}: ${v >= 0 ? '+' : ''}${v}%`
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: {
        grid: { color: grid },
        ticks: { color: tick, callback: (v) => `${v}%` },
        title: { display: true, text: '% verandering t.o.v. eerste jaar', color: tick, font: { size: 10 } },
      },
    },
  }
}

// ─── Chart constants ─────────────────────────────────────────────────────────

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

// ─── Data hooks ──────────────────────────────────────────────────────────────

function useDashboardFetch(endpoint, instelling) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!instelling) return
    setLoading(true)
    setData(null)
    setError(null)
    fetch(`${endpoint}?instelling=${encodeURIComponent(instelling)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [endpoint, instelling])

  return { data, loading, error }
}

export function useDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/instroom', instelling)
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
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata &mdash; Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata &mdash; Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata &mdash; Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

// ─── InlineDashboardRegio ────────────────────────────────────────────────────
// @deprecated Backward-compat voor gebruikers met __builtin_regio__ in localStorage.
// Verwijder na v1.8 zodra alle clients de gesplitste dashboards zien.


function useRegioDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/regio', instelling)
}

function buildBenchmarkLineData(ownDict, benchDict, ownLabel, benchLabel, ownColor, benchColor) {
  if (!ownDict) return null
  const ownEntries = Object.entries(ownDict).sort((a, b) => a[0] - b[0])
  const labels = ownEntries.map(([y]) => String(y))
  const ownRaw = ownEntries.map(([, v]) => v)

  const toIndex = (values, base) =>
    values.map(v => v != null && base > 0 ? Math.round(((v / base) - 1) * 100) : null)

  const ownBase = ownRaw.find(v => v != null && v > 0) ?? ownRaw[0]
  const ownData = toIndex(ownRaw, ownBase)

  const datasets = [
    {
      label: ownLabel,
      data: ownData,
      borderColor: ownColor,
      backgroundColor: ownColor + '18',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2,
    },
  ]
  if (benchDict) {
    const benchMap = new Map(Object.entries(benchDict).map(([k, v]) => [String(k), v]))
    const benchRaw = labels.map(y => benchMap.get(y) ?? null)
    const benchBase = benchRaw.find(v => v != null)
    datasets.push({
      label: benchLabel,
      data: toIndex(benchRaw, benchBase),
      borderColor: benchColor,
      backgroundColor: 'transparent',
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: 3,
      borderWidth: 2,
      fill: false,
    })
  }
  return { labels, datasets }
}

function Sparkline({ values, color = '#2563EB', width = 80, height = 28 }) {
  const pts = values.filter(v => v != null)
  if (pts.length < 2) return null
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  const step = width / (pts.length - 1)
  const points = pts.map((v, i) => {
    const x = i * step
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block', marginTop: 4 }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ margin: '28px 0 12px', borderBottom: '1px solid var(--gray-200, #E5E7EB)', paddingBottom: 8 }}>
      <div style={{ fontWeight: 700, fontSize: '.95rem', color: 'var(--gray-900, #111827)' }}>{title}</div>
      {subtitle && <div style={{ fontSize: '.8rem', color: 'var(--gray-500, #6B7280)', marginTop: 2 }}>{subtitle}</div>}
    </div>
  )
}

export function InlineDashboardRegio({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)
  const bmColor = dark ? '#9CA3AF' : '#94A3B8'

  const bm = data?.benchmark || {}
  const bmLabel = bm.label || 'Benchmark'

  const ingesLineData = buildBenchmarkLineData(
    data?.ingeschrevenen, bm.ingeschrevenen,
    instelling, bmLabel, CHART_COLORS[0], bmColor
  )
  const ejLineData = buildBenchmarkLineData(
    data?.eerstejaars, bm.eerstejaars,
    instelling, bmLabel, CHART_COLORS[2], bmColor
  )
  const diplLineData = buildBenchmarkLineData(
    data?.gediplomeerden, bm.gediplomeerden,
    instelling, bmLabel, CHART_COLORS[5], bmColor
  )
  const sectorData = buildSectorChartData(data?.sectoren)

  const ingesEntries = sortedEntries(data?.ingeschrevenen)
  const lastInges = ingesEntries.at(-1)
  const ingesDelta = yearOverYearDelta(ingesEntries)

  const ejEntries = sortedEntries(data?.eerstejaars)
  const lastEj = ejEntries.at(-1)
  const ejDelta = yearOverYearDelta(ejEntries)

  const diplEntries = sortedEntries(data?.gediplomeerden)
  const lastDipl = diplEntries.at(-1)
  const diplDelta = yearOverYearDelta(diplEntries)

  const totaalProvEntry = bm.totaal_ingeschrevenen
    ? Object.entries(bm.totaal_ingeschrevenen).sort((a, b) => a[0] - b[0]).at(-1)
    : null
  const totaalProv = totaalProvEntry?.[1] ?? null
  const totaalProvJaar = totaalProvEntry?.[0] ?? data?.laatste_jaar

  const vrouw = data?.geslacht?.VROUW || 0
  const man = data?.geslacht?.MAN || 0
  const totaalGeslacht = vrouw + man
  const pctVrouw = totaalGeslacht > 0 ? ((vrouw / totaalGeslacht) * 100).toFixed(1) : null

  const indexOpts = buildIndexChartOpts(dark)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          {data?.provincie && <span className="meta-badge date">Provincie {data.provincie}</span>}
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>

        {/* ── Demografie ── */}
        <SectionHeader
          title="Demografie"
          subtitle="Potentiële lerenden en onderwijsprofessionals in de regio"
        />
        <div className="kpi-grid">
          {lastInges && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Ingeschrevenen {lastInges[0]}–{Number(lastInges[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastInges[1])}</div>
              {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={ingesEntries.map(([,v]) => v)} color="#2563EB" />
            </div>
          )}
          {totaalProv != null && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Provincie totaal {totaalProvJaar}–{Number(totaalProvJaar)+1}</span>
                <div className="kpi-icon" style={{ background: '#F5F3FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(totaalProv)}</div>
              {bm.n_instellingen && <div className="kpi-trend">{bm.n_instellingen} instellingen in provincie</div>}
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
        {ingesLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={ingesLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}

        {/* ── Instroom ── */}
        <SectionHeader
          title="Instroom"
          subtitle="Eerstejaars aanmeldingen per jaar, vergeleken met de provincie"
        />
        <div className="kpi-grid">
          {lastEj && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Eerstejaars {lastEj[0]}–{Number(lastEj[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastEj[1])}</div>
              {ejDelta != null && <div className={`kpi-trend ${ejDelta >= 0 ? 'up' : 'down'}`}>{ejDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ejDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={ejEntries.map(([,v]) => v)} color="#22C55E" />
            </div>
          )}
        </div>
        {ejLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Eerstejaars instroom per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={ejLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}

        {/* ── Voortgang ── */}
        <SectionHeader
          title="Voortgang"
          subtitle="Inschrijvingen en sectoren per onderdeel"
        />
        <div className="charts-grid">
          {sectorData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={sectorData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 } } } } }} /></div>
            </div>
          )}
          {ingesLineData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Inschrijvingen trend</div><div className="chart-sub">{instelling} (alle jaren)</div></div></div>
              <div style={{ height: 200 }}><Bar data={buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])} options={opts} /></div>
            </div>
          )}
        </div>

        {/* ── Diplomering ── */}
        <SectionHeader
          title="Diplomering"
          subtitle="Gediplomeerden per jaar, vergeleken met de provincie"
        />
        <div className="kpi-grid">
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={diplEntries.map(([,v]) => v)} color="#0D9488" />
            </div>
          )}
        </div>
        {diplLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={diplLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}

        {/* ── Arbeidsmarkt (ROA) ── */}
        {data?.arbeidsmarkt_roa && Object.keys(data.arbeidsmarkt_roa).length > 0 && (
          <>
            <SectionHeader
              title="Landelijk referentiekader (ROA)"
              subtitle="Nationale gemiddelden per opleidingsniveau — niet specifiek voor deze instelling (ROA Schoolverlatersinformatie 2024)"
            />
            <div className="kpi-grid">
              {Object.entries(data.arbeidsmarkt_roa).map(([niveau, metrics]) => (
                Object.entries(metrics).map(([indicator, pct]) => {
                  const isGood = indicator === 'vast dienstverband'
                  const isBad = indicator === 'werkloosheid' || indicator === 'buiten de vakrichting'
                  const iconColor = isGood ? '#0D9488' : isBad ? '#DC2626' : '#6B7280'
                  const bgColor = isGood ? '#F0FDFA' : isBad ? '#FEF2F2' : '#F9FAFB'
                  return (
                    <div key={`${niveau}-${indicator}`} className="kpi-card">
                      <div className="kpi-card-header">
                        <span className="kpi-label">{niveau} — {indicator}</span>
                        <div className="kpi-icon" style={{ background: bgColor }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            {isGood
                              ? <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>
                              : <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>
                            }
                          </svg>
                        </div>
                      </div>
                      <div className="kpi-value">{pct}%</div>
                      <div className="kpi-trend" style={{ color: '#6B7280' }}>🏷 landelijk gemiddelde, niet per instelling</div>
                    </div>
                  )
                })
              ))}
            </div>
          </>
        )}

        {/* ── Vacatureaanbod (UWV) ── */}
        {(() => {
          const vac = data?.vacatureaanbod
          if (!vac?.clusters || Object.keys(vac.clusters).length === 0) return null
          const gefilterdOp = vac.gefilterd_op || []
          const clusterHeight = Math.max(180, Object.keys(vac.clusters).length * 32)
          return (
            <>
              <SectionHeader
                title="Vacatureaanbod in de regio"
                subtitle={gefilterdOp.length > 0
                  ? `Clusters passend bij opleidingssectoren — UWV Open Match, ${vac.peildatum || 'mei 2023'} (momentopname)`
                  : `Openstaande vacatures per beroepscluster — UWV Open Match, ${vac.peildatum || 'mei 2023'} (momentopname)`}
              />
              <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 6, padding: '8px 12px', fontSize: '.8rem', color: '#92400E', marginBottom: 12 }}>
                ⚠ Momentopname mei 2023 — geen historische reeks beschikbaar. Gebruik als indicatie, niet als actueel cijfer.
              </div>
              <div className="kpi-grid" style={{ marginBottom: 12 }}>
                <div className="kpi-card">
                  <div className="kpi-card-header">
                    <span className="kpi-label">Totaal vacatures provincie {data.provincie}</span>
                    <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
                    </div>
                  </div>
                  <div className="kpi-value">{fmt(vac.totaal)}</div>
                  <div className="kpi-trend">alle sectoren in provincie</div>
                </div>
              </div>
              <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
                <div className="chart-card">
                  <div className="chart-header">
                    <div>
                      <div className="chart-title">Beroepencluster{gefilterdOp.length > 0 ? ' passend bij opleidingssectoren' : ''}</div>
                      <div className="chart-sub">
                        Provincie {data.provincie}{gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(s => s.toLowerCase()).join(', ')}` : ''}
                      </div>
                    </div>
                  </div>
                  <div style={{ height: clusterHeight }}>
                    <Bar
                      data={{
                        labels: Object.keys(vac.clusters),
                        datasets: [{
                          label: 'Vacatures',
                          data: Object.values(vac.clusters),
                          backgroundColor: CHART_COLORS.slice(0, Object.keys(vac.clusters).length).map(c => c + 'CC'),
                          borderWidth: 0,
                          borderRadius: 4,
                        }],
                      }}
                      options={{
                        ...opts,
                        indexAxis: 'y',
                        plugins: { legend: { display: false } },
                        scales: {
                          x: { grid: { color: dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6' }, ticks: { color: dark ? '#9CA3AF' : '#6B7280' } },
                          y: { grid: { display: false }, ticks: { color: dark ? '#9CA3AF' : '#6B7280', font: { size: 11 } } },
                        },
                      }}
                    />
                  </div>
                </div>
              </div>
            </>
          )
        })()}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/mbo-studenten-per-instelling" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — MBO studenten per instelling</a></li>
            <li><a href="https://data.overheid.nl/dataset/uwv-open-match-data" target="_blank" rel="noreferrer">UWV Open Match — Vacaturedata per provincie en beroepscluster (mei 2023)</a></li>
            <li><a href="https://doi.org/10.34894/DVQTOG" target="_blank" rel="noreferrer">ROA — Arbeidsmarktinformatiesysteem (AIS), Schoolverlatersinformatie 2024 (nationaal gemiddelde)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

// ─── InlineDashboardRegioInstroom ────────────────────────────────────────────

export function InlineDashboardRegioInstroom({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)
  const bmColor = dark ? '#9CA3AF' : '#94A3B8'

  const bm = data?.benchmark || {}
  const bmLabel = bm.label || 'Benchmark'

  const ingesLineData = buildBenchmarkLineData(
    data?.ingeschrevenen, bm.ingeschrevenen,
    instelling, bmLabel, CHART_COLORS[0], bmColor
  )
  const ejLineData = buildBenchmarkLineData(
    data?.eerstejaars, bm.eerstejaars,
    instelling, bmLabel, CHART_COLORS[2], bmColor
  )
  const sectorData = buildSectorChartData(data?.sectoren)

  const ingesEntries = sortedEntries(data?.ingeschrevenen)
  const lastInges = ingesEntries.at(-1)
  const ingesDelta = yearOverYearDelta(ingesEntries)

  const ejEntries = sortedEntries(data?.eerstejaars)
  const lastEj = ejEntries.at(-1)
  const ejDelta = yearOverYearDelta(ejEntries)

  const totaalProvEntry = bm.totaal_ingeschrevenen
    ? Object.entries(bm.totaal_ingeschrevenen).sort((a, b) => a[0] - b[0]).at(-1)
    : null
  const totaalProv = totaalProvEntry?.[1] ?? null
  const totaalProvJaar = totaalProvEntry?.[0] ?? data?.laatste_jaar

  const vrouw = data?.geslacht?.VROUW || 0
  const man = data?.geslacht?.MAN || 0
  const totaalGeslacht = vrouw + man
  const pctVrouw = totaalGeslacht > 0 ? ((vrouw / totaalGeslacht) * 100).toFixed(1) : null

  const indexOpts = buildIndexChartOpts(dark)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          {data?.provincie && <span className="meta-badge date">Provincie {data.provincie}</span>}
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>

        {/* ── Demografie ── */}
        <SectionHeader
          title="Demografie"
          subtitle="Potentiële lerenden en onderwijsprofessionals in de regio"
        />
        <div className="kpi-grid">
          {lastInges && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Ingeschrevenen {lastInges[0]}–{Number(lastInges[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastInges[1])}</div>
              {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={ingesEntries.map(([,v]) => v)} color="#2563EB" />
            </div>
          )}
          {totaalProv != null && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Provincie totaal {totaalProvJaar}–{Number(totaalProvJaar)+1}</span>
                <div className="kpi-icon" style={{ background: '#F5F3FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(totaalProv)}</div>
              {bm.n_instellingen && <div className="kpi-trend">{bm.n_instellingen} instellingen in provincie</div>}
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
        {ingesLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={ingesLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}

        {/* ── Instroom ── */}
        <SectionHeader
          title="Instroom"
          subtitle="Eerstejaars aanmeldingen per jaar, vergeleken met de provincie"
        />
        <div className="kpi-grid">
          {lastEj && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Eerstejaars {lastEj[0]}–{Number(lastEj[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastEj[1])}</div>
              {ejDelta != null && <div className={`kpi-trend ${ejDelta >= 0 ? 'up' : 'down'}`}>{ejDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ejDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={ejEntries.map(([,v]) => v)} color="#22C55E" />
            </div>
          )}
        </div>
        {ejLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Eerstejaars instroom per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={ejLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}
        {sectorData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={sectorData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 } } } } }} /></div>
            </div>
          </div>
        )}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

// ─── InlineDashboardRegioDiplomering ─────────────────────────────────────────

export function InlineDashboardRegioDiplomering({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)
  const bmColor = dark ? '#9CA3AF' : '#94A3B8'

  const bm = data?.benchmark || {}
  const bmLabel = bm.label || 'Benchmark'

  const diplLineData = buildBenchmarkLineData(
    data?.gediplomeerden, bm.gediplomeerden,
    instelling, bmLabel, CHART_COLORS[5], bmColor
  )
  const sectorData = buildSectorChartData(data?.sectoren)

  const diplEntries = sortedEntries(data?.gediplomeerden)
  const lastDipl = diplEntries.at(-1)
  const diplDelta = yearOverYearDelta(diplEntries)

  const indexOpts = buildIndexChartOpts(dark)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          {data?.provincie && <span className="meta-badge date">Provincie {data.provincie}</span>}
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>

        {/* ── Voortgang ── */}
        <SectionHeader
          title="Voortgang"
          subtitle="Inschrijvingen en sectoren per onderdeel"
        />
        <div className="charts-grid">
          {sectorData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={sectorData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 } } } } }} /></div>
            </div>
          )}
          {data?.ingeschrevenen && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Inschrijvingen trend</div><div className="chart-sub">{instelling} (alle jaren)</div></div></div>
              <div style={{ height: 200 }}><Bar data={buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])} options={opts} /></div>
            </div>
          )}
        </div>

        {/* ── Diplomering ── */}
        <SectionHeader
          title="Diplomering"
          subtitle="Gediplomeerden per jaar, vergeleken met de provincie"
        />
        <div className="kpi-grid">
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
              <Sparkline values={diplEntries.map(([,v]) => v)} color="#0D9488" />
            </div>
          )}
        </div>
        {diplLineData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">% verandering t.o.v. eerste jaar — eigen instelling vs. {bmLabel.toLowerCase()}</div></div></div>
              <div style={{ height: 220 }}><Line data={diplLineData} options={indexOpts} /></div>
            </div>
          </div>
        )}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

// ─── InlineDashboardRegioArbeidsmarkt ────────────────────────────────────────

export function InlineDashboardRegioArbeidsmarkt({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const dark = useDarkMode()
  const opts = chartOpts(dark)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          {data?.provincie && <span className="meta-badge date">Provincie {data.provincie}</span>}
          <span className="meta-badge date">Bron: UWV &amp; ROA</span>
        </div>

        {/* ── Arbeidsmarkt (ROA) ── */}
        {data?.arbeidsmarkt_roa && Object.keys(data.arbeidsmarkt_roa).length > 0 && (
          <>
            <SectionHeader
              title="Landelijk referentiekader (ROA)"
              subtitle="Nationale gemiddelden per opleidingsniveau — niet specifiek voor deze instelling (ROA Schoolverlatersinformatie 2024)"
            />
            <div className="kpi-grid">
              {Object.entries(data.arbeidsmarkt_roa).map(([niveau, metrics]) => (
                Object.entries(metrics).map(([indicator, pct]) => {
                  const isGood = indicator === 'vast dienstverband'
                  const isBad = indicator === 'werkloosheid' || indicator === 'buiten de vakrichting'
                  const iconColor = isGood ? '#0D9488' : isBad ? '#DC2626' : '#6B7280'
                  const bgColor = isGood ? '#F0FDFA' : isBad ? '#FEF2F2' : '#F9FAFB'
                  return (
                    <div key={`${niveau}-${indicator}`} className="kpi-card">
                      <div className="kpi-card-header">
                        <span className="kpi-label">{niveau} — {indicator}</span>
                        <div className="kpi-icon" style={{ background: bgColor }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            {isGood
                              ? <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>
                              : <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>
                            }
                          </svg>
                        </div>
                      </div>
                      <div className="kpi-value">{pct}%</div>
                      <div className="kpi-trend" style={{ color: '#6B7280' }}>🏷 landelijk gemiddelde, niet per instelling</div>
                    </div>
                  )
                })
              ))}
            </div>
          </>
        )}

        {/* ── Vacatureaanbod (UWV) ── */}
        {(() => {
          const vac = data?.vacatureaanbod
          if (!vac?.clusters || Object.keys(vac.clusters).length === 0) return null
          const gefilterdOp = vac.gefilterd_op || []
          const clusterHeight = Math.max(180, Object.keys(vac.clusters).length * 32)
          return (
            <>
              <SectionHeader
                title="Vacatureaanbod in de regio"
                subtitle={gefilterdOp.length > 0
                  ? `Clusters passend bij opleidingssectoren — UWV Open Match, ${vac.peildatum || 'mei 2023'} (momentopname)`
                  : `Openstaande vacatures per beroepscluster — UWV Open Match, ${vac.peildatum || 'mei 2023'} (momentopname)`}
              />
              <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 6, padding: '8px 12px', fontSize: '.8rem', color: '#92400E', marginBottom: 12 }}>
                ⚠ Momentopname mei 2023 — geen historische reeks beschikbaar. Gebruik als indicatie, niet als actueel cijfer.
              </div>
              <div className="kpi-grid" style={{ marginBottom: 12 }}>
                <div className="kpi-card">
                  <div className="kpi-card-header">
                    <span className="kpi-label">Totaal vacatures provincie {data.provincie}</span>
                    <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
                    </div>
                  </div>
                  <div className="kpi-value">{fmt(vac.totaal)}</div>
                  <div className="kpi-trend">alle sectoren in provincie</div>
                </div>
              </div>
              <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
                <div className="chart-card">
                  <div className="chart-header">
                    <div>
                      <div className="chart-title">Beroepencluster{gefilterdOp.length > 0 ? ' passend bij opleidingssectoren' : ''}</div>
                      <div className="chart-sub">
                        Provincie {data.provincie}{gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(s => s.toLowerCase()).join(', ')}` : ''}
                      </div>
                    </div>
                  </div>
                  <div style={{ height: clusterHeight }}>
                    <Bar
                      data={{
                        labels: Object.keys(vac.clusters),
                        datasets: [{
                          label: 'Vacatures',
                          data: Object.values(vac.clusters),
                          backgroundColor: CHART_COLORS.slice(0, Object.keys(vac.clusters).length).map(c => c + 'CC'),
                          borderWidth: 0,
                          borderRadius: 4,
                        }],
                      }}
                      options={{
                        ...opts,
                        indexAxis: 'y',
                        plugins: { legend: { display: false } },
                        scales: {
                          x: { grid: { color: dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6' }, ticks: { color: dark ? '#9CA3AF' : '#6B7280' } },
                          y: { grid: { display: false }, ticks: { color: dark ? '#9CA3AF' : '#6B7280', font: { size: 11 } } },
                        },
                      }}
                    />
                  </div>
                </div>
              </div>
            </>
          )
        })()}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://data.overheid.nl/dataset/uwv-open-match-data" target="_blank" rel="noreferrer">UWV Open Match — Vacaturedata per provincie en beroepscluster (mei 2023)</a></li>
            <li><a href="https://doi.org/10.34894/DVQTOG" target="_blank" rel="noreferrer">ROA — Arbeidsmarktinformatiesysteem (AIS), Schoolverlatersinformatie 2024 (nationaal gemiddelde)</a></li>
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
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata &mdash; Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata &mdash; Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
