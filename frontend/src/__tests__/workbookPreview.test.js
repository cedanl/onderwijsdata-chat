// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
const api = vi.hoisted(() => ({ fetchWorkbook: vi.fn() }))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
import WorkbookPreview from '../components/WorkbookPreviews'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.ResizeObserver ??= class { observe() {} disconnect() {} }

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #427: every report thumbnail loaded and drew Plotly; in a long gallery some stayed blank.
describe('report thumbnail', () => {
  it('shows the static top of the report without running its scripts', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const wb = { id: 'wb-1', title: 'Instroom hbo', htmlContent: '<h1>Instroom hbo</h1><script>Plotly.newPlot()</script>' }
    await act(async () => { root.render(createElement(WorkbookPreview, { wb })) })
    const frame = container.querySelector('iframe')
    expect(frame.getAttribute('sandbox')).toBe('')
    expect(frame.getAttribute('loading')).toBe('lazy')
  })
})

// #633: `loading="lazy"` does nothing for a srcdoc frame; 81 report frames at once crashed the tab.
describe('report thumbnail in a long gallery', () => {
  let zichtbaar
  afterEach(() => { delete globalThis.IntersectionObserver })

  function nabootsen() {
    zichtbaar = null
    globalThis.IntersectionObserver = class {
      constructor(cb) { this.cb = cb }
      observe() { zichtbaar = inBeeld => this.cb([{ isIntersecting: inBeeld }]) }
      disconnect() {}
    }
  }

  async function toon(wb) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(WorkbookPreview, { wb })) })
  }

  it('holds no frame and fetches nothing while the card is off screen', async () => {
    nabootsen()
    await toon({ id: 'r1', title: 'R', type: 'report', samenvatting: true })
    expect(container.querySelector('iframe')).toBeNull()
    expect(container.querySelector('.wb-preview-shimmer')).not.toBeNull()
    expect(api.fetchWorkbook).not.toHaveBeenCalled()
  })

  it('fetches the report when the card comes into view, and drops the frame when it leaves', async () => {
    nabootsen()
    api.fetchWorkbook.mockResolvedValue({ id: 'r2', html_content: '<h1>Rapport</h1>' })
    await toon({ id: 'r2', title: 'R', type: 'report', samenvatting: true })
    await act(async () => { zichtbaar(true) })
    expect(api.fetchWorkbook).toHaveBeenCalledWith('r2')
    expect(container.querySelector('iframe').getAttribute('srcdoc')).toBe('<h1>Rapport</h1>')
    await act(async () => { zichtbaar(false) })
    expect(container.querySelector('iframe')).toBeNull()
  })

  it('does not fetch a dashboard: its card shows no report', async () => {
    nabootsen()
    await toon({ id: 'd1', title: 'D', type: 'dashboard', samenvatting: true })
    expect(api.fetchWorkbook).not.toHaveBeenCalled()
    expect(container.querySelector('iframe')).toBeNull()
  })
})
