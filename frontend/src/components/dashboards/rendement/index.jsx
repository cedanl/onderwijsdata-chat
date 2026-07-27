import { useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import {
  useRendementDashboardData, useDarkMode, DashboardShell, SectionHeader, fmt,
} from '../shared/index'

function RendementKpis({ data }) {
  if (!data?.rendement_per_jaar) return null
  const entries = Object.entries(data.rendement_per_jaar).sort((a, b) => Number(b[0]) - Number(a[0]))
  const latest = entries[0]
  const prev = entries[1]
  const delta = latest && prev ? Math.round((latest[1] - prev[1]) * 10000) / 100 : null
  return (
    <div className="kpi-grid">
      {latest && (
        <div className="kpi-card">
          <div className="kpi-label">Rendement {latest[0]}</div>
          <div className="kpi-value">{(latest[1] * 100).toFixed(1)}%</div>
          {delta != null && <div className="kpi-sub" style={{ color: delta >= 0 ? '#16A34A' : '#DC2626' }}>{delta >= 0 ? '+' : ''}{delta.toFixed(1)}pp t.o.v. {prev[0]}</div>}
        </div>
      )}
      {data.pseudo_cohorten?.length > 0 && (() => {
        const last = data.pseudo_cohorten[data.pseudo_cohorten.length - 1]
        return (
          <div className="kpi-card">
            <div className="kpi-label">Instroom {last.instroom_jaar}</div>
            <div className="kpi-value">{fmt(last.instroom)}</div>
            <div className="kpi-sub">eerstejaars in cohort</div>
          </div>
        )
      })()}
    </div>
  )
}

function RendementTrendChart({ rendementPerJaar, benchmarkRendement, peersRendement, instelling, dark }) {
  const chartData = useMemo(() => {
    if (!rendementPerJaar || Object.keys(rendementPerJaar).length < 2) return null
    const jaren = [...new Set([
      ...Object.keys(rendementPerJaar),
      ...Object.keys(benchmarkRendement || {}),
    ])].sort()

    const datasets = [{
      label: instelling,
      data: jaren.map(j => rendementPerJaar[j] != null ? Math.round(rendementPerJaar[j] * 1000) / 10 : null),
      borderColor: CHART_COLORS[0],
      backgroundColor: CHART_COLORS[0] + '33',
      borderWidth: 3,
      tension: 0.3,
      spanGaps: true,
    }]

    if (benchmarkRendement && Object.keys(benchmarkRendement).length > 0) {
      datasets.push({
        label: 'Benchmark (regio)',
        data: jaren.map(j => benchmarkRendement[j] != null ? Math.round(benchmarkRendement[j] * 1000) / 10 : null),
        borderColor: '#9CA3AF',
        backgroundColor: '#9CA3AF33',
        borderWidth: 2,
        borderDash: [6, 3],
        tension: 0.3,
        spanGaps: true,
      })
    }

    if (peersRendement) {
      Object.entries(peersRendement).forEach(([naam, rend], i) => {
        datasets.push({
          label: naam,
          data: jaren.map(j => rend[j] != null ? Math.round(rend[j] * 1000) / 10 : null),
          borderColor: CHART_COLORS[(i + 2) % CHART_COLORS.length],
          borderWidth: 1,
          tension: 0.3,
          spanGaps: true,
          hidden: true,
        })
      })
    }

    return { labels: jaren, datasets }
  }, [rendementPerJaar, benchmarkRendement, peersRendement, instelling])

  if (!chartData) return null
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">Diplomarendement over tijd</div><div className="chart-sub">Gediplomeerden t+3 / instroom — eigen instelling vs. benchmark</div></div></div>
        <div style={{ height: 280 }}>
          <Line data={chartData} options={{
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { display: true, position: 'top', labels: { color: tick, font: { size: 11 }, boxWidth: 14 } },
              tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%` } },
            },
            scales: {
              x: { grid: { display: false }, ticks: { color: tick } },
              y: { grid: { color: grid }, ticks: { color: tick, callback: v => `${v}%` } },
            },
          }} />
        </div>
      </div>
    </div>
  )
}

function SectorRendementChart({ sectorRendement, dark }) {
  const chartData = useMemo(() => {
    if (!sectorRendement || Object.keys(sectorRendement).length === 0) return null
    const entries = Object.entries(sectorRendement)
      .map(([s, v]) => ({ sector: s, pct: Math.round(v * 1000) / 10 }))
      .sort((a, b) => b.pct - a.pct)
    return {
      labels: entries.map(e => e.sector),
      datasets: [{
        label: 'Rendement %',
        data: entries.map(e => e.pct),
        backgroundColor: entries.map((_, i) => CHART_COLORS[i % CHART_COLORS.length] + 'CC'),
        borderWidth: 0,
        borderRadius: 4,
      }],
    }
  }, [sectorRendement])

  if (!chartData) return null
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">Rendement per sector</div><div className="chart-sub">Gediplomeerden / ingeschrevenen (cumulatief)</div></div></div>
        <div style={{ height: Math.max(160, chartData.labels.length * 36) }}>
          <Bar data={chartData} options={{
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.raw}%` } } },
            scales: {
              x: { grid: { color: grid }, ticks: { color: tick, callback: v => `${v}%` } },
              y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 } } },
            },
          }} />
        </div>
      </div>
    </div>
  )
}

function CohortenTable({ cohorten, dark }) {
  if (!cohorten?.length) return null
  const tick = dark ? '#D1D5DB' : '#374151'
  return (
    <div className="chart-card" style={{ overflowX: 'auto' }}>
      <div className="chart-header"><div><div className="chart-title">Pseudo-cohorten</div><div className="chart-sub">Instroom vs. gediplomeerden na 3, 4 en 5 jaar</div></div></div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', color: tick }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200, #E5E7EB)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Instroom</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Eerstejaars</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+3</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+4</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+5</th>
          </tr>
        </thead>
        <tbody>
          {cohorten.map(c => (
            <tr key={c.instroom_jaar} style={{ borderBottom: '1px solid var(--gray-100, #F3F4F6)' }}>
              <td style={{ padding: '5px 8px' }}>{c.instroom_jaar}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(c.instroom)}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t3 || '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t4 || '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t5 || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function InlineDashboardRendement({ instelling }) {
  const { data, loading, error } = useRendementDashboardData(instelling)
  const dark = useDarkMode()

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Diplomarendement</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>

        <SectionHeader title="Kerncijfers" subtitle="Laatst beschikbare rendementspercentage" />
        <RendementKpis data={data} />

        <SectionHeader title="Rendement trend" subtitle="Verloop diplomarendement vs. benchmark regio" />
        <RendementTrendChart
          rendementPerJaar={data?.rendement_per_jaar}
          benchmarkRendement={data?.benchmark_rendement}
          peersRendement={data?.peers_rendement}
          instelling={instelling}
          dark={dark}
        />

        <SectionHeader title="Rendement per sector" subtitle="Cumulatief rendement per onderdeel" />
        <SectorRendementChart sectorRendement={data?.sector_rendement} dark={dark} />

        <SectionHeader title="Cohorten" subtitle="Pseudo-cohortanalyse: instroom vs. diplomering" />
        <CohortenTable cohorten={data?.pseudo_cohorten} dark={dark} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
