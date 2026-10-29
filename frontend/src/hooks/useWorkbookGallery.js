import { useState, useEffect, useCallback } from 'react'
import { getWorkbooks, getWorkbookType, deleteWorkbook, isVolledig, loadWorkbook, loadWorkbooksFromServer } from '../workbooks'
import { buurVan, idsInDocument, kiezerMetId } from '../focusNa'
import { useFocusNaRender } from './useFocusNaRender'

// De kaarten in de galerij, niet die in "Snel terug" (#603): daar staat hetzelfde rapport nog een keer.
const KAART_ZONDER_ID = '.wb-grid .wb-card'
const KAART = `${KAART_ZONDER_ID}[data-wb-id]`

export function useWorkbookGallery({ type, pendingId, clearPending, deleteMessage, initialSelected = null }) {
  const [workbooks, setWorkbooks] = useState(() => {
    const all = getWorkbooks()
    return type ? all.filter(w => getWorkbookType(w) === type) : all
  })
  const [gekozen, setSelected] = useState(initialSelected)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const focusNa = useFocusNaRender()
  // The localStorage list can be empty or stale; only the server list may say "nothing saved".
  const [loading, setLoading] = useState(true)
  const [missingId, setMissingId] = useState(null)
  const [openFout, setOpenFout] = useState(null)
  // Het werkboek waarvan de DELETE niet lukte (#778): het staat weer in de galerij, met een nieuwe poging.
  const [nietVerwijderd, setNietVerwijderd] = useState(null)

  useEffect(() => {
    loadWorkbooksFromServer().then(wbs => {
      setWorkbooks(type ? wbs.filter(w => getWorkbookType(w) === type) : wbs)
    }).finally(() => setLoading(false))
  }, [type])

  // The list holds summaries (#633): a chosen one opens once its content is in. Until then the page
  // shows that it is opening; the viewer never gets a workbook without its report or spec.
  const openen = gekozen && !isVolledig(gekozen) ? gekozen : null
  useEffect(() => {
    if (!openen) return
    let weg = false
    setOpenFout(null)
    loadWorkbook(openen.id).then(full => {
      if (!weg) setSelected(prev => (prev?.id === full.id ? full : prev))
    }).catch(err => {
      if (weg) return
      setSelected(null)
      if (err.status === 404) setMissingId(openen.id)
      else setOpenFout('Dit rapport openen lukt nu niet. Probeer het zo opnieuw.')
    })
    return () => { weg = true }
  }, [openen])

  // A linked id may only be known to the server (other device, cleared storage): look again
  // once the server list is in, and only then call it missing (#387).
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

  const verwijder = useCallback((id) => {
    const lijstNu = () => {
      const all = getWorkbooks()
      setWorkbooks(type ? all.filter(w => getWorkbookType(w) === type) : all)
    }
    // Nu de kaart nog in de galerij staat: de kaart erna, of anders de vorige (#776).
    const buur = buurVan(idsInDocument(KAART, 'data-wb-id'), id)
    const titel = workbooks.find(w => w.id === id)?.title
    setNietVerwijderd(null)
    deleteWorkbook(id).catch(() => {
      lijstNu()
      setNietVerwijderd({ id, titel })
    })
    lijstNu()
    if (gekozen?.id === id) setSelected(null)
    // Zonder dit viel de focus op <body>: de verwijderknop is met zijn kaart weg.
    focusNa(buur && kiezerMetId(KAART_ZONDER_ID, 'data-wb-id', buur), KAART, '.wb-gallery-title')
  }, [type, workbooks, gekozen, focusNa])

  const handleDelete = useCallback((id) => {
    setPendingConfirm({ message: deleteMessage, onConfirm: () => verwijder(id) })
  }, [deleteMessage, verwijder])

  const verwijderFout = nietVerwijderd && { titel: nietVerwijderd.titel, opnieuw: () => verwijder(nietVerwijderd.id) }

  const selected = openen ? null : gekozen
  return {
    workbooks, setWorkbooks, loading, missingId, openFout, opening: Boolean(openen),
    selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete, verwijderFout,
  }
}
