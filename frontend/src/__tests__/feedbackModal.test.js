// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import FeedbackModal from '../components/FeedbackModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const QUESTIONS = [
  { id: 'nuttig', text: 'Hoe nuttig was dit rapport voor je?', type: 'scale', options: ['1', '2', '3', '4', '5'], labels: ['Niet', 'Zeer'] },
  { id: 'mist', text: 'Mist er iets in dit rapport?', type: 'text' },
]
const WORKBOOK = { id: 'wb-1', type: 'report', title: 'Instroom hbo' }

let root
let container

function jsonResponse(status, body) {
  return { ok: status < 400, status, json: async () => body }
}

async function render(props = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(FeedbackModal, { workbook: WORKBOOK, onClose: vi.fn(), onSubmitted: vi.fn(), ...props }))
  })
}

const submitButton = () => container.querySelector('button[type="submit"]')

async function submit() {
  await act(async () => { container.querySelector('form').requestSubmit() })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('FeedbackModal', () => {
  it('shows the questions from the backend and only submits once something is answered', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(container.textContent).toContain('Hoe nuttig was dit rapport voor je?')
    expect(container.querySelector('textarea')).not.toBeNull()
    expect(submitButton().disabled).toBe(true)
  })

  it('posts the answers with the report context and reports success', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    const onSubmitted = vi.fn()
    await render({ onSubmitted })

    await act(async () => { container.querySelector('input[value="4"]').click() })
    expect(submitButton().disabled).toBe(false)
    await submit()

    const [url, options] = fetch.mock.calls[1]
    expect(url).toBe('/api/feedback')
    expect(JSON.parse(options.body)).toEqual({
      workbook_id: 'wb-1', report_type: 'report', report_title: 'Instroom hbo', answers: { nuttig: '4' },
    })
    expect(onSubmitted).toHaveBeenCalledOnce()
  })

  it('shows the backend message when sending fails and stays open', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(429, { detail: 'Je hebt net al feedback op dit rapport gegeven.' }))
    vi.stubGlobal('fetch', fetch)
    const onSubmitted = vi.fn()
    await render({ onSubmitted })

    await act(async () => { container.querySelector('input[value="2"]').click() })
    await submit()

    expect(container.querySelector('[role="alert"]').textContent).toContain('Je hebt net al feedback op dit rapport gegeven.')
    expect(onSubmitted).not.toHaveBeenCalled()
    expect(submitButton().disabled).toBe(false)
  })
})
