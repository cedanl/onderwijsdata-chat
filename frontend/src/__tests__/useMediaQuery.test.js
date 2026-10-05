// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useMediaQuery } from '../hooks/useMediaQuery'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

function fakeMatchMedia(initial) {
  const listeners = new Set()
  const mql = {
    matches: initial,
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
  }
  window.matchMedia = vi.fn(() => mql)
  return { set(v) { mql.matches = v; listeners.forEach(fn => fn()) } }
}

function Probe() {
  return createElement('span', null, useMediaQuery('(max-width: 1024px)') ? 'smal' : 'breed')
}

async function render() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Probe)) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  delete window.matchMedia
})

describe('useMediaQuery', () => {
  it('reports the current match', async () => {
    fakeMatchMedia(true)
    await render()
    expect(container.textContent).toBe('smal')
  })

  it('follows a change of the media query', async () => {
    const media = fakeMatchMedia(false)
    await render()
    expect(container.textContent).toBe('breed')
    await act(async () => media.set(true))
    expect(container.textContent).toBe('smal')
  })

  it('is false where matchMedia does not exist', async () => {
    await render()
    expect(container.textContent).toBe('breed')
  })
})
