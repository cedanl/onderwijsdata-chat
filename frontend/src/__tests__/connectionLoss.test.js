// @vitest-environment jsdom
// #489: verbindingsverlies tijdens een lopende vraag gaf geen melding — `connected`
// werd pas false bij de TCP-timeout. Het offline-event en de heartbeat dichten dat gat.
// #522: een echte close() is asynchroon. De late onclose van een vervangen socket mag de
// nieuwe niet raken; de nep-socket sluit daarom pas als de test finishClose() aanroept.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import useDashboardChat from '../hooks/useDashboardChat'
import { BACKOFF_DELAYS, HEARTBEAT_INTERVAL_MS, PONG_TIMEOUT_MS } from '../socketHealth'
import { FakeWebSocket } from './fakeWebSocket'
import { connectionStatus } from '../connectionStatus'
import { useOnline } from '../hooks/useOnline'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const NA_LANGSTE_BACKOFF_MS = Math.max(...BACKOFF_DELAYS) + 1

let root
let hook
// #532: de status die de footer toont, afgeleid uit navigator.onLine en de socket van de hook.
let status

// De heartbeat start bij onopen; tests met fake timers zetten die daarom vóór mount aan.
async function mount(useHook, { open = true } = {}) {
  function Harness() {
    hook = useHook()
    status = connectionStatus({ online: useOnline(), connected: hook.connected })
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
  if (open) await act(async () => { FakeWebSocket.last.open() })
  return FakeWebSocket.last
}

// Zoals een browser: navigator.onLine wisselt vóór het event.
const setOnLine = value => Object.defineProperty(navigator, 'onLine', { configurable: true, value })
const offline = () => act(async () => { setOnLine(false); window.dispatchEvent(new Event('offline')) })
const online = () => act(async () => { setOnLine(true); window.dispatchEvent(new Event('online')) })
const assistant = () => hook.messages.filter(m => m.role === 'assistant')

async function startTurn(ws) {
  await act(async () => { hook.send('Hoeveel studenten telt het mbo?') })
  await act(async () => {
    ws.emit({ type: 'message_start' })
    ws.emit({ type: 'text_delta', content: 'Het aantal stud' })
  })
}

// Offline, dan online vóór de onclose van de oude socket: de nieuwe opent.
async function reconnectBeforeOldClose() {
  await offline()
  await online()
  const nieuw = FakeWebSocket.last
  await act(async () => { nieuw.open() })
  return nieuw
}

beforeEach(() => {
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  delete navigator.onLine
  vi.useRealTimers()
})

describe.each([
  ['useChat', useChat],
  ['useDashboardChat', useDashboardChat],
])('%s: verbindingsverlies tijdens een lopende vraag', (_, useHook) => {
  it('toont bij het offline-event meteen de herstelmelding en sluit de beurt af', async () => {
    const ws = await mount(useHook)
    await startTurn(ws)
    expect(hook.connected).toBe(true)
    expect(hook.busy).toBe(true)

    await offline()

    // Nog vóór onclose: de socket is pas aan het sluiten.
    expect(ws.readyState).toBe(FakeWebSocket.CLOSING)
    expect(hook.connected).toBe(false)
    expect(hook.busy).toBe(false)
    expect(assistant()).toMatchObject([{ done: true }])
  })

  it('verbindt bij het online-event direct opnieuw, zonder op de backoff te wachten', async () => {
    await mount(useHook)
    await offline()
    const voor = FakeWebSocket.instances.length

    await online()

    expect(FakeWebSocket.instances.length).toBe(voor + 1)
    await act(async () => { FakeWebSocket.last.open() })
    expect(hook.connected).toBe(true)
  })

  it('laat een open verbinding met rust bij een online-event', async () => {
    await mount(useHook)
    const voor = FakeWebSocket.instances.length
    await online()
    expect(FakeWebSocket.instances.length).toBe(voor)
  })

  it('plant na offline en een late onclose van dezelfde socket maar één nieuwe poging', async () => {
    vi.useFakeTimers()
    const ws = await mount(useHook)
    await offline()
    await act(async () => { ws.finishClose() })

    await act(async () => { vi.advanceTimersByTime(NA_LANGSTE_BACKOFF_MS) })

    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('houdt na offline, online en een late onclose van de oude socket precies één verbinding over', async () => {
    vi.useFakeTimers()
    const oud = await mount(useHook)
    await startTurn(oud)
    const nieuw = await reconnectBeforeOldClose()
    expect(nieuw).not.toBe(oud)

    await act(async () => { oud.finishClose() })

    expect(hook.connected).toBe(true)
    await act(async () => { vi.advanceTimersByTime(NA_LANGSTE_BACKOFF_MS) })
    expect(FakeWebSocket.instances).toEqual([oud, nieuw])
    expect(FakeWebSocket.live()).toEqual([nieuw])
    expect(hook.connected).toBe(true)
    // De beurt van vóór offline is één keer afgesloten.
    expect(assistant()).toMatchObject([{ done: true }])
  })

  it('laat een beurt op de nieuwe socket heel bij een late onclose van de oude', async () => {
    vi.useFakeTimers()
    const oud = await mount(useHook)
    const nieuw = await reconnectBeforeOldClose()
    await startTurn(nieuw)

    await act(async () => { oud.finishClose() })

    expect(hook.busy).toBe(true)
    expect(assistant()).toMatchObject([{ done: false }])
    // De heartbeat hoort bij de nieuwe socket; de oude krijgt geen ping.
    await act(async () => { vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS) })
    expect(nieuw.pings()).toBe(1)
    expect(oud.pings()).toBe(0)
  })

  it('negeert wat een vervangen socket nog stuurt', async () => {
    const oud = await mount(useHook)
    await reconnectBeforeOldClose()

    await act(async () => {
      oud.emit({ type: 'message_start' })
      oud.emit({ type: 'text_delta', content: 'antwoord van de oude sessie' })
    })

    expect(hook.messages).toEqual([])
  })

  it('telt een vervangen socket die alsnog opent niet als verbonden', async () => {
    const oud = await mount(useHook, { open: false })
    await offline()
    await online()
    const nieuw = FakeWebSocket.last

    await act(async () => { oud.open() })
    expect(hook.connected).toBe(false)

    await act(async () => { nieuw.open() })
    expect(hook.connected).toBe(true)
  })

  it('sluit bij online eerst de beurt af van een socket die de server nog aan het sluiten is', async () => {
    const oud = await mount(useHook)
    await startTurn(oud)
    // De server begon de closing-handshake; onclose volgt pas als die klaar is.
    oud.readyState = FakeWebSocket.CLOSING

    await online()

    expect(hook.busy).toBe(false)
    expect(assistant()).toMatchObject([{ done: true }])
    const nieuw = FakeWebSocket.last
    expect(nieuw).not.toBe(oud)
    await act(async () => { oud.finishClose() })
    expect(FakeWebSocket.live()).toEqual([nieuw])
  })

  it('meldt een stil gestorven verbinding via de heartbeat meteen, nog vóór onclose', async () => {
    vi.useFakeTimers()
    const ws = await mount(useHook)
    await startTurn(ws)

    // Geen enkel bericht komt terug: na ping + wachttijd is de verbinding dood.
    await act(async () => { vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS + PONG_TIMEOUT_MS) })

    expect(ws.pings()).toBe(1)
    expect(ws.readyState).toBe(FakeWebSocket.CLOSING)
    expect(hook.connected).toBe(false)
    expect(hook.busy).toBe(false)
    expect(assistant()).toMatchObject([{ done: true }])
  })

  it('houdt de verbinding open zolang de server pong blijft sturen', async () => {
    vi.useFakeTimers()
    const ws = await mount(useHook)
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS)
        ws.emit({ type: 'pong' })
      })
    }
    expect(ws.readyState).toBe(FakeWebSocket.OPEN)
    expect(hook.connected).toBe(true)
  })

  it('opent na unmount geen nieuwe verbinding, ook niet bij een late onclose', async () => {
    vi.useFakeTimers()
    const ws = await mount(useHook)
    act(() => root.unmount())
    root = null

    await act(async () => { ws.finishClose() })
    await act(async () => { vi.advanceTimersByTime(NA_LANGSTE_BACKOFF_MS) })

    expect(FakeWebSocket.instances).toEqual([ws])
  })
})

