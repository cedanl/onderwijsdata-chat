// @vitest-environment jsdom
// #480: a token the server no longer accepts (expired or tampered) ends the session in one
// place: token and user cache gone, login screen shown. Only an explicit 401 counts.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { endSession, onSessionEnded, fetchUserInfo, refreshAuthToken, checkSession } from '../auth'
import { fetchWorkbooks, downloadDataCsv } from '../api'
import { useChat } from '../hooks/useChat'
import useDashboardChat from '../hooks/useDashboardChat'
import App from '../App'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const USERINFO = 'userInfo'
const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let ended
let unsubscribe

beforeEach(() => {
  localStorage.clear()
  ended = vi.fn()
  unsubscribe = onSessionEnded(ended)
})

afterEach(() => {
  unsubscribe()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function logIn(token = 'tok') {
  localStorage.setItem(STORAGE_TOKEN, token)
  localStorage.setItem(USERINFO, JSON.stringify({ name: 'Anna' }))
}

const loggedOut = () => localStorage.getItem(STORAGE_TOKEN) === null && localStorage.getItem(USERINFO) === null

describe('endSession', () => {
  it('clears token and user info and tells each subscriber once', () => {
    logIn()
    endSession()
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('no longer calls a subscriber that unsubscribed', () => {
    unsubscribe()
    endSession()
    expect(ended).not.toHaveBeenCalled()
  })
})

describe('fetchUserInfo', () => {
  beforeEach(() => {
    logIn()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  it('ends the session on 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    expect(await fetchUserInfo('tok')).toBeNull()
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['404 (no OIDC endpoint)', async () => response(404)],
    ['500', async () => response(500)],
    ['a network error', async () => { throw new TypeError('Failed to fetch') }],
  ])('keeps the token on %s', async (_, answer) => {
    vi.stubGlobal('fetch', vi.fn(answer))
    expect(await fetchUserInfo('tok')).toBeNull()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    expect(ended).not.toHaveBeenCalled()
  })

  it('leaves a newer session alone when an old token gets a 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    await fetchUserInfo('old')
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    expect(ended).not.toHaveBeenCalled()
  })
})

describe('refreshAuthToken', () => {
  beforeEach(() => {
    logIn()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  it('ends the session on 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    expect(await refreshAuthToken('tok')).toBeNull()
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it.each([404, 500])('keeps the token on %i', async (status) => {
    vi.stubGlobal('fetch', vi.fn(async () => response(status)))
    expect(await refreshAuthToken('tok')).toBeNull()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    expect(ended).not.toHaveBeenCalled()
  })
})

describe('checkSession', () => {
  it('asks the server with the stored token and ends the session on 401', async () => {
    logIn()
    const fetch = vi.fn(async () => response(401))
    vi.stubGlobal('fetch', fetch)
    await checkSession()
    expect(fetch).toHaveBeenCalledWith('/api/auth/user', { headers: { Authorization: 'Bearer tok' } })
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['200', async () => response(200, { name: 'Anna' })],
    ['404', async () => response(404)],
    ['503', async () => response(503)],
    ['a network error', async () => { throw new TypeError('Failed to fetch') }],
  ])('ignores %s', async (_, answer) => {
    logIn()
    vi.stubGlobal('fetch', vi.fn(answer))
    await checkSession()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    expect(ended).not.toHaveBeenCalled()
  })

  it('does not ask without a token', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await checkSession()
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('api 401', () => {
  it('ends the session for a protected call made with a token, and still throws', async () => {
    logIn()
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    await expect(fetchWorkbooks()).rejects.toMatchObject({ message: 'Unauthorized', status: 401 })
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('also ends it for the CSV download', async () => {
    logIn()
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    await expect(downloadDataCsv('k')).rejects.toMatchObject({ status: 401 })
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('has nothing to end without a token', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    await expect(fetchWorkbooks()).rejects.toMatchObject({ status: 401 })
    expect(ended).not.toHaveBeenCalled()
  })

  it('ends it once when parallel calls all get a 401', async () => {
    logIn()
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    await Promise.allSettled([fetchWorkbooks(), fetchWorkbooks(), fetchWorkbooks()])
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it.each([403, 404, 500])('keeps the session on %i', async (status) => {
    logIn()
    vi.stubGlobal('fetch', vi.fn(async () => response(status)))
    await expect(fetchWorkbooks()).rejects.toThrow()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    expect(ended).not.toHaveBeenCalled()
  })
})

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    FakeWebSocket.last = this
  }
  send() {}
  close() {}
}

describe.each([
  ['useChat', () => useChat()],
  ['useDashboardChat', () => useDashboardChat()],
])('%s socket refused', (_, useHook) => {
  let root
  let fetch

  function Harness() {
    useHook()
    return null
  }

  beforeEach(async () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    fetch = vi.fn(async () => response(401))
    vi.stubGlobal('fetch', fetch)
    logIn()
    root = createRoot(document.createElement('div'))
    await act(async () => { root.render(createElement(Harness)) })
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
  })

  const close = (ws, code) => act(async () => { ws.onclose({ code }) })

  it('asks the server when the socket closes without ever opening', async () => {
    await close(FakeWebSocket.last, 1006)
    expect(fetch).toHaveBeenCalledWith('/api/auth/user', { headers: { Authorization: 'Bearer tok' } })
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('keeps the token and retries when the probe is no 401', async () => {
    fetch.mockImplementation(async () => { throw new TypeError('Failed to fetch') })
    const ws = FakeWebSocket.last
    await close(ws, 1006)
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
    await act(async () => { vi.advanceTimersByTime(1000) })
    expect(FakeWebSocket.last).not.toBe(ws)
  })

  it('does not ask when an open connection drops', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { ws.onopen() })
    await close(ws, 1006)
    expect(fetch).not.toHaveBeenCalled()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBe('tok')
  })
})

describe('useChat close code 4001', () => {
  it('ends the session without asking the server', async () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    logIn()
    function Harness() {
      useChat()
      return null
    }
    const root = createRoot(document.createElement('div'))
    await act(async () => { root.render(createElement(Harness)) })
    await act(async () => { FakeWebSocket.last.onclose({ code: 4001 }) })
    expect(loggedOut()).toBe(true)
    expect(ended).toHaveBeenCalledTimes(1)
    expect(fetch).not.toHaveBeenCalled()
    act(() => root.unmount())
  })
})

describe('App', () => {
  let root
  let container

  function serve({ required, user }) {
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (url === '/api/auth/status') return response(200, { required, oidc_enabled: false })
      if (url === '/api/auth/user') return user
      if (url === '/api/instellingen') return response(200, [])
      return response(200, {})
    }))
  }

  async function render() {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(App)) })
  }

  beforeEach(() => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    window.matchMedia = q => ({ matches: false, media: q })
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    delete window.matchMedia
  })

  const loginForm = () => container.querySelector('#login-username')

  it('shows the login page when the stored token is refused', async () => {
    logIn('tampered')
    serve({ required: true, user: response(401) })
    await render()
    expect(loginForm()).not.toBeNull()
    expect(container.querySelector('nav')).toBeNull()
    expect(container.textContent).not.toContain('Uitloggen')
    expect(loggedOut()).toBe(true)
  })

  it('keeps the stored-user fallback when the user endpoint does not exist', async () => {
    logIn()
    serve({ required: true, user: response(404) })
    await render()
    expect(loginForm()).toBeNull()
    expect(container.textContent).toContain('Anna')
    expect(container.textContent).toContain('Uitloggen')
  })

  it('goes to the login page when the session ends while using the app', async () => {
    logIn()
    serve({ required: true, user: response(200, { name: 'Anna' }) })
    await render()
    expect(container.textContent).toContain('Anna')
    await act(async () => { endSession() })
    expect(loginForm()).not.toBeNull()
    expect(container.textContent).not.toContain('Anna')
  })

  it('shows the guest without login when no login is required', async () => {
    serve({ required: false })
    await render()
    expect(loginForm()).toBeNull()
    expect(container.textContent).toContain('gast')
    expect(ended).not.toHaveBeenCalled()
  })
})
