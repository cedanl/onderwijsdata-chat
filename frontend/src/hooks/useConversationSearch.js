import { useEffect, useRef, useState } from 'react'
import { fetchConversations } from '../api'

// Waiting for a pause in typing keeps it to one request per search, not one per key.
export const SEARCH_DELAY_MS = 300
// One page of hits; the server searches all of the user's conversations (#124).
const SEARCH_LIMIT = 50

const parsed = c => ({ ...c, messages: typeof c.messages === 'string' ? JSON.parse(c.messages) : c.messages })

// Search in the conversation history (#124). Lives in the page, not in the sidebar, so the
// query and its results survive closing and opening the mobile drawer.
export function useConversationSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(false)
  const latestRef = useRef('')

  const term = query.trim()

  useEffect(() => {
    latestRef.current = term
    setError(false)
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
          setResults(rows.map(parsed))
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

  return { query, setQuery, results, searching, error }
}
