// @vitest-environment jsdom
// #604: een geopend rapport houdt op een telefoon weinig inhoud over — terugknop, een titel van twee à drie
// regels en twee volle knoppen ('Download als HTML', 'Geef feedback op dit rapport') nemen drie rijen in.
// Zelfde recept als #596 (chat): op smal scherm gaat de titel op één regel met ellipsis en verhuizen de
// acties naar het ⋯-menu van de navbar via het nav-slot; desktop blijft inline.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

// Dashboards pull in Plotly, which jsdom cannot load.
vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))
vi.mock('../api', async importOriginal => ({
  ...await importOriginal(),
  fetchFeedbackGiven: vi.fn().mockResolvedValue([]),
}))

import WorkbookViewer from '../components/WorkbookViewer'
import { NavSlotContext } from '../navSlot'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const smal = vi.hoisted(() => ({ aan: false }))
const NARROW = '(max-width: 1024px)'
window.matchMedia = q => ({
  matches: smal.aan && q === NARROW, media: q, addEventListener() {}, removeEventListener() {},
})

let root
let container

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  smal.aan = false
})

const rapport = {
  id: 'wb-1', type: 'report',
  title: 'Hoe heeft het aantal inschrijvingen bij Avans Hogeschool zich de afgelopen vijf jaar ontwikkeld?',
  htmlContent: '<p>rapport</p>',
}

// De navbar-balk uit App: een slot waar een pagina op smal scherm haar knoppen in zet.
async function renderMetSlot(props = {}) {
  container = document.createElement('div')
  const slot = document.createElement('div')
  slot.className = 'navbar-pagina'
  container.appendChild(slot)
  const houder = document.createElement('div')
  container.appendChild(houder)
  document.body.appendChild(container)
  root = createRoot(houder)
  await act(async () => {
    root.render(createElement(NavSlotContext.Provider, { value: slot },
      createElement(WorkbookViewer, {
        workbook: rapport, instelling: 'HU', onBack: vi.fn(), onUpdate: vi.fn(),
        backLabel: 'Rapporten', feedbackEnabled: true, ...props,
      })))
  })
  return slot
}

const klik = async el => { await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })) }) }

describe('geopend rapport op smal scherm (#604)', () => {
  it('zet Download en feedback in het ⋯-menu van de navbar, niet in de kopbalk', async () => {
    smal.aan = true
    const slot = await renderMetSlot()
    expect(container.querySelector('.wb-viewer-actions')).toBeNull()
    const meer = slot.querySelector('button[aria-label="Meer acties"]')
    expect(meer).not.toBeNull()
    await klik(meer)
    const menu = slot.querySelector('.navbar-meer-menu')
    expect(menu).not.toBeNull()
    expect(menu.textContent).toContain('Download als HTML')
    expect(menu.textContent).toContain('Geef feedback op dit rapport')
  })

  it('opent het feedbackformulier vanuit het ⋯-menu', async () => {
    smal.aan = true
    const slot = await renderMetSlot()
    await klik(slot.querySelector('button[aria-label="Meer acties"]'))
    const knop = [...slot.querySelectorAll('.navbar-meer-menu button')]
      .find(b => b.textContent.includes('Geef feedback op dit rapport'))
    expect(knop).not.toBeUndefined()
    await klik(knop)
    expect(container.querySelector('[role="dialog"]')).not.toBeNull()
  })

  it('houdt de titel op één regel zodat hij de inhoud niet wegduwt', async () => {
    smal.aan = true
    await renderMetSlot()
    const kop = container.querySelector('.wb-viewer-heading')
    expect(kop).not.toBeNull()
    expect(kop.textContent).toContain('Avans Hogeschool')
    // jsdom legt geen stylesheet-cascade aan; leg de ellipsis-regel op de bron vast.
    const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
    expect(css).toMatch(/\.wb-viewer-heading \{[^}]*text-overflow: ellipsis/)
  })
})

describe('geopend dashboard (#795)', () => {
  const dashboard = { ...rapport, type: 'dashboard', htmlContent: undefined, dashboardSpec: {} }

  it('noemt het dashboard in de knop op desktop', async () => {
    await renderMetSlot({ workbook: dashboard })
    const acties = container.querySelector('.wb-viewer-actions')
    expect(acties.textContent).toContain('Geef feedback op dit dashboard')
    expect(acties.textContent).not.toContain('dit rapport')
  })

  it('noemt het dashboard in het ⋯-menu op smal scherm', async () => {
    smal.aan = true
    const slot = await renderMetSlot({ workbook: dashboard })
    await klik(slot.querySelector('button[aria-label="Meer acties"]'))
    const menu = slot.querySelector('.navbar-meer-menu')
    expect(menu.textContent).toContain('Geef feedback op dit dashboard')
    expect(menu.textContent).not.toContain('dit rapport')
  })
})

describe('geopend rapport op desktop (#604)', () => {
  it('houdt Download en feedback inline in de kopbalk en het slot leeg', async () => {
    const slot = await renderMetSlot()
    const acties = container.querySelector('.wb-viewer-actions')
    expect(acties).not.toBeNull()
    expect(acties.textContent).toContain('Download als HTML')
    expect(acties.textContent).toContain('Geef feedback op dit rapport')
    expect(slot.querySelector('button')).toBeNull()
  })
})
