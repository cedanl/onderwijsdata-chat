import { useMemo } from 'react'
import TabelScroll from '../../TabelScroll'
import { CHART_COLORS } from '../../../constants'
import { SectionHeader, ChartCard, Grafiek, fmt, darkColors, afgekapteAs, benchmarkColor, oordeelKleur, WeggelatenNoot } from '../shared/index'
import { asJaar, jaarLabel } from '../../../schooljaar'

const NOOT = { fontSize: '12.5px', color: 'var(--muted-text)' }
const pct = v => Math.round(v * 1000) / 10
// Een cohort heet naar het jaar van zijn eerstejaars: een schooljaar (#904); het soort komt uit de payload, net als
// dat van het diplomajaar.
const cohortJaar = (data, jaar) => jaarLabel(jaar, data?.perioden?.cohorten)
const diplomaJaar = (data, jaar) => jaarLabel(jaar, data?.perioden?.gediplomeerden)

// Mbo: diploma's na drie jaar per eerstejaars, met de definitie en wat niet meetelt uit de payload, zoals het rapport
// (#736, #743). Hbo en wo krijgen geen rendement, alleen de reden (`geen_rendement`, #898).

function LatestCohortKpi({ data }) {
  const last = data.pseudo_cohorten.at(-1)
  return (
    <div className="kpi-card">
      <div className="kpi-label">Instroom {cohortJaar(data, last.instroom_jaar)}</div>
      <div className="kpi-value">{fmt(last.instroom)}</div>
      <div className="kpi-sub">eerstejaars in cohort</div>
    </div>
  )
}

function RendementKpis({ data, dark }) {
  const entries = Object.entries(data.rendement_per_jaar || {}).sort((a, b) => Number(b[0]) - Number(a[0]))
  const latest = entries[0]
  const prev = entries[1]
  const delta = latest && prev ? pct(latest[1]) - pct(prev[1]) : null
  const termijn = data.definitie?.termijn
  const cohort = latest && data.pseudo_cohorten?.find(c => String(c.instroom_jaar) === latest[0])
  return (
    <div className="kpi-grid">
      {latest && (
        <div className="kpi-card">
          <div className="kpi-label">Cohort {cohortJaar(data, latest[0])}</div>
          <div className="kpi-value">{fmt(pct(latest[1]))}%</div>
          <div className="kpi-sub">
            {cohort ? `${fmt(cohort[`gediplomeerden_t${termijn}`])} diploma's in ${diplomaJaar(data, Number(latest[0]) + termijn)} / ${fmt(cohort.instroom)} eerstejaars` : `diploma's na ${termijn} jaar per eerstejaars`}
          </div>
          {delta != null && <div className="kpi-sub" style={{ color: oordeelKleur(delta >= 0 ? 'goed' : 'slecht', dark) }}>{delta >= 0 ? '+' : ''}{fmt(Math.round(delta * 10) / 10)}pp t.o.v. {cohortJaar(data, prev[0])}</div>}
        </div>
      )}
      {data.pseudo_cohorten?.length > 0 && <LatestCohortKpi data={data} />}
    </div>
  )
}

// Wat de verhouding telt en wat niet, vóór de cijfers: ook zonder één cohort staat de uitleg er.
function RendementDefinitie({ definitie }) {
  if (!definitie?.definitie) return null
  return (
    <div className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>
      <p style={{ margin: '0 0 4px' }}><strong>Definitie:</strong> {definitie.definitie}</p>
      {definitie.niet_meegeteld && <p style={{ margin: '0 0 4px' }}><strong>Niet meegeteld:</strong> {definitie.niet_meegeteld}.</p>}
      {definitie.wel_meegeteld && <p style={{ margin: 0 }}><strong>Wel meegeteld:</strong> {definitie.wel_meegeteld}.</p>}
    </div>
  )
}

