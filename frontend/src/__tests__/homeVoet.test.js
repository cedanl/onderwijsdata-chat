// @vitest-environment jsdom
// #650: de disclaimer en de licentieregel onder de homepage hadden een inline font-size van .75rem (11,25 px). Een
// inline stijl wint van de telefoonregel van #613, dus de maat staat nu in de stylesheet, op de klassen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import HomePage from '../pages/HomePage'

vi.mock('../api', () => ({ fetchCatalogCounts: () => new Promise(() => {}) }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('homepage-footer (#650)', () => {
  it('zet de disclaimer en de licentieregel niet in een inline lettergrootte', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(MemoryRouter, null, createElement(HomePage))) })
    for (const kiezer of ['.home-disclaimer', '.home-licentie']) {
      const p = container.querySelector(kiezer)
      expect(p, kiezer).not.toBeNull()
      expect(p.style.fontSize, kiezer).toBe('')
    }
  })
})
