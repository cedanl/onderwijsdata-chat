import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BUILTIN, BUILTIN_ARBEIDSMARKT, BUILTIN_REGIO_INSTROOM, BUILTIN_REGIO_DIPLOMERING, BUILTIN_REGIO_ARBEIDSMARKT, getWorkbooks, getWorkbookType } from '../workbooks'

const BUILTINS = [BUILTIN, BUILTIN_ARBEIDSMARKT, BUILTIN_REGIO_INSTROOM, BUILTIN_REGIO_DIPLOMERING, BUILTIN_REGIO_ARBEIDSMARKT]
import { DEFAULT_INSTELLING } from '../constants'
import DashboardCreator from '../components/DashboardCreator'
import WorkbookViewer from '../components/WorkbookViewer'
import DashboardGallery from '../components/DashboardGallery'
import ConfirmModal from '../components/ConfirmModal'
import { useWorkbookGallery } from '../hooks/useWorkbookGallery'

export default function DashboardPage({ settings }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const pendingId = searchParams.get('id')
  const [showCreator, setShowCreator] = useState(false)

  const { workbooks, setWorkbooks, selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete } =
    useWorkbookGallery({
      type: 'dashboard',
      pendingId,
      clearPending: undefined,
      deleteMessage: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
    })

  useEffect(() => {
    if (!pendingId || selected) return
    const builtin = BUILTINS.find(b => b.id === pendingId)
    if (builtin) setSelected(builtin)
  }, [pendingId, selected])

  const handleSelect = (wb) => {
    setSelected(wb)
    setSearchParams({ id: wb.id }, { replace: true })
  }

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING

  const handleSaved = (newWb) => {
    const stored = getWorkbooks()
    const found = stored.find(w => w.id === newWb?.id)
    setWorkbooks(stored)
    setShowCreator(false)
    if (found) {
      setSelected(found)
      setSearchParams({ id: found.id }, { replace: true })
    }
  }

  const all = [...BUILTINS, ...workbooks.filter(w => getWorkbookType(w) === 'dashboard')]

  if (selected) {
    return (
      <WorkbookViewer
        workbook={selected}
        instelling={instelling}
        onBack={() => { setSelected(null); setSearchParams({}, { replace: true }) }}
        onUpdate={handleUpdate}
        backLabel="Dashboards"
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
        onSelect={handleSelect}
        onDelete={handleDelete}
        onNew={() => setShowCreator(true)}
      />
    </>
  )
}
