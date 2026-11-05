import TabelScroll from '../../TabelScroll'
import { COLOR_EIGEN } from '../../../constants'
import { useDarkMode } from './hooks'
import { fmt } from './getal'
import { SectionHeader, ChartCard, ROA_AIS, ROA_SIS, roaPeilmoment } from './shell'
import { Grafiek } from './grafiek'
import { darkColors, horizontalBarOpts, oordeelKleur, TIK_LIGGEND, categorieTicks, staafHoogte, SECTOR_LABELS, DREMPELLIJNEN } from './chart-opts'
import { MomentopnameBanner, uwvBron } from './momentopname'
import { WeggelatenNoot } from './ondergrens'

// ─── Arbeidsmarktmatch ───────────────────────────────────────────────────────
// Tekst, dus 4,5:1 in beide thema's (#905): evenwicht #16A34A haalde op wit 3,3:1. Het woord staat er ook.
export const MATCH_OORDEEL = { schaarste: 'slecht', overaanbod: 'neutraal', evenwicht: 'goed' }
export const MATCH_LABELS = { schaarste: 'Schaarste', overaanbod: 'Overaanbod', evenwicht: 'Evenwicht' }
// Vanaf zoveel sectoren met een score staat de match als staafgrafiek, daaronder als tegels (#949): Curio kreeg 17
// gekleurde tegels als eerste onderdeel van het dashboard.
export const MATCH_GRAFIEK_VANAF = 8
// Een staaf is hoogstens zo lang (#952): één uitschieter (Tilburg University, Techniek: 52,15) maakte de rest
// onleesbaar. De echte waarde staat in de tooltip, de waardentabel en een noot onder de grafiek.
export const MATCH_KAP = 5

const sectorNaam = s => SECTOR_LABELS[s] || s

// De staven van de match (#949): per sector `match_verhouding` (vacature-aandeel gedeeld door diploma-aandeel, uit
// data/dashboard.py), aflopend. Eén reeks per label, zodat legenda en waardentabel het label in woorden geven en de
// kleur niet de enige drager is; een sector staat alleen in de reeks van zijn eigen label. Een sector met een label
// maar zonder verhouding (geen gediplomeerden) staat in `zonderVerhouding`. `data` is de staaflengte, gekapt op
// MATCH_KAP; `waarden` de echte verhouding, voor tooltip en waardentabel. `afgekapt` noemt de gekapte sectoren.
export function buildMatchVerhoudingData(matchScore, verhouding, dark) {
  const sectoren = Object.keys(matchScore || {}).filter(s => matchScore[s] != null)
  const met = sectoren.filter(s => typeof verhouding?.[s] === 'number').sort((a, b) => verhouding[b] - verhouding[a])
  if (!met.length) return null
  return {
    labels: met.map(sectorNaam),
    datasets: ['schaarste', 'evenwicht', 'overaanbod'].map(score => {
      const waarden = met.map(s => (matchScore[s] === score ? verhouding[s] : null))
      return {
        label: MATCH_LABELS[score],
        data: waarden.map(v => (v == null ? null : Math.min(v, MATCH_KAP))),
        waarden,
        backgroundColor: oordeelKleur(MATCH_OORDEEL[score], dark),
        borderWidth: 0,
        borderRadius: 4,
      }
    }),
    zonderVerhouding: sectoren.filter(s => !met.includes(s)).map(sectorNaam),
    afgekapt: met.filter(s => verhouding[s] > MATCH_KAP).map(s => ({ sector: sectorNaam(s), waarde: verhouding[s] })),
  }
}

// De drempels als waarden op de as: schaarste boven `drempel`, overaanbod onder 1 / `drempel` (_match_label).
export function matchDrempels(drempel) {
  return drempel > 0 ? [1 / drempel, drempel] : []
}

// Op 390 px is de as met sectornamen smal: een naam breekt af op MATCH_LABEL_BREEDTE tekens ("Ondernemerschap" past
// nog); elke sector krijgt een eigen naam op de as en een rij voor zijn regels (staafHoogte, zoals elke liggende staaf).
const MATCH_LABEL_BREEDTE = 15

