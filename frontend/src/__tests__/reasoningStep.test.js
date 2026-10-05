// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReasoningStep from '../components/ReasoningStep'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(tool) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ReasoningStep, { tool })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// Only a step that delivered something is green (#386).
describe('ReasoningStep', () => {
  it('shows a successful step with its label and a done dot', async () => {
    await render({ name: 'query_data', label: 'Data gefilterd', done: true })
    expect(container.textContent).toBe('Data gefilterd')
    expect(container.querySelector('.reasoning-step-dot').className).toBe('reasoning-step-dot done')
  })

  it('shows an empty filter as such, with the values that do exist', async () => {
    await render({
      name: 'query_data', label: 'Data gefilterd', done: true, status: 'empty',
      statusLabel: 'Filter leverde 0 rijen op', suggesties: { Niveau: ['Hbo', 'Wo'], Jaar: 'bereik in de data: 2020 t/m 2024' },
    })
    expect(container.querySelector('.reasoning-step-dot').className).toContain('empty')
    expect(container.textContent).toContain('Filter leverde 0 rijen op')
    expect(container.textContent).not.toContain('Data gefilterd')
    expect(container.textContent).toContain('Niveau: Hbo, Wo')
    expect(container.textContent).toContain('Jaar: bereik in de data: 2020 t/m 2024')
  })

  it('shows a failed step as failed', async () => {
    await render({ name: 'query_data', label: 'Data gefilterd', done: true, status: 'error', statusLabel: 'Filter mislukt' })
    expect(container.querySelector('.reasoning-step-dot').className).toContain('error')
    expect(container.textContent).toBe('Filter mislukt')
  })
})
