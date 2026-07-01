import WorkbookPreview from './WorkbookPreviews'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function DashboardGallery({ workbooks, instelling, onSelect, onDelete, onNew }) {
  return (
    <div className="wb-gallery-page">
      <div className="wb-gallery-header">
        <div>
          <div className="wb-gallery-title">Dashboards</div>
          <div className="wb-gallery-sub">{workbooks.length} dashboard{workbooks.length !== 1 ? 's' : ''}</div>
        </div>
      </div>

      <div className="wb-grid">
        {workbooks.map(wb => (
          <div key={wb.id} className="wb-card" onClick={() => onSelect(wb)}>
            <div className="wb-card-thumb">
              <WorkbookPreview wb={wb} />
              {wb.builtin && (
                <>
                  <span className="wb-builtin-badge">Voorbeeld</span>
                  <div className="wb-builtin-instelling">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/>
                    </svg>
                    {instelling}
                  </div>
                </>
              )}
            </div>
            <div className="wb-card-body">
              <div className="wb-card-title">{wb.title}</div>
              <div className="wb-card-desc">{wb.description}</div>
              <div className="wb-card-footer">
                {!wb.builtin && <span className="wb-card-date">{formatDate(wb.createdAt)}</span>}
                {!wb.builtin && (
                  <button
                    className="wb-delete-btn"
                    title="Verwijder"
                    onClick={e => { e.stopPropagation(); onDelete(wb.id) }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        <button className="wb-new-card" onClick={onNew}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Nieuw dashboard</span>
          <small>Beschrijf welke data je wilt zien</small>
        </button>

        {import.meta.env.DEV && (
          <button className="wb-new-card" onClick={() => { import('../devSeedDashboard').then(({ seedDashboardChat }) => seedDashboardChat()); onNew() }} style={{ borderColor: '#F59E0B', background: '#FFFBEB' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            <span style={{ color: '#92400E' }}>Test dashboard</span>
            <small style={{ color: '#B45309' }}>Opent creator met voorgeladen data</small>
          </button>
        )}
      </div>
    </div>
  )
}
