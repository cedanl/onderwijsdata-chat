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

function Harness() {
  search = useConversationSearch()
  return null
}

beforeEach(async () => {
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
    fetchConversations.mockResolvedValue([{ id: 'c1', title: 'Uitval hbo', timestamp: 1, messages: '[{"role":"user","content":"x"}]' }])
    await act(async () => { search.setQuery('uit') })
    await act(async () => { search.setQuery('uitval') })
    expect(search.searching).toBe(true)
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })

    expect(fetchConversations).toHaveBeenCalledOnce()
    expect(fetchConversations).toHaveBeenCalledWith(expect.objectContaining({ q: 'uitval' }))
    expect(search.searching).toBe(false)
    expect(search.results).toEqual([{ id: 'c1', title: 'Uitval hbo', timestamp: 1, messages: [{ role: 'user', content: 'x' }] }])
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
      .mockResolvedValueOnce([{ id: 'c2', title: 'Tweede', timestamp: 2, messages: [] }])
    await act(async () => { search.setQuery('eerste') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    await act(async () => { search.setQuery('tweede') })
    await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
    await act(async () => { answerFirst([{ id: 'c1', title: 'Eerste', timestamp: 1, messages: [] }]) })

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
