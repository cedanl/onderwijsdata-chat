// @vitest-environment jsdom
// #672: de caches van de service worker gaan weg als de sessie eindigt: uitloggen en een sessie die de server beëindigt.
// ("Verwijder al mijn gegevens" loopt langs dezelfde resetSession; zie mijnGegevensVerwijderenApp.test.js.)
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const caches = vi.hoisted(() => ({ wis: vi.fn().mockResolvedValue() }))
vi.mock('../pwaCaches', () => ({ wisPwaCaches: caches.wis }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import App from '../App'
import { endSession } from '../auth'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
const APP_TEST = { timeout: 20000 }
const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container

async function renderIngelogd() {
  localStorage.setItem(STORAGE_TOKEN, 'tok-1')
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: false })
    if (url === '/api/auth/user') return response(200, { name: 'Anna' })
    if (url === '/api/instellingen') return response(200, [])
    return response(200, {})
  }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

beforeEach(() => {
  localStorage.clear()
  caches.wis.mockClear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  window.history.replaceState({}, '', '/')
})
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App wist de service-worker-caches', APP_TEST, () => {
  it('bij uitloggen', async () => {
    await renderIngelogd()
    expect(caches.wis).not.toHaveBeenCalled()
    const uitloggen = [...container.querySelectorAll('button')].find(b => b.textContent.trim() === 'Uitloggen')
    await act(async () => { uitloggen.click() })
    expect(caches.wis).toHaveBeenCalledTimes(1)
  })

  it('als de server de sessie beëindigt', async () => {
    await renderIngelogd()
    await act(async () => { endSession() })
    expect(caches.wis).toHaveBeenCalledTimes(1)
  })
})
