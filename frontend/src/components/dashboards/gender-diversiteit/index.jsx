import { useMemo } from 'react'
import { Line, Bar } from 'react-chartjs-2'
import {
  useRegioDashboardData, DashboardShell,
  SectionHeader, RegioBadges,
  useDarkMode, fmt,
} from '../shared/index'

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

function _trendOpts(dark) {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.raw}% vrouw` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: {
        min: 0,
        max: 100,
        grid: { color: grid },
        ticks: { color: tick, callback: v => `${v}%` },
        title: { display: true, text: '% vrouw', color: tick, font: { size: 10 } },
      },
    },
  }
}

function _peerBarOpts(dark) {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.raw}% vrouw` } },
    },
    scales: {
      x: {
        min: 0,
        max: 100,
        grid: { color: grid },
        ticks: { color: tick, font: { size: 11 }, callback: v => `${v}%` },
      },
      y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 }, padding: 4 } },
    },
  }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function GeslachtKpis({ pctVrouw, vrouw, man, fiveYearChange, lastJaar }) {
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-card-header">
          <span className="kpi-label">% vrouw {lastJaar}</span>
          <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
          </div>
        </div>
        <div className="kpi-value">{pctVrouw != null ? `${pctVrouw}%` : '—'}</div>
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', height: 10 }}>
            <div style={{ width: `${pctVrouw ?? 0}%`, background: '#0D9488' }} />
            <div style={{ width: `${100 - (pctVrouw ?? 0)}%`, background: '#94A3B8' }} />
          </div>
        </div>
      </div>

      {fiveYearChange != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Verandering t.o.v. 5 jaar geleden</span>
            <div className="kpi-icon" style={{ background: fiveYearChange >= 0 ? '#F0FDFA' : '#FFF1F2' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke={fiveYearChange >= 0 ? '#0D9488' : '#E11D48'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {fiveYearChange >= 0
                  ? <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                  : <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />}
              </svg>
            </div>
          </div>
          <div className="kpi-value" style={{ color: fiveYearChange >= 0 ? '#0D9488' : '#E11D48' }}>
            {fiveYearChange >= 0 ? '+' : ''}{fiveYearChange} pp
          </div>
          <div className="kpi-trend" style={{ color: '#6B7280' }}>procentpunt verandering in aandeel vrouw</div>
        </div>
      )}

      {vrouw != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Vrouw absoluut {lastJaar}</span>
            <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="8" r="4" /><path d="M1 20c0-4 3.6-7 8-7" />
                <circle cx="17" cy="8" r="4" /><path d="M23 20c0-4-3.6-7-8-7" />
              </svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(vrouw)}</div>
        </div>
      )}

      {man != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Man absoluut {lastJaar}</span>
            <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="8" r="4" /><path d="M1 20c0-4 3.6-7 8-7" />
                <circle cx="17" cy="8" r="4" /><path d="M23 20c0-4-3.6-7-8-7" />
              </svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(man)}</div>
        </div>
      )}
    </div>
  )
}

