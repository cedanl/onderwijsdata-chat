// @vitest-environment jsdom
// #671: "Zet op je startscherm" in het menu: een eigen knop als de browser een installatieprompt heeft, uitleg met
// stappen op iOS, en niets als de app al geïnstalleerd draait of er niets te installeren valt.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

const aanbod = vi.hoisted(() => ({ waarde: null, vraag: vi.fn() }))
vi.mock('../installeerApp', () => ({
  useInstallatieAanbod: () => aanbod.waarde,
  vraagInstallatie: aanbod.vraag,
}))

import Nav from '../components/Nav'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  aanbod.waarde = null
  aanbod.vraag.mockClear()
})

async function openMenu() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(MemoryRouter, { initialEntries: ['/chat'] }, createElement(Nav, { user: 'tester', onLogout: vi.fn() })))
  })
  await act(async () => { container.querySelector('button[aria-label="Menu"]').click() })
}
const installeerKnop = () => [...container.querySelectorAll('#navbar-menu button')].find(b => b.textContent === 'Zet op je startscherm')

describe('menu-item "Zet op je startscherm"', () => {
  it('ontbreekt als er niets aan te bieden is', async () => {
    await openMenu()
    expect(installeerKnop()).toBeUndefined()
  })

  it('opent bij een prompt de installatiedialoog van de browser en sluit het menu', async () => {
    aanbod.waarde = 'prompt'
    await openMenu()
    await act(async () => { installeerKnop().click() })
    expect(aanbod.vraag).toHaveBeenCalledTimes(1)
    expect(container.querySelector('#navbar-menu')).toBeNull()
  })

  it('toont op iOS de stappen in een dialoog die je kunt sluiten', async () => {
    aanbod.waarde = 'ios'
    await openMenu()
    await act(async () => { installeerKnop().click() })
    expect(aanbod.vraag).not.toHaveBeenCalled()
    const dialoog = document.querySelector('[role="dialog"][aria-label="Zet op je startscherm"]')
    expect(dialoog).not.toBeNull()
    expect([...dialoog.querySelectorAll('li')].map(li => li.textContent)).toEqual([
      'Tik onderin op Delen (het vierkant met een pijl omhoog).',
      'Kies Zet op beginscherm.',
      'Laat Open als web-app aan.',
      'Tik op Voeg toe.',
    ])
    await act(async () => { dialoog.querySelector('button[aria-label="Sluiten"]').click() })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })
})
