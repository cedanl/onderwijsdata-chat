import { horizontalBarOpts, benchmarkColor } from './chart-opts'
import { COLOR_EIGEN } from '../../../constants'
import { ChartCard } from './shell'
import { Grafiek } from './grafiek'
import { ratioJaar, ratioPercentage } from './diploma-ratio'

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

export function RendementVergelijkingChart({ data, dark }) {
  if (!data) return null
  const h = Math.max(200, data.labels.length * 34 + 40)
  const zonder = data.weggelaten?.length ? ` Zonder cijfers over ${data.jaar}: ${data.weggelaten.join(', ')}.` : ''
  return (
    <ChartCard
      title="Rendement vergelijking"
      subtitle={`Gediplomeerden / ingeschrevenen van ${data.jaar} per instelling, het laatste jaar waarin beide bekend zijn — proxy, geen cohortanalyse.${zonder}`}
    >
      <Grafiek soort="bar" data={data} options={horizontalBarOpts(dark, '%')} hoogte={h} categorie="Instelling" />
    </ChartCard>
  )
}
