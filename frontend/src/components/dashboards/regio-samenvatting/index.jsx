import {
  useRegioDashboardData, DashboardShell,
  useRegioComputed, RegioBadges, KaartSection,
  SectionHeader, fmt,
} from '../shared/index'
import { Sparkline } from '../shared/shell'

function SamenvattingTile({ label, eigenWaarde, regioWaarde, regioLabel, sparkValues, color, icon, suffix }) {
  return (
    <div className="kpi-card">
      <div className="kpi-card-header">
        <span className="kpi-label">{label}</span>
        <div className="kpi-icon" style={{ background: `${color}18` }}>{icon}</div>
      </div>
      <div className="kpi-value">{fmt(eigenWaarde)}{suffix}</div>
      {regioWaarde != null && (
        <div className="kpi-trend" style={{ color: '#6B7280' }}>
          {regioLabel}: {fmt(regioWaarde)}
        </div>
      )}
      {sparkValues && <Sparkline values={sparkValues} color={color} />}
    </div>
  )
}

const iconPersons = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)
const iconChart = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
)
const iconDiploma = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
)
const iconGender = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)

export function InlineDashboardRegioSamenvatting({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  const bmLabel = c.bmLabel || 'Regio'
  const bm = c.bm || {}

  const bmInges = bm.ingeschrevenen ? Object.values(bm.ingeschrevenen).at(-1) : null
  const bmEj = bm.eerstejaars ? Object.values(bm.eerstejaars).at(-1) : null
  const bmDipl = bm.gediplomeerden ? Object.values(bm.gediplomeerden).at(-1) : null

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="DUO Open Onderwijsdata" />

        <KaartSection figureJson={data?.kaart_figure_json} />

        <SectionHeader title="Samenvatting" subtitle={`${instelling} vs. ${bmLabel.toLowerCase()} — kerncijfers in één oogopslag`} />

        <div className="kpi-grid">
          {c.lastInges && (
            <SamenvattingTile
              label={`Ingeschrevenen ${c.lastInges[0]}`}
              eigenWaarde={c.lastInges[1]}
              regioWaarde={bmInges ? Math.round(bmInges) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.ingesEntries.map(([, v]) => v)}
              color="#2563EB"
              icon={iconPersons('#2563EB')}
            />
          )}
          {c.lastEj && (
            <SamenvattingTile
              label={`Eerstejaars ${c.lastEj[0]}`}
              eigenWaarde={c.lastEj[1]}
              regioWaarde={bmEj ? Math.round(bmEj) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.ejEntries.map(([, v]) => v)}
              color="#22C55E"
              icon={iconChart('#22C55E')}
            />
          )}
          {c.lastDipl && (
            <SamenvattingTile
              label={`Gediplomeerden ${c.lastDipl[0]}`}
              eigenWaarde={c.lastDipl[1]}
              regioWaarde={bmDipl ? Math.round(bmDipl) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.diplEntries.map(([, v]) => v)}
              color="#0D9488"
              icon={iconDiploma('#0D9488')}
            />
          )}
          {c.pctVrouw != null && (
            <SamenvattingTile
              label={`Aandeel vrouw ${data?.laatste_jaar}`}
              eigenWaarde={c.pctVrouw}
              suffix="%"
              regioWaarde={null}
              regioLabel=""
              color="#F59E0B"
              icon={iconGender('#F59E0B')}
            />
          )}
        </div>

        {c.totaalRegio != null && (
          <>
            <SectionHeader title="Regio in cijfers" subtitle={`Totaalbeeld ${data?.arbeidsmarktregio || data?.provincie || 'regio'}`} />
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-card-header">
                  <span className="kpi-label">Totaal regio {c.totaalRegioJaar}</span>
                  <div className="kpi-icon" style={{ background: '#F5F3FF' }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                  </div>
                </div>
                <div className="kpi-value">{fmt(c.totaalRegio)}</div>
                {bm.n_instellingen && <div className="kpi-trend">{bm.n_instellingen} instellingen in regio</div>}
              </div>
              {c.rendement != null && (
                <div className="kpi-card">
                  <div className="kpi-card-header">
                    <span className="kpi-label">Ratio diploma/inschrijving</span>
                    <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    </div>
                  </div>
                  <div className="kpi-value" style={{ color: '#2563EB' }}>{c.rendement}%</div>
                  <div className="kpi-trend" style={{ color: '#6B7280' }}>proxy — geen cohortmeting</div>
                </div>
              )}
            </div>
          </>
        )}

        {data?.sectoren && Object.keys(data.sectoren).length > 0 && (
          <>
            <SectionHeader title="Sectorverdeling" subtitle={`Ingeschrevenen naar onderdeel ${data?.laatste_jaar}`} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.entries(data.sectoren).map(([sector, count]) => {
                const total = Object.values(data.sectoren).reduce((s, v) => s + v, 0)
                const pct = total > 0 ? ((count / total) * 100).toFixed(1) : 0
                return (
                  <div key={sector} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '.85rem' }}>
                    <div style={{ width: 140, color: '#374151', fontWeight: 500, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sector}</div>
                    <div style={{ flex: 1, background: '#F3F4F6', borderRadius: 3, height: 16, position: 'relative' }}>
                      <div style={{ width: `${pct}%`, background: '#2563EB', borderRadius: 3, height: '100%', minWidth: 2 }} />
                    </div>
                    <div style={{ width: 80, textAlign: 'right', color: '#6B7280', fontSize: '.8rem' }}>{fmt(count)} ({pct}%)</div>
                  </div>
                )
              })}
            </div>
          </>
        )}

        <div className="dashboard-sources" style={{ marginTop: 24 }}>
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
