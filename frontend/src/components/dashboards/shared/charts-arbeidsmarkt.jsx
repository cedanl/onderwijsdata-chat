import { Bar } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import { fmt } from './hooks'
import { SectionHeader, ChartCard } from './shell'
import { darkColors, horizontalBarOpts } from './chart-opts'

// ─── Arbeidsmarkt chart components ───────────────────────────────────────────

const _ROA_INDICATORS = [
  { key: 'werkloosheid', label: 'Werkloos', color: '#DC2626' },
  { key: 'vast dienstverband', label: 'Vast dienstverband', color: '#0D9488' },
  { key: 'buiten de vakrichting', label: 'Buiten vakrichting', color: '#F59E0B' },
]

export function RoaSection({ data, dark }) {
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
  const { tick, grid, label } = darkColors(dark)
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
        labels: { color: label, font: { size: 11 }, boxWidth: 14 },
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
      <ChartCard>
        <div style={{ height: h }}>
          <Bar data={chartData} options={opts} />
        </div>
        <div style={{ fontSize: '.73rem', color: 'var(--gray-400)', marginTop: 6, fontStyle: 'italic' }}>
          Landelijk gemiddelde — niet specifiek voor deze instelling of regio
        </div>
      </ChartCard>
    </>
  )
}

const _TYPERING_COLORS = {
  'goed': '#059669', 'zeer goed': '#047857',
  'redelijk': '#D97706', 'matig': '#EA580C',
  'slecht': '#DC2626', 'zeer slecht': '#991B1B',
  'hoog': '#059669', 'zeer hoog': '#047857', 'erg hoog': '#047857',
  'gemiddeld': '#D97706',
  'laag': '#EA580C', 'zeer laag': '#DC2626', 'erg laag': '#DC2626',
  'geen': '#94A3B8',
}

const _PROGNOSE_LABELS = {
  'ITA toekomstige arbeidsmarktsituatie in 2030': 'Arbeidsmarktperspectief 2030',
  'verwachte baanopeningen tot 2030': 'Verwachte baanopeningen',
  'verwachte instroom van schoolverlaters tot 2030': 'Verwachte instroom schoolverlaters',
}

export function PrognoseSection({ data }) {
  const prognose = data?.arbeidsmarkt_prognose
  if (!prognose || Object.keys(prognose).length === 0) return null
  const niveaus = Object.keys(prognose)
  return (
    <>
      <SectionHeader
        title="Arbeidsmarktprognose tot 2030 (ROA)"
        subtitle="Nationale verwachtingen per opleidingsniveau — niet specifiek voor deze instelling of regio"
      />
      <ChartCard cardStyle={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600 }}>Niveau</th>
                {Object.values(_PROGNOSE_LABELS).map(label => (
                  <th key={label} style={{ textAlign: 'center', padding: '6px 8px', fontWeight: 600 }}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {niveaus.map(niveau => (
                <tr key={niveau} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 500 }}>{niveau}</td>
                  {Object.keys(_PROGNOSE_LABELS).map(key => {
                    const typering = prognose[niveau]?.[key]
                    const color = _TYPERING_COLORS[typering?.toLowerCase()] || 'var(--gray-500)'
                    return (
                      <td key={key} style={{ textAlign: 'center', padding: '6px 8px' }}>
                        {typering ? <span style={{ color, fontWeight: 600 }}>{typering}</span> : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ fontSize: '.73rem', color: 'var(--gray-400)', marginTop: 6, fontStyle: 'italic' }}>
            Landelijk gemiddelde — niet specifiek voor deze instelling of regio (ROA AIS2030)
          </div>
        </ChartCard>
    </>
  )
}

export function UwvSection({ data, provincie, dark }) {
  const vac = data?.vacatureaanbod
  if (!vac?.clusters || Object.keys(vac.clusters).length === 0) {
    return (
      <ChartCard title="Vacatureaanbod in de regio">
        <p style={{ color: 'var(--gray-500)', fontSize: '.85rem', padding: '8px 0' }}>
          Geen vacaturegegevens beschikbaar{provincie ? ` voor ${provincie}` : ''}.
          UWV Open Match data is beschikbaar t/m mei 2023.
        </p>
      </ChartCard>
    )
  }
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
            <div className="kpi-icon" style={{ background: 'var(--blue-50)' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(vac.totaal)}</div>
          <div className="kpi-trend">alle sectoren in provincie</div>
        </div>
      </div>
      <ChartCard
        title={`Beroepencluster${gefilterdOp.length > 0 ? ' passend bij opleidingssectoren' : ''}`}
        subtitle={`Provincie ${provincie}${gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(s => s.toLowerCase()).join(', ')}` : ''}`}
      >
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
            options={horizontalBarOpts(dark)}
          />
        </div>
      </ChartCard>
    </>
  )
}
