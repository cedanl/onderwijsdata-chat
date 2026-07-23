import { Line } from 'react-chartjs-2'
import { fmt } from './hooks'
import { SectionHeader } from './shell'

// ─── Peer chart components ────────────────────────────────────────────────────

export function BenchmarkLineChart({ title, subtitle, data, indexOpts }) {
  if (!data) return null
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">{title}</div><div className="chart-sub">{subtitle}</div></div></div>
        <div style={{ height: 220 }}><Line data={data} options={indexOpts} /></div>
      </div>
    </div>
  )
}

export function PeerLinesChart({ title, subtitle, data, opts }) {
  if (!data) return null
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header"><div><div className="chart-title">{title}</div><div className="chart-sub">{subtitle}</div></div></div>
        <div style={{ height: 240 }}><Line data={data} options={opts} /></div>
      </div>
    </div>
  )
}

export function PeersTable({ data, instelling }) {
  if (!data?.benchmark?.peers?.ingeschrevenen) return null
  const peers = data.benchmark.peers.ingeschrevenen
  const lastJaar = data.laatste_jaar
  const jaarStr = String(lastJaar)

  // Compute commonStart = max of first-available years across own + all peers
  const allDicts = [data.ingeschrevenen || {}, ...Object.values(peers)]
  const firstYears = allDicts.map(dict => {
    const yrs = Object.keys(dict).map(Number).filter(Boolean).sort((a, b) => a - b)
    return yrs.length > 0 ? yrs[0] : null
  }).filter(y => y != null)
  const commonStart = firstYears.length > 0 ? Math.max(...firstYears) : null

  function groeiPct(dict) {
    if (commonStart == null) return null
    const startVal = dict[commonStart] ?? dict[String(commonStart)]
    const lastVal = dict[lastJaar] ?? dict[jaarStr]
    if (!startVal || lastVal == null) return null
    return Math.round((lastVal - startVal) / startVal * 100)
  }

  const rows = []
  const ownVal = data.ingeschrevenen?.[lastJaar] ?? data.ingeschrevenen?.[jaarStr]
  if (ownVal) rows.push({ naam: instelling, val: ownVal, groei: groeiPct(data.ingeschrevenen || {}), eigen: true })

  for (const [naam, jaarData] of Object.entries(peers)) {
    const val = jaarData[lastJaar] ?? jaarData[jaarStr] ?? jaarData[Object.keys(jaarData).sort((a, b) => b - a)[0]]
    if (val) rows.push({ naam, val, groei: groeiPct(jaarData), eigen: false })
  }

  if (rows.length < 2) return null
  rows.sort((a, b) => b.val - a.val)

  const groeiHeader = commonStart != null ? `Groei (${commonStart}–${lastJaar})` : 'Groei'

  return (
    <>
      <SectionHeader
        title="Overzicht concurrenten"
        subtitle={`${rows.length} instellingen in de benchmark-regio — gesorteerd op omvang ingeschrevenen`}
      />
      <div className="chart-card" style={{ overflow: 'auto', padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
          <thead>
            <tr style={{ background: 'var(--gray-50, #F9FAFB)', borderBottom: '2px solid var(--gray-200, #E5E7EB)' }}>
              <th style={{ textAlign: 'left', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600, #4B5563)' }}>#</th>
              <th style={{ textAlign: 'left', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600, #4B5563)' }}>Instelling</th>
              <th style={{ textAlign: 'right', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600, #4B5563)' }}>Ingeschrevenen {lastJaar}</th>
              <th style={{ textAlign: 'right', padding: '10px 16px', fontWeight: 600, color: 'var(--gray-600, #4B5563)' }}>{groeiHeader}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.naam} style={{
                borderBottom: '1px solid var(--gray-100, #F3F4F6)',
                background: row.eigen ? '#EFF6FF' : 'transparent',
              }}>
                <td style={{ padding: '9px 16px', color: 'var(--gray-400, #9CA3AF)', fontWeight: row.eigen ? 700 : 400 }}>{i + 1}</td>
                <td style={{ padding: '9px 16px', color: row.eigen ? '#1D4ED8' : 'var(--gray-800, #1F2937)', fontWeight: row.eigen ? 700 : 400 }}>
                  {row.naam}{row.eigen ? ' ★' : ''}
                </td>
                <td style={{ padding: '9px 16px', textAlign: 'right', color: 'var(--gray-800, #1F2937)', fontWeight: row.eigen ? 700 : 400 }}>
                  {fmt(row.val)}
                </td>
                <td style={{ padding: '9px 16px', textAlign: 'right', fontWeight: row.eigen ? 700 : 400, color: row.groei == null ? '#9CA3AF' : row.groei >= 0 ? '#059669' : '#DC2626' }}>
                  {row.groei == null ? '—' : `${row.groei >= 0 ? '+' : ''}${row.groei}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
