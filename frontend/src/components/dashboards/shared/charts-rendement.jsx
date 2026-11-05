import { horizontalBarOpts, benchmarkColor } from './chart-opts'
import { COLOR_EIGEN } from '../../../constants'
import { ChartCard } from './shell'
import { Grafiek } from './grafiek'
import { ratioJaar, ratioPercentage } from './diploma-ratio'
import { jaarLabel } from '../../../schooljaar'

// ─── Rendement vergelijking ───────────────────────────────────────────────────

// Eén jaar voor teller en noemer, voor de eigen instelling én elke peer (#927): het laatste jaar waarin de eigen
// instelling beide heeft. Een peer zonder cijfers in dat jaar valt weg en staat in `weggelaten`, in plaats van een ander
// jaar te lenen. De staven kennen geen drempelkleur: alleen de eigen instelling springt eruit.
export function buildRendementVergelijkingData(data, instelling, dark) {
  const peers_inges = data?.benchmark?.peers?.ingeschrevenen
  const peers_dipl = data?.benchmark?.peers?.gediplomeerden
  if (!peers_inges || !peers_dipl || Object.keys(peers_dipl).length === 0) return null

  const jaar = ratioJaar(data.gediplomeerden, data.ingeschrevenen)
  if (jaar == null) return null

  const entries = [{ naam: instelling, rendement: ratioPercentage(data.gediplomeerden, data.ingeschrevenen, jaar), eigen: true }]
  const weggelaten = []
  for (const [naam, ingesData] of Object.entries(peers_inges)) {
    const rendement = ratioPercentage(peers_dipl[naam], ingesData, jaar)
    if (rendement == null) weggelaten.push(naam)
    else entries.push({ naam, rendement, eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.rendement - a.rendement)

  return {
    jaar,
    perioden: data.perioden,
    weggelaten,
    labels: entries.map(e => e.naam),
    datasets: [{
      label: 'Rendement %',
      data: entries.map(e => e.rendement),
      backgroundColor: entries.map(e => (e.eigen ? COLOR_EIGEN : benchmarkColor(dark))),
      borderRadius: 4,
    }],
  }
}

// De teller is een diplomajaar, de noemer een schooljaar met hetzelfde jaartal: de ondertitel noemt beide (#904).
export function RendementVergelijkingChart({ data, dark }) {
  if (!data) return null
  const { jaar, perioden, weggelaten, ...barData } = data
  const h = Math.max(200, barData.labels.length * 34 + 40)
  const dipl = jaarLabel(jaar, perioden?.gediplomeerden)
  const inges = jaarLabel(jaar, perioden?.ingeschrevenen)
  const zonder = weggelaten?.length ? ` Zonder cijfers over ${dipl} en ${inges}: ${weggelaten.join(', ')}.` : ''
  return (
    <ChartCard
      title="Rendement vergelijking"
      subtitle={`Gediplomeerden ${dipl} / ingeschrevenen ${inges} per instelling, het laatste jaar waarin beide bekend zijn — proxy, geen cohortanalyse.${zonder}`}
    >
      <Grafiek soort="bar" data={barData} options={horizontalBarOpts(dark, '%')} hoogte={h} categorie="Instelling" />
    </ChartCard>
  )
}
