// @vitest-environment jsdom
// #1175 en #1171: de navigatiebalk op desktop zegt welke pagina actief is (WCAG 1.3.1), en het hamburgermenu sluit
// als de focus het verlaat, zodat de focus nooit onder het open menu valt (WCAG 2.4.11).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

import Nav from '../components/Nav'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

async function render(pad = '/chat') {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: [pad] },
      createElement(Nav, { user: 'tester', onLogout: vi.fn(), onOpenSettings: vi.fn(), dashboardsEnabled: true, onZoek: vi.fn() })))
  })
}

describe('huidige pagina in de navigatiebalk (#1175)', () => {
  const huidig = () => [...container.querySelectorAll('.navbar-nav a')]
    .map(a => [a.textContent, a.getAttribute('aria-current')])

  it('zet aria-current="page" alleen op de actieve link', async () => {
    await render('/rapporten')
    expect(huidig()).toEqual([['Home', null], ['Chat', null], ['Rapporten', 'page'], ['Dashboard', null]])
  })

  it('geldt ook voor een subroute van de pagina', async () => {
    await render('/dashboards?id=landelijk')
    expect(huidig().filter(([, c]) => c === 'page')).toEqual([['Dashboard', 'page']])
  })

  it('verbergt het icoon voor schermlezers', async () => {
    await render()
    const iconen = container.querySelectorAll('.navbar-nav a svg')
    expect(iconen).toHaveLength(4)
    iconen.forEach(svg => expect(svg.getAttribute('aria-hidden')).toBe('true'))
  })
})

describe('hamburgermenu en focus (#1171)', () => {
  const menuknop = () => container.querySelector('button[aria-label="Menu"]')
  const menu = () => container.querySelector('#navbar-menu')
  const open = async () => { await act(async () => { menuknop().click() }) }
  // De focus verlaat `van` en gaat naar `naar` (null: het venster of een niet-focusbaar vlak).
  const verlaat = async (van, naar) => {
    await act(async () => { van.dispatchEvent(new window.FocusEvent('focusout', { bubbles: true, relatedTarget: naar })) })
  }

  it('sluit als de focus het laatste menu-item verlaat naar een element buiten het menu', async () => {
    await render()
    await open()
    const items = menu().querySelectorAll('a, button')
    await verlaat(items[items.length - 1], container.querySelector('.navbar-zoek-btn'))
    expect(menu()).toBeNull()
    expect(menuknop().getAttribute('aria-expanded')).toBe('false')
  })

  it('sluit als de focus de menuknop met Shift+Tab verlaat', async () => {
    await render()
    await open()
    await verlaat(menuknop(), document.body.appendChild(document.createElement('button')))
    expect(menu()).toBeNull()
  })

  it('blijft open als de focus binnen het menu of naar de menuknop gaat', async () => {
    await render()
    await open()
    const items = menu().querySelectorAll('a, button')
    await verlaat(menuknop(), items[0])
    await verlaat(items[0], items[1])
    await verlaat(items[1], menuknop())
    expect(menu()).not.toBeNull()
    expect(menuknop().getAttribute('aria-expanded')).toBe('true')
  })

  it('blijft open als de focus nergens heen gaat (venster wisselt, tik op het menu zelf)', async () => {
    await render()
    await open()
    await verlaat(menu().querySelector('a'), null)
    expect(menu()).not.toBeNull()
  })
})
