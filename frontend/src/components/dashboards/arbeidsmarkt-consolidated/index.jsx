import { useMemo } from 'react'
import TabelScroll from '../../TabelScroll'
import {
  useArbeidsmarktmatchDashboardData, useRegioDashboardData,
  useDarkMode, DashboardShell, SectionHeader, RegioBadges,
  RoaSection, PrognoseSection, UwvSection,
  darkColors, horizontalBarOpts, staafHoogte, SECTOR_LABELS, ChartCard, Grafiek, oordeelKleur,
  DashboardSources, bronnenVan, bronBadge, buildSupplyDemandData, WeggelatenNoot,
  NietGeladen, DeelLading, gatenVan, MomentopnameBanner, MatchDuiding, uwvBron, jarenTekst, fmt,
  MatchVerhoudingChart, MatchWeggelaten, MATCH_OORDEEL, MATCH_LABELS, MATCH_GRAFIEK_VANAF,
} from '../shared/index'

// Van /api/dashboard/regio toont dit dashboard alleen de UWV- en ROA-onderdelen en -bronnen; de DUO-gaten en
// -bronnen daarvan horen bij mijn instelling.
const REGIO_BRONNEN = ['UWV', 'ROA']

function MatchTegels({ entries, dark }) {
  return (
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
  )
}

// De labels zijn een indicatie op een momentopname (#900): daarom de banner met de peildatum erboven en eronder wat
// de drie labels betekenen, met de drempel, de jaren en de herkomst van de sectorindeling uit de payload. Vanaf
// MATCH_GRAFIEK_VANAF sectoren staat de match als staafgrafiek van `match_verhouding` met de drempels als lijn (#949);
// zonder verhoudingen (een oudere payload) blijven het tegels. Een sector zonder label staat met zijn reden eronder
// (`weggelaten`, #952: te weinig gediplomeerden, geen beroepenclusters); een oudere payload zonder redenen noemt de
// reden van toen.
export function MatchScoreSection({ matchScore, verhouding, weggelaten, duiding, dark }) {
  if (!matchScore) return null
  const entries = Object.entries(matchScore).filter(([, v]) => v != null)
  if (entries.length === 0) return null
  const zonderScore = Object.keys(matchScore).filter(s => matchScore[s] == null).map(s => SECTOR_LABELS[s] || s)
  const alsGrafiek = entries.length >= MATCH_GRAFIEK_VANAF && entries.some(([s]) => typeof verhouding?.[s] === 'number')
  return (
    <>
      <SectionHeader title="Match score" subtitle="Indicatie per sector: aandeel in de vacatures tegenover aandeel in de gediplomeerden" />
      {duiding && <MomentopnameBanner peildatum={duiding.vacatures_peildatum} />}
      {alsGrafiek
        ? <MatchVerhoudingChart matchScore={matchScore} verhouding={verhouding} drempel={duiding?.drempel} dark={dark} />
        : <MatchTegels entries={entries} dark={dark} />}
      {weggelaten
        ? <MatchWeggelaten weggelaten={weggelaten} />
        : <WeggelatenNoot namen={zonderScore} reden="geen beroepenclusters in de sectorindeling" />}
      <MatchDuiding duiding={duiding} />
    </>
  )
}

function SupplyDemandChart({ gediplomeerdenPerSector, vacaturesPerSector, duiding, dark }) {
  const chartData = useMemo(
    () => buildSupplyDemandData(gediplomeerdenPerSector, vacaturesPerSector),
    [gediplomeerdenPerSector, vacaturesPerSector],
  )

  if (!chartData) return null
  const { weggelaten, ...barData } = chartData
  const { label } = darkColors(dark)
  const baseOpts = horizontalBarOpts(dark)
  const jaren = jarenTekst(duiding?.diplomajaren)
  return (
    <ChartCard
      title="Gediplomeerden vs. vacatures per sector"
      subtitle={`Gemiddeld aantal gediplomeerden per jaar (DUO${jaren ? `, diplomajaren ${jaren}` : ''}) vs. gerelateerde vacatures (${uwvBron(duiding?.vacatures_peildatum)}). Een beroepencluster dat bij meer sectoren hoort, telt per sector naar rato mee.`}
    >
      <MomentopnameBanner peildatum={duiding?.vacatures_peildatum} />
      <Grafiek soort="bar" data={barData} categorie="Sector" hoogte={staafHoogte(barData.labels, { perRij: 50, kader: 60, minimum: 200 })} options={{
          ...baseOpts,
          plugins: {
            ...baseOpts.plugins,
            legend: {
              display: true, position: 'top', labels: { color: label, boxWidth: 14 },
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
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.werkloosheid != null ? `${fmt(vals.werkloosheid)}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.vast_dienstverband != null ? `${fmt(vals.vast_dienstverband)}%` : '—'}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{vals.buiten_vakrichting != null ? `${fmt(vals.buiten_vakrichting)}%` : '—'}</td>
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
  const bronnen = bronnenVan([matchData, { bronnen: bronnenVan([regioData], REGIO_BRONNEN) }])
  // Provincie en haar herkomst uit dezelfde payload (#904): de match zodra die er is, anders de regio.
  const plaats = matchData?.provincie ? matchData : regioData

  return (
    <DashboardShell instelling={instelling} loading={loading} data={matchData} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={plaats?.provincie} herkomst={plaats?.provincie_herkomst} arbeidsmarktregio={matchData?.arbeidsmarktregio || regioData?.arbeidsmarktregio} vacatures bron={bronBadge(bronnen)} />
        <NietGeladen onderdelen={gaten} onOpnieuw={allesOpnieuw} />

        <MatchScoreSection matchScore={matchData?.match_score} verhouding={matchData?.match_verhouding} weggelaten={matchData?.match_weggelaten} duiding={matchData?.match_duiding} dark={dark} />

        <SectionHeader title="Aanbod vs. vraag" subtitle="Gediplomeerden tegenover gerelateerde vacatures" />
        <SupplyDemandChart
          gediplomeerdenPerSector={matchData?.gediplomeerden_per_sector}
          vacaturesPerSector={matchData?.vacatures_per_sector}
          duiding={matchData?.match_duiding}
          dark={dark}
        />

        <SectionHeader title="Arbeidsmarktpositie" subtitle="ROA-indicatoren per opleidingsniveau" />
        <RoaNiveauTable roaPerNiveau={matchData?.roa_per_niveau} dark={dark} />

        <DeelLading titel="Vacatures en prognoses in de regio" loading={regio.loading} error={regio.error} onOpnieuw={regio.opnieuw} hoogte={480}>
          <RoaSection data={regioData} dark={dark} />
          <PrognoseSection data={regioData} />
          <UwvSection data={regioData} provincie={regioData?.provincie} dark={dark} />
        </DeelLading>

        <DashboardSources sources={bronnen} />
      </div>
    </DashboardShell>
  )
}