export function MatchVerhoudingChart({ matchScore, verhouding, drempel, dark }) {
  const uitkomst = buildMatchVerhoudingData(matchScore, verhouding, dark)
  if (!uitkomst) return null
  const { zonderVerhouding, afgekapt, ...data } = uitkomst
  const { tick, label } = darkColors(dark)
  const baseOpts = horizontalBarOpts(dark)
  const drempels = matchDrempels(drempel)
  const grootste = Math.max(...data.datasets.flatMap(d => d.data).filter(v => v != null), ...drempels)
  const echt = ctx => ctx.dataset.waarden?.[ctx.dataIndex] ?? ctx.raw
  return (
    <ChartCard
      title="Match per sector"
      subtitle="Vacature-aandeel gedeeld door diploma-aandeel: 1 is gelijk, hoger is meer vraag dan aanbod"
    >
      <Grafiek soort="bar" data={data} categorie="Sector" hoogte={staafHoogte(data.labels, { perRij: 30, kader: 110, minimum: 0, breedte: MATCH_LABEL_BREEDTE })} plugins={[DREMPELLIJNEN]} options={{
          ...baseOpts,
          plugins: {
            ...baseOpts.plugins,
            legend: { display: true, position: 'top', labels: { color: label, boxWidth: 14 } },
            tooltip: {
              filter: item => item.raw != null,
              callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(echt(ctx))} keer` },
            },
            drempellijnen: { waarden: drempels, kleur: tick },
          },
          scales: {
            x: {
              ...baseOpts.scales.x,
              stacked: true,
              beginAtZero: true,
              suggestedMax: Math.ceil(grootste * 1.1 * 10) / 10,
              ...(afgekapt.length > 0 && { max: MATCH_KAP }),
              title: { display: true, text: 'vacature-aandeel ÷ diploma-aandeel', color: tick },
            },
            y: { ...baseOpts.scales.y, stacked: true, ticks: { ...categorieTicks(tick, MATCH_LABEL_BREEDTE), autoSkip: false } },
          },
        }} />
      {drempels.length > 0 && (
        <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '8px 0 0' }}>
          Stippellijnen: de drempels. Boven {fmt(drempel)} is het schaarste, onder {fmt(Math.round(drempels[0] * 100) / 100)} overaanbod
          (het diploma-aandeel is dan meer dan {fmt(drempel)} keer het vacature-aandeel), daartussen evenwicht.
        </p>
      )}
      {afgekapt.length > 0 && (
        <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '8px 0 0' }}>
          Staaf afgekapt bij {fmt(MATCH_KAP)}: {afgekapt.map(a => `${a.sector} (${fmt(a.waarde)})`).join(', ')}.
        </p>
      )}
      <WeggelatenNoot namen={zonderVerhouding} reden="geen gediplomeerden om het vacature-aandeel tegen af te zetten" />
    </ChartCard>
  )
}

// Per reden de sectoren zonder label en verhouding (`match_weggelaten`, #952): te weinig gediplomeerden, geen
// beroepenclusters, geen vacatures. De redenen komen uit de payload; een oudere payload zonder het veld noemt niets.
export function MatchWeggelaten({ weggelaten }) {
  const perReden = new Map()
  for (const [sector, reden] of Object.entries(weggelaten || {})) perReden.set(reden, [...(perReden.get(reden) || []), sectorNaam(sector)])
  return [...perReden].map(([reden, namen]) => <WeggelatenNoot key={reden} namen={namen} reden={reden} />)
}

// ─── Arbeidsmarkt chart components ───────────────────────────────────────────

// "SIS 2024, editie 2025, versie v20251218": het ROA-onderdeel met de editie uit het bronblok van de payload (#904).
const roaNaam = (onderdeel, data) => [onderdeel, roaPeilmoment(data?.bronnen)].filter(Boolean).join(', ')

// Uit het palet: 3:1 tegen de kaart in beide thema's (#905).
const _ROA_INDICATORS = [
  { key: 'werkloosheid', label: 'Werkloos', color: '#EF4444' },
  { key: 'vast dienstverband', label: 'Vast dienstverband', color: '#0D9488' },
  { key: 'buiten de vakrichting', label: 'Buiten vakrichting', color: '#D97706' },
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
      backgroundColor: ind.color,
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
    interaction: TIK_LIGGEND,
    plugins: {
      legend: {
        display: true, position: 'top',
        labels: { color: label, boxWidth: 14 },
      },
      tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.raw)}%` } },
    },
    scales: {
      x: {
        suggestedMax,
        grid: { color: grid },
        ticks: { color: tick, callback: v => `${fmt(v)}%` },
      },
      y: { grid: { display: false }, ticks: categorieTicks(tick) },
    },
  }
  const h = staafHoogte(niveaus, { perRij: 72 })

  return (
    <>
      <SectionHeader
        title="Landelijk referentiekader (ROA)"
        subtitle={`Nationale gemiddelden per opleidingsniveau — niet specifiek voor deze instelling (ROA, ${roaNaam(ROA_SIS, data)})`}
      />
      <ChartCard>
        <Grafiek soort="bar" data={chartData} options={opts} hoogte={h} titel="Landelijk referentiekader (ROA)" categorie="Niveau" />
        <div className="db-noot">
          Landelijk gemiddelde — niet specifiek voor deze instelling of regio
        </div>
      </ChartCard>
    </>
  )
}

