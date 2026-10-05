// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

const server = vi.hoisted(() => ({ resolve: null }))
vi.mock('../workbooks', () => ({
  getWorkbooks: () => [],
  getWorkbookType: (wb) => wb.type,
  deleteWorkbook: vi.fn(),
  migrateLocalWorkbooks: () => Promise.resolve(),
  loadWorkbooksFromServer: () => new Promise(r => { server.resolve = r }),
}))
vi.mock('../components/WorkbookViewer', () => ({
  default: ({ workbook }) => createElement('div', { 'data-testid': 'viewer' }, workbook.title),
}))
vi.mock('../components/WorkbookPreviews', () => ({ default: () => null }))

import RapportenPage from '../pages/RapportenPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(url = '/rapporten') {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [url] }, createElement(RapportenPage, { settings: {} })))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
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
