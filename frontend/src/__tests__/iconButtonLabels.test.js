// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

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

import DashboardGallery from '../components/DashboardGallery'
import { ConversationHistory } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function renderIn(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #224: a title tooltip is not reliably announced; an icon-only button needs an aria-label.
describe('icon buttons name their action', () => {
  it('rename and delete in the conversation list', async () => {
    await renderIn(createElement(ConversationHistory, {
      history: [{ id: 'c1', title: 'Studenten HU', timestamp: Date.now() }],
      onLoad: vi.fn(), onDelete: vi.fn(), onRename: vi.fn(),
    }))
    const labels = [...container.querySelectorAll('.history-item-actions button')].map(b => b.getAttribute('aria-label'))
    expect(labels).toEqual(['Hernoem gesprek Studenten HU', 'Verwijder gesprek Studenten HU'])
  })

  it('delete in the report gallery', async () => {
    const wb = { id: 'wb-1', title: 'Mijn rapport', description: 'd', messages: [], figures: [], createdAt: '2026-01-01T00:00:00.000Z' }
    await renderIn(createElement(MemoryRouter, null, createElement(DashboardGallery, {
      workbooks: [wb], instelling: 'HU', onDelete: vi.fn(), onSelect: vi.fn(), onNew: vi.fn(),
    })))
    expect(container.querySelector('.wb-delete-btn').getAttribute('aria-label')).toBe('Verwijder rapport Mijn rapport')
  })
})
