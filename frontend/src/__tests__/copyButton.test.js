// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import CopyButton from '../components/CopyButton'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function mount(props = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(CopyButton, { text: 'tekst', className: 'copy-btn-message', ...props })) })
}

function unmount() {
  if (!root) return
  act(() => root.unmount())
  container.remove()
  root = null
}

function setClipboard(clipboard) {
  Object.defineProperty(navigator, 'clipboard', { value: clipboard, configurable: true })
}

const button = () => container.querySelector('button')
const liveRegion = () => container.querySelector('[role="status"]')
const click = () => act(async () => button().click())
const advance = ms => act(async () => { vi.advanceTimersByTime(ms) })
const icon = () => button().querySelector('svg').innerHTML

beforeEach(() => {
  vi.useFakeTimers()
  setClipboard({ writeText: vi.fn().mockResolvedValue(undefined) })
})

afterEach(() => {
  unmount()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

// #492: the copy button confirms visibly and announces the result.
describe('CopyButton', () => {
  it('shows "Gekopieerd" with a check mark, then returns to the copy icon', async () => {
    await mount()
    const copyIcon = icon()
    await click()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('tekst')
    expect(button().textContent).toBe('Gekopieerd')
    expect(button().querySelector('polyline')).not.toBeNull()

    await advance(1500)
    expect(button().textContent).toBe('')
    expect(icon()).toBe(copyIcon)
  })

  it('announces through a live region that was already in the DOM', async () => {
    await mount()
    const region = liveRegion()
    expect(region.getAttribute('aria-live')).toBe('polite')
    expect(region.classList.contains('sr-only')).toBe(true)
    expect(region.textContent).toBe('')

    await click()
    expect(liveRegion()).toBe(region)
    expect(region.textContent).toBe('Gekopieerd')

    await advance(1500)
    expect(liveRegion()).toBe(region)
    expect(region.textContent).toBe('')
  })

  it('keeps its label, so only the live region announces', async () => {
    await mount()
    await click()
    expect(button().getAttribute('aria-label')).toBe('Kopieer')
    expect(button().getAttribute('title')).toBe('Kopieer')
    expect(button().querySelector('span').getAttribute('aria-hidden')).toBe('true')
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(1)
  })

  it('restarts the timer on a second click', async () => {
    await mount()
    await click()
    await advance(1000)
    await click()
    await advance(1000)
    expect(button().textContent).toBe('Gekopieerd')
    await advance(500)
    expect(button().textContent).toBe('')
  })

  it('clears the timer on unmount', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    await mount()
    await click()
    expect(vi.getTimerCount()).toBe(1)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
    expect(error).not.toHaveBeenCalled()
  })

  it('sets no timer when it unmounts before the copy settles', async () => {
    let resolve
    setClipboard({ writeText: vi.fn(() => new Promise(r => { resolve = r })) })
    await mount()
    await click()
    unmount()
    await act(async () => resolve())
    expect(vi.getTimerCount()).toBe(0)
  })

  it('says copying failed when writeText rejects', async () => {
    setClipboard({ writeText: vi.fn().mockRejectedValue(new Error('denied')) })
    await mount()
    await click()
    expect(button().textContent).toBe('')
    expect(button().hasAttribute('data-copied')).toBe(false)
    expect(liveRegion().textContent).toBe('Kopiëren mislukt')
    await advance(1500)
    expect(liveRegion().textContent).toBe('')
  })

  it('says copying failed without a clipboard', async () => {
    setClipboard(undefined)
    await mount()
    await click()
    expect(button().textContent).toBe('')
    expect(liveRegion().textContent).toBe('Kopiëren mislukt')
  })

  it('marks the copied state, which the stylesheet keeps visible', async () => {
    await mount()
    expect(button().hasAttribute('data-copied')).toBe(false)
    await click()
    expect(button().hasAttribute('data-copied')).toBe(true)

    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
    expect(css).toMatch(/\.copy-btn\[data-copied\]\s*\{[^}]*opacity:\s*1/)
  })
})
