// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import NotFoundPage from '../pages/NotFoundPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function renderPage(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(MemoryRouter, null, createElement(NotFoundPage, props))) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('NotFoundPage (#223)', () => {
  it('says an unknown path does not exist and links back home', async () => {
    await renderPage({})
    expect(container.querySelector('h1').textContent).toBe('Deze pagina bestaat niet (meer)')
    expect(container.querySelector('a').getAttribute('href')).toBe('/')
  })

  it('says a switched-off page is not available yet, not that it does not exist', async () => {
    await renderPage({ unavailable: true })
    expect(container.querySelector('h1').textContent).toBe('Nog niet beschikbaar')
    expect(container.textContent).not.toContain('bestaat niet')
    expect(container.querySelector('a').getAttribute('href')).toBe('/')
  })
})
