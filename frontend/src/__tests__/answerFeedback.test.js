// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({ fetchAnswerFeedback: vi.fn(), postAnswerFeedback: vi.fn() }))

import { fetchAnswerFeedback, postAnswerFeedback } from '../api'
import AnswerFeedback from '../components/AnswerFeedback'
import { useAnswerFeedback } from '../hooks/useAnswerFeedback'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

function mount(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  return act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const knop = label => container.querySelector(`button[aria-label="${label}"]`)
const tekstknop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent === tekst)

// #248: per antwoord een oordeel; bij 👎 een toelichting.
describe('AnswerFeedback', () => {
  it('stuurt een duim omhoog meteen', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    await mount(createElement(AnswerFeedback, { value: null, onSubmit }))
    await act(async () => knop('Goed antwoord').click())
    expect(onSubmit).toHaveBeenCalledWith('up', '')
  })

  it('vraagt bij een duim omlaag eerst wat er niet klopt', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    await mount(createElement(AnswerFeedback, { value: null, onSubmit }))
    await act(async () => knop('Fout antwoord').click())
    expect(onSubmit).not.toHaveBeenCalled()

    const veld = container.querySelector('textarea')
    expect(document.activeElement).toBe(veld)
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(veld, 'HU had er 40.000')
      veld.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => tekstknop('Verstuur').click())
    expect(onSubmit).toHaveBeenCalledWith('down', 'HU had er 40.000')
    expect(container.querySelector('textarea')).toBeNull()
  })

  it('toont het gegeven oordeel, ook na heropenen', async () => {
    await mount(createElement(AnswerFeedback, { value: 'down', onSubmit: vi.fn() }))
    expect(knop('Fout antwoord').getAttribute('aria-pressed')).toBe('true')
    expect(knop('Goed antwoord').getAttribute('aria-pressed')).toBe('false')
  })

  it('zegt het als opslaan mislukt', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('Antwoord niet gevonden'))
    await mount(createElement(AnswerFeedback, { value: null, onSubmit }))
    await act(async () => knop('Goed antwoord').click())
    expect(container.querySelector('[role="alert"]').textContent).toBe('Feedback opslaan lukt niet: Antwoord niet gevonden')
    expect(container.querySelector('[role="status"]').textContent).toBe('')
  })
})

// #492: a visible confirmation, announced through a live region that is always there.
describe('AnswerFeedback confirmation', () => {
  const BEDANKT = 'Bedankt voor je feedback!'
  const status = () => container.querySelector('[role="status"]')

  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  async function typeAndSend(tekst) {
    const veld = container.querySelector('textarea')
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(veld, tekst)
      veld.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => tekstknop('Verstuur').click())
  }

  it('thanks after a thumbs-up in the live region that was already there', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    const region = status()
    expect(region.textContent).toBe('')
    await act(async () => knop('Goed antwoord').click())
    expect(status()).toBe(region)
    expect(region.textContent).toBe(BEDANKT)
    expect(region.className).toBe('answer-feedback-confirm')
  })

  it('thanks after a thumbs-down and Verstuur, and closes the form', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    const region = status()
    await act(async () => knop('Fout antwoord').click())
    await typeAndSend('klopt niet')
    expect(container.querySelector('textarea')).toBeNull()
    expect(status()).toBe(region)
    expect(region.textContent).toBe(BEDANKT)
  })

  it('disappears after 4 seconds and shows again on a new submit', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    await act(async () => knop('Goed antwoord').click())
    await act(async () => { vi.advanceTimersByTime(3999) })
    expect(status().textContent).toBe(BEDANKT)
    await act(async () => { vi.advanceTimersByTime(1) })
    expect(status().textContent).toBe('')

    await act(async () => knop('Goed antwoord').click())
    expect(status().textContent).toBe(BEDANKT)
  })

  it('restarts the timeout on a new submit', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    await act(async () => knop('Goed antwoord').click())
    await act(async () => { vi.advanceTimersByTime(3000) })
    await act(async () => knop('Goed antwoord').click())
    await act(async () => { vi.advanceTimersByTime(3000) })
    expect(status().textContent).toBe(BEDANKT)
  })

  it('hides on the next interaction and stays hidden after Annuleer', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    await act(async () => knop('Goed antwoord').click())
    await act(async () => knop('Fout antwoord').click())
    expect(status().textContent).toBe('')
    await act(async () => tekstknop('Annuleer').click())
    expect(status().textContent).toBe('')
  })

  it('shows no confirmation when saving fails', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('Serverfout'))
    await mount(createElement(AnswerFeedback, { value: null, onSubmit }))
    await act(async () => knop('Fout antwoord').click())
    await typeAndSend('klopt niet')
    expect(container.querySelector('[role="alert"]').textContent).toBe('Feedback opslaan lukt niet: Serverfout')
    expect(status().textContent).toBe('')
  })

  it('drops an earlier confirmation when the next submit fails', async () => {
    const onSubmit = vi.fn().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('Serverfout'))
    await mount(createElement(AnswerFeedback, { value: null, onSubmit }))
    await act(async () => knop('Goed antwoord').click())
    expect(status().textContent).toBe(BEDANKT)
    await act(async () => knop('Goed antwoord').click())
    expect(container.querySelector('[role="alert"]')).not.toBeNull()
    expect(status().textContent).toBe('')
  })

  it('clears its timeout on unmount', async () => {
    await mount(createElement(AnswerFeedback, { value: null, onSubmit: vi.fn().mockResolvedValue(undefined) }))
    await act(async () => knop('Goed antwoord').click())
    expect(vi.getTimerCount()).toBe(1)
    act(() => root.unmount())
    expect(vi.getTimerCount()).toBe(0)
    root = { unmount() {} }
  })
})

describe('useAnswerFeedback', () => {
  let feedback

  function Harness(props) {
    feedback = useAnswerFeedback(props)
    return null
  }

  beforeEach(() => {
    fetchAnswerFeedback.mockReset()
    postAnswerFeedback.mockReset()
  })

  it('haalt de oordelen van het gesprek op', async () => {
    fetchAnswerFeedback.mockResolvedValue({ 3: 'up' })
    await mount(createElement(Harness, { conversationId: 'c1', enabled: true, save: vi.fn() }))
    expect(fetchAnswerFeedback).toHaveBeenCalledWith('c1')
    expect(feedback.oordelen).toEqual({ 3: 'up' })
  })

  it('slaat het gesprek eerst op, zodat de server het antwoord kent', async () => {
    fetchAnswerFeedback.mockResolvedValue({})
    const volgorde = []
    const save = vi.fn(async () => { volgorde.push('save') })
    postAnswerFeedback.mockImplementation(async () => { volgorde.push('post') })
    await mount(createElement(Harness, { conversationId: 'c1', enabled: true, save }))
    await act(async () => feedback.submit(1, 'down', 'klopt niet'))
    expect(volgorde).toEqual(['save', 'post'])
    expect(postAnswerFeedback).toHaveBeenCalledWith({ conversation_id: 'c1', message_index: 1, oordeel: 'down', toelichting: 'klopt niet' })
    expect(feedback.oordelen).toEqual({ 1: 'down' })
  })

  it('doet niets als feedback uit staat', async () => {
    await mount(createElement(Harness, { conversationId: 'c1', enabled: false, save: vi.fn() }))
    expect(fetchAnswerFeedback).not.toHaveBeenCalled()
  })
})
