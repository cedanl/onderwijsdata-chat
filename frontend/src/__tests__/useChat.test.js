// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
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

describe('useChat stop', () => {
  it('marks an aborted answer as stopped and keeps its partial text', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Half antwoord' })
      ws.emit({ type: 'message_end', aborted: true })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('Half antwoord')
    expect(msg.stopped).toBe(true)
    expect(msg.done).toBe(true)
  })

  it('marks an answer that hit the output limit as truncated', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Conclusie – niet beschikbaar in de', truncated: true })
    })
    expect(assistantMessages()[0].truncated).toBe(true)
  })

  it('keeps what the server check still found wrong on the answer', async () => {
    // #185, #187: a problem that survived the correction round stays visible.
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Toch 6.340.', controle: ['6.340 staat niet in de opgehaalde data.'] })
    })
    expect(assistantMessages()[0].controle).toEqual(['6.340 staat niet in de opgehaalde data.'])
  })

  it('drops the unchecked answer when the server withdraws it for a correction', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'In totaal 6.340.' })
      ws.emit({ type: 'message_cancel' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'In totaal 5.943.' })
    })
    expect(assistantMessages().map(m => m.content)).toEqual(['In totaal 5.943.'])
  })

  it('marks a final answer without any text as empty', async () => {
    // Live-audit 6: message_end without text left a silent, invisible turn.
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: '' })
    })
    expect(assistantMessages()[0]).toMatchObject({ empty: true, done: true })
  })

  it('does not mark a stopped answer without text as empty', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', aborted: true })
    })
    const [msg] = assistantMessages()
    expect(msg.stopped).toBe(true)
    expect(msg.empty).toBeUndefined()
  })

  it('does not mark a normal answer as stopped', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Klaar' })
    })
    expect(assistantMessages()[0].stopped).toBeFalsy()
  })
})

describe('useChat new conversation', () => {
  it('asks the server for a fresh session and holds messages until it confirms', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.startNewConversation() })
    expect(ws.sent).toContainEqual({ action: 'reset' })
    expect(chat.resetting).toBe(true)

    await act(async () => { chat.send('Welke afkorting noemde ik eerder?') })
    expect(ws.sent.filter(m => m.action === 'message')).toEqual([])

    await act(async () => { ws.emit({ type: 'reset_done' }) })
    expect(chat.resetting).toBe(false)
    await act(async () => { chat.send('Welke afkorting noemde ik eerder?') })
    expect(ws.sent.filter(m => m.action === 'message')).toHaveLength(1)
  })

  it('clears the visible messages', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'oud antwoord' })
    })
    await act(async () => { chat.startNewConversation() })
    expect(chat.messages).toEqual([])
  })
})

describe('useChat connection loss', () => {
  const drop = async (ws) => {
    await act(async () => {
      ws.readyState = 3
      ws.onclose({ code: 1006 })
    })
  }

  afterEach(() => vi.useRealTimers())

  it('ends a half-streamed answer visibly and accepts the next question after reconnecting', async () => {
    vi.useFakeTimers()
    const ws = FakeWebSocket.last
    await act(async () => {
      chat.send('Eerste vraag')
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Half' })
    })
    await drop(ws)

    const [msg] = assistantMessages()
    expect(msg).toMatchObject({ content: 'Half', done: true, interrupted: true })
    expect(chat.busy).toBe(false)
    expect(chat.thinking).toBe(false)

    await act(async () => { vi.advanceTimersByTime(1000) })
    const reconnected = FakeWebSocket.last
    expect(reconnected).not.toBe(ws)
    await act(async () => { reconnected.onopen() })
    let accepted
    await act(async () => { accepted = chat.send('Tweede vraag') })
    expect(accepted).toBe(true)
    expect(reconnected.sent).toContainEqual({ action: 'message', content: 'Tweede vraag' })
  })

  it('tells the user when a question got no answer before the connection dropped', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Vraag') })
    await drop(ws)
    const [msg] = assistantMessages()
    expect(msg.isError).toBe(true)
    expect(chat.busy).toBe(false)
  })

  it('also recovers when the answer to a clarification choice is cut off', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      chat.sendClarification('HBO')
      ws.emit({ type: 'message_start' })
    })
    await drop(ws)
    expect(chat.busy).toBe(false)
    expect(assistantMessages()[0].interrupted).toBe(true)
  })

  it('refuses to send while the connection is down', async () => {
    const ws = FakeWebSocket.last
    await drop(ws)
    let accepted
    await act(async () => { accepted = chat.send('Vraag') })
    expect(accepted).toBe(false)
    expect(chat.messages).toEqual([])
  })
})
