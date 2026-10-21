// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import FeedbackModal from '../components/FeedbackModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const QUESTIONS = [
  { id: 'nuttig', text: 'Hoe nuttig was dit rapport voor je?', type: 'scale', options: ['1', '2', '3', '4', '5'], labels: ['Niet', 'Zeer'] },
  { id: 'mist', text: 'Mist er iets in dit rapport?', type: 'text' },
  { id: 'dashboardtool', text: 'Welke dashboardtool gebruiken jullie?', type: 'multi', section: 'Over jouw instelling', options: ['Power BI', 'Tableau', 'Anders', 'Weet ik niet'] },
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

  it('says what is kept, for how long (#485), and that deleting the conversation does not remove it (#552)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    const intro = [...container.querySelectorAll('[role="dialog"] .feedback-intro')].map(p => p.textContent)
    expect(intro[0]).toBe('Alle vragen zijn optioneel. Je antwoorden helpen ons de rapporten te verbeteren.')
    expect(intro[1]).toBe(
      'We bewaren je antwoorden en de titel van het rapport bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.',
    )
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

  it('shows the heading of a section above its first question', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    const headings = [...container.querySelectorAll('h3')].map(h => h.textContent)
    expect(headings).toEqual(['Over jouw instelling'])
  })

  it('lets a multi question take several options, with free text behind Anders', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    await render()

    const box = value => container.querySelector(`input[type="checkbox"][value="${value}"]`)
    expect(container.querySelector('input[aria-label="Anders, welke?"]')).toBeNull()
    await act(async () => { box('Power BI').click() })
    await act(async () => { box('Tableau').click() })
    await act(async () => { box('Tableau').click() })
    await act(async () => { box('Anders').click() })
    const detail = container.querySelector('input[aria-label="Anders, welke?"]')
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(detail, 'Metabase')
      detail.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(submitButton().disabled).toBe(false)
    await submit()

    expect(JSON.parse(fetch.mock.calls[1][1].body).answers).toEqual({ dashboardtool: ['Power BI', 'Anders: Metabase'] })
  })

  it('does not count a multi question without a choice as an answer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    const box = container.querySelector('input[type="checkbox"][value="Power BI"]')
    await act(async () => { box.click() })
    expect(submitButton().disabled).toBe(false)
    await act(async () => { box.click() })
    expect(submitButton().disabled).toBe(true)
  })
})
