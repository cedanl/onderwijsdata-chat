// @vitest-environment jsdom
// #793: de dashboardvlag faalt dicht. Een mislukte of onvolledige /api/config laat dashboards uit, want de server
// houdt de dashboardroutes dan met 403 dicht.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const APP_TEST = { timeout: 20000 }
const NIET_BESCHIKBAAR = 'Nog niet beschikbaar'
let root
let container

const response = (status, body) => ({ ok: status < 400, status, json: async () => body })

function serve(config) {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (url === '/api/config') return config()
    if (url === '/api/auth/status') return response(200, { required: false })
    if (url === '/api/instellingen') return response(200, [])
    if (url.startsWith('/api/workbooks')) return response(200, [])
    return response(200, {})
  }))
}

async function render(path) {
  window.history.replaceState({}, '', path)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
  for (let i = 0; i < 100 && !container.querySelector('.navbar'); i++) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
  }
}

const dashboardLinks = () => container.querySelectorAll('a[href="/dashboards"]')

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
})
afterEach(async () => {
  await act(async () => { root?.unmount() })
  container?.remove()
  delete window.matchMedia
  localStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('dashboardvlag in de frontend (#793)', () => {
  const UIT = {
    'een mislukte /api/config': () => { throw new TypeError('Failed to fetch') },
    'een config zonder het veld': () => response(200, {}),
    'dashboards_enabled: false': () => response(200, { dashboards_enabled: false }),
    'een waarde die geen true is': () => response(200, { dashboards_enabled: 'true' }),
  }

  for (const [naam, config] of Object.entries(UIT)) {
    it(`toont geen dashboardlink en een niet-beschikbaar-pagina bij ${naam}`, APP_TEST, async () => {
      serve(config)
      await render('/')
      expect(dashboardLinks()).toHaveLength(0)

      await act(async () => { root.unmount() })
      container.remove()
      await render('/dashboards')
      expect(container.textContent).toContain(NIET_BESCHIKBAAR)
    })
  }

  it('toont dashboards wel bij dashboards_enabled: true', APP_TEST, async () => {
    serve(() => response(200, { dashboards_enabled: true }))
    await render('/')
    for (let i = 0; i < 100 && !dashboardLinks().length; i++) {
      await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
    }
    expect(dashboardLinks().length).toBeGreaterThan(0)
  })
})
