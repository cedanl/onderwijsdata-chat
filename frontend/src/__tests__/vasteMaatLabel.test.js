// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'
import { useChat } from '../hooks/useChat'
import { conversationMarkdown } from '../conversationExport'
import { conversationMessages } from '../conversationStore'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// #1242: een antwoord dat alleen op get_maat rust, krijgt "Vaste maat: <naam>" eronder. De server zet het veld uit de
// stappen (agent/vaste_maat.py); de frontend bewaart het bij het bericht, toont het en neemt het mee in de export.
const VASTE_MAAT = {
  maat: 'ingeschreven_personen_ho',
  teldefinitie: 'personen: hoofdinschrijvingen op 1 oktober, elke persoon één keer in het hele ho (DUO p01hoinges)',
  vastgelegd_in: '#188',
  vastgelegd_op: '2026-10-14',
}
const ANTWOORD = {
  role: 'assistant', done: true, content: 'De HU had in 2024/25 38.000 ingeschreven personen.',
  bronnen: ['DUO p01hoinges'], vaste_maat: VASTE_MAAT,
  tools: [{ name: 'get_maat', label: 'Vaste maat opgehaald', done: true, snippet: 'df = ...', exportKey: 'duo:p01:a' }],
}

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    FakeWebSocket.last = this
  }
  send() {}
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

async function chatMet(events) {
  globalThis.WebSocket = FakeWebSocket
  let chat
  function Harness() {
    chat = useChat()
    return null
  }
  await act(async () => { root.render(createElement(Harness)) })
  await act(async () => { for (const ev of events) FakeWebSocket.last.emit(ev) })
  return chat.messages.filter(m => m.role === 'assistant')
}

const render = msg => act(() => root.render(createElement(Message, { msg })))

describe('useChat bewaart de vaste maat (#1242)', () => {
  it('zet vaste_maat uit message_end op het bericht, en alleen daar', async () => {
    const [met, zonder] = await chatMet([
      { type: 'message_start' },
      { type: 'message_end', content: ANTWOORD.content, bronnen: ANTWOORD.bronnen, vaste_maat: VASTE_MAAT },
      { type: 'message_start' },
      { type: 'message_end', content: 'Een ander antwoord.', bronnen: ['CBS 85354NED'] },
    ])
    expect(met.vaste_maat).toEqual(VASTE_MAAT)
    expect(zonder).not.toHaveProperty('vaste_maat')
  })

  it('negeert een vaste_maat die niet klopt', async () => {
    const [msg] = await chatMet([
      { type: 'message_start' },
      { type: 'message_end', content: 'Tekst.', vaste_maat: { maat: 'x' } },
    ])
    expect(msg).not.toHaveProperty('vaste_maat')
  })
})

describe('het label onder het antwoord (#1242)', () => {
  it('toont "Vaste maat: <naam>" met teldefinitie en vastlegging in een uitklap', () => {
    render(ANTWOORD)
    const label = container.querySelector('details.vaste-maat')
    expect(label).not.toBeNull()
    expect(label.querySelector('summary').textContent).toBe('Vaste maat: ingeschreven_personen_ho')
    expect(label.open).toBe(false)
    const uitklap = label.textContent
    expect(uitklap).toContain(`Teldefinitie: ${VASTE_MAAT.teldefinitie}`)
    expect(uitklap).toContain('Vastgelegd in #188 op 14 oktober 2026.')
    // Het label zegt welke route het getal gaf, niet dat het klopt.
    expect(uitklap).toContain('niet dat het gecontroleerd is')
  })

  it('staat direct onder de tekst, vóór de vaste blokken', () => {
    render(ANTWOORD)
    const label = container.querySelector('.vaste-maat')
    const blokken = container.querySelector('.answer-blocks')
    expect(label.compareDocumentPosition(blokken) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('ontbreekt zonder het veld, ook als de modeltekst "vaste maat" zegt', () => {
    const { vaste_maat: _weg, ...zonder } = ANTWOORD
    render({ ...zonder, content: 'Dit is een vaste maat: ingeschreven_personen_ho.' })
    expect(container.querySelector('.vaste-maat')).toBeNull()
  })

  it('ontbreekt bij een onleesbaar veld uit een oud of veranderd bericht', () => {
    render({ ...ANTWOORD, vaste_maat: 'ingeschreven_personen_ho' })
    expect(container.querySelector('.vaste-maat')).toBeNull()
  })
})

describe('de vaste maat in export en heropenen (#1242)', () => {
  const GESPREK = [{ role: 'user', content: 'Hoeveel studenten heeft de HU?' }, ANTWOORD]

  it('staat in de gespreksexport onder het antwoord', () => {
    const md = conversationMarkdown(GESPREK, { datum: '25 november 2026' })
    expect(md).toContain('**Vaste maat: ingeschreven_personen_ho**')
    expect(md).toContain(`Teldefinitie: ${VASTE_MAAT.teldefinitie}`)
    expect(md).toContain('Vastgelegd in #188 op 14 oktober 2026.')
    expect(md.indexOf('### Antwoord')).toBeLessThan(md.indexOf('Vaste maat:'))
  })

  it('staat niet in de export van een antwoord zonder het veld', () => {
    const md = conversationMarkdown([GESPREK[0], { ...ANTWOORD, vaste_maat: undefined }], { datum: '25 november 2026' })
    expect(md).not.toContain('Vaste maat:')
  })

  it('overleeft het heropenen van een bewaard gesprek', () => {
    const heropend = conversationMessages({ messages: JSON.stringify(GESPREK) })
    expect(heropend[1].vaste_maat).toEqual(VASTE_MAAT)
    render(heropend[1])
    expect(container.querySelector('.vaste-maat summary').textContent).toBe('Vaste maat: ingeschreven_personen_ho')
  })
})
