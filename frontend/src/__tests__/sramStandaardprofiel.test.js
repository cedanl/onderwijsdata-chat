// @vitest-environment jsdom
// #777: a recognised SRAM instelling is the default profile. The kop shows what the chat sends, the user's own choice
// wins, and the onboarding opens while there is no profile yet, after the password form and after SRAM alike.
// The profile still goes on logout (shared device, besluit 30-10).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { effectieveInstelling, effectiefProfiel, zonderProfiel } from '../profiel'
import { STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_TOKEN } from '../constants'
import { FakeWebSocket } from './fakeWebSocket'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// Each App test renders the whole app; on a busy machine that nears the 5 s default.
const APP_TEST = { timeout: 20000 }
const INSTELLINGEN = [
  { naam: 'Hogeschool Utrecht', type: 'hbo', aliassen: ['HU'], domeinen: ['hu.nl'] },
  { naam: 'Universiteit Utrecht', type: 'wo', aliassen: ['UU'], domeinen: ['uu.nl'] },
]
// What SRAM lands with: the token in the fragment, the identity from /api/auth/user.
const SRAM_LANDING = '#token=tok-1&user_data=%7B%22name%22%3A%22Anna%22%7D'

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container

function serve(gebruiker) {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: true })
    if (url === '/api/auth/user') return response(200, gebruiker)
    if (url === '/api/auth/login') return response(200, { token: 'tok-2', user: 'anna' })
    if (url === '/api/instellingen') return response(200, INSTELLINGEN)
    if (url.startsWith('/api/conversations')) return response(200, [])
    return response(200, {})
  }))
}

async function open(adres) {
  window.history.replaceState({}, '', adres)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

const welkom = () => container.querySelector('[role="dialog"][aria-label="Welkom onderwijsprofessional"]')
const kop = () => container.querySelector('.navbar-profile-instelling')?.textContent ?? null
const loginForm = () => container.querySelector('#login-username')
const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === tekst)

// The settings the chat sends the server once its socket opens. The chat page is lazy: the first load takes a while.
async function chatInstelling() {
  await vi.waitFor(() => expect(FakeWebSocket.last).not.toBeNull(), { timeout: 10000 })
  await act(async () => { FakeWebSocket.last.open() })
  const verzonden = FakeWebSocket.last.sent.filter(m => m.action === 'settings')
  expect(verzonden.length).toBeGreaterThan(0)
  return verzonden.at(-1).settings.instelling ?? null
}

async function logInMetWachtwoord() {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
  await act(async () => {
    for (const [id, waarde] of [['#login-username', 'anna'], ['#login-password', 'geheim']]) {
      const veld = container.querySelector(id)
      set.call(veld, waarde)
      veld.dispatchEvent(new Event('input', { bubbles: true }))
    }
  })
  await act(async () => { container.querySelector('form').requestSubmit() })
  await vi.waitFor(() => expect(loginForm()).toBeNull())
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  FakeWebSocket.reset()
  vi.stubGlobal('WebSocket', FakeWebSocket)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  container = null
  delete window.matchMedia
  localStorage.clear()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('profiel', () => {
  it('takes the SRAM instelling only while the user chose none, and an empty choice is a choice', () => {
    expect(effectieveInstelling({}, 'Hogeschool Utrecht')).toBe('Hogeschool Utrecht')
    expect(effectieveInstelling({ instelling: 'Universiteit Utrecht' }, 'Hogeschool Utrecht')).toBe('Universiteit Utrecht')
    expect(effectieveInstelling({ instelling: '' }, 'Hogeschool Utrecht')).toBe('')
    expect(effectieveInstelling({}, null)).toBe('')
    expect(effectiefProfiel({ functie: 'Beleidsmedewerker', mode: 'dark' }, 'HU-naam'))
      .toEqual({ functie: 'Beleidsmedewerker', mode: 'dark', instelling: 'HU-naam' })
  })

  it('counts an instelling (chosen or from SRAM) or a functie as a profile', () => {
    expect(zonderProfiel({ instelling: '' })).toBe(true)
    expect(zonderProfiel({ instelling: '  ' })).toBe(true)
    expect(zonderProfiel({ instelling: 'Hogeschool Utrecht' })).toBe(false)
    expect(zonderProfiel({ instelling: '', functie: 'Docent' })).toBe(false)
  })
})

describe('App: SRAM instelling as default profile', APP_TEST, () => {
  it('without a choice of their own, the kop and the chat use the SRAM instelling and no onboarding opens', async () => {
    serve({ name: 'Anna', org: 'Hogeschool Utrecht' })
    await open(`/chat${SRAM_LANDING}`)
    expect(loginForm()).toBeNull()
    expect(welkom()).toBeNull()
    expect(kop()).toBe('Hogeschool Utrecht')
    expect(await chatInstelling()).toBe('Hogeschool Utrecht')
  })

  it('the user\'s own choice wins over SRAM, in the kop and the chat', async () => {
    localStorage.setItem(STORAGE_SETTINGS, JSON.stringify({ instelling: 'Universiteit Utrecht' }))
    serve({ name: 'Anna', org: 'Hogeschool Utrecht' })
    await open(`/chat${SRAM_LANDING}`)
    expect(kop()).toBe('Universiteit Utrecht')
    expect(await chatInstelling()).toBe('Universiteit Utrecht')
  })

  it('a cleared choice wins too: no instelling in the kop or the chat, and the dialog starts empty', async () => {
    localStorage.setItem(STORAGE_SETTINGS, JSON.stringify({ instelling: '', functie: 'Docent' }))
    serve({ name: 'Anna', org: 'Hogeschool Utrecht' })
    await open(`/chat${SRAM_LANDING}`)
    expect(kop()).toBeNull()
    expect(await chatInstelling()).toBeNull()
    await act(async () => { container.querySelector('button[title="Instellingen"]').click() })
    expect(container.querySelector('#settings-instelling').value).toBe('')
  })
})

describe('App: onboarding while there is no profile', APP_TEST, () => {
  it('opens after the password form when there is no profile', async () => {
    serve({ name: 'Anna' })
    await open('/')
    await logInMetWachtwoord()
    expect(welkom()).not.toBeNull()
  })

  it('opens after SRAM when the SRAM identity matches no known instelling', async () => {
    serve({ name: 'Anna', org: 'Onbekende Academie' })
    await open(`/${SRAM_LANDING}`)
    expect(loginForm()).toBeNull()
    expect(kop()).toBeNull()
    expect(welkom()).not.toBeNull()
  })

  it('stays closed once it was closed, until logout', async () => {
    localStorage.setItem(STORAGE_ONBOARDED, '1')
    serve({ name: 'Anna', org: 'Onbekende Academie' })
    await open(`/${SRAM_LANDING}`)
    expect(welkom()).toBeNull()
  })
})

describe('App: logout still wipes the profile', APP_TEST, () => {
  it('removes the saved profile, and the next login without one gets the onboarding', async () => {
    localStorage.setItem(STORAGE_SETTINGS, JSON.stringify({ instelling: 'Universiteit Utrecht', functie: 'Docent' }))
    localStorage.setItem(STORAGE_ONBOARDED, '1')
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    serve({ name: 'Anna' })
    await open('/')
    expect(kop()).toBe('Universiteit Utrecht')
    await act(async () => { knop('Uitloggen').click() })
    expect(localStorage.getItem(STORAGE_SETTINGS)).toBeNull()
    expect(localStorage.getItem(STORAGE_ONBOARDED)).toBeNull()
    await logInMetWachtwoord()
    expect(kop()).toBeNull()
    expect(welkom()).not.toBeNull()
  })
})
