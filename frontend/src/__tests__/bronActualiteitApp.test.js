// @vitest-environment jsdom
// #1266: /bronnen is een route van de app (lazy geladen) en een onbekend pad blijft de 404-pagina.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_USERINFO } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const APP_TEST = { timeout: 30000 }
const OVERZICHT = {
  bronnen: [{
    bron: 'cbs', naam: 'CBS', titel: 'Centraal Bureau voor de Statistiek', url: 'https://opendata.cbs.nl', bereikbaar: 'onbekend',
    laatste_periode: 'verschilt per dataset', laatste_wijziging: '2026-03-12', status: 'definitief', frequentie: 'Jaarlijks',
    verwachte_volgende_editie: 'onbekend', verwachte_volgende_editie_bron: 'onbekend', datasets: [],
  }],
}

let root
let container

// Een server die alleen /api/bronactualiteit kent; de rest gaat mis zoals zonder server (appZonderServer.test.js).
async function render(pad) {
  localStorage.setItem(STORAGE_TOKEN, 'tok-1')
  localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
  window.history.replaceState({}, '', pad)
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (String(url).split('?')[0] !== '/api/bronactualiteit') throw new TypeError('Failed to fetch')
    return new Response(JSON.stringify(OVERZICHT), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
  // De pagina laadt lazy, daarna haalt ze de actualiteit op: wacht tot de laadmeldingen weg zijn.
  for (let i = 0; i < 200 && /wordt geladen/.test(container.textContent); i++) {
    await act(async () => { await new Promise(r => setTimeout(r, 20)) })
  }
}

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
})
afterEach(async () => {
  await act(async () => { root?.unmount() })
  container?.remove()
  delete window.matchMedia
  localStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.history.replaceState({}, '', '/')
})

describe('de route /bronnen (#1266)', () => {
  it('toont de pagina met de bronnen van de server', APP_TEST, async () => {
    await render('/bronnen')
    expect(container.querySelector('main h1').textContent).toBe('Actualiteit van de bronnen')
    expect(container.querySelector('section.bronact-bron h2').textContent).toContain('CBS')
    expect(document.title).toBe('Actualiteit van de bronnen — openEDUdata+')
  })

  it('laat een onbekend pad de 404-pagina', APP_TEST, async () => {
    await render('/bronnen-bestaat-niet')
    expect(container.querySelector('main h1').textContent).toBe('Deze pagina bestaat niet (meer)')
  })
})
