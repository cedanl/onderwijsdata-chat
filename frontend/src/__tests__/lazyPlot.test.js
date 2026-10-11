// @vitest-environment jsdom
// #512: Plotly (1,4 MB gzip) laadt pas bij de eerste figuur; de plaatsvervanger
// houdt de hoogte vast zodat de layout niet springt.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({
  default: (props) => createElement('div', { 'data-testid': 'plot', style: props.style }),
}))

import LazyPlot from '../components/LazyPlot'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

async function toon(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  // Twee act-rondes: één voor de Suspense-fallback, één voor de opgeloste lazy import.
  await act(async () => { root.render(createElement(LazyPlot, props)) })
  await act(async () => {})
}

describe('LazyPlot', () => {
  it('rendert de grafiek zodra de lazy chunk er is', async () => {
    await toon({ data: [], layout: {}, style: { width: '100%', height: 340 } })
    expect(container.querySelector('[data-testid="plot"]')).not.toBeNull()
  })

  it('geeft de stijl met vaste hoogte door aan grafiek én plaatsvervanger', async () => {
    await toon({ data: [], style: { width: '100%', height: 480 } })
    const plot = container.querySelector('[data-testid="plot"]')
    expect(plot.style.height).toBe('480px')
  })
})
