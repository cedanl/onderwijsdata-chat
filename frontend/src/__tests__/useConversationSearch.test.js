// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({ fetchConversations: vi.fn() }))

import { fetchConversations } from '../api'
import { useConversationSearch, SEARCH_DELAY_MS } from '../hooks/useConversationSearch'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container
let search

beforeEach(async () => {
  function Harness() {
    search = useConversationSearch()
    return null
  }
  vi.useFakeTimers()
  fetchConversations.mockReset()
  container = document.createElement('div')
  root = createRoot(container)
  await act(async () => { root.render(createElement(Harness)) })
})

afterEach(() => {
  act(() => root.unmount())
  vi.useRealTimers()
})

// #124: zoeken in de gespreksgeschiedenis, server-side op titel en inhoud.
describe('useConversationSearch', () => {
  it('asks the server once the user stops typing', async () => {
    // The hits are summaries: the server matched on the text, the list carries none of it (#509).
    fetchConversations.mockResolvedValue([{ id: 'c1', title: 'Uitval hbo', timestamp: 1 }])
    await act(async () => { search.setQuery('uit') })
    await act(async () => { search.setQuery('uitval') })
    expect(search.searching).toBe(true)
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })

    expect(fetchConversations).toHaveBeenCalledOnce()
    expect(fetchConversations).toHaveBeenCalledWith(expect.objectContaining({ q: 'uitval' }))
    expect(search.searching).toBe(false)
    expect(search.results).toEqual([{ id: 'c1', title: 'Uitval hbo', timestamp: 1 }])
  })

  it('has no results without a query, and does not ask the server', async () => {
    await act(async () => { search.setQuery('   ') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    expect(search.results).toBeNull()
    expect(fetchConversations).not.toHaveBeenCalled()
  })

  it('drops the answer to a query that was already changed', async () => {
    let answerFirst
    fetchConversations
      .mockImplementationOnce(() => new Promise(resolve => { answerFirst = resolve }))
      .mockResolvedValueOnce([{ id: 'c2', title: 'Tweede', timestamp: 2 }])
    await act(async () => { search.setQuery('eerste') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    await act(async () => { search.setQuery('tweede') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    await act(async () => { answerFirst([{ id: 'c1', title: 'Eerste', timestamp: 1 }]) })

    expect(search.results.map(c => c.id)).toEqual(['c2'])
  })

  it('says so when the server cannot be reached', async () => {
    fetchConversations.mockRejectedValue(new Error('offline'))
    await act(async () => { search.setQuery('uitval') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    expect(search.error).toBe(true)
    expect(search.searching).toBe(false)
  })
})

// #529: a hit deleted from the results goes at once and comes back on undo, in its place.
describe('useConversationSearch remove and restore', () => {
  const hits = [
    { id: 'c1', title: 'Uitval hbo', timestamp: 3 },
    { id: 'c2', title: 'Uitval mbo', timestamp: 2 },
    { id: 'c3', title: 'Uitval wo', timestamp: 1 },
  ]

  async function searchFor(query) {
    await act(async () => { search.setQuery(query) })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
  }

  it('removes a hit and puts it back at its index', async () => {
    fetchConversations.mockResolvedValue(hits)
    await searchFor('uitval')

    await act(async () => { search.removeResult('c2') })
    expect(search.results.map(c => c.id)).toEqual(['c1', 'c3'])

    await act(async () => { search.restoreResult(hits[1], 1) })
    expect(search.results.map(c => c.id)).toEqual(['c1', 'c2', 'c3'])
  })

  it('keeps a removed hit out of a later answer that still has it', async () => {
    fetchConversations.mockResolvedValue(hits)
    await searchFor('uitval')
    await act(async () => { search.removeResult('c2') })

    await searchFor('uitval hbo')
    expect(search.results.map(c => c.id)).toEqual(['c1', 'c3'])
  })

  it('does not put a hit back into the results of another query', async () => {
    fetchConversations.mockResolvedValueOnce(hits).mockResolvedValueOnce([hits[0]])
    await searchFor('uitval')
    await act(async () => { search.removeResult('c2') })
    await searchFor('hbo')

    await act(async () => { search.restoreResult(hits[1], 1) })
    expect(search.results.map(c => c.id)).toEqual(['c1'])
  })

  it('leaves the results alone without a search', async () => {
    await act(async () => { search.removeResult('c2') })
    await act(async () => { search.restoreResult(hits[1], 1) })
    expect(search.results).toBeNull()
  })

  it('only lifts the hiding when the hit was not in the results', async () => {
    fetchConversations.mockResolvedValue(hits)
    await act(async () => { search.removeResult('c2') })
    await act(async () => { search.restoreResult(hits[1], -1) })

    await searchFor('uitval')
    expect(search.results.map(c => c.id)).toEqual(['c1', 'c2', 'c3'])
  })
})
