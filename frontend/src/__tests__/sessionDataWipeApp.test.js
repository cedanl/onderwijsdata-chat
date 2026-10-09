// @vitest-environment jsdom
// #498: logout, a fresh login, the SRAM landing and a session the server ended remove the
// dashboard chat from this browser, so the next user of a shared device does not see it.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const auth = await import('../auth')

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    FakeWebSocket.last = this
  }
  send() {}
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container

function serve({ oidc = true } = {}) {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: oidc })
    if (url === '/api/auth/user') return response(200, { name: 'Anna' })
    if (url === '/api/auth/login') return response(200, { token: 'nieuw', user: 'bert' })
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

// Logged in, with the dashboard chat open on /dashboards.
async function openDashboardChat() {
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  seedDashboardChat()
  serve()
  await render('/dashboards')
  await waitFor(() => button('Nieuw dashboard'))
  await click('Nieuw dashboard')
  await waitFor(() => container.querySelector('.dc-textarea') && FakeWebSocket.last)
  expect(dcKeys()).not.toEqual([])
}

beforeEach(() => {
  localStorage.clear()
  FakeWebSocket.last = null
  vi.stubGlobal('WebSocket', FakeWebSocket)
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

describe('App wipes the dashboard chat', () => {
  it('on logout while the dashboard chat is open, also when its socket delivers late', async () => {
    await openDashboardChat()
    const ws = FakeWebSocket.last

    await click('Uitloggen')
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end' })
      ws.onclose({ code: 1000 })
    })

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

// endSession arrives with !384 (#480); until then this case is skipped.
describe('App wipes the dashboard chat when the server ends the session', () => {
  it.skipIf(!auth.endSession)('while the dashboard chat is open', async () => {
    await openDashboardChat()

    await act(async () => { auth.endSession() })

    expect(container.querySelector('#login-username')).not.toBeNull()
    expect(dcKeys()).toEqual([])
  })
})
