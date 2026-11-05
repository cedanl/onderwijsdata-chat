import { useMemo } from 'react'
import TabelScroll from '../../TabelScroll'
import {
  useNationaalDashboardData, useDarkMode, DashboardShell, SectionHeader, fmt,
  SECTOR_LABELS, darkColors, horizontalBarOpts, tellingAs, ChartCard, Grafiek, sectorKleuren, buildSectorTrendData,
  DashboardSources, BRONNEN_NATIONAAL, POPULATIE_NATIONAAL, TenMinste, OndergrensNoot, WeggelatenNoot,
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
  const kleuren = sectorKleuren(entries.map(e => e.sector))
  return {
    jaar: latestYear,
    weggelaten,
    data: {
      labels: entries.map(e => sectorNaam(e.sector)),
      datasets: [{
        label: 'Marktaandeel %',
        data: entries.map(e => e.pct),
        backgroundColor: entries.map(e => kleuren.get(e.sector)),
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
    <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '0 0 16px' }}>
      Landelijk is hier {landelijk.definitie}. {landelijk.verschil_met_chat}
    </p>
  )
}

// {sector: {jaar: n}} als reeksen voor de ondergrensnoot.
function sectorReeksen(perSector) {
  return Object.entries(perSector || {}).map(([s, onderdrukt]) => ({ label: sectorNaam(s), onderdrukt }))
}

function RankingTable({ alleInstellingen, instelling, populatie, dark }) {
  if (!alleInstellingen?.length) return null
  const eigenIdx = alleInstellingen.findIndex(i => i.naam.toLowerCase() === instelling.toLowerCase())
  const { label: tick } = darkColors(dark)
  return (
    <ChartCard title="Nationale ranking" subtitle={`Totaal ingeschrevenen — ${populatie}`}>
      <TabelScroll label="Nationale ranking" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', color: tick }}>
        <caption className="sr-only">Nationale ranking naar totaal ingeschrevenen</caption>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th scope="col" style={{ textAlign: 'left', padding: '6px 8px' }}>#</th>
            <th scope="col" style={{ textAlign: 'left', padding: '6px 8px' }}>Instelling</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Ingeschrevenen</th>
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
      </TabelScroll>
    </ChartCard>
  )
}

// Een positie waarin een onderdrukte cel meetelt, kan verschuiven: die heet indicatief (#902).
export function PositieKpis({ eigenPositie, onzeker, weggelaten }) {
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

// De eigen sectoren als lijnen; de reeksen bouwt buildSectorTrendData van Mijn instelling, hier zonder vlakvulling.
// Een eigen naam: SectorTrendChart in shared/ is de gestapelde grafiek van Mijn instelling (#907).
export function buildEigenSectorenTrendData(eigenSectoren) {
  const vlakken = buildSectorTrendData(eigenSectoren)
  if (!vlakken) return null
  return {
    ...vlakken,
    datasets: vlakken.datasets.map(d => ({ ...d, backgroundColor: d.borderColor + '33', borderWidth: 2, tension: 0.3, fill: false })),
  }
}

function EigenSectorenTrendChart({ eigenSectoren, dark }) {
  const chartData = useMemo(() => buildEigenSectorenTrendData(eigenSectoren), [eigenSectoren])

  if (!chartData) return null
  const { tick, grid, label } = darkColors(dark)
  return (
    <ChartCard title="Eigen sectoren over tijd" subtitle="Ingeschrevenen per sector/leerweg">
      <Grafiek soort="line" data={chartData} hoogte={280} options={{
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true, position: 'top', labels: { color: label, boxWidth: 14 },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: tick } },
            y: tellingAs({ grid: { color: grid }, ticks: { color: tick } }),
          },
        }} />
    </ChartCard>
  )
}

// Een eigen naam: MarktaandeelChart in shared/ is de marktpositie per instelling in de regio (#907).
function MarktaandeelPerSectorChart({ eigenSectoren, sectorenLandelijk, dark }) {
  const uitkomst = useMemo(
    () => buildMarktaandeelPerSector(eigenSectoren, sectorenLandelijk),
    [eigenSectoren, sectorenLandelijk],
  )
  const chartData = uitkomst?.data
  if (!chartData) return null
  const baseOpts = horizontalBarOpts(dark, '%')
  return (
    <ChartCard title="Marktaandeel per sector" subtitle="Percentage van landelijk totaal (laatste jaar)">
      <Grafiek soort="bar" categorie="Sector" hoogte={Math.max(160, chartData.labels.length * 36)} options={{
          ...baseOpts,
          scales: {
            ...baseOpts.scales,
            x: { ...baseOpts.scales.x, ticks: { ...baseOpts.scales.x.ticks, callback: v => `${v}%` } },
          },
        }} data={chartData} />
      <WeggelatenNoot namen={uitkomst.weggelaten} reden={`geen eigen of landelijke ingeschrevenen in ${uitkomst.jaar}`} />
    </ChartCard>
  )
}

export function InlineDashboardNationaal({ instelling }) {
  const { data, loading, error, opnieuw } = useNationaalDashboardData(instelling)
  const dark = useDarkMode()
  const populatie = POPULATIE_NATIONAAL[data?.type] || 'alle instellingen'

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Landelijk overzicht</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata, som per instelling</span>
        </div>
        <LandelijkDefinitie landelijk={data?.landelijk} />

        <SectionHeader title="Positie per sector" subtitle={`Ranking binnen ${populatie} per sector/leerweg`} />
        <PositieKpis eigenPositie={data?.eigen_positie} onzeker={data?.onderdrukt?.eigen_positie} weggelaten={data?.positie_weggelaten} />

        <SectionHeader title="Marktaandeel" subtitle="Aandeel in landelijk totaal per sector" />
        <MarktaandeelPerSectorChart eigenSectoren={data?.eigen_sectoren} sectorenLandelijk={data?.sectoren_landelijk} dark={dark} />
        <OndergrensNoot reeksen={[
          ...sectorReeksen(data?.onderdrukt?.sectoren_landelijk).map(r => ({ ...r, label: `Landelijk ${r.label}` })),
          ...sectorReeksen(data?.onderdrukt?.eigen_sectoren).map(r => ({ ...r, label: `Eigen ${r.label}` })),
        ]} />

        <SectionHeader title="Trend" subtitle="Ingeschrevenen per sector over tijd" />
        <EigenSectorenTrendChart eigenSectoren={data?.eigen_sectoren} dark={dark} />

        <SectionHeader title="Ranking" subtitle="Top instellingen naar totaal ingeschrevenen" />
        <RankingTable alleInstellingen={data?.alle_instellingen} instelling={instelling} populatie={populatie} dark={dark} />

        <DashboardSources sources={BRONNEN_NATIONAAL[data?.type] || []} />
      </div>
    </DashboardShell>
  )
}
