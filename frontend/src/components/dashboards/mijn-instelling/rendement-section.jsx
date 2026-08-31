import { useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import { SectionHeader, ChartCard, fmt, darkColors, horizontalBarOpts } from '../shared/index'

function LatestCohortKpi({ cohorten }) {
  const last = cohorten.at(-1)
  return (
    <div className="kpi-card">
      <div className="kpi-label">Instroom {last.instroom_jaar}</div>
      <div className="kpi-value">{fmt(last.instroom)}</div>
      <div className="kpi-sub">eerstejaars in cohort</div>
    </div>
  )
}

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
          <div className="kpi-label">Rendement cohort {latest[0]}</div>
          <div className="kpi-value">{(latest[1] * 100).toFixed(1)}%</div>
          <div className="kpi-sub">gediplomeerden t+3 / instroom</div>
          {delta != null && <div className="kpi-sub" style={{ color: delta >= 0 ? '#16A34A' : '#DC2626' }}>{delta >= 0 ? '+' : ''}{delta.toFixed(1)}pp t.o.v. {prev[0]}</div>}
        </div>
      )}
      {data.pseudo_cohorten?.length > 0 && <LatestCohortKpi cohorten={data.pseudo_cohorten} />}
    </div>
  )
}

function RendementTrendChart({ rendementPerJaar, benchmarkRendement, peersRendement, instelling, dark }) {
  const { tick, grid, label } = darkColors(dark)
  const chartData = useMemo(() => {
    if (!rendementPerJaar || Object.keys(rendementPerJaar).length < 2) return null
    const jaren = [...new Set([
      ...Object.keys(rendementPerJaar),
      ...Object.keys(benchmarkRendement || {}),
    ])].sort((a, b) => a.localeCompare(b, 'nl'))

    const datasets = [{
      label: instelling,
      data: jaren.map(j => rendementPerJaar[j] != null ? Math.round(rendementPerJaar[j] * 1000) / 10 : null),
      borderColor: CHART_COLORS[0],
      backgroundColor: CHART_COLORS[0] + '33',
      borderWidth: 3, tension: 0.3, spanGaps: true,
    }]

    if (benchmarkRendement && Object.keys(benchmarkRendement).length > 0) {
      datasets.push({
        label: 'Benchmark (regio)',
        data: jaren.map(j => benchmarkRendement[j] != null ? Math.round(benchmarkRendement[j] * 1000) / 10 : null),
        borderColor: '#9CA3AF', backgroundColor: '#9CA3AF33',
        borderWidth: 2, borderDash: [5, 4], tension: 0.3, spanGaps: true,
      })
    }

    if (peersRendement) {
      Object.entries(peersRendement).forEach(([naam, rend], i) => {
        datasets.push({
          label: naam,
          data: jaren.map(j => rend[j] != null ? Math.round(rend[j] * 1000) / 10 : null),
          borderColor: CHART_COLORS[(i + 2) % CHART_COLORS.length],
          borderWidth: 1, tension: 0.3, spanGaps: true, hidden: true,
        })
      })
    }

    return { labels: jaren, datasets }
  }, [rendementPerJaar, benchmarkRendement, peersRendement, instelling])

  if (!chartData) return null
  return (
    <ChartCard title="Diplomarendement over tijd" subtitle="Gediplomeerden t+3 / instroom — eigen instelling vs. benchmark">
      <div style={{ height: 280 }}>
        <Line data={chartData} options={{
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true, position: 'top', labels: { color: label, font: { size: 11 }, boxWidth: 14 },
              onClick: (e, legendItem, legend) => {
                const index = legendItem.datasetIndex
                const chart = legend.chart
                const meta = chart.getDatasetMeta(index)
                meta.hidden = !meta.hidden
                chart.update()
              },
            },
            tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%` } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: tick } },
            y: { grid: { color: grid }, ticks: { color: tick, callback: v => `${v}%` } },
          },
        }} />
      </div>
    </ChartCard>
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
        borderWidth: 0, borderRadius: 4,
      }],
    }
  }, [sectorRendement])

  if (!chartData) return null
  return (
    <ChartCard title="Rendement per sector" subtitle="Gediplomeerden / ingeschrevenen (cumulatief)">
      <div style={{ height: Math.max(160, chartData.labels.length * 36) }}>
        <Bar data={chartData} options={horizontalBarOpts(dark, '%')} />
      </div>
    </ChartCard>
  )
}

function CohortenTable({ cohorten, dark }) {
  if (!cohorten?.length) return null
  // Hide rows where t3 exceeds instroom (WO: total annual diplomas include BSc+MSc,
  // which inflates the count beyond the eerstejaars cohort being tracked).
  const rows = cohorten.filter(c =>
    (c.gediplomeerden_t3 > 0 && c.gediplomeerden_t3 <= c.instroom) ||
    (c.gediplomeerden_t4 > 0 && c.gediplomeerden_t4 <= c.instroom) ||
    (c.gediplomeerden_t5 > 0 && c.gediplomeerden_t5 <= c.instroom)
  )
  if (!rows.length) return null
  const { tick } = darkColors(dark)
  return (
    <ChartCard title="Pseudo-cohorten" subtitle="Instroom vs. gediplomeerden na 3, 4 en 5 jaar" cardStyle={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', color: tick }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Instroom</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Eerstejaars</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+3</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+4</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+5</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.instroom_jaar} style={{ borderBottom: '1px solid var(--gray-100)' }}>
              <td style={{ padding: '5px 8px' }}>{c.instroom_jaar}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(c.instroom)}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t3 || '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t4 || '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{c.gediplomeerden_t5 || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartCard>
  )
}

export function RendementSection({ data, instelling, dark }) {
  if (!data?.gevonden) return null
  return (
    <>
      <SectionHeader title="Diplomarendement" subtitle="Rendement per cohort en sector, vergeleken met regio-peers" />
      <RendementKpis data={data} />
      <RendementTrendChart
        rendementPerJaar={data?.rendement_per_jaar}
        benchmarkRendement={data?.benchmark_rendement}
        peersRendement={data?.peers_rendement}
        instelling={instelling}
        dark={dark}
      />
      <SectorRendementChart sectorRendement={data?.sector_rendement} dark={dark} />
      <CohortenTable cohorten={data?.pseudo_cohorten} dark={dark} />
    </>
  )
}
