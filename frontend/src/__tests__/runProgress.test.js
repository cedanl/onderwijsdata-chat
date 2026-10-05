// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import RunProgress, { countRunSteps, currentRunStep, formatElapsed } from '../components/RunProgress'

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

// UX-10.4: time and step number said nothing about what the run was doing.
describe('currentRunStep', () => {
  it('is the running step of this run', () => {
    const messages = [
      { role: 'user', content: 'eerste' },
      { role: 'assistant', tools: [{ label: 'Oud', done: false }] },
      { role: 'user', content: 'tweede' },
      { role: 'assistant', tools: [{ label: 'Catalogus doorzoeken', done: true }, { label: 'DUO-data ophalen', done: false }] },
    ]
    expect(currentRunStep(messages)).toBe('DUO-data ophalen')
  })

  it('falls back to the last step taken, or nothing', () => {
    expect(currentRunStep([{ role: 'user' }, { role: 'assistant', tools: [{ label: 'Grafiek maken', done: true }] }])).toBe('Grafiek maken')
    expect(currentRunStep([{ role: 'user' }])).toBeNull()
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

  it('names the current step', async () => {
    await render({ busy: true, steps: 2, stepLabel: 'DUO-data ophalen' })
    expect(container.querySelector('.run-progress-step').textContent).toBe('DUO-data ophalen')
  })

  it('disappears when the run ends', async () => {
    await render({ busy: true, steps: 2 })
    expect(container.querySelector('.run-progress')).not.toBeNull()
    await act(async () => { root.render(createElement(RunProgress, { busy: false, steps: 2 })) })
    expect(container.querySelector('.run-progress')).toBeNull()
  })
})
