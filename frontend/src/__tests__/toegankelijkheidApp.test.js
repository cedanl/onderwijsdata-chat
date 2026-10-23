// @vitest-environment jsdom
// #687: een skip-link naar de inhoud (WCAG 2.4.1) en een axe-poort over de hoofdroutes. jsdom rekent geen layout, dus
// axe meet hier geen contrast; wat het wel ziet (namen, rollen, landmarks, kopjes, aria) faalt op serious/critical.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_USERINFO } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const APP_TEST = { timeout: 30000 }
let root
let container

// Zonder server: de app toont het loginscherm, of met een bewaarde sessie de app zelf (appZonderServer.test.js).
async function render(pad, { ingelogd }) {
  if (ingelogd) {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
  }
  window.history.replaceState({}, '', pad)
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
  // Lazy routes (chat, rapporten) laden na de eerste render; axe moet de pagina zelf zien, niet de laadmelding.
  for (let i = 0; i < 200 && container.textContent.includes('wordt geladen'); i++) {
    await act(async () => { await new Promise(r => setTimeout(r, 50)) })
  }
  expect(container.textContent).not.toContain('wordt geladen')
}

async function ernstigeBevindingen() {
  const { violations } = await axe.run(container, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
    // De container is een div in body; landmarks en de taal van het document toetst de echte pagina.
    rules: { region: { enabled: false }, 'html-has-lang': { enabled: false } },
  })
  return violations
    .filter(v => ['serious', 'critical'].includes(v.impact))
    .map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`)
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

describe('skip-link (#687)', () => {
  it('is het eerste focusbare element en zet de focus op de inhoud', APP_TEST, async () => {
    await render('/', { ingelogd: true })
    const eerste = container.querySelector('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')
    expect(eerste.className).toBe('skip-link')
    expect(eerste.textContent).toBe('Naar de inhoud')
    const main = container.querySelector('main')
    expect(eerste.getAttribute('href')).toBe(`#${main.id}`)
    expect(main.tabIndex).toBe(-1)

    await act(async () => { eerste.click() })
    expect(document.activeElement).toBe(main)
    expect(window.location.hash).toBe('') // geen navigatie via de router
  })
})

describe('axe-poort (#687)', () => {
  it.each([
    ['/login', false],
    ['/privacy', false],
    ['/', true],
    ['/chat', true],
    ['/rapporten', true],
    ['/privacy', true],
  ])('%s (ingelogd: %s) heeft geen ernstige bevindingen', APP_TEST, async (pad, ingelogd) => {
    await render(pad, { ingelogd })
    expect(await ernstigeBevindingen()).toEqual([])
  })
})
