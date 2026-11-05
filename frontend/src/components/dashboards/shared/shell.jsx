import { COLOR_EIGEN } from '../../../constants'
import { GrafiekTitel } from './grafiek'

// ─── Shell ──────────────────────────────────────────────────────────────────

// Een nieuwe poging onder een melding (#901), met de knop van een gesprek dat de server niet kreeg (#785).
function OpnieuwKnop({ onOpnieuw }) {
  if (!onOpnieuw) return null
  return <button type="button" className="niet-bewaard-actie" onClick={onOpnieuw}>Opnieuw proberen</button>
}

export function DashboardShell({ instelling, children, loading, data, error, onOpnieuw }) {
  if (loading) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }} role="status" aria-busy="true">
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Data laden&hellip;</span>
        </div>
        <div className="db-skeleton-grid">
          {[1,2,3,4].map(n => <div key={n} className="db-skeleton-kpi" />)}
        </div>
        <div className="db-skeleton-grid" style={{ marginTop: 16 }}>
          {[1,2,3,4].map(n => <div key={n} className="db-skeleton-chart" />)}
        </div>
      </div>
    )
  }

  // Een storing is geen "niet gevonden" (#901): de melding van de server, en een nieuwe poging als die zin heeft.
  if (error || !data) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" role="alert" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <div style={{ fontSize: '.85rem', color: '#991B1B' }}>
            Kon geen data ophalen voor <strong>{instelling}</strong>. {error?.melding}
            {error?.herstelbaar && <OpnieuwKnop onOpnieuw={onOpnieuw} />}
          </div>
        </div>
      </div>
    )
  }

  if (!data.gevonden) {
    const suggesties = data.beschikbare_instellingen || []
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
          <div style={{ fontSize: '.85rem', color: '#92400E', lineHeight: 1.6 }}>
            <strong>&ldquo;{instelling}&rdquo;</strong> niet gevonden in DUO-data.
            {suggesties.length > 0 && (
              <> Bedoel je misschien: {suggesties.slice(0,5).join(', ')}?</>
            )}
            <br />Pas de naam aan via <strong>Instellingen</strong>.
          </div>
        </div>
      </div>
    )
  }

  return children
}

// De onderdelen die niet laadden (#901): het dashboard noemt ze en waarom, in plaats van ze stil weg te laten.
// `onderdelen` komt uit `niet_beschikbaar` van de payload: [{ onderdeel, bron, reden }].
export function NietGeladen({ onderdelen, onOpnieuw }) {
  if (!onderdelen?.length) return null
  return (
    <div className="dashboard-gaten" role="status">
      <strong>Niet alles kon worden geladen.</strong>
      <ul>
        {onderdelen.map(({ onderdeel, reden }) => <li key={onderdeel}>{onderdeel}: {reden}.</li>)}
      </ul>
      <OpnieuwKnop onOpnieuw={onOpnieuw} />
    </div>
  )
}

// De gaten van meer payloads samen, elk onderdeel één keer; `bronnen` beperkt ze tot wat dit dashboard toont.
export function gatenVan(payloads, bronnen = null) {
  const gezien = new Map()
  for (const payload of payloads) {
    for (const gat of payload?.niet_beschikbaar || []) {
      if (bronnen && !bronnen.includes(gat.bron)) continue
      if (!gezien.has(gat.onderdeel)) gezien.set(gat.onderdeel, gat)
    }
  }
  return [...gezien.values()]
}

// Een tweede lading binnen een dashboard (#901), zoals `regio` bij de arbeidsmarkt en `rendement` bij mijn instelling.
// Tijdens het laden een vlak van vaste hoogte, zodat de pagina niet verschuift als de data binnenkomt (#808); na een
// fout de melding met een nieuwe poging. Zonder die twee las "Geen vacaturegegevens beschikbaar" als inhoud.
export function DeelLading({ titel, loading, error, onOpnieuw, hoogte = 240, children }) {
  if (loading) {
    return (
      <ChartCard title={titel}>
        <div className="db-skeleton-chart" style={{ height: hoogte }} role="status" aria-label={titel + ' laden'} />
      </ChartCard>
    )
  }
  if (error) {
    return (
      <ChartCard title={titel}>
        <p className="dashboard-deelfout" role="alert">
          {titel} kon niet worden geladen. {error.melding}
          {error.herstelbaar && <OpnieuwKnop onOpnieuw={onOpnieuw} />}
        </p>
      </ChartCard>
    )
  }
  return children
}

export function Sparkline({ values, color = COLOR_EIGEN, width = 80, height = 28 }) {
  const pts = values.filter(v => v != null)
  if (pts.length < 2) return null
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  const step = width / (pts.length - 1)
  const points = pts.map((v, i) => {
    const x = i * step
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block', marginTop: 4 }} aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// De kopjes van een dashboard volgen op de titel (h1, WorkbookViewer): een sectie is h2, een grafiek erin h3 (#905).
export function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ margin: '28px 0 12px', borderBottom: '1px solid var(--gray-200)', paddingBottom: 8 }}>
      <h2 style={{ fontWeight: 700, fontSize: '.95rem', color: 'var(--gray-900)', margin: 0 }}>{title}</h2>
      {subtitle && <div className="db-sectie-sub">{subtitle}</div>}
    </div>
  )
}

export function ChartCard({ title, subtitle, children, cardStyle, actions }) {
  return (
    <div className="charts-grid charts-grid-single">
      <div className="chart-card" style={cardStyle}>
        {(title || subtitle || actions) && (
          <div className="chart-header" style={actions ? { display: 'flex', alignItems: 'flex-start' } : undefined}>
            <div>
              {title && <h3 className="chart-title">{title}</h3>}
              {subtitle && <div className="chart-sub">{subtitle}</div>}
            </div>
            {actions}
          </div>
        )}
        <GrafiekTitel.Provider value={title || null}>{children}</GrafiekTitel.Provider>
      </div>
    </div>
  )
}

