// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ErrorRetry, { alternativeModel, offersRetry } from '../components/ErrorRetry'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const MODELS = [
  { id: 'gpt-oss-120b', name: 'gpt-oss' },
  { id: 'claude-sonnet', name: 'Sonnet' },
]

let root
let container

async function render(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(ErrorRetry, { question: 'Hoeveel studenten heeft de HU?', models: MODELS, busy: false, onRetry: vi.fn(), ...props }))
  })
}

const buttons = () => [...container.querySelectorAll('button')]

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #333: a failed answer had no way back but retyping the question.
describe('ErrorRetry', () => {
  it('retries the same question with the current model', async () => {
    const onRetry = vi.fn()
    await render({ failedModel: 'gpt-oss-120b', onRetry })
    await act(async () => { buttons()[0].click() })
    expect(onRetry).toHaveBeenCalledWith('Hoeveel studenten heeft de HU?')
  })

  it('offers a model other than the one that failed', async () => {
    const onRetry = vi.fn()
    await render({ failedModel: 'gpt-oss-120b', onRetry })
    expect(buttons()[1].textContent).toBe('Opnieuw met Sonnet')
    await act(async () => { buttons()[1].click() })
    expect(onRetry).toHaveBeenCalledWith('Hoeveel studenten heeft de HU?', 'claude-sonnet')
  })

  it('offers only a plain retry when there is no other model', async () => {
    await render({ failedModel: 'gpt-oss-120b', models: [MODELS[0]] })
    expect(buttons().map(b => b.textContent)).toEqual(['Opnieuw'])
  })

  // #404: een interne fout faalt bij elk model gelijk; een ander model aanbieden helpt niet.
  it('offers no other model after an internal error', async () => {
    await render({ failedModel: 'gpt-oss-120b', modelafhankelijk: false })
    expect(buttons().map(b => b.textContent)).toEqual(['Opnieuw'])
  })

  it('is disabled while a run is going', async () => {
    await render({ failedModel: 'gpt-oss-120b', busy: true })
    expect(buttons().every(b => b.disabled)).toBe(true)
  })

  it('shows nothing without a question to retry', async () => {
    await render({ question: undefined })
    expect(buttons()).toEqual([])
  })
})

// #515: a refused report is made again with its own button; re-asking stays possible.
describe('ErrorRetry after a refused report', () => {
  const labels = () => buttons().map(b => b.textContent)

  it('offers the report again and the question again, and no other model', async () => {
    await render({ herstel: 'rapport', failedModel: 'gpt-oss-120b', onRapport: vi.fn() })
    expect(labels()).toEqual(['Opnieuw proberen', 'Vraag opnieuw stellen'])
  })

  it('makes the report again without re-sending the question', async () => {
    const onRapport = vi.fn()
    const onRetry = vi.fn()
    await render({ herstel: 'rapport', onRapport, onRetry })
    await act(async () => { buttons()[0].click() })
    expect(onRapport).toHaveBeenCalledTimes(1)
    expect(onRetry).not.toHaveBeenCalled()
  })

  it('asks the same question again with the current model', async () => {
    const onRapport = vi.fn()
    const onRetry = vi.fn()
    await render({ herstel: 'rapport', onRapport, onRetry })
    await act(async () => { buttons()[1].click() })
    expect(onRetry).toHaveBeenCalledWith('Hoeveel studenten heeft de HU?')
    expect(onRapport).not.toHaveBeenCalled()
  })

  it('is disabled while a run or a report is going', async () => {
    await render({ herstel: 'rapport', onRapport: vi.fn(), busy: true })
    expect(buttons()).toHaveLength(2)
    expect(buttons().every(b => b.disabled)).toBe(true)
  })

  it('offers only the question again when no report can be made', async () => {
    await render({ herstel: 'rapport', onRapport: null })
    expect(labels()).toEqual(['Vraag opnieuw stellen'])
  })
})

describe('alternativeModel', () => {
  it('is the first model that is not the failed one', () => {
    expect(alternativeModel(MODELS, 'claude-sonnet').id).toBe('gpt-oss-120b')
    expect(alternativeModel([], 'x')).toBeNull()
  })
})

describe('offersRetry (#405)', () => {
  it('biedt herstel bij een fout en bij een deelantwoord, niet bij een gewoon antwoord', () => {
    expect(offersRetry({ isError: true })).toBe(true)
    expect(offersRetry({ partial: true, content: 'Dit is een deelantwoord.' })).toBe(true)
    expect(offersRetry({ content: 'Het zijn er 36.201.', done: true })).toBe(false)
  })
})
