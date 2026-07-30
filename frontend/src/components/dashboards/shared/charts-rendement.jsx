import { Bar } from 'react-chartjs-2'
import { horizontalBarOpts } from './chart-opts'
import { ChartCard } from './shell'

// ─── Rendement vergelijking ───────────────────────────────────────────────────

export function buildRendementVergelijkingData(data, instelling, dark) {
  const peers_inges = data?.benchmark?.peers?.ingeschrevenen
  const peers_dipl = data?.benchmark?.peers?.gediplomeerden
  if (!peers_inges || !peers_dipl || Object.keys(peers_dipl).length === 0) return null

  const lastJaar = data.laatste_jaar
  const jaarStr = String(lastJaar)

  const entries = []

  const ownInges = data.ingeschrevenen?.[lastJaar] ?? data.ingeschrevenen?.[jaarStr]
  const ownDipl = data.gediplomeerden?.[lastJaar] ?? data.gediplomeerden?.[jaarStr] ??
    data.gediplomeerden?.[Object.keys(data.gediplomeerden || {}).sort((a, b) => b - a)[0]]
  if (ownInges && ownDipl) {
    entries.push({ naam: instelling, rendement: Math.round(ownDipl / ownInges * 100), eigen: true })
  }

  for (const [naam, ingesData] of Object.entries(peers_inges)) {
    const diplData = peers_dipl[naam]
    if (!diplData) continue
    const inges = ingesData[lastJaar] ?? ingesData[jaarStr] ?? ingesData[Object.keys(ingesData).sort((a, b) => b - a)[0]]
    const dipl = diplData[lastJaar] ?? diplData[jaarStr] ?? diplData[Object.keys(diplData).sort((a, b) => b - a)[0]]
    if (inges && dipl) entries.push({ naam, rendement: Math.round(dipl / inges * 100), eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.rendement - a.rendement)

  return {
    labels: entries.map(e => e.naam),
    datasets: [{
      label: 'Rendement %',
      data: entries.map(e => e.rendement),
      backgroundColor: entries.map(e =>
        e.eigen ? '#2563EB' : e.rendement >= 70 ? (dark ? '#064E3B' : '#D1FAE5') : (dark ? '#475569' : '#E2E8F0')
      ),
      borderRadius: 4,
    }],
  }
}

export function RendementVergelijkingChart({ data, dark }) {
  if (!data) return null
  const h = Math.max(200, data.labels.length * 34 + 40)
  return (
    <ChartCard
      title="Rendement vergelijking"
      subtitle="Gediplomeerden / ingeschrevenen per instelling — proxy, geen cohortanalyse"
    >
      <div style={{ height: h }}>
        <Bar data={data} options={horizontalBarOpts(dark, '%')} />
      </div>
    </ChartCard>
  )
}
