import { useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import {
  useNationaalDashboardData, useDarkMode, DashboardShell, SectionHeader, fmt,
} from '../shared/index'
import { SECTOR_LABELS, darkColors, horizontalBarOpts } from '../shared/chart-opts'

function RankingTable({ alleInstellingen, instelling, dark }) {
  if (!alleInstellingen?.length) return null
  const eigenIdx = alleInstellingen.findIndex(i => i.naam.toLowerCase() === instelling.toLowerCase())
  const { label: tick } = darkColors(dark)
  return (
    <div className="chart-card" style={{ overflowX: 'auto' }}>
      <div className="chart-header"><div><div className="chart-title">Nationale ranking</div><div className="chart-sub">Totaal ingeschrevenen — alle instellingen</div></div></div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', color: tick }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200, #E5E7EB)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>#</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Instelling</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Ingeschrevenen</th>
          </tr>
        </thead>
        <tbody>
          {alleInstellingen.slice(0, 20).map((inst, i) => {
            const isOwn = inst.naam.toLowerCase() === instelling.toLowerCase()
            return (
              <tr key={inst.naam} style={{
                borderBottom: '1px solid var(--gray-100, #F3F4F6)',
                background: isOwn ? 'var(--primary-50, #EFF6FF)' : undefined,
                fontWeight: isOwn ? 700 : 400,
              }}>
                <td style={{ padding: '5px 8px' }}>{i + 1}</td>
                <td style={{ padding: '5px 8px' }}>{inst.naam}</td>
                <td style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(inst.ingeschrevenen)}</td>
              </tr>
            )
          })}
          {eigenIdx >= 20 && (
            <>
              <tr><td colSpan={3} style={{ padding: '4px 8px', color: 'var(--gray-400)' }}>…</td></tr>
              <tr style={{ background: 'var(--primary-50, #EFF6FF)', fontWeight: 700 }}>
                <td style={{ padding: '5px 8px' }}>{eigenIdx + 1}</td>
                <td style={{ padding: '5px 8px' }}>{alleInstellingen[eigenIdx].naam}</td>
                <td style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(alleInstellingen[eigenIdx].ingeschrevenen)}</td>
              </tr>
            </>
          )}
        </tbody>
      </table>
    </div>
  )
}

function PositieKpis({ eigenPositie }) {
  if (!eigenPositie || Object.keys(eigenPositie).length === 0) return null
  const entries = Object.entries(eigenPositie).sort((a, b) => a[1] - b[1])
  return (
    <div className="kpi-grid">
      {entries.map(([sector, pos]) => (
        <div key={sector} className="kpi-card">
          <div className="kpi-label">{SECTOR_LABELS[sector] || sector}</div>
          <div className="kpi-value">#{pos}</div>
          <div className="kpi-sub">positie landelijk</div>
        </div>
      ))}
    </div>
  )
}

function SectorTrendChart({ eigenSectoren, dark }) {
  const chartData = useMemo(() => {
    if (!eigenSectoren || Object.keys(eigenSectoren).length === 0) return null
    const sectors = Object.keys(eigenSectoren)
    const allJaren = [...new Set(sectors.flatMap(s => Object.keys(eigenSectoren[s]).map(String)))].sort()
    if (allJaren.length < 2) return null
    return {
      labels: allJaren,
      datasets: sectors.map((s, i) => ({
        label: SECTOR_LABELS[s] || s,
        data: allJaren.map(j => eigenSectoren[s][j] ?? eigenSectoren[s][Number(j)] ?? 0),
        borderColor: CHART_COLORS[i % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '33',
        borderWidth: 2,
        tension: 0.3,
        fill: false,
      })),
    }
  }, [eigenSectoren])

  if (!chartData) return null
  const { tick, grid } = darkColors(dark)
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">Eigen sectoren over tijd</div><div className="chart-sub">Ingeschrevenen per sector/leerweg</div></div></div>
        <div style={{ height: 280 }}>
          <Line data={chartData} options={{
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: true, position: 'top', labels: { color: tick, font: { size: 11 }, boxWidth: 14 } } },
            scales: {
              x: { grid: { display: false }, ticks: { color: tick } },
              y: { grid: { color: grid }, ticks: { color: tick } },
            },
          }} />
        </div>
      </div>
    </div>
  )
}

function MarktaandeelChart({ eigenSectoren, sectorenLandelijk, dark }) {
  const chartData = useMemo(() => {
    if (!eigenSectoren || !sectorenLandelijk) return null
    const sectors = Object.keys(eigenSectoren)
    const latestYear = Math.max(...sectors.flatMap(s => Object.keys(eigenSectoren[s]).map(Number)))
    const entries = sectors
      .map(s => {
        const eigen = eigenSectoren[s]?.[latestYear] || 0
        const landelijk = sectorenLandelijk[s]?.[latestYear] || 0
        const pct = landelijk > 0 ? Math.round((eigen / landelijk) * 1000) / 10 : 0
        return { sector: s, pct }
      })
      .filter(e => e.pct > 0)
      .sort((a, b) => b.pct - a.pct)
    if (!entries.length) return null
    return {
      labels: entries.map(e => SECTOR_LABELS[e.sector] || e.sector),
      datasets: [{
        label: 'Marktaandeel %',
        data: entries.map(e => e.pct),
        backgroundColor: entries.map((_, i) => CHART_COLORS[i % CHART_COLORS.length] + 'CC'),
        borderWidth: 0,
        borderRadius: 4,
      }],
    }
  }, [eigenSectoren, sectorenLandelijk])

  if (!chartData) return null
  const { tick, grid } = darkColors(dark)
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">Marktaandeel per sector</div><div className="chart-sub">Percentage van landelijk totaal (laatste jaar)</div></div></div>
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

export function InlineDashboardNationaal({ instelling }) {
  const { data, loading, error } = useNationaalDashboardData(instelling)
  const dark = useDarkMode()

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Landelijk overzicht</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>

        <SectionHeader title="Positie per sector" subtitle="Ranking binnen alle instellingen per sector/leerweg" />
        <PositieKpis eigenPositie={data?.eigen_positie} />

        <SectionHeader title="Marktaandeel" subtitle="Aandeel in landelijk totaal per sector" />
        <MarktaandeelChart eigenSectoren={data?.eigen_sectoren} sectorenLandelijk={data?.sectoren_landelijk} dark={dark} />

        <SectionHeader title="Trend" subtitle="Ingeschrevenen per sector over tijd" />
        <SectorTrendChart eigenSectoren={data?.eigen_sectoren} dark={dark} />

        <SectionHeader title="Ranking" subtitle="Top instellingen naar totaal ingeschrevenen" />
        <RankingTable alleInstellingen={data?.alle_instellingen} instelling={instelling} dark={dark} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/datasets/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling</a></li>
            <li><a href="https://onderwijsdata.duo.nl/datasets/mbo-studenten-per-instelling" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — MBO studenten per instelling</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
