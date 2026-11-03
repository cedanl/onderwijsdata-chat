// @vitest-environment jsdom
// ADR-009 (#875): de server legt het bewijs van een antwoord vast onder de sha256 van de `content` van `message_end`
// en zoekt het terug via de tekst in de PUT-body. Verandert de client die tekst onderweg (inkorten, opschonen,
// witruimte), dan vindt de hash niets en herstelt een heropend gesprek niets. Deze test legt vast dat de tekst van
// `message_end` ongewijzigd in het bericht en in de body van de PUT terechtkomt.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import { conversationRecord } from '../conversationStore'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

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
let chat

beforeEach(async () => {
  globalThis.WebSocket = FakeWebSocket
  container = document.createElement('div')
  root = createRoot(container)
  function Harness() {
    chat = useChat()
    return null
  }
  await act(async () => { root.render(createElement(Harness)) })
})

afterEach(() => {
  act(() => root.unmount())
})

// Wat de server stuurt is soms ruim: kopregels, spaties, een afsluitende regelovergang, niet-ASCII en een tabel.
const TEKSTEN = [
  'In 2024 waren er 470.000 studenten.',
  '  Ik ga uit van het studiejaar 2023/24.\n\n| Jaar | Aantal |\n|---|---|\n| 2024 | 470.000 |\n\n',
  'Café-studenten: één op de drie, “zoals gezegd” – 🎓\n',
  '',
]

describe('de tekst van message_end in de PUT-body', () => {
  it.each(TEKSTEN)('is byte voor byte de content van het bericht (%j)', async tekst => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'deel van de tekst' })
      ws.emit({ type: 'message_end', content: tekst, actions: [], bronnen: [] })
    })

    const record = conversationRecord('c1', [{ id: 1, role: 'user', content: 'Vraag?', done: true }, ...chat.messages])
    const body = JSON.parse(JSON.stringify({ title: record.title, timestamp: record.timestamp, messages: record.messages }))
    const antwoord = body.messages.find(m => m.role === 'assistant')

    expect(antwoord.content).toBe(tekst)
  })
})