function SingleYearStackedBar({ vrouw, man, lastJaar }) {
  const totaal = (vrouw ?? 0) + (man ?? 0)
  if (totaal === 0) return null
  const pctV = Math.round((vrouw / totaal) * 1000) / 10
  const pctM = Math.round((man / totaal) * 1000) / 10
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Geslachtsverdeling {lastJaar}</div>
          <div className="chart-sub">Aandeel vrouw vs. man — huidig jaar (historische trend in ontwikkeling)</div>
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', height: 32 }}>
          <div style={{ width: `${pctV}%`, background: '#0D9488', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {pctV >= 12 && <span style={{ color: '#fff', fontSize: '.78rem', fontWeight: 600 }}>{pctV}%</span>}
          </div>
          <div style={{ width: `${pctM}%`, background: '#94A3B8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {pctM >= 12 && <span style={{ color: '#fff', fontSize: '.78rem', fontWeight: 600 }}>{pctM}%</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: '.78rem', color: '#6B7280' }}>
          <span><span style={{ color: '#0D9488' }}>●</span> Vrouw — {fmt(vrouw)} ({pctV}%)</span>
          <span><span style={{ color: '#94A3B8' }}>●</span> Man — {fmt(man)} ({pctM}%)</span>
        </div>
      </div>
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function InlineDashboardGenderDiversiteit({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const dark = useDarkMode()

  const computed = useMemo(() => {
    if (!data) return {}

    const geslacht = data.geslacht ?? {}
    const vrouw = geslacht.VROUW ?? null
    const man = geslacht.MAN ?? null
    const totaal = (vrouw ?? 0) + (man ?? 0)
    const pctVrouw = totaal > 0 ? Math.round(((vrouw ?? 0) / totaal) * 1000) / 10 : null

    const geslachtTrend = data.geslacht_trend ?? null
    const trendLineData = buildTrendLineData(geslachtTrend)

    // 5-year change from trend data
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

    // Peers gender comparison
    const peersGeslacht = data.benchmark?.peers?.geslacht ?? null
    const peerData = buildPeerGenderData(peersGeslacht, instelling, pctVrouw, dark)
    const hasPeers = peerData != null

    // Sectoren available (HO only indicator)
    const hasSectoren = data.sectoren && Object.keys(data.sectoren).length > 0

    return { vrouw, man, pctVrouw, trendLineData, fiveYearChange, peerData, hasPeers, hasSectoren }
  }, [data, instelling, dark])

  const {
    vrouw, man, pctVrouw, trendLineData, fiveYearChange,
    peerData, hasPeers, hasSectoren,
  } = computed

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges
          instelling={instelling}
          provincie={data?.provincie}
          arbeidsmarktregio={data?.arbeidsmarktregio}
          bron="DUO"
        />

        <SectionHeader
          title="Geslachtsverhouding"
          subtitle={`Verdeling vrouw/man — ${instelling}`}
        />

        <GeslachtKpis
          pctVrouw={pctVrouw}
          vrouw={vrouw}
          man={man}
          fiveYearChange={fiveYearChange}
          lastJaar={data?.laatste_jaar}
        />

        {trendLineData ? (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header">
                <div>
                  <div className="chart-title">% vrouw per jaar</div>
                  <div className="chart-sub">Aandeel vrouwelijke ingeschrevenen over tijd — Y-as 0–100%</div>
                </div>
              </div>
              <div style={{ height: 220 }}>
                <Line data={trendLineData} options={_trendOpts(dark)} />
              </div>
            </div>
          </div>
        ) : (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div className="chart-card" style={{ background: 'var(--gray-50, #F9FAFB)', border: '1px dashed var(--gray-300, #D1D5DB)' }}>
                <div style={{ fontSize: '.85rem', color: '#6B7280', fontStyle: 'italic' }}>
                  Historische data in ontwikkeling — trend over meerdere jaren is nog niet beschikbaar.
                </div>
              </div>
              {vrouw != null && man != null && (
                <SingleYearStackedBar vrouw={vrouw} man={man} lastJaar={data?.laatste_jaar} />
              )}
            </div>
          </div>
        )}

        {hasPeers && (
          <>
            <SectionHeader
              title="Regionale vergelijking"
              subtitle="Aandeel vrouw per instelling in de regio — eigen instelling groen"
            />
            <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
              <div className="chart-card">
                <div className="chart-header">
                  <div>
                    <div className="chart-title">% vrouw — benchmark peers</div>
                    <div className="chart-sub">Gesorteerd op aandeel vrouw (eigen instelling groen)</div>
                  </div>
                </div>
                <div style={{ height: Math.max(200, peerData.labels.length * 34 + 40) }}>
                  <Bar data={peerData} options={_peerBarOpts(dark)} />
                </div>
              </div>
            </div>
          </>
        )}

        {hasSectoren && (
          <>
            <SectionHeader
              title="Sectorbalans"
              subtitle="Sectorverdeling — geslachtsdata per sector in ontwikkeling"
            />
            <div className="chart-card" style={{ background: 'var(--gray-50, #F9FAFB)', border: '1px dashed var(--gray-300, #D1D5DB)' }}>
              <div style={{ fontSize: '.85rem', color: '#6B7280' }}>
                Sector-uitgesplitste geslachtsdata is in ontwikkeling — huidige data toont alleen totaalverhouding.
              </div>
            </div>
          </>
        )}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li>
              <a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">
                DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)
              </a>
            </li>
            <li>
              <a href="https://onderwijsdata.duo.nl/dataset/p30mbo-deelnemers" target="_blank" rel="noreferrer">
                DUO Open Onderwijsdata — Deelnemers MBO (p30mbo-deelnemers)
              </a>
            </li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
