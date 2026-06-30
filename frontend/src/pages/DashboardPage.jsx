import { useState, useEffect } from 'react'
import { BUILTIN, BUILTIN_ARBEIDSMARKT, getWorkbooks, deleteWorkbook } from '../workbooks'
import { DEFAULT_INSTELLING } from '../constants'
import DashboardCreator from '../components/DashboardCreator'
import WorkbookPreview from '../components/WorkbookPreviews'
import { InlineDashboard, InlineDashboardArbeidsmarkt } from '../components/InlineDashboards'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function DashboardPage({ setPage, settings, pendingWorkbookId, clearPendingWorkbook }) {
  const [userWorkbooks, setUserWorkbooks] = useState(getWorkbooks)
  const [selected, setSelected] = useState(null)
  const [showCreator, setShowCreator] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  // pendingConfirm = { message: string, onConfirm: () => void } | null

  useEffect(() => {
    if (!pendingWorkbookId) return
    const wbs = getWorkbooks()
    const wb = wbs.find(w => w.id === pendingWorkbookId)
    if (wb) {
      setUserWorkbooks(wbs)
      setSelected(wb)
    }
    clearPendingWorkbook?.()
  }, [pendingWorkbookId, clearPendingWorkbook])

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING

  const all = [BUILTIN, BUILTIN_ARBEIDSMARKT, ...userWorkbooks]

  const handleDelete = (id) => {
    setPendingConfirm({
      message: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
      onConfirm: () => {
        deleteWorkbook(id)
        setUserWorkbooks(getWorkbooks())
        if (selected?.id === id) setSelected(null)
      },
    })
  }

  const handleSaved = (newWb) => {
    const stored = getWorkbooks()
    const found = stored.find(w => w.id === newWb?.id)
    setUserWorkbooks(stored)
    setShowCreator(false)
    if (found) setSelected(found)
  }

  if (selected) {
    return (
      <div className="wb-viewer">
        <div className="wb-viewer-bar">
          <button className="wb-back-btn" onClick={() => setSelected(null)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboards
          </button>
          <span className="wb-viewer-title">{selected.title}</span>
          <div />
        </div>
        <div className="wb-viewer-content" style={{ overflowY: 'auto' }}>
          {selected.id === '__builtin__'
            ? <InlineDashboard instelling={instelling} />
            : selected.id === '__builtin_arbeidsmarkt__'
            ? <InlineDashboardArbeidsmarkt instelling={instelling} />
            : <iframe className="wb-iframe" srcDoc={selected.htmlContent} title={selected.title} sandbox="allow-scripts" />
          }
        </div>
      </div>
    )
  }

  if (showCreator) {
    return (
      <div className="wb-gallery-page">
        <div className="wb-gallery-header">
          <button className="wb-back-btn" onClick={() => setShowCreator(false)} style={{ border: 'none', background: 'none', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--gray-600)', fontWeight: 600, fontSize: '.88rem', cursor: 'pointer' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboards
          </button>
        </div>
        <DashboardCreator onSaved={handleSaved} instelling={instelling} />
      </div>
    )
  }

  return (
    <>
    {pendingConfirm && (
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
        <div style={{ background: 'var(--bg)', borderRadius: 12, padding: 24, maxWidth: 360, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
          <p style={{ marginBottom: 20, fontSize: '.95rem' }}>{pendingConfirm.message}</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button onClick={() => setPendingConfirm(null)} style={{ padding: '8px 16px', borderRadius: 8, border: '1.5px solid var(--border)', background: 'none', cursor: 'pointer' }}>Annuleren</button>
            <button onClick={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#DC2626', color: 'white', cursor: 'pointer', fontWeight: 600 }}>Verwijderen</button>
          </div>
        </div>
      </div>
    )}
    <div className="wb-gallery-page">
      <div className="wb-gallery-header">
        <div>
          <div className="wb-gallery-title">Dashboards</div>
          <div className="wb-gallery-sub">{all.length} dashboard{all.length !== 1 ? 's' : ''}</div>
        </div>
      </div>

      <div className="wb-grid">
        {all.map(wb => (
          <div key={wb.id} className="wb-card" onClick={() => setSelected(wb)}>
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
                    onClick={e => { e.stopPropagation(); handleDelete(wb.id) }}
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

        <button className="wb-new-card" onClick={() => setShowCreator(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Nieuw dashboard</span>
          <small>Beschrijf welke data je wilt zien</small>
        </button>

        {import.meta.env.DEV && (
        <button className="wb-new-card" onClick={() => { import('../devSeedDashboard').then(({ seedDashboardChat }) => seedDashboardChat()); setShowCreator(true) }} style={{ borderColor: '#F59E0B', background: '#FFFBEB' }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          <span style={{ color: '#92400E' }}>Test dashboard</span>
          <small style={{ color: '#B45309' }}>Opent creator met voorgeladen data</small>
        </button>
        )}
      </div>
    </div>
    </>
  )
}