// {cohort: reden} van de instelling, of {peer: {cohort: reden}}, als [{ reden, namen }]: per reden de cohorten, of de
// peers met hun cohorten. Zo noemt het dashboard elk cohort dat afviel (#898), in plaats van het weg te laten.
export function weggelatenPerReden(weggelaten, peers = false, jaar = String) {
  const per = new Map()
  const voeg = (reden, naam) => per.set(reden, [...(per.get(reden) || []), naam])
  for (const [sleutel, waarde] of Object.entries(weggelaten || {})) {
    if (!peers) { voeg(waarde, jaar(sleutel)); continue }
    const cohorten = new Map()
    for (const [cohort, reden] of Object.entries(waarde)) cohorten.set(reden, [...(cohorten.get(reden) || []), jaar(cohort)])
    for (const [reden, jaren] of cohorten) voeg(reden, `${sleutel} (${jaren.join(', ')})`)
  }
  return [...per].map(([reden, namen]) => ({ reden, namen }))
}

function WeggelatenNoten({ weggelaten, peers, label, jaar }) {
  return weggelatenPerReden(weggelaten, peers, jaar).map(({ reden, namen }) => (
    <WeggelatenNoot key={reden} namen={namen} reden={label ? `${label}: ${reden}` : reden} />
  ))
}

