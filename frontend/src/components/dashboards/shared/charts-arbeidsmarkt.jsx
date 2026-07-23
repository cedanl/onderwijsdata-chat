import { Bar } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import { useDarkMode, fmt } from './hooks'
import { SectionHeader } from './shell'

// ─── Arbeidsmarkt chart components ───────────────────────────────────────────

const _ROA_INDICATORS = [
  { key: 'werkloosheid', label: 'Werkloos', color: '#DC2626' },
  { key: 'vast dienstverband', label: 'Vast dienstverband', color: '#0D9488' },
  { key: 'buiten de vakrichting', label: 'Buiten vakrichting', color: '#F59E0B' },
]

export function RoaSection({ data }) {
  const dark = useDarkMode()
  const roa = data?.arbeidsmarkt_roa
  if (!roa || Object.keys(roa).length === 0) return null

  const niveaus = Object.keys(roa)
  const chartData = {
    labels: niveaus,
    datasets: _ROA_INDICATORS.map(ind => ({
      label: ind.label,
      data: niveaus.map(n => roa[n]?.[ind.key] ?? null),
      backgroundColor: ind.color + 'BB',
      borderWidth: 0,
      borderRadius: 3,
    })),
  }
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  const allValues = _ROA_INDICATORS.flatMap(ind => niveaus.map(n => roa[n]?.[ind.key] ?? 0))
  const maxVal = Math.max(...allValues.filter(v => v != null && v > 0), 0)
  const suggestedMax = Math.ceil((maxVal * 1.1) / 10) * 10 || 50
  const opts = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true, position: 'top',
        labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 }, boxWidth: 14 },
      },
      tooltip: { callbacks: { label: ctx => ` ${ctx.raw}%` } },
    },
    scales: {
      x: {
        suggestedMax,
        grid: { color: grid },
        ticks: { color: tick, callback: v => `${v}%` },
      },
      y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 } } },
    },
  }
  const h = Math.max(160, niveaus.length * 72)

  return (
    <>
      <SectionHeader
        title="Landelijk referentiekader (ROA)"
        subtitle="Nationale gemiddelden per opleidingsniveau — niet specifiek voor deze instelling (ROA Schoolverlatersinformatie 2024)"
      />
      <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
        <div className="chart-card">
          <div style={{ height: h }}>
            <Bar data={chartData} options={opts} />
          </div>
          <div style={{ fontSize: '.73rem', color: '#9CA3AF', marginTop: 6, fontStyle: 'italic' }}>
            Landelijk gemiddelde — niet specifiek voor deze instelling of regio
          </div>
        </div>
      </div>
    </>
  )
}

export function UwvSection({ data, provincie, dark, opts }) {
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
        Momentopname mei 2023 — geen historische reeks beschikbaar. Gebruik als indicatie, niet als actueel cijfer.
      </div>
      <div className="kpi-grid" style={{ marginBottom: 12 }}>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Totaal vacatures provincie {provincie}</span>
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
                Provincie {provincie}{gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(s => s.toLowerCase()).join(', ')}` : ''}
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
}
