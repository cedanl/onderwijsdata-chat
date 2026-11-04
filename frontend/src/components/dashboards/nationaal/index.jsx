import { useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { CHART_COLORS } from '../../../constants'
import {
  useNationaalDashboardData, useDarkMode, DashboardShell, SectionHeader, fmt,
  SECTOR_LABELS, darkColors, horizontalBarOpts, tellingAs, ChartCard,
  DashboardSources, BRONNEN_NATIONAAL, TenMinste, OndergrensNoot, WeggelatenNoot,
} from '../shared/index'

const sectorNaam = s => SECTOR_LABELS[s] || s

// Het eigen aandeel per sector in het laatste jaar, aflopend. Een sector zonder eigen of landelijke waarde, of met 0
// eigen ingeschrevenen, valt weg en staat in `weggelaten` (#902).
export function buildMarktaandeelPerSector(eigenSectoren, sectorenLandelijk) {
  if (!eigenSectoren || !sectorenLandelijk) return null
  const sectors = Object.keys(eigenSectoren)
  const jaren = sectors.flatMap(s => Object.keys(eigenSectoren[s]).map(Number))
  if (!jaren.length) return null
  const latestYear = Math.max(...jaren)
  const entries = []
  const weggelaten = []
  for (const s of sectors) {
    const eigen = eigenSectoren[s]?.[latestYear]
    const landelijk = sectorenLandelijk[s]?.[latestYear]
    if (!(eigen > 0) || !(landelijk > 0)) {
      weggelaten.push(sectorNaam(s))
      continue
    }
    entries.push({ sector: s, pct: Math.round((eigen / landelijk) * 1000) / 10 })
  }
  entries.sort((a, b) => b.pct - a.pct)
  if (!entries.length) return null
  return {
    jaar: latestYear,
    weggelaten,
    data: {
      labels: entries.map(e => sectorNaam(e.sector)),
      datasets: [{
        label: 'Marktaandeel %',
        data: entries.map(e => e.pct),
        backgroundColor: entries.map((_, i) => CHART_COLORS[i % CHART_COLORS.length] + 'CC'),
        borderWidth: 0,
        borderRadius: 4,
      }],
    },
  }
}

// Wat "landelijk" hier telt (#903): de som van het DUO-bestand per instelling, niet de vaste CBS-maat van de chat.
// De backend geeft de definitie en het verschil met de chat (`landelijk`); zonder die velden staat er niets.
export function LandelijkDefinitie({ landelijk }) {
  if (!landelijk?.definitie) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: 'var(--font-klein)', color: 'var(--muted-text)', margin: '0 0 16px' }}>
      Landelijk is hier {landelijk.definitie}. {landelijk.verschil_met_chat}
    </p>
  )
}

// {sector: {jaar: n}} als reeksen voor de ondergrensnoot.
function sectorReeksen(perSector) {
  return Object.entries(perSector || {}).map(([s, onderdrukt]) => ({ label: sectorNaam(s), onderdrukt }))
}

function RankingTable({ alleInstellingen, instelling, dark }) {
  if (!alleInstellingen?.length) return null
  const eigenIdx = alleInstellingen.findIndex(i => i.naam.toLowerCase() === instelling.toLowerCase())
  const { label: tick } = darkColors(dark)
  return (
    <ChartCard title="Nationale ranking" subtitle="Totaal ingeschrevenen — alle instellingen" cardStyle={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', color: tick }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
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
                borderBottom: '1px solid var(--gray-100)',
                background: isOwn ? 'var(--blue-50)' : undefined,
                fontWeight: isOwn ? 700 : 400,
              }}>
                <td style={{ padding: '5px 8px' }}>{i + 1}</td>
                <td style={{ padding: '5px 8px' }}>{inst.naam}</td>
                <td style={{ textAlign: 'right', padding: '5px 8px' }}><TenMinste actief={inst.onderdrukt > 0} />{fmt(inst.ingeschrevenen)}</td>
              </tr>
            )
          })}
          {eigenIdx >= 20 && (
            <>
              <tr><td colSpan={3} style={{ padding: '4px 8px', color: 'var(--muted-text)' }}>…</td></tr>
              <tr style={{ background: 'var(--blue-50)', fontWeight: 700 }}>
                <td style={{ padding: '5px 8px' }}>{eigenIdx + 1}</td>
                <td style={{ padding: '5px 8px' }}>{alleInstellingen[eigenIdx].naam}</td>
                <td style={{ textAlign: 'right', padding: '5px 8px' }}><TenMinste actief={alleInstellingen[eigenIdx].onderdrukt > 0} />{fmt(alleInstellingen[eigenIdx].ingeschrevenen)}</td>
              </tr>
            </>
          )}
        </tbody>
      </table>
    </ChartCard>
  )
}

