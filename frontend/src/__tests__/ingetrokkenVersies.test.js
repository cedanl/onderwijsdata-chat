// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import IngetrokkenVersies from '../components/IngetrokkenVersies'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

function render(versies, eindtekst = 'Het zijn er 36.201.') {
  container = document.createElement('div')
  root = createRoot(container)
  act(() => root.render(createElement(IngetrokkenVersies, { versies, eindtekst })))
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

  // CH-01: boven 4 van 8 correcte antwoorden stond een leeg uitklapblok, of een blok met
  // dezelfde tekst als het eindantwoord.
  it('toont niets als de ingetrokken versie gelijk is aan het eindantwoord', () => {
    expect(render([{ tekst: ' Het zijn er 36.201.\n', naStap: 2 }]).innerHTML).toBe('')
  })

  it('toont niets voor een lege versie', () => {
    expect(render([{ tekst: '  \n', naStap: 2 }]).innerHTML).toBe('')
  })

  it('noemt de reden van de controle in gewone taal', () => {
    const el = render([{ tekst: 'Het zijn er 99.', naStap: 2, reden: ['99 staat niet in de opgehaalde data.'] }])
    expect(el.textContent).toContain('99 staat niet in de opgehaalde data.')
  })
})
