// @vitest-environment jsdom
// #1169: een pod die crasht (OOM-kill, node weg, ingress-time-out) sluit zonder 1012. De hook gaf dan na MAX_RETRIES
// pogingen (± 31 s) op met "Geen verbinding.", terwijl de nieuwe pod pas na tientallen seconden klaar is. Nu blijft hij
// daarna op de achtergrond kijken of de server terug is en verbindt hij zonder klik; de knop blijft voor wie niet wil
// wachten, en 1013 en 4003 blijven zonder achtergrondpogingen opgeven (#783).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import { ACHTERGROND_MS, BACKOFF_DELAYS, MAX_RETRIES, createRetry } from '../socketHealth'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let hook
// Of de server antwoordt op /health, en op de websocket: de test zet dit om als de nieuwe pod klaar is.
let serverTerug

async function mount() {
  function Harness() {
    hook = useChat()
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
}

const wacht = ms => act(async () => { vi.advanceTimersByTime(ms) })
const gezondheidsvragen = () => fetch.mock.calls.filter(([url]) => url === '/health')

// Elke poging van de gewone reeks faalt als een kale 1006, zoals bij een weggevallen pod.
async function geefOp() {
  await act(async () => { FakeWebSocket.last.finishClose() })
  for (let i = 0; i < MAX_RETRIES; i++) {
    await wacht(BACKOFF_DELAYS[i])
    await act(async () => { FakeWebSocket.last.finishClose() })
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  serverTerug = false
  vi.stubGlobal('fetch', vi.fn(async url => (url === '/health' && serverTerug
    ? { ok: true, status: 200, json: async () => ({ status: 'ok' }) }
    : { ok: false, status: 503, json: async () => ({}) })))
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('createRetry na de laatste poging (#1169)', () => {
  const opgeven = (retry) => {
    for (let i = 0; i < MAX_RETRIES; i++) {
      retry.schedule()
      vi.advanceTimersByTime(BACKOFF_DELAYS[i])
    }
    retry.schedule()
  }

  it('vraagt elke ACHTERGROND_MS of de server terug is en verbindt pas als hij antwoordt', async () => {
    const connect = vi.fn()
    const opgegeven = vi.fn()
    const bereikbaar = vi.fn().mockResolvedValue(false)
    const retry = createRetry(connect, { opgegeven, bereikbaar })

    opgeven(retry)
    expect(opgegeven).toHaveBeenCalledOnce()
    const gewoon = connect.mock.calls.length

    await vi.advanceTimersByTimeAsync(ACHTERGROND_MS * 2)
    expect(bereikbaar).toHaveBeenCalledTimes(2)
    expect(connect).toHaveBeenCalledTimes(gewoon)

    bereikbaar.mockResolvedValue(true)
    await vi.advanceTimersByTimeAsync(ACHTERGROND_MS)
    expect(connect).toHaveBeenCalledTimes(gewoon + 1)
    expect(bereikbaar).toHaveBeenCalledTimes(3)
  })

  it('stopt zodra een socket opent of de gebruiker opnieuw verbindt, ook als een controle nog loopt', async () => {
    const connect = vi.fn()
    let antwoord
    const bereikbaar = vi.fn(() => new Promise(resolve => { antwoord = resolve }))
    const retry = createRetry(connect, { opgegeven: vi.fn(), bereikbaar })
    opgeven(retry)
    const gewoon = connect.mock.calls.length

    await vi.advanceTimersByTimeAsync(ACHTERGROND_MS)
    retry.reset()
    antwoord(true)
    await vi.advanceTimersByTimeAsync(ACHTERGROND_MS * 3)
    expect(connect).toHaveBeenCalledTimes(gewoon)
    expect(bereikbaar).toHaveBeenCalledTimes(1)

    opgeven(retry)
    retry.opened()
    await vi.advanceTimersByTimeAsync(ACHTERGROND_MS * 3)
    expect(bereikbaar).toHaveBeenCalledTimes(1)
  })
})

describe('useChat na een crash zonder sluitcode 1012 (#1169)', () => {
  it('geeft na ± 30 s op, maar verbindt vanzelf zodra de server na een minuut terug is', async () => {
    await mount()
    await act(async () => { FakeWebSocket.last.open() })
    await geefOp()
    expect(hook.opgegeven).toBe('weg')
    const sockets = FakeWebSocket.instances.length

    // De pod is er nog niet: /health weigert, er komt geen nieuwe socket en de status blijft staan.
    await wacht(ACHTERGROND_MS * 2)
    expect(gezondheidsvragen().length).toBeGreaterThanOrEqual(1)
    expect(FakeWebSocket.instances).toHaveLength(sockets)
    expect(hook.opgegeven).toBe('weg')

    serverTerug = true
    await wacht(ACHTERGROND_MS)
    expect(FakeWebSocket.instances).toHaveLength(sockets + 1)
    await act(async () => { FakeWebSocket.last.open() })
    expect(hook.connected).toBe(true)
    expect(hook.opgegeven).toBeNull()

    // Verbonden: geen controles meer.
    const vragen = gezondheidsvragen().length
    await wacht(ACHTERGROND_MS * 4)
    expect(gezondheidsvragen()).toHaveLength(vragen)
  })

  it('de knop "Opnieuw verbinden" blijft werken en stopt het wachten', async () => {
    await mount()
    await geefOp()
    expect(hook.opgegeven).toBe('weg')
    const sockets = FakeWebSocket.instances.length

    await act(async () => { hook.verbindOpnieuw() })
    expect(FakeWebSocket.instances).toHaveLength(sockets + 1)
    await act(async () => { FakeWebSocket.last.open() })
    const vragen = gezondheidsvragen().length
    await wacht(ACHTERGROND_MS - 1)
    expect(gezondheidsvragen()).toHaveLength(vragen)
  })

  it('1013 en 4003 blijven zonder achtergrondpogingen opgeven', async () => {
    serverTerug = true
    await mount()
    await act(async () => { FakeWebSocket.last.finishClose(4003) })
    await wacht(ACHTERGROND_MS * 10)
    expect(hook.opgegeven).toBe('weg')
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(gezondheidsvragen()).toHaveLength(0)

    await act(async () => { hook.verbindOpnieuw() })
    await act(async () => { FakeWebSocket.last.open(); FakeWebSocket.last.finishClose(1013) })
    await wacht(ACHTERGROND_MS * 10)
    expect(hook.opgegeven).toBe('te_veel')
    expect(FakeWebSocket.instances).toHaveLength(2)
    expect(gezondheidsvragen()).toHaveLength(0)
  })

  it('een component die verdwijnt laat geen controle achter', async () => {
    await mount()
    await geefOp()
    await act(async () => root.unmount())
    root = null
    const sockets = FakeWebSocket.instances.length
    serverTerug = true
    await wacht(ACHTERGROND_MS * 4)
    expect(FakeWebSocket.instances).toHaveLength(sockets)
  })
})