// Een positie waarin een onderdrukte cel meetelt, kan verschuiven: die heet indicatief (#902).
function PositieKpis({ eigenPositie, onzeker, weggelaten }) {
  if (!eigenPositie || Object.keys(eigenPositie).length === 0) return null
  const entries = Object.entries(eigenPositie).sort((a, b) => a[1] - b[1])
  return (
    <>
      <div className="kpi-grid">
        {entries.map(([sector, pos]) => (
          <div key={sector} className="kpi-card">
            <div className="kpi-label">{sectorNaam(sector)}</div>
            <div className="kpi-value">#{pos}</div>
            <div className="kpi-sub">{onzeker?.[sector] > 0 ? 'positie landelijk, indicatief: onderdrukte cellen tellen niet mee' : 'positie landelijk'}</div>
          </div>
        ))}
      </div>
      <WeggelatenNoot namen={(weggelaten || []).map(sectorNaam)} reden="geen ingeschrevenen in het laatste jaar" />
    </>
  )
}

function SectorTrendChart({ eigenSectoren, dark }) {
  const chartData = useMemo(() => {
    if (!eigenSectoren || Object.keys(eigenSectoren).length === 0) return null
    const sectors = Object.keys(eigenSectoren)
    const allJaren = [...new Set(sectors.flatMap(s => Object.keys(eigenSectoren[s]).map(String)))].sort((a, b) => a.localeCompare(b, 'nl'))
    if (allJaren.length < 2) return null
    return {
      labels: allJaren,
      datasets: sectors.map((s, i) => ({
        label: SECTOR_LABELS[s] || s,
        data: allJaren.map(j => eigenSectoren[s][j] ?? eigenSectoren[s][Number(j)] ?? null),
        borderColor: CHART_COLORS[i % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '33',
        borderWidth: 2,
        tension: 0.3,
        fill: false,
      })),
    }
  }, [eigenSectoren])

  if (!chartData) return null
  const { tick, grid, label } = darkColors(dark)
  return (
    <ChartCard title="Eigen sectoren over tijd" subtitle="Ingeschrevenen per sector/leerweg">
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
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: tick } },
            y: tellingAs({ grid: { color: grid }, ticks: { color: tick } }),
          },
        }} />
      </div>
    </ChartCard>
  )
}

function MarktaandeelChart({ eigenSectoren, sectorenLandelijk, dark }) {
  const uitkomst = useMemo(
    () => buildMarktaandeelPerSector(eigenSectoren, sectorenLandelijk),
    [eigenSectoren, sectorenLandelijk],
  )
  const chartData = uitkomst?.data
  if (!chartData) return null
  const baseOpts = horizontalBarOpts(dark, '%')
  return (
    <ChartCard title="Marktaandeel per sector" subtitle="Percentage van landelijk totaal (laatste jaar)">
      <div style={{ height: Math.max(160, chartData.labels.length * 36) }}>
        <Bar data={chartData} options={{
          ...baseOpts,
          scales: {
            ...baseOpts.scales,
            x: { ...baseOpts.scales.x, ticks: { ...baseOpts.scales.x.ticks, callback: v => `${v}%` } },
          },
        }} />
      </div>
      <WeggelatenNoot namen={uitkomst.weggelaten} reden={`geen eigen of landelijke ingeschrevenen in ${uitkomst.jaar}`} />
    </ChartCard>
  )
}

export function InlineDashboardNationaal({ instelling }) {
  const { data, loading, error, opnieuw } = useNationaalDashboardData(instelling)
  const dark = useDarkMode()

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Landelijk overzicht</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata, som per instelling</span>
        </div>
        <LandelijkDefinitie landelijk={data?.landelijk} />

        <SectionHeader title="Positie per sector" subtitle="Ranking binnen alle instellingen per sector/leerweg" />
        <PositieKpis eigenPositie={data?.eigen_positie} onzeker={data?.onderdrukt?.eigen_positie} weggelaten={data?.positie_weggelaten} />

        <SectionHeader title="Marktaandeel" subtitle="Aandeel in landelijk totaal per sector" />
        <MarktaandeelChart eigenSectoren={data?.eigen_sectoren} sectorenLandelijk={data?.sectoren_landelijk} dark={dark} />
        <OndergrensNoot reeksen={[
          ...sectorReeksen(data?.onderdrukt?.sectoren_landelijk).map(r => ({ ...r, label: `Landelijk ${r.label}` })),
          ...sectorReeksen(data?.onderdrukt?.eigen_sectoren).map(r => ({ ...r, label: `Eigen ${r.label}` })),
        ]} />

        <SectionHeader title="Trend" subtitle="Ingeschrevenen per sector over tijd" />
        <SectorTrendChart eigenSectoren={data?.eigen_sectoren} dark={dark} />

        <SectionHeader title="Ranking" subtitle="Top instellingen naar totaal ingeschrevenen" />
        <RankingTable alleInstellingen={data?.alle_instellingen} instelling={instelling} dark={dark} />

        <DashboardSources sources={BRONNEN_NATIONAAL} />
      </div>
    </DashboardShell>
  )
}
