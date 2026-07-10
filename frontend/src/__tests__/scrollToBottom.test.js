// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createElement, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'

// We must set up the IntersectionObserver mock before importing the component
let observeCallback
let mockObserve
let mockDisconnect

beforeEach(() => {
  mockObserve = vi.fn()
  mockDisconnect = vi.fn()

  globalThis.IntersectionObserver = vi.fn((callback) => {
    observeCallback = callback
    return { observe: mockObserve, disconnect: mockDisconnect }
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

// Helper: render a Wrapper that provides refs to ScrollToBottom
function createWrapper(ScrollToBottom) {
  let refs = {}
  function Wrapper() {
    const sentinelRef = useRef(null)
    const scrollContainerRef = useRef(null)
    refs.sentinelRef = sentinelRef
    refs.scrollContainerRef = scrollContainerRef
    return createElement('div', { ref: scrollContainerRef, style: { overflow: 'auto' } },
      createElement('div', { ref: sentinelRef }),
      createElement(ScrollToBottom, { sentinelRef, scrollContainerRef })
    )
  }
  return { Wrapper, refs }
}

describe('ScrollToBottom', () => {
  it('creates an IntersectionObserver watching the sentinel', async () => {
    const { default: ScrollToBottom } = await import('../components/ScrollToBottom.jsx')
    const { Wrapper } = createWrapper(ScrollToBottom)

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(() => root.render(createElement(Wrapper)))

    expect(globalThis.IntersectionObserver).toHaveBeenCalledTimes(1)
    expect(mockObserve).toHaveBeenCalledTimes(1)

    root.unmount()
    document.body.removeChild(container)
  })

  it('shows button when sentinel is not intersecting, hides when it is', async () => {
    const { default: ScrollToBottom } = await import('../components/ScrollToBottom.jsx')
    const { Wrapper } = createWrapper(ScrollToBottom)

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(() => root.render(createElement(Wrapper)))

    // Initially no button (sentinel assumed visible before observer fires)
    expect(container.querySelector('.scroll-to-bottom-btn')).toBeNull()

    // Simulate: user scrolled up, sentinel not visible
    await act(() => observeCallback([{ isIntersecting: false }]))
    expect(container.querySelector('.scroll-to-bottom-btn')).not.toBeNull()
    expect(container.querySelector('.scroll-to-bottom-btn').getAttribute('aria-label')).toBe('Scroll naar beneden')

    // Simulate: user scrolled back to bottom
    await act(() => observeCallback([{ isIntersecting: true }]))
    expect(container.querySelector('.scroll-to-bottom-btn')).toBeNull()

    root.unmount()
    document.body.removeChild(container)
  })

  it('calls scrollIntoView with smooth behavior on click', async () => {
    const { default: ScrollToBottom } = await import('../components/ScrollToBottom.jsx')
    const { Wrapper, refs } = createWrapper(ScrollToBottom)

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(() => root.render(createElement(Wrapper)))
    await act(() => observeCallback([{ isIntersecting: false }]))

    refs.sentinelRef.current.scrollIntoView = vi.fn()

    const btn = container.querySelector('.scroll-to-bottom-btn')
    await act(() => btn.click())

    expect(refs.sentinelRef.current.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })

    root.unmount()
    document.body.removeChild(container)
  })

  it('disconnects observer on unmount', async () => {
    const { default: ScrollToBottom } = await import('../components/ScrollToBottom.jsx')
    const { Wrapper } = createWrapper(ScrollToBottom)

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(() => root.render(createElement(Wrapper)))
    expect(mockDisconnect).not.toHaveBeenCalled()

    root.unmount()
    expect(mockDisconnect).toHaveBeenCalled()

    document.body.removeChild(container)
  })
})
