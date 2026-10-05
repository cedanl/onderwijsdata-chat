import { useState, useEffect, useCallback } from 'react'
import { getWorkbooks, getWorkbookType, deleteWorkbook, loadWorkbooksFromServer, migrateLocalWorkbooks } from '../workbooks'

export function useWorkbookGallery({ type, pendingId, clearPending, deleteMessage, initialSelected = null }) {
  const [workbooks, setWorkbooks] = useState(() => {
    const all = getWorkbooks()
    return type ? all.filter(w => getWorkbookType(w) === type) : all
  })
  const [selected, setSelected] = useState(initialSelected)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  // The localStorage list can be empty or stale; only the server list may say "nothing saved".
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    migrateLocalWorkbooks().then(() => loadWorkbooksFromServer()).then(wbs => {
      setWorkbooks(type ? wbs.filter(w => getWorkbookType(w) === type) : wbs)
    }).finally(() => setLoading(false))
  }, [type])

  // A linked id may only be known to the server (other device, cleared storage): look again
  // once the server list is in, and only then call it missing (#387).
  const [missingId, setMissingId] = useState(null)
  useEffect(() => {
    if (!pendingId) return
    const wbs = getWorkbooks()
    const local = wbs.find(w => w.id === pendingId)
    if (local) {
      setWorkbooks(type ? wbs.filter(w => getWorkbookType(w) === type) : wbs)
      setSelected(local)
      clearPending?.()
      return
    }
    if (loading) return
    const fromServer = workbooks.find(w => w.id === pendingId)
    if (fromServer) {
      setSelected(fromServer)
      clearPending?.()
    } else {
      setMissingId(pendingId)
    }
  // workbooks only matters once the server list is in, and that flips loading too.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingId, clearPending, type, loading])

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

  return { workbooks, setWorkbooks, loading, missingId, selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete }
}
