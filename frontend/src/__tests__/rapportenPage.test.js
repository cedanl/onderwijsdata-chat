// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act, Fragment } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, useLocation } from 'react-router-dom'

const server = vi.hoisted(() => ({ resolve: null, local: [] }))
vi.mock('../workbooks', () => ({
  getWorkbooks: () => server.local,
  getWorkbookType: (wb) => wb.type,
  deleteWorkbook: vi.fn(id => { server.local = server.local.filter(wb => wb.id !== id) }),
  migrateLocalWorkbooks: () => Promise.resolve(),
  loadWorkbooksFromServer: () => new Promise(r => { server.resolve = r }),
}))
vi.mock('../components/WorkbookViewer', () => ({
  default: ({ workbook, onBack }) => createElement(Fragment, null,
    createElement('div', { 'data-testid': 'viewer' }, workbook.title),
    createElement('button', { type: 'button', 'data-testid': 'back', onClick: onBack }, 'Rapporten'),
  ),
}))
vi.mock('../components/WorkbookPreviews', () => ({ default: () => null }))

import RapportenPage from '../pages/RapportenPage'
import { deleteWorkbook } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

// Shows the current query string, so a test can see the ?id= the page sets.
function LocationProbe() {
  return createElement('output', { 'data-testid': 'location' }, useLocation().search)
}

async function render(url = '/rapporten') {
  document.title = 'openEDUdata+'
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [url] },
      createElement(RapportenPage, { settings: {} }),
      createElement(LocationProbe),
    ))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  server.local = []
  vi.clearAllMocks()
})

