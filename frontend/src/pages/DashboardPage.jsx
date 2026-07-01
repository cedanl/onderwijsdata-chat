import { useState, useEffect, useCallback } from 'react'
import { BUILTIN, BUILTIN_ARBEIDSMARKT, getWorkbooks, deleteWorkbook, loadWorkbooksFromServer, migrateLocalWorkbooks } from '../workbooks'
import { DEFAULT_INSTELLING } from '../constants'
import DashboardCreator from '../components/DashboardCreator'
import DashboardViewer from '../components/DashboardViewer'
import DashboardGallery from '../components/DashboardGallery'
import ConfirmModal from '../components/ConfirmModal'

export default function DashboardPage({ setPage, settings, pendingWorkbookId, clearPendingWorkbook }) {
  const [userWorkbooks, setUserWorkbooks] = useState(getWorkbooks)
  const [selected, setSelected] = useState(null)
  const [showCreator, setShowCreator] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState(null)

  useEffect(() => {
    migrateLocalWorkbooks().then(() => loadWorkbooksFromServer()).then(wbs => {
      setUserWorkbooks(wbs)
    })
  }, [])

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

  const handleUpdate = useCallback((updated) => {
    setSelected(updated)
    setUserWorkbooks(prev => prev.map(w => w.id === updated.id ? updated : w))
  }, [])

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

  const all = [BUILTIN, BUILTIN_ARBEIDSMARKT, ...userWorkbooks]

  if (selected) {
    return (
      <DashboardViewer
        workbook={selected}
        instelling={instelling}
        onBack={() => setSelected(null)}
        onUpdate={handleUpdate}
      />
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
        <ConfirmModal
          message={pendingConfirm.message}
          onConfirm={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      <DashboardGallery
        workbooks={all}
        instelling={instelling}
        onSelect={setSelected}
        onDelete={handleDelete}
        onNew={() => setShowCreator(true)}
      />
    </>
  )
}
