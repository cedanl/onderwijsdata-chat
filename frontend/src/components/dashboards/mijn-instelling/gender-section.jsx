import { useMemo } from 'react'
import { COLOR_DIPLOM } from '../../../constants'
import { SectionHeader, ChartCard, Grafiek, fmt, darkColors, horizontalBarOpts, benchmarkColor } from '../shared/index'

// Man in de verdeelbalken: grijs met 3:1 tegen de kaart in beide thema's (#905); #94A3B8 haalde op wit 2,6:1.
const KLEUR_MAN = '#64748B'

// Het aandeel vrouw van vrouw en man samen; ontbreekt een van beide, dan is er geen aandeel, geen 0 (#902).
export function pctVrouwFromGeslacht(g) {
  if (g?.VROUW == null || g?.MAN == null) return null
  const t = g.VROUW + g.MAN
  return t > 0 ? Math.round((g.VROUW / t) * 1000) / 10 : null
}

// Het label van een genderbalk: het aandeel vrouw en zijn noemer, vrouw + man. Studenten met geslacht onbekend tellen
// niet mee; zijn ze er, dan noemt het label ze, want "totaal" was hier vrouw + man zonder hen (#931).
function genderBalkLabel(g) {
  const onbekend = g.ONBEKEND > 0 ? ` (${fmt(g.ONBEKEND)} onbekend)` : ''
  return `${pctVrouwFromGeslacht(g)}% vrouw — ${fmt(g.VROUW + g.MAN)} vrouw + man${onbekend}`
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
      borderColor: COLOR_DIPLOM,
      backgroundColor: COLOR_DIPLOM + '18',
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
      backgroundColor: rows.map(r => r.eigen ? COLOR_DIPLOM : benchmarkColor(dark)),
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
        {pctVrouw != null && (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', height: 10 }}>
              <div style={{ width: `${pctVrouw}%`, background: 'var(--teal-600)' }} />
              <div style={{ width: `${100 - pctVrouw}%`, background: KLEUR_MAN }} />
            </div>
          </div>
        )}
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
    const pctVrouw = pctVrouwFromGeslacht(geslacht)

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

  const balkOpts = horizontalBarOpts(dark, '% vrouw')
  const peerOpts = {
    ...balkOpts,
    scales: {
      ...balkOpts.scales,
      x: { min: 0, max: 100, grid: { color: grid }, ticks: { color: tick, callback: v => `${v}%` } },
    },
  }

  return (
    <>
      <SectionHeader title="Gender & diversiteit" subtitle={`Verdeling vrouw/man — ${instelling}`} />
      <GeslachtKpis pctVrouw={pctVrouw} vrouw={vrouw} man={man} fiveYearChange={fiveYearChange} lastJaar={data?.laatste_jaar} />

      {trendLineData && (
        <ChartCard title="% vrouw per jaar" subtitle="Aandeel vrouwelijke ingeschrevenen over tijd">
          <Grafiek soort="line" data={trendLineData} options={trendOpts} hoogte={220} />
        </ChartCard>
      )}

      {peerData && (
        <ChartCard title="% vrouw — benchmark peers" subtitle="Gesorteerd op aandeel vrouw (eigen instelling groen)">
          <Grafiek soort="bar" data={peerData} options={peerOpts} hoogte={Math.max(200, peerData.labels.length * 34 + 40)} categorie="Instelling" />
        </ChartCard>
      )}

      {hasSectorGeslacht && (
        <div className="chart-card">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(geslachtPerSector)
              .sort((a, b) => (b[1].VROUW + b[1].MAN) - (a[1].VROUW + a[1].MAN))
              .map(([sector, g]) => {
                const pv = pctVrouwFromGeslacht(g)
                if (pv == null) return null
                return (
                  <div key={sector}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px', color: 'var(--muted-text)', marginBottom: 3 }}>
                      <span>{sector}</span>
                      <span>{genderBalkLabel(g)}</span>
                    </div>
                    <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', height: 14 }}>
                      <div style={{ width: `${pv}%`, background: 'var(--teal-600)' }} />
                      <div style={{ width: `${100 - pv}%`, background: KLEUR_MAN }} />
                    </div>
                  </div>
                )
              })}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '12.5px', color: 'var(--muted-text)' }}>
            <span><span aria-hidden="true" style={{ color: 'var(--teal-600)' }}>●</span> Vrouw</span>
            <span><span aria-hidden="true" style={{ color: KLEUR_MAN }}>●</span> Man</span>
          </div>
        </div>
      )}
    </>
  )
}
