// @vitest-environment jsdom
// #499: when the session ends (the server refused the token, or the user logged out), the app stops
// the token refresh timer and closes the settings dialog. Driven by the real triggers on the real App.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { endSession } from '../auth'
import { fetchWorkbooks } from '../api'
import { useChat } from '../hooks/useChat'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_USERINFO, STORAGE_ONBOARDED } from '../constants'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
// The app refreshes five minutes before the token expires: 55 minutes into a one-hour token.
const PAST_REFRESH = 56 * MINUTE

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

// Same shape as core.auth.make_token: base64url("<user>|<expiry seconds>"), then a signature.
// Reads the faked clock, so call it after vi.useFakeTimers().
const serverToken = (username, expiresInMs) => {
  const exp = Math.floor((Date.now() + expiresInMs) / 1000)
  return btoa(`${username}|${exp}`).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '') + '.sig'
}
const refreshed = () => response(200, { token: serverToken('anna', HOUR), user: { name: 'Anna' } })

let token
let fetch
let answers
let root
let container
let chatRoot

// Each answer is a function of the call, so a test can switch one after the app has mounted.
function serve() {
  answers = {
    '/api/auth/status': () => response(200, { required: true, oidc_enabled: false }),
    '/api/auth/user': () => response(200, { name: 'Anna' }),
    '/api/auth/refresh': refreshed,
    '/api/instellingen': () => response(200, []),
  }
  fetch = vi.fn(async (url) => (answers[url] ?? (() => response(200, {})))())
  vi.stubGlobal('fetch', fetch)
}

async function render() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

// The chat page's hook in a root of its own, as in sessionEnd.test.js: its socket is the trigger.
async function mountChat() {
  function Chat() {
    useChat()
    return null
  }
  chatRoot = createRoot(document.createElement('div'))
  await act(async () => { chatRoot.render(createElement(Chat)) })
  return FakeWebSocket.last
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q })
  FakeWebSocket.reset()
  vi.stubGlobal('WebSocket', FakeWebSocket)
  token = serverToken('anna', HOUR)
  localStorage.setItem(STORAGE_TOKEN, token)
  localStorage.setItem(STORAGE_USERINFO, JSON.stringify({ name: 'Anna' }))
  serve()
})

afterEach(() => {
  if (chatRoot) act(() => chatRoot.unmount())
  chatRoot = null
  act(() => root.unmount())
  container.remove()
  delete window.matchMedia
  // The refresh timer is module state without unmount cleanup: real timers drop whatever is still armed.
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const advance = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const refreshCalls = () => fetch.mock.calls.filter(([url]) => url === '/api/auth/refresh')
const loggedOut = () => localStorage.getItem(STORAGE_TOKEN) === null && localStorage.getItem(STORAGE_USERINFO) === null
const loginForm = () => container.querySelector('#login-username')
const dialog = () => container.querySelector('[role="dialog"]')
const logoutButton = () => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === 'Uitloggen')

const endedDirectly = ['endSession() is called', () => act(async () => { endSession() })]
const apiRefused = ['a protected API call gets a 401', async () => {
  answers['/api/workbooks'] = () => response(401)
  await act(async () => { await expect(fetchWorkbooks()).rejects.toMatchObject({ status: 401 }) })
}]
const socketRefused = ['the chat socket closes with 4001', async () => {
  const ws = await mountChat()
  await act(async () => { ws.finishClose(4001) })
}]
const handshakeRefused = ['the chat socket closes with 1006 before opening and the server refuses the token', async () => {
  const ws = await mountChat()
  answers['/api/auth/user'] = () => response(401)
  await act(async () => {
    ws.finishClose(1006)
    await vi.advanceTimersByTimeAsync(0)
  })
}]
const loggedOutByUser = ['the user logs out', () => act(async () => { logoutButton().click() })]

describe('token refresh timer', () => {
  // Without this control, a test that sees no refresh after the session ended proves nothing.
  it('refreshes the stored token once, five minutes before it expires, while the session lasts', async () => {
    await render()
    await advance(54 * MINUTE)
    expect(refreshCalls()).toEqual([])
    await advance(PAST_REFRESH - 54 * MINUTE)
    expect(refreshCalls()).toEqual([[
      '/api/auth/refresh',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) },
    ]])
    expect(loginForm()).toBeNull()
  })
})

describe('session end stops the refresh timer', () => {
  it.each([endedDirectly, apiRefused, socketRefused, handshakeRefused, loggedOutByUser])(
    'no refresh follows and the login form shows when %s',
    async (_, end) => {
      await render()
      await end()
      await advance(2 * HOUR)
      expect(refreshCalls()).toEqual([])
      expect(loggedOut()).toBe(true)
      expect(loginForm()).not.toBeNull()
    },
  )
})

describe('session end closes the settings dialog', () => {
  async function openSettings() {
    await act(async () => { container.querySelector('button[title="Instellingen"]').click() })
    expect(dialog()).not.toBeNull()
  }

  // React tracks an input's value itself: set it through the native setter, then fire input.
  function type(input, value) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }

  async function logInAgain() {
    await act(async () => {
      type(container.querySelector('#login-username'), 'anna')
      type(container.querySelector('#login-password'), 'geheim')
    })
    await act(async () => {
      container.querySelector('button[type="submit"]').click()
      await vi.advanceTimersByTimeAsync(0)
    })
  }

  it.each([apiRefused, socketRefused, handshakeRefused])('closes it when %s', async (_, end) => {
    await render()
    await openSettings()
    await end()
    expect(dialog()).toBeNull()
    expect(loginForm()).not.toBeNull()
  })

  // The login page replaces the whole app, so the dialog is gone once the session ends either way;
  // resetSession also closes it in state. That shows on the next login, when another tab has finished
  // onboarding in the meantime (so no Welkom dialog opens): a dialog left open would come back.
  it('does not reopen it after logging in again', async () => {
    await render()
    await openSettings()
    await apiRefused[1]()
    localStorage.setItem(STORAGE_ONBOARDED, '1')
    answers['/api/auth/login'] = () => response(200, { token: serverToken('anna', HOUR), user: 'anna' })
    await logInAgain()
    expect(container.querySelector('nav')).not.toBeNull()
    expect(dialog()).toBeNull()
  })

  it('closes it when the refresh gets a 401 while it is open, and schedules no second refresh', async () => {
    answers['/api/auth/refresh'] = () => response(401)
    await render()
    await openSettings()
    await advance(PAST_REFRESH)
    expect(refreshCalls()).toHaveLength(1)
    expect(dialog()).toBeNull()
    expect(loginForm()).not.toBeNull()
    await advance(2 * HOUR)
    expect(refreshCalls()).toHaveLength(1)
  })
})
