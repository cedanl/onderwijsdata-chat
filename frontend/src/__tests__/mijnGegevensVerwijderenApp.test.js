// @vitest-environment jsdom
// #646 in the whole app: "Verwijder al mijn gegevens" only with a login of one's own, and after it the browser copy
// and the profile are gone and the login page says why, without a logout call (the server already revoked the token).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { GEGEVENS_VERWIJDERD } from '../components/MijnGegevensVerwijderen'
import {
  SESSION_DATA_KEYS, STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_TOKEN, STORAGE_USERINFO, STORAGE_MODEL, STORAGE_RECENT,
} from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// Each App test renders the whole app; on a busy machine that nears the 5 s default.
const APP_TEST = { timeout: 20000 }
const LABEL = 'Verwijder al mijn gegevens'
const ZESMAAL_NUL = { conversations: 0, workbooks: 0, feedback: 0, algemene_feedback: 0, answer_feedback: 0, data_recipes: 0 }

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container
let fetchMock

function serve({ required = true } = {}) {
  fetchMock = vi.fn(async (url, opties = {}) => {
    if (url === '/api/auth/status') return response(200, { required, oidc_enabled: false })
    if (url === '/api/auth/user') return response(200, { name: 'Anna' })
    if (url === '/api/instellingen') return response(200, [])
    if (url === '/api/mijn-gegevens' && opties.method === 'DELETE') return response(200, { ok: true, verwijderd: ZESMAAL_NUL })
    return response(200, {})
  })
  vi.stubGlobal('fetch', fetchMock)
}

async function render() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

async function openSettings() {
  await act(async () => { container.querySelector('button[title="Instellingen"]').click() })
  expect(container.querySelector('.settings-modal')).not.toBeNull()
}

const deleteKnop = () => [...document.querySelectorAll('button')].find(b => b.textContent === LABEL)

function vulLocalStorage() {
  for (const key of SESSION_DATA_KEYS) localStorage.setItem(key, `[${key}]`)
  localStorage.setItem(STORAGE_SETTINGS, '{"instelling":"Hogeschool Utrecht"}')
  localStorage.setItem(STORAGE_ONBOARDED, '1')
  localStorage.setItem(STORAGE_TOKEN, 'tok-1')
  localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
  localStorage.setItem(STORAGE_MODEL, 'claude')
  localStorage.setItem(STORAGE_RECENT, '{"gesprekken":["c1"]}')
}

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  window.history.replaceState({}, '', '/')
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App: Verwijder al mijn gegevens', APP_TEST, () => {
  it('is offered in the settings when login is required', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    serve({ required: true })
    await render()
    await openSettings()
    expect(deleteKnop()).toBeDefined()
  })

  it('is not offered when login is off: every visitor is the shared guest', async () => {
    serve({ required: false })
    await render()
    await openSettings()
    expect(deleteKnop()).toBeUndefined()
    // The export stays, as before (#645).
    expect(container.querySelector('.mijn-gegevens-export-btn')).not.toBeNull()
  })

  it('after success empties the browser copy, the profile and the login, keeps model and recent, and shows the login page', async () => {
    vulLocalStorage()
    serve({ required: true })
    await render()
    await openSettings()

    await act(async () => { deleteKnop().click() })
    const invoer = document.querySelector('[role="alertdialog"] input')
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(invoer, 'verwijder')
      invoer.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => { document.querySelector('[role="alertdialog"] button[type="submit"]').click() })

    const deletes = fetchMock.mock.calls.filter(([url]) => url === '/api/mijn-gegevens')
    expect(deletes).toHaveLength(1)
    expect(deletes[0][1].headers.Authorization).toBe('Bearer tok-1')
    for (const key of [...SESSION_DATA_KEYS, STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_TOKEN, STORAGE_USERINFO]) {
      expect(localStorage.getItem(key), key).toBeNull()
    }
    expect(localStorage.getItem(STORAGE_MODEL)).toBe('claude')
    expect(localStorage.getItem(STORAGE_RECENT)).toBe('{"gesprekken":["c1"]}')
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/auth/logout')).toBe(false)

    expect(container.querySelector('#login-username')).not.toBeNull()
    expect(document.querySelector('[role="alertdialog"]')).toBeNull()
    expect(container.querySelector('.settings-modal')).toBeNull()
    const status = container.querySelector('[role="status"]')
    expect(status.textContent).toBe(GEGEVENS_VERWIJDERD)
    expect(GEGEVENS_VERWIJDERD).toBe('Al je gegevens zijn verwijderd. Je bent uitgelogd.')
  })
})
