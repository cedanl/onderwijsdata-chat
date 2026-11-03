// @vitest-environment jsdom
// #498: logout, a fresh login, the SRAM landing and a session the server ended remove the
// dashboard chat from this browser, so the next user of a shared device does not see it. The dashboard builder is
// gone (#765), but a browser that used it still holds its chat: that goes too.
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { endSession } from '../auth'
import { STORAGE_TOKEN, STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// Each App test renders the whole app; on a busy machine that nears the 5 s default.
const APP_TEST = { timeout: 20000 }

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container

function serve({ oidc = true } = {}) {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: oidc })
    if (url === '/api/auth/user') return response(200, { name: 'Anna' })
    if (url === '/api/auth/login') return response(200, { token: 'nieuw', user: 'bert' })
    if (url === '/api/config') return response(200, { dashboards_enabled: true })
    if (url === '/api/instellingen') return response(200, [])
    if (url.startsWith('/api/workbooks')) return response(200, [])
    return response(200, {})
  }))
}

async function render(path = '/') {
  window.history.replaceState({}, '', path)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

// Lazy routes load asynchronously; the first import of a page takes a while.
async function waitFor(check) {
  for (let i = 0; i < 300 && !check(); i++) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
  }
  expect(check()).toBeTruthy()
}

const button = label => [...container.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(label))

async function click(label) {
  await act(async () => { button(label).click() })
}

function type(selector, value) {
  const input = container.querySelector(selector)
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function seedDashboardChat() {
  localStorage.setItem(STORAGE_DC_MESSAGES, JSON.stringify([{ id: 1, role: 'user', content: 'vorige gebruiker', done: true }]))
  localStorage.setItem(STORAGE_DC_FIGURES, JSON.stringify([{ data: [], layout: {} }]))
}

const dcKeys = () =>
  Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).filter(key => key.startsWith('edudata_dc_'))

// Logged in on /dashboards, with the chat of the old dashboard builder still in this browser.
async function openDashboards() {
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  seedDashboardChat()
  serve()
  await render('/dashboards')
  await waitFor(() => container.querySelector('.wb-gallery-title'))
  expect(dcKeys()).not.toEqual([])
}

// Load the lazy dashboard page once up front, so the first test does not pay for it.
beforeAll(async () => { await import('../pages/DashboardPage') }, APP_TEST.timeout)

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  Element.prototype.scrollIntoView = () => {}
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  delete Element.prototype.scrollIntoView
  window.history.replaceState({}, '', '/')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App wipes the dashboard chat', APP_TEST, () => {
  it('on logout', async () => {
    await openDashboards()

    await click('Uitloggen')

    expect(container.querySelector('#login-username')).not.toBeNull()
    expect(dcKeys()).toEqual([])
  })

  it('on the SRAM landing', async () => {
    seedDashboardChat()
    serve()
    await render('/#token=nieuw')
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('nieuw')
    expect(dcKeys()).toEqual([])
  })

  it('on a login with the password form', async () => {
    seedDashboardChat()
    serve({ oidc: false })
    await render('/')
    expect(dcKeys()).not.toEqual([])

    await act(async () => {
      type('#login-username', 'bert')
      type('#login-password', 'geheim')
    })
    await act(async () => { container.querySelector('form').requestSubmit() })

    await waitFor(() => button('Uitloggen'))
    expect(dcKeys()).toEqual([])
  })
})

describe('App wipes the dashboard chat when the server ends the session', APP_TEST, () => {
  it('on /dashboards', async () => {
    await openDashboards()

    await act(async () => { endSession() })

    expect(container.querySelector('#login-username')).not.toBeNull()
    expect(dcKeys()).toEqual([])
  })
})
