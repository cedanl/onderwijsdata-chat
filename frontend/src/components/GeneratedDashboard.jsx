import { useState, useCallback } from 'react'
import Plot from 'react-plotly.js'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const TREND_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E']
const KPI_BACKGROUNDS = ['#EFF6FF', '#F0FDFA', '#FFF7ED', '#F0FDF4']

function KpiCard({ kpi, index }) {
  const color = TREND_COLORS[index % TREND_COLORS.length]
  const bg = KPI_BACKGROUNDS[index % KPI_BACKGROUNDS.length]
  return (
    <div className="kpi-card">
      <div className="kpi-card-header">
        <span className="kpi-label">{kpi.label}</span>
        <div className="kpi-icon" style={{ background: bg }}>
          <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
      </div>
      <div className="kpi-value">{kpi.value}</div>
      {kpi.trend && (
        <div className={`kpi-trend ${kpi.trendDirection === 'down' ? 'down' : 'up'}`}>
          {kpi.trendDirection === 'down' ? '↓' : '↑'} {kpi.trend}
          {kpi.sub && <span style={{ color: 'var(--gray-500)', marginLeft: 4 }}>{kpi.sub}</span>}
        </div>
      )}
      {!kpi.trend && kpi.sub && (
        <div className="kpi-trend">{kpi.sub}</div>
      )}
    </div>
  )
}

function ChartCard({ figureJson }) {
  let figure
  try {
    figure = typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
  } catch {
    return null
  }

  const layout = {
    ...figure.layout,
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { t: 48, r: 24, b: 48, l: 60 },
    font: { family: 'system-ui, sans-serif', size: 12 },
    autosize: true,
  }

  return (
    <div className="chart-card">
      <Plot
        data={figure.data || []}
        layout={layout}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%', height: 300 }}
      />
    </div>
  )
}

function SourcesList({ sources }) {
  if (!sources?.length) return null
  return (
    <div className="dashboard-sources">
      <div className="dashboard-sources-title">Bronnen</div>
      <ul className="dashboard-sources-list">
        {sources.map((src, i) => (
          <li key={i}><span style={{ fontSize: '.8rem', color: 'var(--gray-700)' }}>{src}</span></li>
        ))}
      </ul>
    </div>
  )
}

export default function GeneratedDashboard({ spec, instelling, onRefresh, refreshing }) {
  const kpis = spec?.kpis || []
  const figures = spec?.figures_json || []
  const narrative = spec?.narrative || ''
  const sources = spec?.sources || []

  return (
    <div className="dashboard-content" style={{ padding: 24 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {instelling && <span className="meta-badge instelling">{instelling}</span>}
        <span className="meta-badge date">Gegenereerd dashboard</span>
        {onRefresh && (
          <button
            className="meta-badge"
            onClick={onRefresh}
            disabled={refreshing}
            style={{
              cursor: refreshing ? 'wait' : 'pointer',
              background: 'var(--gray-100)',
              color: 'var(--gray-600)',
              border: '1px solid var(--gray-200)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12 }}>
              <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
            {refreshing ? 'Verversen…' : 'Ververs data'}
          </button>
        )}
      </div>

      {kpis.length > 0 && (
        <div className="kpi-grid">
          {kpis.map((kpi, i) => <KpiCard key={i} kpi={kpi} index={i} />)}
        </div>
      )}

      {figures.length > 0 && (
        <div className="charts-grid">
          {figures.map((fig, i) => <ChartCard key={i} figureJson={fig} />)}
        </div>
      )}

      {narrative && (
        <div className="chart-card" style={{ marginTop: 16 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{narrative}</ReactMarkdown>
        </div>
      )}

      <SourcesList sources={sources} />
    </div>
  )
}
