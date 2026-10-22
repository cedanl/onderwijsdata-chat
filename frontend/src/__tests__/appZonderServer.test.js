// @vitest-environment jsdom
// #670: zonder antwoord van /api/auth/status (offline, server weg) bleef de app oneindig op "wordt geladen…" staan.
// Een geïnstalleerde app opent offline met de shell uit de cache, dus dan moet hij zich tonen met de bewaarde sessie,
// of met het loginscherm als er geen is.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { bewaardeSessieNaam } from '../auth'
import { STORAGE_TOKEN, STORAGE_USERINFO } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const APP_TEST = { timeout: 20000 }
let root
let container

async function renderOffline() {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  window.history.replaceState({}, '', '/')
})
afterEach(async () => {
  await act(async () => { root?.unmount() })
  container?.remove()
  delete window.matchMedia
  localStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('App zonder antwoord van de server', () => {
  it('toont het loginscherm in plaats van eeuwig te laden als er geen sessie is', APP_TEST, async () => {
    await renderOffline()
    expect(container.textContent).not.toContain('wordt geladen')
    expect(container.querySelector('input[type="password"]')).not.toBeNull()
  })

  it('toont de app met de bewaarde sessie als er een token is', APP_TEST, async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
    await renderOffline()
    expect(container.textContent).not.toContain('openEDUdata+ wordt geladen')
    expect(container.querySelector('input[type="password"]')).toBeNull()
    expect(container.querySelector('.navbar')).not.toBeNull()
  })
})

describe('bewaardeSessieNaam', () => {
  it('geeft null zonder token, de bewaarde naam met token, en user als alleen het token er is', () => {
    expect(bewaardeSessieNaam()).toBeNull()
    localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
    expect(bewaardeSessieNaam()).toBeNull()
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    expect(bewaardeSessieNaam()).toBe('Anna')
    localStorage.removeItem(STORAGE_USERINFO)
    expect(bewaardeSessieNaam()).toBe('user')
  })
})
