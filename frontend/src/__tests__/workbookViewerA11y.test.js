// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// Dashboards pull in Plotly, which jsdom cannot load.
vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import WorkbookViewer from '../components/WorkbookViewer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('report viewer accessibility', () => {
  it('has the report title as h1 and a keyboard-scrollable content region', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root.render(createElement(WorkbookViewer, {
        workbook: { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<p>rapport</p>' },
        onBack: vi.fn(), onUpdate: vi.fn(),
      }))
    })
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(container.querySelector('h1').textContent).toContain('Instroom hbo')
    const region = container.querySelector('.wb-viewer-content')
    expect(region.getAttribute('role')).toBe('region')
    expect(region.getAttribute('aria-label')).toBe('Rapportinhoud')
    expect(region.tabIndex).toBe(0)
  })
})
