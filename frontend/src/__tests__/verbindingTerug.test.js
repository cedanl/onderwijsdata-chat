// @vitest-environment jsdom
// #617: na een verbindingsbreuk blijft het antwoord bewust onvolledig staan met "Probeer opnieuw". Zodra de
// verbinding terug is, zegt de regel dat en licht de knop op; er komt geen automatische tweede run.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = null
})

const afgebroken = { id: 2, role: 'assistant', content: 'Er waren 475', tools: [], done: true, interrupted: true }

function render(props) {
  if (!root) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  }
  act(() => root.render(createElement(Message, { msg: afgebroken, herhaal: props.herhaal ?? vi.fn(), ...props })))
  return container.querySelector('.message-stopped')
}

describe('een afgebroken antwoord', () => {
  it('zegt zonder verbinding dat het antwoord onvolledig is', () => {
    const regel = render({ verbinding: false })
    expect(regel.textContent).toContain('Verbinding verbroken — antwoord onvolledig')
    expect(regel.querySelector('.message-continue--licht')).toBeNull()
  })

  it('zegt met de verbinding terug dat opnieuw proberen kan, als melding, en laat de knop oplichten', () => {
    render({ verbinding: false })
    const regel = render({ verbinding: true })
    expect(regel.textContent).toContain('Verbinding terug — probeer opnieuw')
    expect(regel.getAttribute('aria-live')).toBe('polite')
    expect(regel.classList.contains('verbinding-terug')).toBe(true)
    expect(regel.querySelector('button.message-continue--licht').textContent).toBe('Probeer opnieuw')
  })

  it('start niets vanzelf: alleen een tik op de knop herhaalt de vraag, één keer', () => {
    const herhaal = vi.fn()
    const regel = render({ verbinding: true, herhaal })
    expect(herhaal).not.toHaveBeenCalled()
    act(() => regel.querySelector('button').click())
    expect(herhaal).toHaveBeenCalledOnce()
  })
})
