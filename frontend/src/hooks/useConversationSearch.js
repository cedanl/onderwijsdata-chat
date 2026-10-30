import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchConversations } from '../api'
import { terugInLijst } from '../verwijderenMetUitstel'

// Waiting for a pause in typing keeps it to one request per search, not one per key.
export const SEARCH_DELAY_MS = 300
// One page of hits, the server's maximum; the server searches all of the user's conversations (#124), newest first.
export const SEARCH_LIMIT = 50

// Search in the conversation history (#124). Lives in the page, not in the sidebar, so the
// query and its results survive closing and opening the mobile drawer.
export function useConversationSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(false)
  // A full page: older hits may be missing, and the list says so (#779).
  const [full, setFull] = useState(false)
  const latestRef = useRef('')
  // Hits deleted while their undo is pending (#529): id -> the query they were removed from.
  const hiddenRef = useRef(new Map())

  const term = query.trim()

  useEffect(() => {
    latestRef.current = term
    setError(false)
    setFull(false)
    if (!term) {
      setResults(null)
      setSearching(false)
      return undefined
    }
    setSearching(true)
    const timer = setTimeout(() => {
      fetchConversations({ q: term, limit: SEARCH_LIMIT })
        .then(rows => {
          if (latestRef.current !== term) return
          setFull(rows.length >= SEARCH_LIMIT)
          setResults(rows.filter(c => !hiddenRef.current.has(String(c.id))))
        })
        .catch(() => {
          if (latestRef.current !== term) return
          setResults(null)
          setError(true)
        })
        .finally(() => {
          if (latestRef.current === term) setSearching(false)
        })
    }, SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [term])

  // Hide a hit now and in later answers: the server keeps it until the undo period ends.
  const removeResult = useCallback(id => {
    hiddenRef.current.set(String(id), latestRef.current)
    setResults(rows => rows && rows.filter(c => String(c.id) !== String(id)))
  }, [])

  // Undo: stop hiding the hit, and put it back at `index` if it was a hit (index >= 0) of the query still shown.
  const restoreResult = useCallback((conv, index) => {
    const removedFrom = hiddenRef.current.get(String(conv.id))
    hiddenRef.current.delete(String(conv.id))
    if (index < 0 || removedFrom !== latestRef.current) return
    setResults(rows => rows && terugInLijst(rows, conv, index))
  }, [])

  return { query, setQuery, results, searching, error, full, removeResult, restoreResult }
}
