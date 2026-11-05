import TabelScroll from '../../TabelScroll'
import { fmt } from './hooks'
import { SectionHeader, ChartCard } from './shell'
import { groeiStartjaar, groeiPct } from './chart-builders'
import { Grafiek } from './grafiek'
import { oordeelKleur } from './chart-opts'

// ─── Peer chart components ────────────────────────────────────────────────────

// De ondertitel krijgt het startjaar van de groei uit de data (#903): `subtitle(startjaar)`.
export function BenchmarkLineChart({ title, subtitle, data, indexOpts }) {
  if (!data) return null
  const { startjaar, ...lineData } = data
  return (
    <ChartCard title={title} subtitle={subtitle(startjaar)}>
      <Grafiek soort="line" data={lineData} options={indexOpts} hoogte={220} />
    </ChartCard>
  )
}

export function PeerLinesChart({ title, subtitle, data, opts }) {
  if (!data) return null
  const { startjaar, ...lineData } = data
  return (
    <ChartCard title={title} subtitle={subtitle(startjaar)}>
      <Grafiek soort="line" data={lineData} options={opts} hoogte={240} />
    </ChartCard>
  )
}

export function PeersTable({ data, instelling, dark }) {
  if (!data?.benchmark?.peers?.ingeschrevenen) return null
  const peers = data.benchmark.peers.ingeschrevenen
  const lastJaar = data.laatste_jaar
  const jaarStr = String(lastJaar)

  // De ene groeiregel van chart-builders (#903): hetzelfde startjaar als de lijnen en de groeiranking.
  const commonStart = groeiStartjaar([data.ingeschrevenen || {}, ...Object.values(peers)])
  const groei = dict => groeiPct(dict, commonStart, lastJaar)

  const rows = []
  const ownVal = data.ingeschrevenen?.[lastJaar] ?? data.ingeschrevenen?.[jaarStr]
  if (ownVal) rows.push({ naam: instelling, val: ownVal, groei: groei(data.ingeschrevenen || {}), eigen: true })

  for (const [naam, jaarData] of Object.entries(peers)) {
    const val = jaarData[lastJaar] ?? jaarData[jaarStr] ?? jaarData[Object.keys(jaarData).sort((a, b) => b - a)[0]]
    if (val) rows.push({ naam, val, groei: groei(jaarData), eigen: false })
  }

  if (rows.length < 2) return null
  rows.sort((a, b) => b.val - a.val)
  // Peers zonder één waarde boven 0 tellen niet mee in het gemiddelde, maar horen wel bij de regio (#925).
  for (const naam of data.benchmark.geen_gegevens?.ingeschrevenen ?? []) {
    rows.push({ naam, val: null, groei: null, eigen: false })
  }

  const groeiHeader = commonStart != null ? `Groei (${commonStart}–${lastJaar})` : 'Groei'

  return (
    <>
      <SectionHeader
        title="Overzicht concurrenten"
        subtitle={`${rows.length} instellingen in de benchmark-regio — gesorteerd op omvang ingeschrevenen`}
      />
      <div className="chart-card" style={{ padding: 0 }}>
        <TabelScroll label="Overzicht concurrenten" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
          <caption className="sr-only">Overzicht concurrenten in de benchmark-regio, gesorteerd op ingeschrevenen</caption>
          <thead>
            <tr style={{ background: 'var(--gray-50)', borderBottom: '2px solid var(--gray-200)' }}>
              <th scope="col" style={{ textAlign: 'left', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600)' }}>#</th>
              <th scope="col" style={{ textAlign: 'left', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600)' }}>Instelling</th>
              <th scope="col" style={{ textAlign: 'right', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600)' }}>Ingeschrevenen {lastJaar}</th>
              <th scope="col" style={{ textAlign: 'right', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600)' }}>{groeiHeader}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.naam} style={{
                borderBottom: '1px solid var(--gray-100)',
                background: row.eigen ? 'var(--blue-50)' : 'transparent',
              }}>
                <td style={{ padding: '9px 16px', color: 'var(--muted-text)', fontWeight: row.eigen ? 700 : 400 }}>{row.val == null ? '—' : i + 1}</td>
                <td style={{ padding: '9px 16px', color: row.eigen ? 'var(--accent-text)' : 'var(--gray-800, #1F2937)', fontWeight: row.eigen ? 700 : 400 }}>
                  {row.naam}{row.eigen ? ' ★' : ''}
                </td>
                <td style={{ padding: '9px 16px', textAlign: 'right', color: 'var(--gray-800, #1F2937)', fontWeight: row.eigen ? 700 : 400 }}>
                  {row.val == null ? 'geen gegevens' : fmt(row.val)}
                </td>
                <td style={{ padding: '9px 16px', textAlign: 'right', fontWeight: row.eigen ? 700 : 400, color: row.groei == null ? 'var(--muted-text)' : oordeelKleur(row.groei >= 0 ? 'goed' : 'slecht', dark) }}>
                  {row.groei == null ? '—' : `${row.groei >= 0 ? '+' : ''}${row.groei}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </TabelScroll>
      </div>
    </>
  )
}
