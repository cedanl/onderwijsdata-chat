// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import RunProgress, { countRunSteps, currentRunStep, formatElapsed, heavyRun, HEAVY_TOOLS } from '../components/RunProgress'

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

// #547: a UWV or ROA question takes minutes; the run says so once such a tool has started.
describe('heavyRun', () => {
  const run = (...tools) => [{ role: 'user', content: 'vraag' }, { role: 'assistant', tools }]

  it('holds the UWV vacancies and the ROA benchmark', () => {
    expect([...HEAVY_TOOLS].sort()).toEqual(['get_roa_benchmark', 'get_uwv_vacatures'])
  })

  it('is true once a heavy tool has started in this run, running or done', () => {
    expect(heavyRun(run({ name: 'search_catalog', done: true }, { name: 'get_uwv_vacatures', done: false }))).toBe(true)
    expect(heavyRun(run({ name: 'get_roa_benchmark', done: true }, { name: 'create_plot', done: false }))).toBe(true)
  })

  it('is false for a run with only other tools, or none', () => {
    expect(heavyRun(run({ name: 'search_catalog', done: true }, { name: 'get_cbs_data', done: false }))).toBe(false)
    expect(heavyRun([{ role: 'user', content: 'vraag' }])).toBe(false)
    expect(heavyRun([])).toBe(false)
  })

  it('ignores a heavy tool from an earlier turn', () => {
    const messages = [
      ...run({ name: 'get_uwv_vacatures', done: true }),
      { role: 'user', content: 'tweede' },
      { role: 'assistant', tools: [{ name: 'get_duo_data', done: false }] },
    ]
    expect(heavyRun(messages)).toBe(false)
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

  it('says a heavy run takes minutes, outside the timer and without a live region', async () => {
    await render({ busy: true, steps: 2, heavy: true })
    const note = container.querySelector('.run-progress-note')
    expect(note.textContent).toBe('Dit kan 2–3 minuten duren.')
    expect(note.closest('[role="timer"]')).toBeNull()
    expect(note.closest('[role="alert"], [role="status"], [aria-live]')).toBeNull()
  })

  it('says nothing about the wait for a light run', async () => {
    await render({ busy: true, steps: 2 })
    expect(container.textContent).not.toContain('minuten duren')
  })

  it('says nothing about the wait when no run is going', async () => {
    await render({ busy: false, steps: 2, heavy: true })
    expect(container.textContent).not.toContain('minuten duren')
  })

  it('disappears when the run ends', async () => {
    await render({ busy: true, steps: 2 })
    expect(container.querySelector('.run-progress')).not.toBeNull()
    await act(async () => { root.render(createElement(RunProgress, { busy: false, steps: 2 })) })
    expect(container.querySelector('.run-progress')).toBeNull()
  })
})
