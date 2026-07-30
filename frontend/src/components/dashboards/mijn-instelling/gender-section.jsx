import { useMemo } from 'react'
import { Line, Bar } from 'react-chartjs-2'
import { SectionHeader, ChartCard, fmt, darkColors, horizontalBarOpts } from '../shared/index'

function pctVrouwFromGeslacht(g) {
  if (!g) return null
  const v = g.VROUW ?? 0
  const m = g.MAN ?? 0
  const t = v + m
  return t > 0 ? Math.round((v / t) * 1000) / 10 : null
}

function buildTrendLineData(geslachtTrend) {
  if (!geslachtTrend || Object.keys(geslachtTrend).length < 2) return null
  const entries = Object.entries(geslachtTrend)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([jaar, g]) => [jaar, pctVrouwFromGeslacht(g)])
    .filter(([, pct]) => pct != null)
  if (entries.length < 2) return null
  return {
    labels: entries.map(([y]) => y),
    datasets: [{
      label: '% vrouw',
      data: entries.map(([, v]) => v),
      borderColor: '#0D9488',
      backgroundColor: '#0D948818',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2.5,
    }],
  }
}

function buildPeerGenderData(peersGeslacht, ownInstelling, ownPct, dark) {
  if (!peersGeslacht || Object.keys(peersGeslacht).length === 0) return null
  const rows = []
  if (ownPct != null) rows.push({ naam: ownInstelling, pct: ownPct, eigen: true })
  for (const [naam, g] of Object.entries(peersGeslacht)) {
    const pct = pctVrouwFromGeslacht(g)
    if (pct != null) rows.push({ naam, pct, eigen: false })
  }
  if (rows.length < 2) return null
  rows.sort((a, b) => b.pct - a.pct)
  return {
    labels: rows.map(r => r.naam),
    datasets: [{
      label: '% vrouw',
      data: rows.map(r => r.pct),
      backgroundColor: rows.map(r => r.eigen ? '#0D9488' : (dark ? '#475569' : '#CBD5E1')),
      borderRadius: 4,
    }],
  }
}

function GeslachtKpis({ pctVrouw, vrouw, man, fiveYearChange, lastJaar }) {
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-card-header">
          <span className="kpi-label">% vrouw {lastJaar}</span>
        </div>
        <div className="kpi-value">{pctVrouw != null ? `${pctVrouw}%` : '—'}</div>
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', height: 10 }}>
            <div style={{ width: `${pctVrouw ?? 0}%`, background: 'var(--teal-600)' }} />
            <div style={{ width: `${100 - (pctVrouw ?? 0)}%`, background: '#94A3B8' }} />
          </div>
        </div>
      </div>
      {fiveYearChange != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Verandering t.o.v. 5 jaar geleden</span>
          </div>
          <div className="kpi-value" style={{ color: fiveYearChange >= 0 ? 'var(--teal-600)' : '#E11D48' }}>
            {fiveYearChange >= 0 ? '+' : ''}{fiveYearChange} pp
          </div>
          <div className="kpi-trend" style={{ color: 'var(--gray-500)' }}>procentpunt verandering in aandeel vrouw</div>
        </div>
      )}
      {vrouw != null && (
        <div className="kpi-card">
          <span className="kpi-label">Vrouw absoluut {lastJaar}</span>
          <div className="kpi-value">{fmt(vrouw)}</div>
        </div>
      )}
      {man != null && (
        <div className="kpi-card">
          <span className="kpi-label">Man absoluut {lastJaar}</span>
          <div className="kpi-value">{fmt(man)}</div>
        </div>
      )}
    </div>
  )
}

