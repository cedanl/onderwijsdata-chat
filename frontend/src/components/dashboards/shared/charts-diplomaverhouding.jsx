import { horizontalBarOpts, benchmarkColor, darkColors, staafHoogte } from './chart-opts'
import { COLOR_EIGEN } from '../../../constants'
import { ChartCard } from './shell'
import { Grafiek } from './grafiek'
import { ratioJaar, ratioPercentage } from './diploma-ratio'
import { jaarLabel } from '../../../schooljaar'

// ─── Diploma's per 100 ingeschrevenen ─────────────────────────────────────────

// De maat heet zo, en niet rendement (#1135): de gediplomeerden en de ingeschrevenen zijn niet dezelfde studenten, dus het
// is geen cohortmaat. Dat is de naam van de grafiek, haar reeks en haar as, en van de KPI-tegel (kpis.jsx).
export const DIPLOMA_VERHOUDING = "Diploma's per 100 ingeschrevenen"

// Eén jaar voor teller en noemer, voor de eigen instelling én elke peer (#927): het laatste jaar waarin de eigen
// instelling beide heeft. Een peer zonder cijfers in dat jaar valt weg en staat in `weggelaten`, in plaats van een ander
// jaar te lenen. De staven kennen geen drempelkleur: alleen de eigen instelling springt eruit.
export function buildDiplomaVerhoudingData(data, instelling, dark) {
  const peers_inges = data?.benchmark?.peers?.ingeschrevenen
  const peers_dipl = data?.benchmark?.peers?.gediplomeerden
  if (!peers_inges || !peers_dipl || Object.keys(peers_dipl).length === 0) return null

  const jaar = ratioJaar(data.gediplomeerden, data.ingeschrevenen)
  if (jaar == null) return null

  const entries = [{ naam: instelling, verhouding: ratioPercentage(data.gediplomeerden, data.ingeschrevenen, jaar), eigen: true }]
  const weggelaten = []
  for (const [naam, ingesData] of Object.entries(peers_inges)) {
    const verhouding = ratioPercentage(peers_dipl[naam], ingesData, jaar)
    if (verhouding == null) weggelaten.push(naam)
    else entries.push({ naam, verhouding, eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.verhouding - a.verhouding)

  return {
    jaar,
    perioden: data.perioden,
    weggelaten,
    labels: entries.map(e => e.naam),
    datasets: [{
      label: DIPLOMA_VERHOUDING,
      data: entries.map(e => e.verhouding),
      backgroundColor: entries.map(e => (e.eigen ? COLOR_EIGEN : benchmarkColor(dark))),
      borderRadius: 4,
    }],
  }
}

// De waardeas heeft een titel, zodat het getal een eenheid heeft.
function verhoudingOpts(dark) {
  const opts = horizontalBarOpts(dark, ' per 100 ingeschrevenen')
  const { label } = darkColors(dark)
  return { ...opts, scales: { ...opts.scales, x: { ...opts.scales.x, title: { display: true, text: DIPLOMA_VERHOUDING, color: label } } } }
}

// De teller is een diplomajaar, de noemer een schooljaar met hetzelfde jaartal: de ondertitel noemt beide (#904).
export function DiplomaVerhoudingChart({ data, dark }) {
  if (!data) return null
  const { jaar, perioden, weggelaten, ...barData } = data
  const h = staafHoogte(barData.labels, { minimum: 200 })
  const dipl = jaarLabel(jaar, perioden?.gediplomeerden)
  const inges = jaarLabel(jaar, perioden?.ingeschrevenen)
  const zonder = weggelaten?.length ? ` Zonder cijfers over ${dipl} en ${inges}: ${weggelaten.join(', ')}.` : ''
  return (
    <ChartCard
      title={DIPLOMA_VERHOUDING}
      subtitle={`Gediplomeerden ${dipl} per 100 ingeschrevenen ${inges}, het laatste jaar waarin beide bekend zijn. Het is geen rendement: de diploma's komen niet van dezelfde studenten.${zonder}`}
    >
      <Grafiek soort="bar" data={barData} options={verhoudingOpts(dark)} hoogte={h} categorie="Instelling" />
    </ChartCard>
  )
}
