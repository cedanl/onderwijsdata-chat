// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReasoningStep from '../components/ReasoningStep'
import { markRecovered } from '../toolSteps'

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
    expect(container.querySelector('span').textContent).toBe('Filter mislukt')
    expect(container.textContent).toContain('kon niet op de data worden uitgevoerd')
  })

  // #426: the app retried and the retry delivered; a bare red "Filter mislukt" read as a dead end.
  it('dims a failed step that a later attempt made good, and says so', async () => {
    await render({ name: 'query_data', label: 'Data gefilterd', done: true, status: 'error', statusLabel: 'Filter mislukt', recovered: true })
    expect(container.querySelector('.reasoning-step').className).toContain('recovered')
    expect(container.querySelector('.reasoning-step-dot').className).toContain('recovered')
    expect(container.textContent).toContain('Een volgende poging lukte')
    expect(container.textContent).not.toContain('kon niet op de data')
  })

  it('drops the hints of an empty filter once a later attempt delivered', async () => {
    await render({
      name: 'query_data', label: 'Data gefilterd', done: true, status: 'empty',
      statusLabel: 'Filter leverde 0 rijen op', suggesties: { Niveau: ['Hbo'] }, recovered: true,
    })
    expect(container.textContent).toContain('Een volgende poging lukte')
    expect(container.textContent).not.toContain('Niveau: Hbo')
  })
})

describe('markRecovered', () => {
  const fout = { name: 'query_data', done: true, status: 'error', statusLabel: 'Filter mislukt' }
  const gelukt = { name: 'query_data', done: true }

  it('marks a failed step followed by a successful run of the same tool', () => {
    expect(markRecovered([fout, gelukt])[0].recovered).toBe(true)
  })

  it('leaves a failed step alone when no later run of that tool delivered', () => {
    const steps = [fout, { name: 'get_cbs_data', done: true }, { ...fout }, { name: 'query_data', done: false }]
    expect(markRecovered(steps).some(s => s.recovered)).toBe(false)
  })

  it('does not count an earlier success as a recovery', () => {
    expect(markRecovered([gelukt, fout])[1].recovered).toBeUndefined()
  })
})