export function GenderSection({ data, instelling, dark }) {
  const { tick, grid } = darkColors(dark)

  const computed = useMemo(() => {
    if (!data) return {}
    const geslacht = data.geslacht ?? {}
    const vrouw = geslacht.VROUW ?? null
    const man = geslacht.MAN ?? null
    const totaal = (vrouw ?? 0) + (man ?? 0)
    const pctVrouw = totaal > 0 ? Math.round(((vrouw ?? 0) / totaal) * 1000) / 10 : null

    const geslachtTrend = data.geslacht_trend ?? null
    const trendLineData = buildTrendLineData(geslachtTrend)

    let fiveYearChange = null
    if (geslachtTrend) {
      const lastJaar = String(data.laatste_jaar)
      const fiveAgoJaar = String(Number(data.laatste_jaar) - 5)
      const lastPct = pctVrouwFromGeslacht(geslachtTrend[lastJaar]) ?? pctVrouw
      const fiveAgoPct = pctVrouwFromGeslacht(geslachtTrend[fiveAgoJaar])
      if (lastPct != null && fiveAgoPct != null) {
        fiveYearChange = Math.round((lastPct - fiveAgoPct) * 10) / 10
      }
    }

    const peersGeslacht = data.benchmark?.peers?.geslacht ?? null
    const peerData = buildPeerGenderData(peersGeslacht, instelling, pctVrouw, dark)
    const geslachtPerSector = data.geslacht_per_sector ?? null
    const hasSectorGeslacht = geslachtPerSector && Object.keys(geslachtPerSector).length > 0

    return { vrouw, man, pctVrouw, trendLineData, fiveYearChange, peerData, hasSectorGeslacht, geslachtPerSector }
  }, [data, instelling, dark])

  const { vrouw, man, pctVrouw, trendLineData, fiveYearChange, peerData, hasSectorGeslacht, geslachtPerSector } = computed

  if (pctVrouw == null && !trendLineData) return null

  const trendOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.raw}% vrouw` } } },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: { min: 0, max: 100, grid: { color: grid }, ticks: { color: tick, callback: v => `${v}%` } },
    },
  }

  const peerOpts = {
    ...horizontalBarOpts(dark, '% vrouw'),
    scales: {
      x: { min: 0, max: 100, grid: { color: grid }, ticks: { color: tick, font: { size: 11 }, callback: v => `${v}%` } },
      y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 }, padding: 4 } },
    },
  }

  return (
    <>
      <SectionHeader title="Gender & diversiteit" subtitle={`Verdeling vrouw/man — ${instelling}`} />
      <GeslachtKpis pctVrouw={pctVrouw} vrouw={vrouw} man={man} fiveYearChange={fiveYearChange} lastJaar={data?.laatste_jaar} />

      {trendLineData && (
        <ChartCard title="% vrouw per jaar" subtitle="Aandeel vrouwelijke ingeschrevenen over tijd">
          <div style={{ height: 220 }}><Line data={trendLineData} options={trendOpts} /></div>
        </ChartCard>
      )}

      {peerData && (
        <ChartCard title="% vrouw — benchmark peers" subtitle="Gesorteerd op aandeel vrouw (eigen instelling groen)">
          <div style={{ height: Math.max(200, peerData.labels.length * 34 + 40) }}>
            <Bar data={peerData} options={peerOpts} />
          </div>
        </ChartCard>
      )}

      {hasSectorGeslacht && (
        <div className="chart-card">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(geslachtPerSector)
              .sort((a, b) => (b[1].VROUW + b[1].MAN) - (a[1].VROUW + a[1].MAN))
              .map(([sector, g]) => {
                const t = g.VROUW + g.MAN
                if (t <= 0) return null
                const pv = Math.round((g.VROUW / t) * 1000) / 10
                return (
                  <div key={sector}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.78rem', color: 'var(--gray-500)', marginBottom: 3 }}>
                      <span>{sector}</span>
                      <span>{pv}% vrouw — {fmt(t)} totaal</span>
                    </div>
                    <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', height: 14 }}>
                      <div style={{ width: `${pv}%`, background: 'var(--teal-600)' }} />
                      <div style={{ width: `${100 - pv}%`, background: '#94A3B8' }} />
                    </div>
                  </div>
                )
              })}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '.75rem', color: 'var(--gray-500)' }}>
            <span><span style={{ color: 'var(--teal-600)' }}>●</span> Vrouw</span>
            <span><span style={{ color: '#94A3B8' }}>●</span> Man</span>
          </div>
        </div>
      )}
    </>
  )
}
