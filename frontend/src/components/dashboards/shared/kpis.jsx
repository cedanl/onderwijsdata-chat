import { fmt } from './hooks'
import { COLOR_EIGEN, COLOR_DIPLOM, COLOR_EERSTEJAARS } from '../../../constants'
import { Sparkline } from './shell'
import { schooljaarLabel } from '../../../schooljaar'

// ─── KPI components ─────────────────────────────────────────────────────────

// De bron achter de Eerstejaars-KPI, zoals het dashboard hem onderaan noemt.
const EERSTEJAARS_BRON = { mbo: 'DUO, Instromende MBO-studenten', ho: 'DUO, Eerstejaars HO per instelling' }

// Loopt het laatste jaar van de eerstejaars achter op dat van de ingeschrevenen, dan zegt de pagina waarom (#920):
// de bron is nog niet verder. Anders geen noot; twee jaren naast elkaar zonder uitleg lijken een fout.
export function eerstejaarsNoot({ ejJaar, ingesJaar, type }) {
  if (ejJaar == null || ingesJaar == null || Number(ejJaar) >= Number(ingesJaar)) return null
  const bron = EERSTEJAARS_BRON[type === 'mbo' ? 'mbo' : 'ho']
  return `${schooljaarLabel(ejJaar)} is het laatst beschikbare jaar in de bron (${bron}); de ingeschrevenen lopen door tot ${schooljaarLabel(ingesJaar)}.`
}

export function JaarNoot({ noot }) {
  if (!noot) return null
  return <div className="kpi-trend" data-testid="jaarnoot" style={{ color: 'var(--muted-text)' }}>{noot}</div>
}

// Een nationaal benchmark (wo) is een landelijk totaal; een regionaal benchmark een regiototaal (#918).
export function DemografieKpis({ lastInges, ingesDelta, ingesEntries, totaalRegio, totaalRegioJaar, nInstellingen, regioType, pctVrouw, vrouw, man, laatsteJaar }) {
  const landelijk = regioType === 'nationaal'
  return (
    <div className="kpi-grid">
      {lastInges && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Ingeschrevenen {lastInges[0]}–{Number(lastInges[0])+1}</span>
            <div className="kpi-icon" style={{ background: 'var(--blue-50)' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke={COLOR_EIGEN} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(lastInges[1])}</div>
          {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
          <Sparkline values={ingesEntries.map(([,v]) => v)} color={COLOR_EIGEN} />
        </div>
      )}
      {totaalRegio != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">{landelijk ? 'Landelijk totaal' : 'Regio totaal'} {totaalRegioJaar}–{Number(totaalRegioJaar)+1}</span>
            <div className="kpi-icon" style={{ background: '#F5F3FF' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
          </div>
          <div className="kpi-value">{fmt(totaalRegio)}</div>
          {nInstellingen && <div className="kpi-trend">{nInstellingen} instellingen{landelijk ? '' : ' in regio'}</div>}
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
              <div style={{ width: `${pctVrouw}%`, background: 'var(--teal-600)' }} />
              <div style={{ width: `${100 - pctVrouw}%`, background: '#64748B' }} />
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 5, fontSize: '12.5px', color: 'var(--muted-text)' }}>
              <span><span aria-hidden="true" style={{ color: 'var(--teal-600)' }}>●</span> {fmt(vrouw)} vrouw</span>
              <span><span aria-hidden="true" style={{ color: '#64748B' }}>●</span> {fmt(man)} man</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function InstroomKpis({ lastEj, ejDelta, ejEntries, lastInges, type }) {
  if (!lastEj) return null
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-card-header">
          <span className="kpi-label">Eerstejaars {schooljaarLabel(lastEj[0])}</span>
          <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke={COLOR_EERSTEJAARS} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          </div>
        </div>
        <div className="kpi-value">{fmt(lastEj[1])}</div>
        {ejDelta != null && <div className={`kpi-trend ${ejDelta >= 0 ? 'up' : 'down'}`}>{ejDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ejDelta))} t.o.v. vorig jaar</div>}
        <JaarNoot noot={eerstejaarsNoot({ ejJaar: lastEj[0], ingesJaar: lastInges?.[0], type })} />
        <Sparkline values={ejEntries.map(([,v]) => v)} color={COLOR_EERSTEJAARS} />
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
          <div className="kpi-icon" style={{ background: 'var(--teal-50)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke={COLOR_DIPLOM} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
          </div>
        </div>
        <div className="kpi-value">{fmt(lastDipl[1])}</div>
        {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
        <Sparkline values={diplEntries.map(([,v]) => v)} color={COLOR_DIPLOM} />
      </div>
      {rendement != null && (
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Ratio diploma/inschrijving</span>
            <div className="kpi-icon" style={{ background: 'var(--blue-50)' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke={COLOR_EIGEN} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--accent-text)' }}>{rendement}%</div>
          <div className="kpi-trend" style={{ color: 'var(--gray-500)' }}>proxy — geen cohortmeting, zie Rendementsmonitor</div>
        </div>
      )}
    </div>
  )
}
