// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import RunProgress, { countRunSteps, formatElapsed } from '../components/RunProgress'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('countRunSteps', () => {
  it('counts the tool calls after the last user message only', () => {
    const messages = [
      { role: 'user', content: 'eerste' },
      { role: 'assistant', tools: [{}, {}, {}] },
      { role: 'user', content: 'tweede' },
      { role: 'assistant', tools: [{}, {}] },
      { role: 'assistant', content: 'figuur' },
    ]
    expect(countRunSteps(messages)).toBe(2)
  })

  it('is zero without tools or messages', () => {
    expect(countRunSteps([])).toBe(0)
    expect(countRunSteps([{ role: 'user', content: 'x' }])).toBe(0)
  })
})

it('formats elapsed time as m:ss', () => {
  expect(formatElapsed(0)).toBe('0:00')
  expect(formatElapsed(65)).toBe('1:05')
  expect(formatElapsed(600)).toBe('10:00')
})

describe('RunProgress', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.useRealTimers()
  })

  async function render(props) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(RunProgress, props)) })
  }

  it('shows nothing while no run is going', async () => {
    await render({ busy: false, steps: 3 })
    expect(container.querySelector('.run-progress')).toBeNull()
  })

  it('shows elapsed time and steps, and counts up while the run goes', async () => {
    vi.useFakeTimers()
    await render({ busy: true, steps: 1 })
    expect(container.textContent).toContain('0:00')
    expect(container.textContent).toContain('1 stap')
    expect(container.textContent).not.toContain('1 stappen')

    await act(async () => { vi.advanceTimersByTime(7000) })
    expect(container.textContent).toContain('0:07')
  })

  it('disappears when the run ends', async () => {
    await render({ busy: true, steps: 2 })
    expect(container.querySelector('.run-progress')).not.toBeNull()
    await act(async () => { root.render(createElement(RunProgress, { busy: false, steps: 2 })) })
    expect(container.querySelector('.run-progress')).toBeNull()
  })
})
