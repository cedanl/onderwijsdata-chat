import TabelScroll from '../../TabelScroll'
import { COLOR_EIGEN } from '../../../constants'
import { useDarkMode } from './hooks'
import { fmt } from './getal'
import { SectionHeader, ChartCard, ROA_AIS, ROA_SIS, roaPeilmoment } from './shell'
import { Grafiek } from './grafiek'
import { darkColors, horizontalBarOpts, oordeelKleur, TIK_LIGGEND, categorieTicks } from './chart-opts'
import { MomentopnameBanner, uwvBron } from './momentopname'

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
  const h = Math.max(160, niveaus.length * 72)

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
                    const typering = prognose[niveau]?.[key]
                    const oordeel = _TYPERING_OORDEEL[typering?.toLowerCase()]
                    const color = oordeel ? oordeelKleur(oordeel, dark) : 'var(--muted-text)'
                    return (
                      <td key={key} style={{ textAlign: 'center', padding: '6px 8px' }}>
                        {typering ? <span style={{ color, fontWeight: 600 }}>{typering}</span> : '—'}
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
        subtitle={`Provincie ${provincie}${gefilterdOp.length > 0 ? ` — sectoren: ${gefilterdOp.map(s => s.toLowerCase()).join(', ')}` : ''}`}
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
