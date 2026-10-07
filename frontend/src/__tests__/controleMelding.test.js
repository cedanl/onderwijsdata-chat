// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #429: a withheld answer says "Hieronder staat wat er niet klopte", but the chart with its
// buttons stood between that sentence and the reasons. The reasons now follow the text.
describe('control notes under an answer', () => {
  it('come directly after the answer text, before any chart', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const figure = JSON.stringify({ data: [{ type: 'bar', x: ['2024'], y: [1] }], layout: {} })
    const msg = {
      role: 'assistant', done: true,
      content: 'Dit antwoord is ingehouden. Hieronder staat wat er niet klopte.',
      figures: [{ json: figure, label: 'Instroom' }],
      controle: ['1234 staat niet in de opgehaalde data.'],
    }
    await act(async () => { root.render(createElement(Message, { msg })) })
    const melding = container.querySelector('.message-controle')
    const grafiek = container.querySelector('.plotly-figure-wrap')
    expect(melding.textContent).toBe('Let op: 1234 staat niet in de opgehaalde data.')
    expect(grafiek).not.toBeNull()
    expect(melding.compareDocumentPosition(grafiek) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
