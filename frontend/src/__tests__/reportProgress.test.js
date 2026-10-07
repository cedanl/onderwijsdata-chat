// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReportProgress from '../components/ReportProgress'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// #339: making a report takes one to two minutes; the wait shows time and step and can be cancelled.
describe('ReportProgress', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(props) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(ReportProgress, props)))
  }

  it('shows elapsed time, steps and the current step', () => {
    render({ busy: true, progress: { steps: 2, label: 'Grafiek maken' }, onCancel: () => {} })
    const timer = container.querySelector('[role="timer"]')
    expect(timer.textContent).toContain('0:00')
    expect(timer.textContent).toContain('2 stappen')
    expect(timer.textContent).toContain('Grafiek maken')
  })

  // #417: na de laatste stap schrijft het model minutenlang zonder nieuwe stap; zeg dat dat hoort.
  it('zegt dat een rapport een paar minuten duurt', () => {
    render({ busy: true, progress: { steps: 2, label: 'Grafiek maken' }, onCancel: () => {} })
    const melding = container.querySelector('.report-progress-note')
    expect(melding.textContent).toMatch(/paar minuten/)
  })

  it('cancels on click', () => {
    const onCancel = vi.fn()
    render({ busy: true, progress: { steps: 0, label: null }, onCancel })
    const knop = [...container.querySelectorAll('button')].find(b => b.textContent === 'Annuleer')
    act(() => knop.click())
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('renders nothing when no report is being made', () => {
    render({ busy: false, progress: { steps: 0, label: null }, onCancel: () => {} })
    expect(container.innerHTML).toBe('')
  })
})
