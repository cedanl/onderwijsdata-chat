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