describe('RapportenPage first load', () => {
  it('does not claim there are no reports while the server list is loading', async () => {
    await render()
    expect(container.textContent).not.toContain('Nog geen rapporten opgeslagen.')
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull()
  })

  it('shows the reports once the server answers', async () => {
    await render()
    await act(async () => {
      server.resolve([{ id: 'wb-1', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' }])
    })
    expect(container.querySelector('[aria-busy="true"]')).toBeNull()
    expect(container.textContent).toContain('Instroom hbo')
  })

  it('groups the reports under a heading per month (#427)', async () => {
    await render()
    await act(async () => {
      server.resolve([
        { id: 'wb-1', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' },
        { id: 'wb-2', type: 'report', title: 'Uitval mbo', createdAt: '2026-09-15T00:00:00Z' },
      ])
    })
    const headings = [...container.querySelectorAll('.wb-gallery-group-title')].map(h => h.textContent)
    expect(headings).toEqual(['Oktober 2026 (1)', 'September 2026 (1)'])
  })

  it('shows the empty state only when the server list is empty', async () => {
    await render()
    await act(async () => { server.resolve([]) })
    expect(container.textContent).toContain('Nog geen rapporten opgeslagen.')
  })
})

// A report link opened on a device that has never seen the report (#387): the id is only
// known to the server, so the page waits for the server list instead of dropping the id.
describe('RapportenPage opened via a report link', () => {
  it('says the report is being fetched while the server list loads', async () => {
    await render('/rapporten?id=wb-9')
    const busy = container.querySelector('[aria-busy="true"]')
    expect(busy).not.toBeNull()
    expect(busy.textContent).toContain('Rapport wordt opgehaald')
  })

  it('opens the report once the server list has it', async () => {
    await render('/rapporten?id=wb-9')
    await act(async () => {
      server.resolve([{ id: 'wb-9', type: 'report', title: 'Uitval mbo', createdAt: '2026-10-01T00:00:00Z' }])
    })
    expect(container.querySelector('[data-testid="viewer"]')?.textContent).toBe('Uitval mbo')
  })

  it('falls back to the gallery with a notice when the report does not exist', async () => {
    await render('/rapporten?id=wb-weg')
    await act(async () => {
      server.resolve([{ id: 'wb-1', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' }])
    })
    expect(container.querySelector('[data-testid="viewer"]')).toBeNull()
    expect(container.textContent).toContain('Instroom hbo')
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('niet gevonden')
  })
})

// #491: the tab names the page, and an open report by its own title.
describe('RapportenPage tab title', () => {
  it('names the list, also while it loads', async () => {
    await render()
    expect(document.title).toBe('Rapporten — openEDUdata+')
    await act(async () => { server.resolve([]) })
    expect(document.title).toBe('Rapporten — openEDUdata+')
  })

  it('names the list while a linked report is being fetched', async () => {
    await render('/rapporten?id=wb-9')
    expect(document.title).toBe('Rapporten — openEDUdata+')
  })

  it('uses the title of a report opened via a link, and goes back to the list title', async () => {
    await render('/rapporten?id=wb-9')
    await act(async () => {
      server.resolve([{ id: 'wb-9', type: 'report', title: 'Uitval mbo', createdAt: '2026-10-01T00:00:00Z' }])
    })
    expect(document.title).toBe('Uitval mbo — openEDUdata+')
    await act(async () => { container.querySelector('[data-testid="back"]').click() })
    expect(document.title).toBe('Rapporten — openEDUdata+')
  })

  it('uses the title of a report passed in from the chat', async () => {
    const pendingWorkbook = { id: 'wb-3', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' }
    await render({ pathname: '/rapporten', state: { pendingWorkbook } })
    expect(document.title).toBe('Instroom hbo — openEDUdata+')
  })
})

// #562: a title search above the report cards.
describe('RapportenPage search', () => {
  const rapporten = [
    { id: 'wb-1', type: 'report', title: 'Instroom hbo', createdAt: '2026-10-01T00:00:00Z' },
    { id: 'wb-2', type: 'report', title: 'Uitval mbo', createdAt: '2026-10-02T00:00:00Z' },
    { id: 'wb-3', type: 'report', title: 'Instroom Economië', createdAt: '2026-09-15T00:00:00Z' },
  ]

  async function renderWith(list) {
    server.local = list
    await render()
    await act(async () => { server.resolve(list) })
  }

  const searchInput = () => container.querySelector('input[type="search"]')
  const cardTitles = () => [...container.querySelectorAll('.wb-card-title')].map(t => t.textContent)
  const headings = () => [...container.querySelectorAll('.wb-gallery-group-title')].map(h => h.textContent)
  const subtitle = () => container.querySelector('.wb-gallery-sub').textContent
  const buttonNamed = name => [...container.querySelectorAll('button')].find(b => b.textContent === name)

  // React tracks the input value itself; the native setter plus an input event is what a keystroke does.
  async function type(value) {
    const input = searchInput()
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    await act(async () => {
      setValue.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('is absent while the list loads and when there are no reports', async () => {
    await render()
    expect(searchInput()).toBeNull()
    await act(async () => { server.resolve([]) })
    expect(container.textContent).toContain('Nog geen rapporten opgeslagen.')
    expect(searchInput()).toBeNull()
  })

  it('is a search field named "Zoek in rapporten" once there are reports', async () => {
    await renderWith(rapporten)
    const input = searchInput()
    expect(input).not.toBeNull()
    const name = input.getAttribute('aria-label') ?? [...input.labels].map(l => l.textContent).join(' ')
    expect(name).toBe('Zoek in rapporten')
    expect(input.value).toBe('')
    expect(subtitle()).toBe('3 rapporten')
  })

  it('narrows the cards, month groups and counts on every keystroke', async () => {
    await renderWith(rapporten)
    await type('instroom')
    expect(cardTitles()).toEqual(['Instroom hbo', 'Instroom Economië'])
    expect(headings()).toEqual(['Oktober 2026 (1)', 'September 2026 (1)'])
    expect(subtitle()).toBe('2 van 3 rapporten')

    await type('instroom economie')
    expect(cardTitles()).toEqual(['Instroom Economië'])
    expect(headings()).toEqual(['September 2026 (1)'])
    expect(subtitle()).toBe('1 van 3 rapporten')

    await type('')
    expect(cardTitles()).toHaveLength(3)
    expect(subtitle()).toBe('3 rapporten')
  })

  it('keeps the singular for a single report', async () => {
    await renderWith(rapporten.slice(0, 1))
    expect(subtitle()).toBe('1 rapport')
    await type('hbo')
    expect(subtitle()).toBe('1 van 1 rapport')
  })

  it('says nothing was found, shows the query as text, and clears it back to the full list', async () => {
    await renderWith(rapporten)
    await type('<b>arbeidsmarkt</b>')
    expect(cardTitles()).toEqual([])
    expect(container.textContent).toContain("Geen rapporten gevonden voor '<b>arbeidsmarkt</b>'")
    expect(container.querySelector('.wb-gallery-page b')).toBeNull()
    expect(subtitle()).toBe('0 van 3 rapporten')

    await act(async () => { buttonNamed('Wis zoekopdracht').click() })
    expect(searchInput().value).toBe('')
    expect(cardTitles()).toHaveLength(3)
    expect(container.textContent).not.toContain('Geen rapporten gevonden')
    expect(document.activeElement).toBe(searchInput())
  })

  it('opens a report found by the search', async () => {
    await renderWith(rapporten)
    await type('uitval')
    await act(async () => { container.querySelector('.wb-card').click() })
    expect(container.querySelector('[data-testid="viewer"]')?.textContent).toBe('Uitval mbo')
    expect(container.querySelector('[data-testid="location"]').textContent).toBe('?id=wb-2')
  })

  it('deletes a report found by the search and keeps the search applied', async () => {
    await renderWith(rapporten)
    await type('instroom')
    await act(async () => { container.querySelector('[aria-label="Verwijder rapport Instroom hbo"]').click() })
    await act(async () => { container.querySelector('.confirm-destructive').click() })
    expect(deleteWorkbook).toHaveBeenCalledWith('wb-1')
    expect(searchInput().value).toBe('instroom')
    expect(cardTitles()).toEqual(['Instroom Economië'])
    expect(subtitle()).toBe('1 van 2 rapporten')
  })
})
