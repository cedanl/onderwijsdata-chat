// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ErrorRetry, { alternativeModel } from '../components/ErrorRetry'

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

  it('is disabled while a run is going', async () => {
    await render({ failedModel: 'gpt-oss-120b', busy: true })
    expect(buttons().every(b => b.disabled)).toBe(true)
  })

  it('shows nothing without a question to retry', async () => {
    await render({ question: undefined })
    expect(buttons()).toEqual([])
  })
})

describe('alternativeModel', () => {
  it('is the first model that is not the failed one', () => {
    expect(alternativeModel(MODELS, 'claude-sonnet').id).toBe('gpt-oss-120b')
    expect(alternativeModel([], 'x')).toBeNull()
  })
})
