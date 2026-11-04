import { useMemo } from 'react'
import TabelScroll from '../../TabelScroll'
import {
  useArbeidsmarktmatchDashboardData, useRegioDashboardData,
  useDarkMode, DashboardShell, SectionHeader, RegioBadges,
  RoaSection, PrognoseSection, UwvSection,
  darkColors, horizontalBarOpts, SECTOR_LABELS, ChartCard, Grafiek, oordeelKleur,
  DashboardSources, BRONNEN_ARBEIDSMARKT, buildSupplyDemandData, WeggelatenNoot,
  NietGeladen, DeelLading, gatenVan,
} from '../shared/index'

// Van /api/dashboard/regio toont dit dashboard alleen de UWV- en ROA-onderdelen; de DUO-gaten horen bij mijn instelling.
const REGIO_BRONNEN = ['UWV', 'ROA']

// Tekst, dus 4,5:1 in beide thema's (#905): evenwicht #16A34A haalde op wit 3,3:1. Het woord staat er ook.
const MATCH_OORDEEL = { schaarste: 'slecht', overaanbod: 'neutraal', evenwicht: 'goed' }
const MATCH_LABELS = { schaarste: 'Schaarste', overaanbod: 'Overaanbod', evenwicht: 'Evenwicht' }

function MatchScoreSection({ matchScore, dark }) {
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
            <div className="kpi-value" style={{ color: MATCH_OORDEEL[score] ? oordeelKleur(MATCH_OORDEEL[score], dark) : 'inherit', fontSize: '1rem' }}>
              {MATCH_LABELS[score] || score}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function SupplyDemandChart({ gediplomeerdenPerSector, vacaturesPerSector, dark }) {
  const chartData = useMemo(
    () => buildSupplyDemandData(gediplomeerdenPerSector, vacaturesPerSector),
    [gediplomeerdenPerSector, vacaturesPerSector],
  )

  if (!chartData) return null
  const { weggelaten, ...barData } = chartData
  const { label } = darkColors(dark)
  const baseOpts = horizontalBarOpts(dark)
  return (
    <ChartCard
      title="Gediplomeerden vs. vacatures per sector"
      subtitle="Gemiddeld aantal gediplomeerden (3 jaar) vs. gerelateerde vacatures (UWV). Een beroepencluster dat bij meer sectoren hoort, telt per sector naar rato mee."
    >
      <Grafiek soort="bar" data={barData} categorie="Sector" hoogte={Math.max(200, barData.labels.length * 50)} options={{
          ...baseOpts,
          plugins: {
            ...baseOpts.plugins,
            legend: {
              display: true, position: 'top', labels: { color: label, boxWidth: 14 },
              onClick: (e, legendItem, legend) => {
                const index = legendItem.datasetIndex
                const chart = legend.chart
                const meta = chart.getDatasetMeta(index)
                meta.hidden = !meta.hidden
                chart.update()
              },
            },
          },
        }} />
      <WeggelatenNoot namen={weggelaten} reden="geen gediplomeerden in de laatste drie jaar" />
    </ChartCard>
  )
}

function RoaNiveauTable({ roaPerNiveau, dark }) {
  if (!roaPerNiveau || Object.keys(roaPerNiveau).length === 0) return null
  const { label: tick } = darkColors(dark)
  const entries = Object.entries(roaPerNiveau)
  return (
    <ChartCard title="Arbeidsmarktpositie per niveau" subtitle="ROA — werkloosheid, vast dienstverband, buiten vakrichting">
      <TabelScroll label="Arbeidsmarktpositie per niveau" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', color: tick }}>
        <caption className="sr-only">Arbeidsmarktpositie per opleidingsniveau (ROA)</caption>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th scope="col" style={{ textAlign: 'left', padding: '6px 8px' }}>Niveau</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Werkloosheid</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Vast dienstverband</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Buiten vakrichting</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([niveau, vals]) => (
            <tr key={niveau} style={{ borderBottom: '1px solid var(--gray-100)' }}>
              <th scope="row" style={{ textAlign: 'left', fontWeight: 400, padding: '5px 8px' }}>{niveau}</th>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.werkloosheid != null ? `${vals.werkloosheid}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.vast_dienstverband != null ? `${vals.vast_dienstverband}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.buiten_vakrichting != null ? `${vals.buiten_vakrichting}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </TabelScroll>
    </ChartCard>
  )
}

export function InlineDashboardArbeidsmarkt({ instelling }) {
  const { data: matchData, loading, error, opnieuw } = useArbeidsmarktmatchDashboardData(instelling)
  const regio = useRegioDashboardData(instelling)
  const regioData = regio.data
  const dark = useDarkMode()
  const gaten = gatenVan([matchData, { niet_beschikbaar: gatenVan([regioData], REGIO_BRONNEN) }])
  const allesOpnieuw = () => { opnieuw(); regio.opnieuw() }

  return (
    <DashboardShell instelling={instelling} loading={loading} data={matchData} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={matchData?.provincie || regioData?.provincie} arbeidsmarktregio={matchData?.arbeidsmarktregio || regioData?.arbeidsmarktregio} bron="DUO, UWV &amp; ROA" />
        <NietGeladen onderdelen={gaten} onOpnieuw={allesOpnieuw} />

        <MatchScoreSection matchScore={matchData?.match_score} dark={dark} />

        <SectionHeader title="Aanbod vs. vraag" subtitle="Gediplomeerden tegenover gerelateerde vacatures" />
        <SupplyDemandChart
          gediplomeerdenPerSector={matchData?.gediplomeerden_per_sector}
          vacaturesPerSector={matchData?.vacatures_per_sector}
          dark={dark}
        />

        <SectionHeader title="Arbeidsmarktpositie" subtitle="ROA-indicatoren per opleidingsniveau" />
        <RoaNiveauTable roaPerNiveau={matchData?.roa_per_niveau} dark={dark} />

        <DeelLading titel="Vacatures en prognoses in de regio" loading={regio.loading} error={regio.error} onOpnieuw={regio.opnieuw} hoogte={480}>
          <RoaSection data={regioData} dark={dark} />
          <PrognoseSection data={regioData} />
          <UwvSection data={regioData} provincie={regioData?.provincie} dark={dark} />
        </DeelLading>

        <DashboardSources sources={BRONNEN_ARBEIDSMARKT} />
      </div>
    </DashboardShell>
  )
}
