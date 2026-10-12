// @vitest-environment jsdom
// #486: een rapport van vóór de eigen Plotly noemt nog cdn.plot.ly; de viewer herschrijft dat bij het tonen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import WorkbookViewer from '../components/WorkbookViewer'
import { PLOTLY_URL } from '../plotlyBron'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('report viewer and Plotly (#486)', () => {
  it('toont een oud rapport met de Plotly van de eigen server in plaats van de CDN', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const oud = '<head><script src="https://cdn.plot.ly/plotly-4.1.0.min.js"></script></head><p>rapport</p>'
    await act(async () => {
      root.render(createElement(WorkbookViewer, {
        workbook: { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: oud },
        onBack: vi.fn(), onUpdate: vi.fn(),
      }))
    })
    const srcdoc = container.querySelector('iframe.wb-iframe').getAttribute('srcdoc')
    expect(srcdoc).not.toContain('cdn.plot.ly')
    expect(srcdoc).toContain(`<script src="${PLOTLY_URL}"></script>`)
    expect(srcdoc).toContain('<p>rapport</p>')
  })
})
