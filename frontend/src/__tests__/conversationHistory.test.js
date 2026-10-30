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

  // #779: de server geeft hoogstens 50 treffers, nieuwste eerst; zonder melding leek dat alles.
  it('says when older hits may be missing behind a full page', async () => {
    const results = [{ id: 'c9', title: 'Uitval hbo', timestamp: Date.now() }]
    await renderHistory({ search: zoek({ query: 'hbo', results, full: true }) })
    expect(container.querySelector('.history-search-note').textContent)
      .toBe('De 50 nieuwste treffers staan hier. Maak je zoekterm preciezer om oudere te vinden.')
  })

  it('says nothing extra when the page was not full', async () => {
    const results = [{ id: 'c9', title: 'Uitval hbo', timestamp: Date.now() }]
    await renderHistory({ search: zoek({ query: 'hbo', results, full: false }) })
    expect(container.querySelector('.history-search-note')).toBeNull()
  })
})

// #779: het hernoemveld stond binnen de gespreksknop; een <input> in een <button> is ongeldige HTML.
describe('conversation history: rename', () => {
  const hernoemKnop = () => container.querySelector('[aria-label="Hernoem gesprek Studenten HU"]')
  const veld = () => container.querySelector('.title-edit-input')
  const gespreksKnop = () => container.querySelector('.history-btn[data-conv-id="c1"]')

  async function typ(waarde) {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    await act(async () => {
      set.call(veld(), waarde)
      veld().dispatchEvent(new Event('input', { bubbles: true }))
    })
  }
  const toets = key => act(async () => { veld().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })) })

  it('shows the field outside any button, with a name, and focuses it', async () => {
    await renderHistory()
    await act(async () => { hernoemKnop().click() })
    await act(async () => { await new Promise(r => setTimeout(r, 0)) })

    expect(veld()).not.toBeNull()
    expect(veld().closest('button')).toBeNull()
    expect(veld().getAttribute('aria-label')).toBe('Nieuwe naam voor gesprek Studenten HU')
    expect(document.activeElement).toBe(veld())
    expect(gespreksKnop()).toBeNull()
  })

  it('saves on Enter and puts the focus back on the conversation', async () => {
    const onRename = vi.fn()
    await renderHistory({ onRename })
    await act(async () => { hernoemKnop().click() })
    await typ('Studenten HU 2024')
    await toets('Enter')

    expect(onRename).toHaveBeenCalledWith('c1', 'Studenten HU 2024')
    expect(veld()).toBeNull()
    expect(document.activeElement).toBe(gespreksKnop())
  })

  it('drops the edit on Escape and puts the focus back on the conversation', async () => {
    const onRename = vi.fn()
    await renderHistory({ onRename })
    await act(async () => { hernoemKnop().click() })
    await typ('Iets anders')
    await toets('Escape')

    expect(onRename).not.toHaveBeenCalled()
    expect(veld()).toBeNull()
    expect(document.activeElement).toBe(gespreksKnop())
  })
})
