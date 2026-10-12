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

// De lazy import wordt per module-instantie onthouden; voor een hangende of mislukte
// chunk laadt elke test daarom React en LazyPlot opnieuw met een eigen mock.
async function laadMet(plotlyModule) {
  vi.resetModules()
  vi.doMock('react-plotly.js', plotlyModule)
  const { createElement: maak, act: actie, Component } = await import('react')
  const { createRoot: maakRoot } = await import('react-dom/client')
  const { default: Vers } = await import('../components/LazyPlot')
  const houder = document.createElement('div')
  document.body.appendChild(houder)
  const wortel = maakRoot(houder)
  return {
    houder,
    wortel,
    actie,
    toon: async (props, ouder = Vers) => {
      await actie(async () => { wortel.render(maak(ouder, props)) })
    },
    maak,
    Component,
    LazyPlot: Vers,
  }
}

describe('LazyPlot plaatsvervanger en fout', () => {
  let pagina

  afterEach(async () => {
    if (pagina) await pagina.actie(async () => pagina.wortel.unmount())
    pagina?.houder.remove()
    pagina = null
    vi.doUnmock('react-plotly.js')
    vi.restoreAllMocks()
  })

  it('toont zolang Plotly laadt een melding voor hulptechnologie en houdt de hoogte vast', async () => {
    pagina = await laadMet(() => new Promise(() => {}))
    await pagina.toon({ style: { width: '100%', height: 480 } })
    const status = pagina.houder.querySelector('[role="status"]')
    expect(status.textContent).toBe('Grafiek wordt geladen…')
    expect(status.getAttribute('aria-busy')).toBe('true')
    expect(status.style.minHeight).toBe('480px')
  })

  it('geeft de plaatsvervanger een minimumhoogte als de aanroeper alleen een breedte meegeeft', async () => {
    pagina = await laadMet(() => new Promise(() => {}))
    await pagina.toon({ style: { width: '100%' } })
    expect(pagina.houder.querySelector('[role="status"]').style.minHeight).toBe('340px')
  })

  it('toont een korte melding als de chunk niet te laden is, zonder de ouder te laten crashen', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    pagina = await laadMet(() => { throw new Error('Failed to fetch dynamically imported module') })
    const { maak, Component, LazyPlot } = pagina
    const ouderGevangen = vi.fn()
    class Ouder extends Component {
      static getDerivedStateFromError() { return {} }
      componentDidCatch(...args) { ouderGevangen(...args) }
      render() { return maak('section', { 'data-testid': 'ouder' }, maak(LazyPlot, { style: { width: '100%', height: 340 } }), maak('p', null, 'rest van de pagina')) }
    }
    await pagina.toon({}, Ouder)

    const melding = pagina.houder.querySelector('[role="alert"]')
    expect(melding.textContent).toBe('De grafiek kon niet worden geladen; vernieuw de pagina.')
    expect(pagina.houder.textContent).toContain('rest van de pagina')
    expect(ouderGevangen).not.toHaveBeenCalled()
  })
})

