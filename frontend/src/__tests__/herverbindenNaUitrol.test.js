// @vitest-environment jsdom
// #677: productie draait bewust één pod, dus elke uitrol is een onderbreking. Uvicorn sluit elke chatsocket dan met
// 1012 (Service Restart). Daarna gaf de app na vier pogingen (± 15 s) op met "Geen verbinding.", terwijl de nieuwe pod
// minuten nodig heeft (op test 8 minuten 503 bij Recreate), en zei hij niet waarom.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import { BACKOFF_DELAYS, HERSTART, HERSTART_MS, MAX_RETRIES, createRetry } from '../socketHealth'
import { connectionStatus, connectionStatusText, wachtOpGebruiker } from '../connectionStatus'
import ConnectionStatus from '../components/ConnectionStatus'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let hook

async function mount() {
  function Harness() {
    hook = useChat()
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
}

const wacht = ms => act(async () => { vi.advanceTimersByTime(ms) })
const LANGSTE = Math.max(...BACKOFF_DELAYS)

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })))
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('createRetry na een herstart van de server (#677)', () => {
  it('blijft na 1012 proberen tot HERSTART_MS, en geeft dan alsnog op', () => {
    const connect = vi.fn()
    const opgegeven = vi.fn()
    const retry = createRetry(connect, { opgegeven })

    retry.herstart()
    // Ruim voorbij de gewone reeks: elke mislukte poging plant een volgende.
    let verstreken = 0
    while (verstreken < HERSTART_MS - LANGSTE) {
      retry.schedule()
      vi.advanceTimersByTime(LANGSTE)
      verstreken += LANGSTE
    }
    expect(connect.mock.calls.length).toBeGreaterThan(MAX_RETRIES * 5)
    expect(opgegeven).not.toHaveBeenCalled()

    vi.advanceTimersByTime(LANGSTE)
    retry.schedule()
    expect(opgegeven).toHaveBeenCalledOnce()
  })

  it('een socket die opent, beëindigt de herstart: daarna weer de gewone reeks', () => {
    const connect = vi.fn()
    const opgegeven = vi.fn()
    const retry = createRetry(connect, { opgegeven })

    retry.herstart()
    retry.opened()
    retry.reset()
    for (let i = 0; i < MAX_RETRIES; i++) {
      retry.schedule()
      vi.advanceTimersByTime(BACKOFF_DELAYS[i])
    }
    retry.schedule()
    expect(opgegeven).toHaveBeenCalledOnce()
  })
})

describe('de status tijdens een uitrol (#677)', () => {
  it('zegt dat de app wordt bijgewerkt, zonder knop; offline en een open verbinding gaan voor', () => {
    expect(connectionStatus({ online: true, connected: false, bijwerken: true })).toBe('bijwerken')
    expect(connectionStatus({ online: false, connected: false, bijwerken: true })).toBe('offline')
    expect(connectionStatus({ online: true, connected: true, bijwerken: true })).toBe('ok')
    expect(wachtOpGebruiker('bijwerken')).toBe(false)
    expect(connectionStatusText('bijwerken')).toBe('De app wordt bijgewerkt. De verbinding komt vanzelf terug.')
  })

  it('ConnectionStatus toont die tekst', async () => {
    const div = document.createElement('div')
    root = createRoot(div)
    await act(async () => { root.render(createElement(ConnectionStatus, { connected: false, bijwerken: true })) })
    expect(div.querySelector('[role="status"]').textContent).toBe(
      'De app wordt bijgewerkt. De verbinding komt vanzelf terug.',
    )
    expect(div.querySelector('button')).toBeNull()
  })
})

describe('useChat bij een uitrol (#677)', () => {
  it('1012: "wordt bijgewerkt", blijft minuten proberen en is terug zodra de nieuwe pod opent', async () => {
    await mount()
    await act(async () => { FakeWebSocket.last.open() })
    await act(async () => { FakeWebSocket.last.finishClose(HERSTART) })
    expect(hook.bijwerken).toBe(true)

    // De nieuwe pod is er nog niet: elke handshake faalt als een kale 1006, minutenlang.
    for (let i = 0; i < MAX_RETRIES * 4; i++) {
      await wacht(LANGSTE)
      await act(async () => { FakeWebSocket.last.finishClose() })
    }
    expect(hook.opgegeven).toBeNull()
    expect(hook.bijwerken).toBe(true)

    await wacht(LANGSTE)
    await act(async () => { FakeWebSocket.last.open() })
    expect(hook.connected).toBe(true)
    expect(hook.bijwerken).toBe(false)
  })

  it('komt de pod niet terug binnen HERSTART_MS, dan "Geen verbinding." met de knop', async () => {
    await mount()
    await act(async () => { FakeWebSocket.last.finishClose(HERSTART) })
    for (let t = 0; t <= HERSTART_MS + LANGSTE; t += LANGSTE) {
      await wacht(LANGSTE)
      if (hook.opgegeven) break
      await act(async () => { FakeWebSocket.last.finishClose() })
    }
    expect(hook.opgegeven).toBe('weg')
    expect(hook.bijwerken).toBe(false)
  })

  it('een gewone onderbreking is geen uitrol', async () => {
    await mount()
    await act(async () => { FakeWebSocket.last.open() })
    await act(async () => { FakeWebSocket.last.finishClose(1006) })
    expect(hook.bijwerken).toBe(false)
  })
})
