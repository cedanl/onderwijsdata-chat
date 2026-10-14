// @vitest-environment jsdom
// #541: a report frame that does not load or shows nothing left only the title bar. Outside the frame the viewer
// now asks "Zie je dit rapport niet?" with the download, but only when the frame says it is empty or stays silent.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import WorkbookViewer from '../components/WorkbookViewer'
import { FRAME_BRON, FRAME_TIMEOUT_MS } from '../reportFrame'
import { PLOTLY_URL } from '../plotlyBron'
import { BUILTIN_ARBEIDSMARKT } from '../workbooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const MELDING = 'Zie je dit rapport niet? Download het als HTML.'
const RAPPORT = { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<html><body><p>rapport</p></body></html>' }

let root
let container
let releaseFrameLoad

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  releaseFrameLoad?.()
  releaseFrameLoad = null
  vi.useRealTimers()
})

// jsdom fires the frame's load event on insertion (and never runs a srcdoc); a real browser waits for the
// report. Hold that event back so the frame stays silent until the test speaks for it.
function holdFrameLoad() {
  const hold = e => { if (e.target.tagName === 'IFRAME') e.stopPropagation() }
  document.addEventListener('load', hold, true)
  releaseFrameLoad = () => document.removeEventListener('load', hold, true)
}

async function render(workbook, props = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(WorkbookViewer, { workbook, onBack: vi.fn(), onUpdate: vi.fn(), ...props }))
  })
}

const frame = () => container.querySelector('iframe.wb-iframe')
const region = () => container.querySelector('.wb-viewer-content')
const fallback = () => container.querySelector('.wb-viewer-fallback-status')
const isBusy = () => (region().getAttribute('aria-busy') ?? 'false') === 'true'

async function frameSays(data, source = frame().contentWindow) {
  await act(async () => { window.dispatchEvent(new MessageEvent('message', { data, source })) })
}

describe('report frame fallback (#541)', () => {
  it('asks outside the frame when the frame says it shows nothing', async () => {
    holdFrameLoad()
    await render(RAPPORT)
    expect(isBusy()).toBe(true)
    await frameSays({ bron: FRAME_BRON, zichtbaar: false })
    const status = fallback()
    expect(status.getAttribute('role')).toBe('status')
    expect(status.textContent).toBe(MELDING)
    expect(frame().contains(status) || region().contains(status)).toBe(false)
    expect(container.querySelector('.wb-viewer-loading')).toBeNull()
    expect(isBusy()).toBe(false)
  })

  it('asks after FRAME_TIMEOUT_MS without a word from the frame, not before', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    holdFrameLoad()
    await render(RAPPORT)
    await act(async () => { vi.advanceTimersByTime(FRAME_TIMEOUT_MS - 1) })
    expect(fallback().textContent).toBe('')
    expect(isBusy()).toBe(true)
    await act(async () => { vi.advanceTimersByTime(1) })
    expect(fallback().textContent).toBe(MELDING)
    expect(container.querySelector('.wb-viewer-loading')).toBeNull()
    expect(isBusy()).toBe(false)
  })

  it('stays empty when the frame shows something, and a late word clears the notice again', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    holdFrameLoad()
    await render(RAPPORT)
    // The live region is there before it has anything to say.
    expect(fallback().getAttribute('role')).toBe('status')
    expect(fallback().textContent).toBe('')
    await act(async () => { vi.advanceTimersByTime(FRAME_TIMEOUT_MS) })
    expect(fallback().textContent).toBe(MELDING)
    await frameSays({ bron: FRAME_BRON, zichtbaar: true })
    expect(fallback().textContent).toBe('')
    expect(container.querySelector('.wb-viewer-loading')).toBeNull()
    expect(isBusy()).toBe(false)
  })

  it('stays empty and stops the spinner when the frame reports content', async () => {
    holdFrameLoad()
    await render(RAPPORT)
    await frameSays({ bron: FRAME_BRON, zichtbaar: true })
    expect(fallback().textContent).toBe('')
    expect(container.querySelector('.wb-viewer-loading')).toBeNull()
    expect(isBusy()).toBe(false)
  })

  it.each([
    ['another source', { bron: FRAME_BRON, zichtbaar: false }, () => window],
    ['another bron', { bron: 'iets-anders', zichtbaar: false }, undefined],
    ['a non-boolean zichtbaar', { bron: FRAME_BRON, zichtbaar: 'false' }, undefined],
  ])('ignores a message with %s', async (_, data, source) => {
    holdFrameLoad()
    await render(RAPPORT)
    await frameSays(data, source?.())
    expect(fallback().textContent).toBe('')
    expect(container.querySelector('.wb-viewer-loading')).not.toBeNull()
    expect(isBusy()).toBe(true)
  })

  it('starts over for another report', async () => {
    holdFrameLoad()
    await render(RAPPORT)
    await frameSays({ bron: FRAME_BRON, zichtbaar: false })
    expect(fallback().textContent).toBe(MELDING)
    const ander = { ...RAPPORT, id: 'wb-2', htmlContent: '<html><body><p>ander rapport</p></body></html>' }
    await act(async () => {
      root.render(createElement(WorkbookViewer, { workbook: ander, onBack: vi.fn(), onUpdate: vi.fn() }))
    })
    expect(fallback().textContent).toBe('')
    expect(isBusy()).toBe(true)
  })
})

