// @vitest-environment jsdom
// #687: een skip-link naar de inhoud (WCAG 2.4.1) en een axe-poort over de hoofdroutes. jsdom rekent geen layout, dus
// axe meet hier geen contrast; wat het wel ziet (namen, rollen, landmarks, kopjes, aria) faalt op serious/critical.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_USERINFO } from '../constants'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'
import DASHBOARDS from './fixtures/dashboards.json'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
// jsdom heeft geen canvas; react-chartjs-2 zoals het tekent: een canvas met role="img" en de overige props (#905).
vi.mock('react-chartjs-2', async () => {
  const { createElement: maak } = await import('react')
  // eslint-disable-next-line no-unused-vars -- data en options gaan naar Chart.js, niet naar het canvas
  const Canvas = ({ data, options, ...canvas }) => maak('canvas', { role: 'img', ...canvas })
  return { Line: Canvas, Bar: Canvas }
})

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const APP_TEST = { timeout: 30000 }
let root
let container

// Met de dashboards (#905) antwoordt de server op de config en de dashboarddata (echte antwoorden van 04-11, ingekort);
// de rest gaat mis zoals zonder server.
const DASHBOARD_ANTWOORDEN = {
  '/api/config': { dashboards_enabled: true },
  '/api/dashboard/regio': DASHBOARDS.regio,
  '/api/dashboard/rendement': DASHBOARDS.rendement,
  '/api/dashboard/nationaal': DASHBOARDS.nationaal,
  '/api/dashboard/arbeidsmarktmatch': DASHBOARDS.arbeidsmarktmatch,
}
const metDashboards = async url => {
  const antwoord = DASHBOARD_ANTWOORDEN[String(url).split('?')[0]]
  if (!antwoord) throw new TypeError('Failed to fetch')
  return new Response(JSON.stringify(antwoord), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

// Zonder server: de app toont het loginscherm, of met een bewaarde sessie de app zelf (appZonderServer.test.js).
async function render(pad, { ingelogd, server = async () => { throw new TypeError('Failed to fetch') } }) {
  if (ingelogd) {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
  }
  window.history.replaceState({}, '', pad)
  vi.stubGlobal('fetch', vi.fn(server))
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

  // #905: de dashboards zelf, met data en zonder ze weg te mocken. Wacht tot het dashboard getekend is (de laadstatus
  // is weg en er staat een grafiek of tabel).
  it.each([
    ['/dashboards', null],
    ['/dashboards (mijn instelling)', BUILTIN_MIJN_INSTELLING.id],
    ['/dashboards (arbeidsmarkt)', BUILTIN_ARBEIDSMARKT.id],
    ['/dashboards (landelijk)', BUILTIN_NATIONAAL.id],
  ])('%s heeft geen ernstige bevindingen', APP_TEST, async (_, id) => {
    await render(id ? `/dashboards?id=${id}` : '/dashboards', { ingelogd: true, server: metDashboards })
    if (id) {
      for (let i = 0; i < 200 && !container.querySelector('.dashboard-content canvas, .dashboard-content table'); i++) {
        await act(async () => { await new Promise(r => setTimeout(r, 20)) })
      }
      expect(container.querySelector('.db-skeleton-grid')).toBeNull()
      expect(container.querySelectorAll('.dashboard-content canvas[role="img"][aria-label]').length).toBeGreaterThan(0)
    } else {
      expect(container.textContent).toContain('Mijn instelling')
      // De miniaturen met hun cijfers (#933): axe moet de kaarten zien zoals ze er geladen uitzien.
      for (let i = 0; i < 200 && container.querySelectorAll('.wb-miniatuur .kpi-card').length === 0; i++) {
        await act(async () => { await new Promise(r => setTimeout(r, 20)) })
      }
      expect(container.querySelectorAll('.wb-miniatuur-pagina')).toHaveLength(3)
    }
    expect(await ernstigeBevindingen()).toEqual([])
  })
})
