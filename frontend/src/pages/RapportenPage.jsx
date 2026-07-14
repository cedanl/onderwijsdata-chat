import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { DEFAULT_INSTELLING } from '../constants'
import WorkbookViewer from '../components/WorkbookViewer'
import ConfirmModal from '../components/ConfirmModal'
import WorkbookPreview from '../components/WorkbookPreviews'
import { useWorkbookGallery } from '../hooks/useWorkbookGallery'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function RapportenPage({ settings }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const pendingId = searchParams.get('id')
  // Workbook passed via navigation state (from chat → rapport generation); avoids
  // setSearchParams/History API calls that can hit Firefox's rate limit.
  const navWorkbook = location.state?.pendingWorkbook ?? null

  const { workbooks: rapporten, selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete } =
    useWorkbookGallery({
      type: 'report',
      pendingId: navWorkbook ? null : pendingId,
      clearPending: navWorkbook ? undefined : () => setSearchParams({}, { replace: true }),
      deleteMessage: 'Weet je zeker dat je dit rapport wilt verwijderen?',
      initialSelected: navWorkbook,
    })

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING

  if (selected) {
    return (
      <WorkbookViewer
        workbook={selected}
        instelling={instelling}
        onBack={() => setSelected(null)}
        onUpdate={handleUpdate}
        backLabel="Rapporten"
      />
    )
  }

  return (
    <>
      {pendingConfirm && (
        <ConfirmModal
          message={pendingConfirm.message}
          onConfirm={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      <div className="wb-gallery-page">
        <div className="wb-gallery-header">
          <div>
            <div className="wb-gallery-title">Rapporten</div>
            <div className="wb-gallery-sub">{rapporten.length} rapport{rapporten.length !== 1 ? 'en' : ''}</div>
          </div>
        </div>

        {rapporten.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--gray-500)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 48, height: 48, margin: '0 auto 16px', display: 'block', opacity: .4 }}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            <p style={{ marginBottom: 16, fontSize: '.95rem' }}>Nog geen rapporten opgeslagen.</p>
            <button className="navbar-cta" onClick={() => navigate('/chat')}>
              Ga naar Chat
            </button>
            <p style={{ marginTop: 12, fontSize: '.82rem', color: 'var(--gray-400)' }}>
              Stel een vraag en klik op "Genereer rapport" om een rapport hier op te slaan.
            </p>
          </div>
        ) : (
          <div className="wb-grid">
            {rapporten.map(wb => (
              <div key={wb.id} className="wb-card" onClick={() => setSelected(wb)}>
                <div className="wb-card-thumb">
                  <WorkbookPreview wb={wb} />
                </div>
                <div className="wb-card-body">
                  <div className="wb-card-title">{wb.title}</div>
                  <div className="wb-card-desc">{wb.description}</div>
                  <div className="wb-card-footer">
                    <span className="wb-card-date">{formatDate(wb.createdAt)}</span>
                    <button
                      className="wb-delete-btn"
                      title="Verwijder"
                      onClick={e => { e.stopPropagation(); handleDelete(wb.id) }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
