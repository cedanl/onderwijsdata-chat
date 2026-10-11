// @vitest-environment jsdom
// #489: verbindingsverlies tijdens een lopende vraag gaf geen melding — `connected`
// werd pas false bij de TCP-timeout. Het offline-event en de heartbeat dichten dat gat.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 3
  static instances = []
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    this.sent = []
    FakeWebSocket.instances.push(this)
    FakeWebSocket.last = this
  }
  send(data) { this.sent.push(JSON.parse(data)) }
  close() {
    if (this.readyState === FakeWebSocket.CLOSED) return
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code: 1006 })
  }
  open() { this.onopen?.() }
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container
let chat

function Harness() {
  chat = useChat()
  return null
}

// De heartbeat start bij onopen; tests met fake timers zetten die daarom vóór mount aan.
async function mount() {
  container = document.createElement('div')
  root = createRoot(container)
  await act(async () => { root.render(createElement(Harness)) })
  await act(async () => { FakeWebSocket.last.open() })
}

beforeEach(() => {
  FakeWebSocket.instances = []
  globalThis.WebSocket = FakeWebSocket
})

afterEach(() => {
  act(() => root.unmount())
  vi.useRealTimers()
})

describe('verbindingsverlies tijdens een lopende vraag', () => {
  it('toont bij het offline-event meteen de herstelmelding en sluit de beurt af', async () => {
    await mount()
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Hoeveel studenten telt het mbo?') })
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Het aantal stud' })
    })
    expect(chat.connected).toBe(true)
    expect(chat.busy).toBe(true)

    await act(async () => { window.dispatchEvent(new Event('offline')) })

    expect(chat.connected).toBe(false)
    expect(chat.busy).toBe(false)
    const [msg] = chat.messages.filter(m => m.role === 'assistant')
    expect(msg.done).toBe(true)
    expect(msg.interrupted).toBe(true)
  })

  it('verbindt bij het online-event direct opnieuw, zonder op de backoff te wachten', async () => {
    await mount()
    await act(async () => { window.dispatchEvent(new Event('offline')) })
    const voor = FakeWebSocket.instances.length

    await act(async () => { window.dispatchEvent(new Event('online')) })

    expect(FakeWebSocket.instances.length).toBe(voor + 1)
    await act(async () => { FakeWebSocket.last.open() })
    expect(chat.connected).toBe(true)
  })

  it('laat een open verbinding met rust bij een online-event', async () => {
    await mount()
    const voor = FakeWebSocket.instances.length
    await act(async () => { window.dispatchEvent(new Event('online')) })
    expect(FakeWebSocket.instances.length).toBe(voor)
  })

  it('sluit via de heartbeat een stil gestorven verbinding', async () => {
    vi.useFakeTimers()
    await mount()
    const ws = FakeWebSocket.last
    // Geen enkel bericht komt terug: na ping + wachttijd gaat de verbinding dicht.
    await act(async () => { vi.advanceTimersByTime(25000) })
    expect(ws.sent).toContainEqual({ action: 'ping' })
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED)
    expect(chat.connected).toBe(false)
  })

  it('houdt de verbinding open zolang de server pong blijft sturen', async () => {
    vi.useFakeTimers()
    await mount()
    const ws = FakeWebSocket.last
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        vi.advanceTimersByTime(15000)
        ws.emit({ type: 'pong' })
      })
    }
    expect(ws.readyState).toBe(FakeWebSocket.OPEN)
    expect(chat.connected).toBe(true)
  })
})