// ─── Bronvermeldingen ────────────────────────────────────────────────────────

export const BRONNEN_HO = [
  { label: 'DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)', url: 'https://onderwijsdata.duo.nl/datasets/p01hoinges' },
  { label: 'DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)', url: 'https://onderwijsdata.duo.nl/datasets/p02ho1ejrs' },
  { label: 'DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)', url: 'https://onderwijsdata.duo.nl/datasets/p04hogdipl' },
]

export const BRONNEN_MBO = [
  { label: 'DUO Open Onderwijsdata — Ingeschrevenen MBO per instelling', url: 'https://onderwijsdata.duo.nl/datasets/mbo-studenten-per-instelling' },
  { label: 'DUO Open Onderwijsdata — Instromende MBO-studenten', url: 'https://onderwijsdata.duo.nl/datasets/instromende-mbo-studenten' },
  { label: 'DUO Open Onderwijsdata — Gediplomeerde MBO-studenten', url: 'https://onderwijsdata.duo.nl/datasets/gediplomeerde-mbo-studenten' },
]

// Landelijk (#919): per niveau de ene bron waar de ranking en de sectorpositie uit komen, met dataset-ID. De ranking
// voor "ho" is de gemengde top van hbo en wo samen (p01hoinges kent geen aparte wo-ranking).
export const BRONNEN_NATIONAAL = {
  ho: [
    { label: 'DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)', url: 'https://onderwijsdata.duo.nl/datasets/p01hoinges' },
  ],
  mbo: [
    { label: 'DUO Open Onderwijsdata — MBO studenten per instelling (mbo-studenten-per-instelling)', url: 'https://onderwijsdata.duo.nl/datasets/mbo-studenten-per-instelling' },
  ],
}

// De populatie die de ranking telt, per niveau (#919): de ondertitels noemen dit, zodat "alle instellingen" niet als wo-
// of sectorranking leest.
export const POPULATIE_NATIONAAL = { ho: 'alle HO-instellingen (hbo + wo)', mbo: 'alle MBO-instellingen' }

// De namen van de ROA-bronnen (#917): AIS tot 2030 en de schoolverlatersinformatie. De footer en de teksten bij de
// ROA-grafieken gebruiken dezelfde twee, zodat één bron niet twee namen krijgt. Er staat bewust geen editie bij: de
// editie komt uit de data (`/version`, catalogus roa), en een vast label loopt achter zodra er een nieuwe uitkomt;
// het structurele bronblok met editie is #904.
export const ROA_AIS = 'AIS tot 2030'
export const ROA_SIS = 'SIS 2024'

// Arbeidsmarkt (#917): de aanbodkant is de DUO-gediplomeerden van het niveau van de instelling (zie
// `_arbeidsmarktmatch_ho` en `_arbeidsmarktmatch_mbo` in data/dashboard.py), de vraagkant UWV, de context ROA.
// `kort` is de naam in de badge; de badge is afgeleid van deze lijst, zodat badge en footer niet uiteenlopen.
const BRONNEN_ARBEIDSMARKT_AANBOD = {
  ho: [
    { kort: 'DUO', label: 'DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)', url: 'https://onderwijsdata.duo.nl/datasets/p04hogdipl' },
  ],
  mbo: [
    { kort: 'DUO', label: 'DUO Open Onderwijsdata — Gediplomeerde MBO-studenten (gediplomeerde-mbo-studenten)', url: 'https://onderwijsdata.duo.nl/datasets/gediplomeerde-mbo-studenten' },
  ],
}

const BRONNEN_ARBEIDSMARKT_VRAAG_EN_CONTEXT = [
  { kort: 'UWV', label: 'UWV Open Match — Vacaturedata per provincie en beroepscluster', url: 'https://data.overheid.nl/dataset/uwv-open-match-data' },
  { kort: 'ROA', label: `ROA — ${ROA_AIS}, incl. ${ROA_SIS}`, url: 'https://doi.org/10.34894/DVQTOG' },
]

// Zonder bekend niveau (de instelling is niet gevonden) is er geen aanbodkant en dus geen DUO-bron.
export const bronnenArbeidsmarkt = type => [...(BRONNEN_ARBEIDSMARKT_AANBOD[type] || []), ...BRONNEN_ARBEIDSMARKT_VRAAG_EN_CONTEXT]

// "DUO, UWV & ROA": de korte namen van de bronnen in de lijst, ieder één keer.
export function bronBadge(bronnen) {
  const namen = [...new Set(bronnen.map(b => b.kort))]
  return namen.length > 1 ? `${namen.slice(0, -1).join(', ')} & ${namen[namen.length - 1]}` : namen.join('')
}

export function DashboardSources({ sources }) {
  if (!sources?.length) return null
  return (
    <div className="dashboard-sources">
      <div className="dashboard-sources-title">Bronnen</div>
      <ul className="dashboard-sources-list">
        {sources.map(({ label, url }) => (
          <li key={url}>
            <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`${label} (opent in een nieuw tabblad)`}>
              <span>{label}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function RegioBadges({ instelling, provincie, arbeidsmarktregio, bron }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
      <span className="meta-badge instelling">{instelling}</span>
      {arbeidsmarktregio && <span className="meta-badge date">Regio {arbeidsmarktregio}</span>}
      {provincie && <span className="meta-badge date">Provincie {provincie}</span>}
      <span className="meta-badge date">Bron: {bron}</span>
    </div>
  )
}