// Het oordeel achter een typering; de kleur ervan haalt 4,5:1 als tekst in beide thema's (#905). De tekst zelf blijft
// staan, dus de kleur is een extra, geen enige drager.
const _TYPERING_OORDEEL = {
  'goed': 'goed', 'zeer goed': 'goed',
  'redelijk': 'gemiddeld', 'matig': 'matig',
  'slecht': 'slecht', 'zeer slecht': 'slecht',
  'hoog': 'goed', 'zeer hoog': 'goed', 'erg hoog': 'goed',
  'gemiddeld': 'gemiddeld',
  'laag': 'matig', 'zeer laag': 'slecht', 'erg laag': 'slecht',
  'geen': 'neutraal',
}

const _PROGNOSE_LABELS = {
  'ITA toekomstige arbeidsmarktsituatie in 2030': 'Arbeidsmarktperspectief 2030',
  'verwachte baanopeningen tot 2030': 'Verwachte baanopeningen',
  'verwachte instroom van schoolverlaters tot 2030': 'Verwachte instroom schoolverlaters',
}

// Een typering ("matig") in de kleur van haar oordeel, een aantal (de baanopeningen en de instroom van schoolverlaters,
// #951) als getal; zonder waarde een streepje.
function PrognoseWaarde({ waarde, dark }) {
  if (waarde == null || waarde === '') return '—'
  if (typeof waarde === 'number') return fmt(waarde)
  const oordeel = _TYPERING_OORDEEL[String(waarde).toLowerCase()]
  const color = oordeel ? oordeelKleur(oordeel, dark) : 'var(--muted-text)'
  return <span style={{ color, fontWeight: 600 }}>{waarde}</span>
}

export function PrognoseSection({ data }) {
  const dark = useDarkMode()
  const prognose = data?.arbeidsmarkt_prognose
  if (!prognose || Object.keys(prognose).length === 0) return null
  const niveaus = Object.keys(prognose)
  return (
    <>
      <SectionHeader
        title="Arbeidsmarktprognose tot 2030 (ROA)"
        subtitle="Nationale verwachtingen per opleidingsniveau — niet specifiek voor deze instelling of regio"
      />
      <ChartCard>
        <TabelScroll label="Arbeidsmarktprognose tot 2030" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
            <caption className="sr-only">Arbeidsmarktprognose tot 2030 per opleidingsniveau (ROA)</caption>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
                <th scope="col" style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600 }}>Niveau</th>
                {Object.values(_PROGNOSE_LABELS).map(label => (
                  <th key={label} scope="col" style={{ textAlign: 'center', padding: '6px 8px', fontWeight: 600 }}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {niveaus.map(niveau => (
                <tr key={niveau} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                  <th scope="row" style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>{niveau}</th>
                  {Object.keys(_PROGNOSE_LABELS).map(key => {
                    const waarde = prognose[niveau]?.[key]
                    return (
                      <td key={key} style={{ textAlign: 'center', padding: '6px 8px' }}>
                        <PrognoseWaarde waarde={waarde} dark={dark} />
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </TabelScroll>
          <div className="db-noot">
            Landelijk gemiddelde — niet specifiek voor deze instelling of regio · ROA, {roaNaam(ROA_AIS, data)}
          </div>
        </ChartCard>
    </>
  )
}

export function UwvSection({ data, provincie, dark }) {
  const vac = data?.vacatureaanbod
  if (!vac?.clusters || Object.keys(vac.clusters).length === 0) {
    return (
      <ChartCard title="Vacatureaanbod in de provincie">
        <p style={{ color: 'var(--gray-500)', fontSize: '.85rem', padding: '8px 0' }}>
          Geen vacaturegegevens beschikbaar{provincie ? ` voor ${provincie}` : ''}.
          UWV Open Match data is beschikbaar t/m mei 2023.
        </p>
      </ChartCard>
    )
  }
  const gefilterdOp = vac.gefilterd_op || []
  const clusterHeight = staafHoogte(Object.keys(vac.clusters), { perRij: 32, minimum: 180 })
  // Het blok heette "in de regio"; data en KPI zijn per provincie (UWV, F5 in #951).
  return (
    <>
      <SectionHeader
        title="Vacatureaanbod in de provincie"
        subtitle={gefilterdOp.length > 0
          ? `Clusters passend bij opleidingssectoren — ${uwvBron(vac.peildatum)} (momentopname)`
          : `Openstaande vacatures per beroepscluster — ${uwvBron(vac.peildatum)} (momentopname)`}
      />
      <MomentopnameBanner peildatum={vac.peildatum} />
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
        subtitle={`Provincie ${provincie}${gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(sectorNaam).join(', ')}` : ''}`}
      >
        <Grafiek
          soort="bar"
          hoogte={clusterHeight}
          categorie="Beroepencluster"
          data={{
            labels: Object.keys(vac.clusters),
            datasets: [{
              label: 'Vacatures',
              data: Object.values(vac.clusters),
              // Eén kleur: de clusters staan al op de as, een kleur per staaf zei niets (#905).
              backgroundColor: COLOR_EIGEN,
              borderWidth: 0,
              borderRadius: 4,
            }],
          }}
          options={horizontalBarOpts(dark)}
        />
      </ChartCard>
    </>
  )
}
