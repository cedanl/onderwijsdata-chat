import { fmt } from './hooks'
import { Sparkline } from './shell'

// ─── KPI components ─────────────────────────────────────────────────────────

export function DemografieKpis({ lastInges, ingesDelta, ingesEntries, totaalRegio, totaalRegioJaar, nInstellingen, pctVrouw, totaalGeslacht, vrouw, man, laatsteJaar }) {
  return (
    <div className="kpi-grid">
      {lastInges && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Ingeschrevenen {lastInges[0]}–{Number(lastInges[0])+1}</span>
            <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(lastInges[1])}</div>
          {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
          <Sparkline values={ingesEntries.map(([,v]) => v)} color="#2563EB" />
        </div>
      )}
      {totaalRegio != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Regio totaal {totaalRegioJaar}–{Number(totaalRegioJaar)+1}</span>
            <div className="kpi-icon" style={{ background: '#F5F3FF' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(totaalRegio)}</div>
          {nInstellingen && <div className="kpi-trend">{nInstellingen} instellingen in regio</div>}
        </div>
      )}
      {pctVrouw != null && vrouw != null && man != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Geslachtsverhouding {laatsteJaar}</span>
            <div className="kpi-icon" style={{ background: '#FFF7ED' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
          </div>
          <div className="kpi-value">{pctVrouw}% vrouw</div>
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', height: 10 }}>
              <div style={{ width: `${pctVrouw}%`, background: '#0D9488' }} />
              <div style={{ width: `${100 - pctVrouw}%`, background: '#94A3B8' }} />
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 5, fontSize: '.72rem', color: '#6B7280' }}>
              <span><span style={{ color: '#0D9488' }}>●</span> {fmt(vrouw)} vrouw</span>
              <span><span style={{ color: '#94A3B8' }}>●</span> {fmt(man)} man</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function InstroomKpis({ lastEj, ejDelta, ejEntries }) {
  if (!lastEj) return null
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-card-header">
          <span className="kpi-label">Eerstejaars {lastEj[0]}–{Number(lastEj[0])+1}</span>
          <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          </div>
        </div>
        <div className="kpi-value">{fmt(lastEj[1])}</div>
        {ejDelta != null && <div className={`kpi-trend ${ejDelta >= 0 ? 'up' : 'down'}`}>{ejDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ejDelta))} t.o.v. vorig jaar</div>}
        <Sparkline values={ejEntries.map(([,v]) => v)} color="#22C55E" />
      </div>
    </div>
  )
}

export function DiplomeringKpis({ lastDipl, diplDelta, diplEntries, rendement }) {
  if (!lastDipl) return null
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-card-header">
          <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
          <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
          </div>
        </div>
        <div className="kpi-value">{fmt(lastDipl[1])}</div>
        {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
        <Sparkline values={diplEntries.map(([,v]) => v)} color="#0D9488" />
      </div>
      {rendement != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Ratio diploma/inschrijving</span>
            <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
          </div>
          <div className="kpi-value" style={{ color: '#2563EB' }}>{rendement}%</div>
          <div className="kpi-trend" style={{ color: '#6B7280' }}>proxy — geen cohortmeting, zie Rendementsmonitor</div>
        </div>
      )}
    </div>
  )
}
