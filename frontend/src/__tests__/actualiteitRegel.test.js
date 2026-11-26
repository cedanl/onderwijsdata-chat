// @vitest-environment jsdom
// #1266: onder een antwoord met voorlopige CBS-cijfers staat de regel "Let op: voorlopig cijfer" uit het veld
// `actualiteit` van message_end (agent/bronvermelding.py), en die regel gaat mee in de kopie en de exports.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'
import { kopieerTekst } from '../answerBlocks'
import { voorbehoudRegels } from '../voorbehoud'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('de regel over voorlopige cijfers onder een antwoord (#1266)', () => {
  const regel = 'Let op: voorlopig cijfer: 2025/26 in 85423NED. CBS kan het nog herzien.'
  const msg = { role: 'assistant', done: true, content: 'Er zijn 12.345 studenten.', bronnen: ['CBS · tabel'], actualiteit: [regel, '', 7] }

  it('staat onder het antwoord, één keer, zonder lege of vreemde regels', async () => {
    await render(createElement(Message, { msg }))
    expect([...container.querySelectorAll('.message-actualiteit')].map(p => p.textContent)).toEqual([regel])
  })

  it('gaat mee in de kopie en in de voorbehoudregels van een export', async () => {
    await render(createElement('div'))
    expect(kopieerTekst(msg)).toContain(regel)
    expect(voorbehoudRegels(msg)).toContain(regel)
  })

  it('ontbreekt zonder het veld', async () => {
    await render(createElement(Message, { msg: { ...msg, actualiteit: undefined } }))
    expect(container.querySelector('.message-actualiteit')).toBeNull()
  })
})
