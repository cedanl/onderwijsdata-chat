import { useState, useEffect, useCallback } from 'react'
import { getWorkbooks, getWorkbookType, deleteWorkbook, loadWorkbooksFromServer, migrateLocalWorkbooks } from '../workbooks'

export function useWorkbookGallery({ type, pendingId, clearPending, deleteMessage, initialSelected = null }) {
  const [workbooks, setWorkbooks] = useState(() => {
    const all = getWorkbooks()
    return type ? all.filter(w => getWorkbookType(w) === type) : all
  })
  const [selected, setSelected] = useState(initialSelected)
  const [pendingConfirm, setPendingConfirm] = useState(null)

  useEffect(() => {
    migrateLocalWorkbooks().then(() => loadWorkbooksFromServer()).then(wbs => {
      setWorkbooks(type ? wbs.filter(w => getWorkbookType(w) === type) : wbs)
    })
  }, [type])

  useEffect(() => {
    if (!pendingId) return
    const wbs = getWorkbooks()
    const wb = wbs.find(w => w.id === pendingId)
    if (wb) {
      setWorkbooks(type ? wbs.filter(w => getWorkbookType(w) === type) : wbs)
      setSelected(wb)
      clearPending?.()
    }
  }, [pendingId, clearPending, type])

  const handleUpdate = useCallback((updated) => {
    setSelected(updated)
    setWorkbooks(prev => prev.map(w => w.id === updated.id ? updated : w))
  }, [])

  const handleDelete = useCallback((id) => {
    setPendingConfirm({
      message: deleteMessage,
      onConfirm: () => {
        deleteWorkbook(id)
        const all = getWorkbooks()
        setWorkbooks(type ? all.filter(w => getWorkbookType(w) === type) : all)
        if (selected?.id === id) setSelected(null)
      },
    })
  }, [type, deleteMessage, selected])

  return { workbooks, setWorkbooks, selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete }
}