function RendementTrendChart({ data, instelling, dark }) {
  const { tick, grid, label } = darkColors(dark)
  const { rendement_per_jaar: rendementPerJaar, benchmark_rendement: benchmarkRendement, peers_rendement: peersRendement } = data
  const benchmarkLabel = data.benchmark_label || 'Regiogemiddelde'
  const nPerJaar = data.benchmark_n_per_jaar
  const soort = data.perioden?.cohorten
  const chartData = useMemo(() => {
    if (!rendementPerJaar || Object.keys(rendementPerJaar).length < 2) return null
    const jaren = [...new Set([
      ...Object.keys(rendementPerJaar),
      ...Object.keys(benchmarkRendement || {}),
    ])].sort((a, b) => a.localeCompare(b, 'nl'))

    const datasets = [{
      label: instelling,
      data: jaren.map(j => rendementPerJaar[j] != null ? pct(rendementPerJaar[j]) : null),
      borderColor: CHART_COLORS[0],
      backgroundColor: CHART_COLORS[0] + '33',
      borderWidth: 3, tension: 0.3, spanGaps: true,
    }]

    if (benchmarkRendement && Object.keys(benchmarkRendement).length > 0) {
      datasets.push({
        label: benchmarkLabel,
        data: jaren.map(j => benchmarkRendement[j] != null ? pct(benchmarkRendement[j]) : null),
        aantalPeers: jaren.map(j => nPerJaar?.[j] ?? null),
        borderColor: benchmarkColor(dark), backgroundColor: benchmarkColor(dark) + '33',
        borderWidth: 2, borderDash: [5, 4], tension: 0.3, spanGaps: true,
      })
    }

    if (peersRendement) {
      Object.entries(peersRendement).forEach(([naam, rend], i) => {
        datasets.push({
          label: naam,
          data: jaren.map(j => rend[j] != null ? pct(rend[j]) : null),
          borderColor: CHART_COLORS[(i + 2) % CHART_COLORS.length],
          borderWidth: 1, tension: 0.3, spanGaps: true, hidden: true,
        })
      })
    }

    return { labels: jaren.map(j => asJaar(j, soort)), datasets }
  }, [rendementPerJaar, benchmarkRendement, peersRendement, benchmarkLabel, nPerJaar, instelling, soort, dark])

  if (!chartData) return null
  const peers = n => (n == null ? '' : ` (${n} ${n === 1 ? 'instelling' : 'instellingen'})`)
  return (
    <ChartCard title={`${data.definitie?.naam || 'Diploma\'s per eerstejaars'} over tijd`} subtitle={`Per cohort — eigen instelling vs. ${benchmarkLabel}`}>
      <Grafiek soort="line" data={chartData} hoogte={280} options={{
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true, position: 'top', labels: { color: label, boxWidth: 14 },
            },
            tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)}%${peers(ctx.dataset.aantalPeers?.[ctx.dataIndex])}` } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: tick } },
            y: afgekapteAs({ grid: { color: grid }, ticks: { color: tick, callback: v => `${fmt(v)}%` } }, chartData.datasets, tick),
          },
        }} />
    </ChartCard>
  )
}

const _T = ['gediplomeerden_t3', 'gediplomeerden_t4', 'gediplomeerden_t5']

// Een cohort met meer gediplomeerden dan instroom of zonder enig diplomajaar laat de tabel weg, en zegt welke (#902).
// Een ontbrekend diplomajaar is null: '—', geen 0.
export function verdeelCohorten(cohorten) {
  const rows = []
  const teVeel = []
  const zonderDiploma = []
  for (const c of cohorten || []) {
    const bekend = _T.map(t => c[t]).filter(v => v != null)
    const binnenInstroom = bekend.some(v => v > 0 && v <= c.instroom)
    if (!bekend.length) zonderDiploma.push(c.instroom_jaar)
    else if (!binnenInstroom && bekend.some(v => v > c.instroom)) teVeel.push(c.instroom_jaar)
    else rows.push(c)
  }
  return { rows, teVeel, zonderDiploma }
}

// Ook als geen cohort overblijft, zegt de tabel welke er afvielen: de noten staan dan zonder kaart (#898).
function CohortenTable({ data, dark }) {
  const cohorten = data?.pseudo_cohorten
  if (!cohorten?.length) return null
  const { rows, teVeel, zonderDiploma } = verdeelCohorten(cohorten)
  const { tick } = darkColors(dark)
  const jaar = j => cohortJaar(data, j)
  const noten = (
    <>
      <WeggelatenNoot namen={teVeel.map(jaar)} reden="meer gediplomeerden dan instroom, dus geen cohortmaat" />
      <WeggelatenNoot namen={zonderDiploma.map(jaar)} reden="nog geen diplomajaar na 3, 4 of 5 jaar" />
    </>
  )
  if (!rows.length) return <div style={NOOT}>{noten}</div>
  return (
    <ChartCard title="Eerstejaars en diploma's per cohort" subtitle="Eerstejaars van het cohort en de diploma's van de instelling 3, 4 en 5 jaar later">
      <TabelScroll label="Eerstejaars en diploma's per cohort" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', color: tick }}>
        <caption className="sr-only">{"Eerstejaars per cohort en de diploma's van de instelling 3, 4 en 5 jaar later"}</caption>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th scope="col" style={{ textAlign: 'left', padding: '6px 8px' }}>Cohort</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Eerstejaars</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+3</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+4</th>
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Dipl. t+5</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.instroom_jaar} style={{ borderBottom: '1px solid var(--gray-100)' }}>
              <td style={{ padding: '5px 8px' }}>{jaar(c.instroom_jaar)}</td>
              <td style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(c.instroom)}</td>
              {_T.map(t => <td key={t} style={{ textAlign: 'right', padding: '5px 8px' }}>{fmt(c[t])}</td>)}
            </tr>
          ))}
        </tbody>
      </TabelScroll>
      {noten}
    </ChartCard>
  )
}

// Hbo en wo: geen lege sectie, één noot waarom er geen rendement staat en waar het wel kan (#898).
function GeenRendement({ reden }) {
  return (
    <>
      <SectionHeader title="Diplomarendement" />
      <p className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>{reden}</p>
    </>
  )
}

export function RendementSection({ data, instelling, dark }) {
  if (!data?.gevonden) return null
  if (data.geen_rendement) return <GeenRendement reden={data.geen_rendement} />
  const naam = data.definitie?.naam || 'Diplomarendement'
  return (
    <>
      <SectionHeader title={naam} subtitle="Een ruwe verhouding per cohort, geen cohortrendement; vergeleken met de regio" />
      <RendementDefinitie definitie={data.definitie} />
      <RendementKpis data={data} dark={dark} />
      <div style={NOOT}><WeggelatenNoten weggelaten={data.weggelaten} jaar={j => cohortJaar(data, j)} /></div>
      <RendementTrendChart data={data} instelling={instelling} dark={dark} />
      <div style={NOOT}><WeggelatenNoten weggelaten={data.peers_weggelaten} peers label="niet in het regiogemiddelde" jaar={j => cohortJaar(data, j)} /></div>
      <CohortenTable data={data} dark={dark} />
    </>
  )
}