describe.each([
  ['useChat', useChat],
  ['useDashboardChat', useDashboardChat],
])('%s: verbindingsstatus voor de footer (#532)', (_, useHook) => {
  it('is offline na het offline-event zonder lopende vraag, en ok zodra de nieuwe socket open is', async () => {
    await mount(useHook)
    expect(status).toBe('ok')

    await offline()
    expect(status).toBe('offline')

    await online()
    expect(status).toBe('reconnecting')
    await act(async () => { FakeWebSocket.last.open() })
    expect(status).toBe('ok')
  })

  it('is offline na het offline-event tijdens een lopende vraag, en ok zodra de nieuwe socket open is', async () => {
    const ws = await mount(useHook)
    await startTurn(ws)
    expect(status).toBe('ok')

    await offline()
    expect(hook.busy).toBe(false)
    expect(status).toBe('offline')

    await online()
    await act(async () => { FakeWebSocket.last.open() })
    expect(status).toBe('ok')
  })
})

describe('useChat: rapport bij verbindingsverlies', () => {
  it('meldt een lopend rapport bij het offline-event meteen als mislukt, één keer', async () => {
    const ws = await mount(useChat)
    await act(async () => { hook.generateReport('tester') })
    expect(hook.reportBusy).toBe(true)

    await offline()
    expect(hook.reportBusy).toBe(false)
    await act(async () => { ws.finishClose() })

    expect(assistant().map(m => m.content)).toEqual([
      'De verbinding viel weg tijdens het maken van het rapport. Probeer het opnieuw.',
    ])
  })

  it('markeert het afgebroken antwoord als onderbroken', async () => {
    const ws = await mount(useChat)
    await startTurn(ws)
    await offline()
    expect(assistant()).toMatchObject([{ done: true, interrupted: true }])
  })
})
