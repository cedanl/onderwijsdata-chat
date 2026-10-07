// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
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