describe('the download in the notice (#541)', () => {
  async function renderWithNotice(workbook, save) {
    holdFrameLoad()
    await render(workbook, { save })
    await frameSays({ bron: FRAME_BRON, zichtbaar: false })
    return fallback().querySelector('button')
  }

  it('is a keyboard-reachable button named "Download het als HTML"', async () => {
    const knop = await renderWithNotice(RAPPORT, vi.fn())
    expect(knop.tagName).toBe('BUTTON')
    expect(knop.getAttribute('type')).toBe('button')
    expect(knop.textContent).toBe('Download het als HTML')
    expect(knop.tabIndex).toBe(0)
    expect(knop.disabled).toBe(false)
  })

  it('saves the same file as the bar button: the report without the probe', async () => {
    const save = vi.fn()
    const knop = await renderWithNotice(RAPPORT, save)
    await act(async () => knop.click())
    await act(async () => container.querySelector('.wb-download-btn').click())
    expect(save).toHaveBeenCalledTimes(2)
    const [[blob, naam], [blobBalk, naamBalk]] = save.mock.calls
    expect(naam).toBe('Instroom_hbo.html')
    expect(naamBalk).toBe(naam)
    expect(blob.type).toBe('text/html;charset=utf-8')
    const tekst = await blob.text()
    expect(tekst).toBe(RAPPORT.htmlContent)
    expect(tekst).not.toContain(FRAME_BRON)
    expect(await blobBalk.text()).toBe(tekst)
  })

  it('says so when the download fails', async () => {
    const save = vi.fn(() => { throw new Error('Opslaan mislukt') })
    const knop = await renderWithNotice(RAPPORT, save)
    await act(async () => knop.click())
    const alert = container.querySelector('.wb-viewer-fallback-error')
    expect(alert.getAttribute('role')).toBe('alert')
    expect(alert.textContent).toBe('Opslaan mislukt')
    expect(fallback().contains(alert)).toBe(false)
  })
})

describe('the report frame itself (#541)', () => {
  it('keeps the sandbox and carries the probe once, next to one Plotly script of our own', async () => {
    const oud = '<head><script src="https://cdn.plot.ly/plotly-4.1.0.min.js"></script></head><p>rapport</p>'
    await render({ ...RAPPORT, htmlContent: oud })
    expect(frame().getAttribute('sandbox')).toBe('allow-scripts')
    const srcdoc = frame().getAttribute('srcdoc')
    expect(srcdoc.split(FRAME_BRON)).toHaveLength(2)
    expect(srcdoc.split(PLOTLY_URL)).toHaveLength(2)
    expect(srcdoc).not.toContain('cdn.plot.ly')
  })
})

describe('no notice where there is no report frame (#541)', () => {
  it.each([[''], [undefined], ['   ']])('keeps "Dit rapport heeft geen inhoud." for htmlContent %j', async htmlContent => {
    await render({ ...RAPPORT, htmlContent })
    expect(region().textContent).toContain('Dit rapport heeft geen inhoud.')
    expect(frame()).toBeNull()
    expect(fallback()).toBeNull()
  })

  it.each([
    ['a built-in dashboard', BUILTIN_ARBEIDSMARKT],
    ['a generated dashboard', { id: 'db-1', title: 'Dashboard', dashboardSpec: { kpis: [] }, htmlContent: '<p>x</p>' }],
  ])('renders no fallback region for %s', async (_, workbook) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await render(workbook)
    await act(async () => { vi.advanceTimersByTime(FRAME_TIMEOUT_MS) })
    expect(fallback()).toBeNull()
    expect(container.querySelector('.wb-viewer-fallback')).toBeNull()
  })
})
