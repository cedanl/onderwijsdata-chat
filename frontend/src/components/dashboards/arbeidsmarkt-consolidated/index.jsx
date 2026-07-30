import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  useArbeidsmarktmatchDashboardData, useRegioDashboardData,
  useDarkMode, DashboardShell, SectionHeader, RegioBadges,
  RoaSection, PrognoseSection, UwvSection,
  darkColors, horizontalBarOpts, SECTOR_LABELS, ChartCard,
} from '../shared/index'

const MATCH_COLORS = { schaarste: '#DC2626', overaanbod: '#2563EB', evenwicht: '#16A34A' }
const MATCH_LABELS = { schaarste: 'Schaarste', overaanbod: 'Overaanbod', evenwicht: 'Evenwicht' }

function MatchScoreSection({ matchScore }) {
  if (!matchScore) return null
  const entries = Object.entries(matchScore).filter(([, v]) => v != null)
  if (entries.length === 0) return null
  return (
    <>
      <SectionHeader title="Match score" subtitle="Verhouding gediplomeerden vs. vacatures per sector" />
      <div className="kpi-grid">
        {entries.map(([sector, score]) => (
          <div key={sector} className="kpi-card">
            <div className="kpi-label">{SECTOR_LABELS[sector] || sector}</div>
            <div className="kpi-value" style={{ color: MATCH_COLORS[score] || 'inherit', fontSize: '1rem' }}>
              {MATCH_LABELS[score] || score}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function SupplyDemandChart({ gediplomeerdenPerSector, vacaturesPerCluster, sectorClusterMapping, dark }) {
  const chartData = useMemo(() => {
    if (!gediplomeerdenPerSector || !vacaturesPerCluster || !sectorClusterMapping) return null
    const sectors = Object.keys(gediplomeerdenPerSector)
    if (!sectors.length) return null
    const diplData = sectors.map(s => gediplomeerdenPerSector[s] || 0)
    const vacData = sectors.map(s => {
      const clusters = sectorClusterMapping[s] || []
      return clusters.reduce((sum, cl) => sum + (vacaturesPerCluster[cl] || 0), 0)
    })
    return {
      labels: sectors.map(s => SECTOR_LABELS[s] || s),
      datasets: [
        { label: 'Gediplomeerden', data: diplData, backgroundColor: '#2563EBCC', borderWidth: 0, borderRadius: 4 },
        { label: 'Vacatures (gerelateerd)', data: vacData, backgroundColor: '#F59E0BCC', borderWidth: 0, borderRadius: 4 },
      ],
    }
  }, [gediplomeerdenPerSector, vacaturesPerCluster, sectorClusterMapping])

  if (!chartData) return null
  const { label } = darkColors(dark)
  const baseOpts = horizontalBarOpts(dark)
  return (
    <ChartCard
      title="Gediplomeerden vs. vacatures per sector"
      subtitle="Gemiddeld aantal gediplomeerden (3 jaar) vs. gerelateerde vacatures (UWV)"
    >
      <div style={{ height: Math.max(200, chartData.labels.length * 50) }}>
        <Bar data={chartData} options={{
          ...baseOpts,
          plugins: {
            ...baseOpts.plugins,
            legend: { display: true, position: 'top', labels: { color: label, font: { size: 11 }, boxWidth: 14 } },
          },
        }} />
      </div>
    </ChartCard>
  )
}

function RoaNiveauTable({ roaPerNiveau, dark }) {
  if (!roaPerNiveau || Object.keys(roaPerNiveau).length === 0) return null
  const { label: tick } = darkColors(dark)
  const entries = Object.entries(roaPerNiveau)
  return (
    <ChartCard title="Arbeidsmarktpositie per niveau" subtitle="ROA — werkloosheid, vast dienstverband, buiten vakrichting" cardStyle={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', color: tick }}>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Niveau</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Werkloosheid</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Vast dienstverband</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Buiten vakrichting</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([niveau, vals]) => (
            <tr key={niveau} style={{ borderBottom: '1px solid var(--gray-100)' }}>
              <td style={{ padding: '5px 8px' }}>{niveau}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.werkloosheid != null ? `${vals.werkloosheid}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.vast_dienstverband != null ? `${vals.vast_dienstverband}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.buiten_vakrichting != null ? `${vals.buiten_vakrichting}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartCard>
  )
}

export function InlineDashboardArbeidsmarkt({ instelling }) {
  const { data: matchData, loading, error } = useArbeidsmarktmatchDashboardData(instelling)
  const { data: regioData } = useRegioDashboardData(instelling)
  const dark = useDarkMode()

  return (
    <DashboardShell instelling={instelling} loading={loading} data={matchData} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={matchData?.provincie || regioData?.provincie} arbeidsmarktregio={matchData?.arbeidsmarktregio || regioData?.arbeidsmarktregio} bron="DUO, UWV &amp; ROA" />

        <MatchScoreSection matchScore={matchData?.match_score} />

        <SectionHeader title="Aanbod vs. vraag" subtitle="Gediplomeerden tegenover gerelateerde vacatures" />
        <SupplyDemandChart
          gediplomeerdenPerSector={matchData?.gediplomeerden_per_sector}
          vacaturesPerCluster={matchData?.vacatures_per_cluster}
          sectorClusterMapping={matchData?.sector_cluster_mapping}
          dark={dark}
        />

        <SectionHeader title="Arbeidsmarktpositie" subtitle="ROA-indicatoren per opleidingsniveau" />
        <RoaNiveauTable roaPerNiveau={matchData?.roa_per_niveau} dark={dark} />

        <RoaSection data={regioData} dark={dark} />
        <PrognoseSection data={regioData} />
        <UwvSection data={regioData} provincie={regioData?.provincie} dark={dark} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://data.overheid.nl/dataset/uwv-open-match-data" target="_blank" rel="noreferrer">UWV Open Match — Vacaturedata per provincie en beroepscluster</a></li>
            <li><a href="https://doi.org/10.34894/DVQTOG" target="_blank" rel="noreferrer">ROA — Arbeidsmarktinformatiesysteem (AIS) 2024</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
