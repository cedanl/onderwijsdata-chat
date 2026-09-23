// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    this.sent = []
    FakeWebSocket.last = this
  }
  send(data) { this.sent.push(JSON.parse(data)) }
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container
let chat

function Harness() {
  chat = useChat()
  return null
}

beforeEach(async () => {
  globalThis.WebSocket = FakeWebSocket
  container = document.createElement('div')
  root = createRoot(container)
  await act(async () => { root.render(createElement(Harness)) })
})

afterEach(() => {
  act(() => root.unmount())
})

const assistantMessages = () => chat.messages.filter(m => m.role === 'assistant')

describe('useChat streaming', () => {
  it('keeps every delta when message_end arrives in the same batch', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'D' })
      ws.emit({ type: 'text_delta', content: 'U' })
      ws.emit({ type: 'text_delta', content: 'O' })
      ws.emit({ type: 'message_end', content: 'DUO' })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('DUO')
    expect(msg.done).toBe(true)
  })

  it('treats message_end content as the final text', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await act(async () => { ws.emit({ type: 'text_delta', content: 'de registratie van' }) })
    await act(async () => {
      ws.emit({ type: 'message_end', content: 'de registratie van studiekeuze en -financiering.' })
    })
    expect(assistantMessages()[0].content).toBe('de registratie van studiekeuze en -financiering.')
  })

  it('applies late updates to their own message when the next one has started', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'eerste' })
      ws.emit({ type: 'message_end', content: 'eerste' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'tweede' })
      ws.emit({ type: 'message_end', content: 'tweede' })
    })
    expect(assistantMessages().map(m => m.content)).toEqual(['eerste', 'tweede'])
    expect(assistantMessages().every(m => m.done)).toBe(true)
  })
})

describe('useChat report errors', () => {
  it('shows a report error as a lasting chat message, not a toast', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'report_generating' })
      ws.emit({ type: 'report_error', message: 'Rapport kon niet worden gemaakt. Probeer het opnieuw.' })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('Rapport kon niet worden gemaakt. Probeer het opnieuw.')
    expect(msg.isError).toBe(true)
    expect(chat.toasts).toEqual([])
    expect(chat.reportBusy).toBe(false)
  })
})
