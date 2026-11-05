import WorkbookPreview from './WorkbookPreviews'
import { korteDatum } from '../relatieveDatum'

// Opgeslagen dashboards uit de dashboardbouwer (#765): de bouwer is weg en ze openen niet meer, maar ze staan nog op
// de server (en in de export van je gegevens). Hier zie je welke het zijn en kun je ze één voor één verwijderen.
function OpgeslagenDashboards({ dashboards, onDelete }) {
  if (!dashboards.length) return null
  return (
    <section className="wb-opgeslagen" aria-labelledby="wb-opgeslagen-kop">
      <h2 id="wb-opgeslagen-kop" className="wb-snel-kop">Opgeslagen met de dashboardbouwer</h2>
      <p className="wb-snel-noot">
        De dashboardbouwer is uit de app gehaald; deze dashboards openen niet meer. Ze zijn niet weggegooid: ze staan in
        de export van je gegevens, tot je ze hier verwijdert.
      </p>
      <ul className="wb-opgeslagen-lijst">
        {dashboards.map(wb => (
          <li key={wb.id} className="wb-opgeslagen-item" data-wb-id={wb.id}>
            <span className="wb-opgeslagen-titel">{wb.title}</span>
            <span className="wb-card-date">{korteDatum(wb.createdAt)}</span>
            <button type="button"
              className="wb-delete-btn"
              title="Verwijder"
              aria-label={`Verwijder dashboard ${wb.title}`}
              onClick={() => onDelete(wb.id)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
              </svg>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function DashboardGallery({ workbooks, opgeslagen = [], instelling, onSelect, onDelete }) {
  return (
    <div className="wb-gallery-page">
      <div className="wb-gallery-header">
        <div>
          <h1 className="wb-gallery-title" tabIndex={-1}>Dashboards</h1>
          <div className="wb-gallery-sub">{workbooks.length} dashboard{workbooks.length !== 1 ? 's' : ''}</div>
        </div>
      </div>

      <div className="wb-grid">
        {workbooks.map(wb => (
          <a
            key={wb.id}
            href={`/dashboards?id=${encodeURIComponent(wb.id)}`}
            className="wb-card"
            data-wb-id={wb.id}
            onClick={e => { e.preventDefault(); onSelect(wb) }}
          >
            <div className="wb-card-thumb">
              <WorkbookPreview wb={wb} />
              <span className="wb-builtin-badge">Vast dashboard</span>
              <div className="wb-builtin-instelling">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/>
                </svg>
                {instelling}
              </div>
            </div>
            <div className="wb-card-body">
              <div className="wb-card-title">{wb.title}</div>
              <div className="wb-card-desc">{wb.description}</div>
            </div>
          </a>
        ))}
      </div>

      <OpgeslagenDashboards dashboards={opgeslagen} onDelete={onDelete} />
    </div>
  )
}
