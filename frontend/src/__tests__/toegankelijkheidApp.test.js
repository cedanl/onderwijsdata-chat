// @vitest-environment jsdom
// #687: een skip-link naar de inhoud (WCAG 2.4.1) en een axe-poort over de hoofdroutes. jsdom rekent geen layout, dus
// axe meet hier geen contrast; wat het wel ziet (namen, rollen, landmarks, kopjes, aria) faalt op serious/critical.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_USERINFO } from '../constants'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL, BUILTIN_OPLEIDINGEN } from '../workbooks'
import DASHBOARDS from './fixtures/dashboards.json'
import OPLEIDINGEN from './fixtures/dashboardOpleidingen.json'
import { FIN, PERS, FIN_BRON, WOPI_BRON } from './fixtures/bestuurEnPersoneel'

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
// de rest gaat mis zoals zonder server. De bronnen met een omgevingsregel staan aan (#973), zodat ook Opleidingen
// (#957) en de kaarten Financiën (#935) en Personeel (#936) op Mijn instelling getoetst worden. Zonder
// /api/instellingen kent de pagina het niveau van de instelling niet en vraagt ze het personeel op.
const DASHBOARD_ANTWOORDEN = {
  '/api/config': { dashboards_enabled: true, bronnen: { studiekeuze: true, financien: true, wo_personeel: true } },
  '/api/dashboard/regio': DASHBOARDS.regio,
  '/api/dashboard/rendement': DASHBOARDS.rendement,
  '/api/dashboard/nationaal': DASHBOARDS.nationaal,
  '/api/dashboard/arbeidsmarktmatch': DASHBOARDS.arbeidsmarktmatch,
  '/api/dashboard/opleidingen': OPLEIDINGEN.hbo,
  '/api/dashboard/financien': { ...FIN, bronnen: [FIN_BRON] },
  '/api/dashboard/personeel': { ...PERS, bronnen: [WOPI_BRON] },
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

  // #990: op een telefoon staat het ⋯-menu van de chat er ook zonder gesprek, met de melding over de externe AI-dienst.
  it('/chat op een telefoon, zonder gesprek en met het ⋯-menu open, heeft geen ernstige bevindingen', APP_TEST, async () => {
    window.matchMedia = q => ({ matches: q === '(max-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {} })
    await render('/chat', { ingelogd: true })
    const meer = container.querySelector('.navbar-pagina button[aria-label="Meer acties"]')
    await act(async () => { meer.click() })
    expect(meer.getAttribute('aria-expanded')).toBe('true')
    expect(container.querySelectorAll('#navbar-meer-menu')).toHaveLength(1)
    expect(container.querySelector('#navbar-meer-menu .navbar-meer-noot')).not.toBeNull()
    expect(await ernstigeBevindingen()).toEqual([])
  })

  // #905: de dashboards zelf, met data en zonder ze weg te mocken. Wacht tot het dashboard getekend is (de laadstatus
  // en de laadvlakken van de kaarten zijn weg en er staat een grafiek of tabel). `kaarten`: wat er dan moet staan.
  // Een uitklap gaat open (#973), zodat axe ook de tabel erachter ziet (NSE-thema's, kengetaldefinities).
  it.each([
    ['/dashboards', null, []],
    ['/dashboards (mijn instelling)', BUILTIN_MIJN_INSTELLING.id, ['Kengetallen per verslagjaar', 'Personeel (wo)']],
    ['/dashboards (arbeidsmarkt)', BUILTIN_ARBEIDSMARKT.id, []],
    ['/dashboards (landelijk)', BUILTIN_NATIONAAL.id, []],
    ['/dashboards (opleidingen)', BUILTIN_OPLEIDINGEN.id, ["NSE-thema's per opleidingsvorm", 'Numerus fixus en decentrale selectie']],
  ])('%s heeft geen ernstige bevindingen', APP_TEST, async (_, id, kaarten) => {
    await render(id ? `/dashboards?id=${id}` : '/dashboards', { ingelogd: true, server: metDashboards })
    if (id) {
      const getekend = () => container.querySelector('.dashboard-content canvas, .dashboard-content table')
        && !container.querySelector('.db-skeleton-grid, .db-skeleton-chart')
      for (let i = 0; i < 200 && !getekend(); i++) {
        await act(async () => { await new Promise(r => setTimeout(r, 20)) })
      }
      expect(getekend()).toBeTruthy()
      expect(container.querySelectorAll('.dashboard-content :is(canvas[role="img"][aria-label], .tabel-scroll table)').length).toBeGreaterThan(0)
      for (const kaart of kaarten) expect(container.textContent).toContain(kaart)
      await act(async () => { for (const d of container.querySelectorAll('.dashboard-content details')) d.open = true })
    } else {
      expect(container.textContent).toContain('Mijn instelling')
      // De miniaturen met hun cijfers (#933): axe moet de kaarten zien zoals ze er geladen uitzien.
      for (let i = 0; i < 200 && container.querySelectorAll('.wb-miniatuur .kpi-card').length === 0; i++) {
        await act(async () => { await new Promise(r => setTimeout(r, 20)) })
      }
      expect(container.querySelectorAll('.wb-miniatuur-pagina')).toHaveLength(4)
    }
    expect(await ernstigeBevindingen()).toEqual([])
  })
})
