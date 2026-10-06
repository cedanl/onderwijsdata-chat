// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import IngetrokkenVersies from '../components/IngetrokkenVersies'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

function render(versies) {
  container = document.createElement('div')
  root = createRoot(container)
  act(() => root.render(createElement(IngetrokkenVersies, { versies })))
  return container
}

afterEach(() => act(() => root.unmount()))

describe('IngetrokkenVersies (#398)', () => {
  it('toont de ingetrokken tekst ingeklapt', () => {
    const el = render([{ tekst: 'Het zijn er 99.', naStap: 2 }])
    const details = el.querySelector('details')
    expect(details.open).toBe(false)
    expect(details.querySelector('summary').textContent).toBe('Eerdere versie ingetrokken na controle')
    expect(details.textContent).toContain('Het zijn er 99.')
  })

  it('toont niets zonder ingetrokken versies', () => {
    expect(render(undefined).innerHTML).toBe('')
  })
})
