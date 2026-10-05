// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn(),
  renameConversationApi: vi.fn(),
  deleteConversationApi: vi.fn(),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { ConversationHistory } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function renderHistory(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(ConversationHistory, {
      history: [{ id: 'c1', title: 'Studenten HU', timestamp: Date.now() }],
      onLoad: vi.fn(), onDelete: vi.fn(), onRename: vi.fn(),
      ...props,
    }))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const moreButton = () => container.querySelector('.history-more-btn')

// #123: gesprek 16+ is bereikbaar via "meer laden".
describe('conversation history: load more', () => {
  it('offers "Meer laden" while the server has older conversations', async () => {
    const onLoadMore = vi.fn()
    await renderHistory({ hasMore: true, onLoadMore })
    expect(moreButton().textContent).toBe('Meer laden')
    await act(async () => { moreButton().click() })
    expect(onLoadMore).toHaveBeenCalledOnce()
  })

  it('shows no button on the last page', async () => {
    await renderHistory({ hasMore: false })
    expect(moreButton()).toBeNull()
  })

  it('cannot be clicked twice while a page is loading', async () => {
    await renderHistory({ hasMore: true, loadingMore: true, onLoadMore: vi.fn() })
    expect(moreButton().disabled).toBe(true)
  })
})

// #124: the search field filters the history; results replace the list while there is a query.
describe('conversation history: search', () => {
  const zoek = (props) => ({ query: '', setQuery: vi.fn(), results: null, searching: false, error: false, ...props })

  it('types into the search', async () => {
    const search = zoek()
    await renderHistory({ search })
    const input = container.querySelector('input[type="search"]')
    expect(input.getAttribute('aria-label')).toBe('Zoek in gesprekken')
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
      setter.call(input, 'uitval')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(search.setQuery).toHaveBeenCalledWith('uitval')
  })

  it('shows the results instead of the list, without "Meer laden"', async () => {
    await renderHistory({
      hasMore: true,
      search: zoek({ query: 'uitval', results: [{ id: 'c9', title: 'Uitval hbo', timestamp: Date.now() }] }),
    })
    const titels = [...container.querySelectorAll('.history-btn-title')].map(t => t.textContent)
    expect(titels).toEqual(['Uitval hbo'])
    expect(moreButton()).toBeNull()
  })

  it('says when nothing was found', async () => {
    await renderHistory({ search: zoek({ query: 'xyz', results: [] }) })
    expect(container.textContent).toContain('Geen gesprekken gevonden')
  })

  it('says when the search failed', async () => {
    await renderHistory({ search: zoek({ query: 'xyz', error: true }) })
    expect(container.textContent).toContain('Zoeken lukt nu niet')
  })
})
