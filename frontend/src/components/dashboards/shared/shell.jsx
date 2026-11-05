import { COLOR_EIGEN } from '../../../constants'
import { korteDatum } from '../../../relatieveDatum'
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
            {suggesties.length > 0 ? (
              <> Bedoel je misschien: {suggesties.slice(0,5).join(', ')}?</>
            ) : data.geen_suggesties && <> {data.geen_suggesties}</>}
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

// De regels van één veld uit meer payloads samen, elke sleutel één keer; `bronnen` beperkt ze tot de bronnen (DUO, UWV,
// ROA) die dit dashboard toont. `/api/dashboard/regio` dient twee dashboards, dus elk neemt er zijn eigen deel uit.
function uitPayloads(payloads, veld, sleutel, bronnen) {
  const gezien = new Map()
  for (const payload of payloads) {
    for (const regel of payload?.[veld] || []) {
      if (bronnen && !bronnen.includes(regel.bron)) continue
      if (!gezien.has(sleutel(regel))) gezien.set(sleutel(regel), regel)
    }
  }
  return [...gezien.values()]
}

// De gaten van meer payloads samen, elk onderdeel één keer.
export const gatenVan = (payloads, bronnen = null) => uitPayloads(payloads, 'niet_beschikbaar', g => g.onderdeel, bronnen)

// Het bronblok van meer payloads samen (#904), elke dataset één keer.
export const bronnenVan = (payloads, bronnen = null) => uitPayloads(payloads, 'bronnen', b => `${b.bron}:${b.dataset}`, bronnen)

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
// Het bronblok komt uit de payload (`bronnen`, data/bronblok.py, #904): per bron wat de lading echt laadde, met de
// versie of editie, de peildatum, de voorlopige jaren en het moment van ophalen. Eerder stonden hier vaste lijsten per
// dashboard: zonder editie, en niet per se wat de pagina gebruikte (#917, #919).

// De populatie die de ranking telt, per niveau (#919): de ondertitels noemen dit, zodat "alle instellingen" niet als wo-
// of sectorranking leest.
export const POPULATIE_NATIONAAL = { ho: 'alle HO-instellingen (hbo + wo)', mbo: 'alle MBO-instellingen' }

// De namen van de ROA-onderdelen (#917) in de teksten bij de ROA-grafieken. De editie staat er niet in: die komt uit
// het bronblok (`roaPeilmoment`). De SIS-editie ligt vast in het filter van de backend (`_ROA_SIS` in
// data/arbeidsmarkt.py): een ander SIS-thema geeft daar geen cijfers, dus deze naam loopt er niet bij achter.
export const ROA_AIS = 'AIS tot 2030'
export const ROA_SIS = 'SIS 2024'

// "DUO — Gediplomeerde mbo-studenten (gediplomeerde-mbo-studenten)": de titel uit de catalogus, zoals de chat de bron
// noemt, met het dataset-ID.
export const bronLabel = ({ bron, titel, dataset }) => (titel && titel !== dataset ? `${bron} — ${titel} (${dataset})` : `${bron} — ${dataset}`)

// Wat er onder de link staat: versie of editie, peildatum, voorlopige jaren en wanneer de app de bron ophaalde.
export function bronDetails({ peilmoment, peildatum, voorlopig, voorlopig_jaren: jaren, opgehaald_op: opgehaald }) {
  return [
    peilmoment,
    peildatum && !peilmoment?.includes(peildatum) ? `peildatum ${peildatum}` : null,
    voorlopig && jaren?.length ? `cijfers ${jaren.join(', ')} voorlopig` : null,
    opgehaald ? `opgehaald ${korteDatum(opgehaald)}` : null,
  ].filter(Boolean)
}

// "editie 2025, versie v20251218": de editie van ROA uit het bronblok, voor de teksten bij de ROA-grafieken.
export const roaPeilmoment = bronnen => (bronnen || []).find(b => b.bron === 'ROA')?.peilmoment || null

// "DUO, UWV & ROA": de bronnen in het bronblok, ieder één keer.
export function bronBadge(bronnen) {
  const namen = [...new Set(bronnen.map(b => b.bron))]
  return namen.length > 1 ? `${namen.slice(0, -1).join(', ')} & ${namen[namen.length - 1]}` : namen.join('')
}

export function DashboardSources({ sources }) {
  if (!sources?.length) return null
  return (
    <div className="dashboard-sources">
      <div className="dashboard-sources-title">Bronnen</div>
      <ul className="dashboard-sources-list">
        {sources.map(bron => {
          const label = bronLabel(bron)
          const details = bronDetails(bron)
          return (
            <li key={`${bron.bron}:${bron.dataset}`}>
              <div>
                {bron.url
                  ? (
                    <a href={bron.url} target="_blank" rel="noopener noreferrer" aria-label={`${label} (opent in een nieuw tabblad)`}>
                      <span>{label}</span>
                    </a>
                  )
                  : <span className="dashboard-sources-naam">{label}</span>}
                {details.length > 0 && <div className="dashboard-sources-meta">{details.join(' · ')}</div>}
              </div>
            </li>
          )
        })}
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
      {bron && <span className="meta-badge date">Bron: {bron}</span>}
    </div>
  )
}
