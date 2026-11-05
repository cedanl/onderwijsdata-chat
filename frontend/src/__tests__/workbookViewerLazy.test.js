// @vitest-environment jsdom
// #907: de rapportenroute laadde de dashboards (Chart.js en alle dashboardcode) mee, omdat WorkbookViewer ze statisch
// importeerde. Een rapport openen laadt ze niet; een vast dashboard laadt ze pas als het opent.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const geladen = vi.hoisted(() => ({ dashboards: false }))
vi.mock('../components/dashboards', async () => {
  const { createElement: maak } = await import('react')
  geladen.dashboards = true
  const stub = naam => function Stub({ instelling }) { return maak('p', { 'data-dashboard': naam }, instelling) }
  return {
    InlineDashboardMijnInstelling: stub('mijn-instelling'),
    InlineDashboardArbeidsmarkt: stub('arbeidsmarkt'),
    InlineDashboardNationaal: stub('nationaal'),
  }
})

import WorkbookViewer from '../components/WorkbookViewer'
import { BUILTIN_NATIONAAL } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(workbook) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(WorkbookViewer, { workbook, instelling: 'Hogeschool Utrecht', onBack: vi.fn(), onUpdate: vi.fn() }))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('WorkbookViewer laadt de dashboards lazy (#907)', () => {
  it('laadt de dashboardcode niet voor een rapport', async () => {
    await render({ id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<p>rapport</p>' })
    expect(container.querySelector('h1').textContent).toContain('Instroom hbo')
    expect(geladen.dashboards).toBe(false)
  })

  it('laadt en toont een vast dashboard als het opent', async () => {
    await render(BUILTIN_NATIONAAL)
    await act(async () => { await vi.dynamicImportSettled() })
    expect(geladen.dashboards).toBe(true)
    const dashboard = container.querySelector('[data-dashboard="nationaal"]')
    expect(dashboard?.textContent).toBe('Hogeschool Utrecht')
  })
})
