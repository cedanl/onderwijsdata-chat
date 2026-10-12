// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// Dashboards pull in Plotly, which jsdom cannot load: a stand-in with the two repeat buttons.
vi.mock('../components/GeneratedDashboard', async () => {
  const { createElement: h } = await import('react')
  return {
    default: ({ onRefresh }) => h('div', null,
      h('button', { type: 'button', onClick: () => onRefresh('ververs') }, 'Ververs'),
      h('button', { type: 'button', onClick: () => onRefresh('reproduceer') }, 'Reproduceer'),
    ),
  }
})
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))
vi.mock('../api', () => ({ refreshDashboard: vi.fn(), fetchFeedbackGiven: vi.fn().mockResolvedValue([]) }))
vi.mock('../workbooks', () => ({
  updateWorkbook: vi.fn(),
  BUILTIN_MIJN_INSTELLING: { id: 'builtin-1' }, BUILTIN_ARBEIDSMARKT: { id: 'builtin-2' }, BUILTIN_NATIONAAL: { id: 'builtin-3' },
}))

import { refreshDashboard } from '../api'
import { updateWorkbook } from '../workbooks'
import WorkbookViewer from '../components/WorkbookViewer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const SPEC = {
  figures_json: ['{"data":[]}'],
  recipe: [{ name: 'get_cbs_data', arguments: '{"dataset_id":"85423NED"}' }],
  figure_recipes: [{ query: { data_key: 'cbs:85423NED' }, plot: { chart_type: 'bar' } }],
}
const WORKBOOK = { id: 'wb-1', type: 'dashboard', title: 'Instroom', dashboardSpec: SPEC }

let root
let container
let onUpdate

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(WorkbookViewer, { workbook: WORKBOOK, instelling: 'HU', onBack: vi.fn(), onUpdate }))
  })
}

const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent === tekst)

beforeEach(() => {
  onUpdate = vi.fn()
  refreshDashboard.mockReset()
  updateWorkbook.mockReset()
})

afterEach(() => {
  if (!root) return
  act(() => root.unmount())
  container.remove()
  root = null
})

// #524: ververs bewaart de verse data; reproduceer toont alleen wat afwijkt en bewaart niets.
describe('WorkbookViewer repeat modes', () => {
  it('ververs calls the API in ververs mode and saves the fresh spec', async () => {
    const fresh = { ...SPEC, figures_json: ['{"data":[1]}'] }
    const saved = { ...WORKBOOK, dashboardSpec: fresh }
    refreshDashboard.mockResolvedValue({ spec: fresh, mode: 'ververs', melding: 'Data ververst; geen wijzigingen.', veranderingen: [] })
    updateWorkbook.mockResolvedValue(saved)
    await mount()

    await act(async () => knop('Ververs').click())

    expect(refreshDashboard).toHaveBeenCalledWith(SPEC, { instelling: 'HU' }, 'ververs')
    expect(updateWorkbook).toHaveBeenCalledWith(WORKBOOK, { dashboardSpec: fresh })
    expect(onUpdate).toHaveBeenCalledWith(saved)
    expect(container.querySelector('[role="status"]').textContent).toContain('Data ververst; geen wijzigingen.')
  })

  it('reproduceer calls the API in reproduceer mode, shows the deviations and saves nothing', async () => {
    refreshDashboard.mockResolvedValue({
      spec: { ...SPEC, figures_json: ['{"data":[2]}'] },
      mode: 'reproduceer',
      melding: 'De reproductie uit de opgeslagen data wijkt af van het bewaarde dashboard; het bewaarde dashboard is niet aangepast.',
      veranderingen: ["'Instroom', 2024: 475.460 → 478.660"],
    })
    await mount()

    await act(async () => knop('Reproduceer').click())

    expect(refreshDashboard).toHaveBeenCalledWith(SPEC, { instelling: 'HU' }, 'reproduceer')
    expect(updateWorkbook).not.toHaveBeenCalled()
    expect(onUpdate).not.toHaveBeenCalled()
    const status = container.querySelector('[role="status"]')
    expect(status.textContent).toContain('wijkt af van het bewaarde dashboard')
    expect([...status.querySelectorAll('li')].map(li => li.textContent)).toEqual(["'Instroom', 2024: 475.460 → 478.660"])
  })

  it('shows an API error as an alert and saves nothing', async () => {
    refreshDashboard.mockRejectedValue(new Error('De data kon niet opnieuw opgehaald worden: 1 van de 2 dataset(s) niet geladen.'))
    await mount()

    await act(async () => knop('Ververs').click())

    expect(container.querySelector('[role="alert"]').textContent).toContain('1 van de 2 dataset(s) niet geladen')
    expect(container.querySelector('[role="status"]')).toBeNull()
    expect(updateWorkbook).not.toHaveBeenCalled()
    expect(onUpdate).not.toHaveBeenCalled()
  })
})

describe('refreshDashboard request', () => {
  afterEach(() => vi.unstubAllGlobals())

  it.each(['ververs', 'reproduceer'])('sends mode %s in the request body', async mode => {
    const { refreshDashboard: echteRefresh } = await vi.importActual('../api')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)

    await echteRefresh(SPEC, { instelling: 'HU' }, mode)

    const [path, options] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/dashboard/refresh')
    expect(JSON.parse(options.body)).toMatchObject({ mode, recipe: SPEC.recipe, figure_recipes: SPEC.figure_recipes })
  })
})
