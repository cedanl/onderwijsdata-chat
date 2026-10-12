import Plot from 'react-plotly.js'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import KolomKop from './KolomKop'

const MARKDOWN_COMPONENTS = { th: KolomKop }

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

  const dark = document.documentElement.classList.contains('dark')
  const fontColor = dark ? '#E2E8F0' : '#374151'
  const legendBg = dark ? 'rgba(30,41,59,0.9)' : 'rgba(255,255,255,0.8)'
  const legendBorder = dark ? '#475569' : '#ddd'
  const layout = {
    ...figure.layout,
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { t: 48, r: 24, b: 48, l: 60 },
    font: { family: 'system-ui, sans-serif', size: 12, color: fontColor },
    legend: {
      ...figure.layout?.legend,
      bgcolor: legendBg,
      bordercolor: legendBorder,
      font: { color: fontColor },
    },
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
        {sources.map(src => (
          <li key={src}><span style={{ fontSize: '.8rem', color: 'var(--gray-700)' }}>{src}</span></li>
        ))}
      </ul>
    </div>
  )
}

const HERHAAL_BUTTON_STYLE = (refreshing) => ({
  cursor: refreshing ? 'wait' : 'pointer',
  background: 'var(--gray-100)',
  color: 'var(--gray-600)',
  border: '1px solid var(--gray-200)',
  display: 'flex',
  alignItems: 'center',
  gap: 4,
})

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
          <>
            <button type="button"
              className="meta-badge"
              onClick={() => onRefresh('ververs')}
              disabled={!!refreshing}
              title="Haal de data opnieuw op bij de bron en toon wat er veranderd is"
              style={HERHAAL_BUTTON_STYLE(refreshing)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12 }}>
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
              </svg>
              {refreshing === 'ververs' ? 'Verversen…' : 'Ververs bij de bron'}
            </button>
            {(spec?.figure_recipes?.length > 0) && <button type="button"
              className="meta-badge"
              onClick={() => onRefresh('reproduceer')}
              disabled={!!refreshing}
              title="Maak de grafieken opnieuw uit de opgeslagen data, zonder de bron te raadplegen"
              style={HERHAAL_BUTTON_STYLE(refreshing)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12 }}>
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              {refreshing === 'reproduceer' ? 'Reproduceren…' : 'Reproduceer uit opslag'}
            </button>}
          </>
        )}
      </div>

      {kpis.length > 0 && (
        <div className="kpi-grid">
          {kpis.map((kpi, i) => <KpiCard key={kpi.label || i} kpi={kpi} index={i} />)}
        </div>
      )}

      {figures.length > 0 && (
        <div className="charts-grid">
          {figures.map((fig, i) => <ChartCard key={fig?.layout?.title?.text || i} figureJson={fig} />)}
        </div>
      )}

      {narrative && (
        <div className="chart-card" style={{ marginTop: 16 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>{narrative}</ReactMarkdown>
        </div>
      )}

      <SourcesList sources={sources} />
    </div>
  )
}
