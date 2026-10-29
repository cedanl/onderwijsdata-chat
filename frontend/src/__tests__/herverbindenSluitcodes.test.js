// @vitest-environment jsdom
// #783: het herverbinden paste niet bij de sluitcodes van de server.
// - 1013 (te veel vensters): de server opent en sluit meteen. De reset bij onopen liet de backoff nooit groeien:
//   elke seconde een poging en een nieuwe foutbubbel.
// - Na de laatste poging stopte het stil, en de voettekst bleef "Verbinding herstellen..." zeggen.
// - 4003 (origin geweigerd) werd behandeld als een netwerkstoring.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import useDashboardChat from '../hooks/useDashboardChat'
import { BACKOFF_DELAYS, MAX_RETRIES, STABIEL_MS, createRetry, opgevenBij } from '../socketHealth'
import { connectionStatus, connectionStatusText } from '../connectionStatus'
import ConnectionStatus from '../components/ConnectionStatus'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const TE_VEEL = 'Er staan te veel vensters open.'
let root
let hook

async function mount(useHook) {
  function Harness() {
    hook = useHook()
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
}

// Zoals routes/chat.py: accept, een foutmelding, dan sluiten met 1013.
async function weigerTeVeel(ws) {
  await act(async () => {
    ws.open()
    ws.emit({ type: 'error', message: TE_VEEL, modelafhankelijk: false })
    ws.finishClose(1013)
  })
}

const wacht = ms => act(async () => { vi.advanceTimersByTime(ms) })
const fouten = () => hook.messages.filter(m => m.isError)

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })))
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('createRetry (#783)', () => {
  it('begint pas opnieuw te tellen als een socket STABIEL_MS open bleef', () => {
    const connect = vi.fn()
    const opgegeven = vi.fn()
    const retry = createRetry(connect, { opgegeven })

    // Open en meteen weer dicht, vier keer: de pauze groeit, dan geeft hij op.
    for (let i = 0; i < MAX_RETRIES; i++) {
      retry.schedule()
      vi.advanceTimersByTime(BACKOFF_DELAYS[i] - 1)
      expect(connect).toHaveBeenCalledTimes(i)
      vi.advanceTimersByTime(1)
      retry.opened()
      vi.advanceTimersByTime(STABIEL_MS - 1)
    }
    retry.schedule()
    expect(opgegeven).toHaveBeenCalledOnce()

    // Een socket die lang genoeg open blijft, geeft de volle reeks weer.
    retry.reset()
    retry.schedule()
    vi.advanceTimersByTime(BACKOFF_DELAYS[0])
    retry.opened()
    vi.advanceTimersByTime(STABIEL_MS)
    retry.schedule()
    vi.advanceTimersByTime(BACKOFF_DELAYS[0])
    expect(connect).toHaveBeenCalledTimes(MAX_RETRIES + 2)
  })

  it('kent de sluitcodes waarbij opnieuw proberen niet helpt', () => {
    expect(opgevenBij(1013)).toBe('te_veel')
    expect(opgevenBij(4003)).toBe('weg')
    expect(opgevenBij(1006)).toBeNull()
    expect(opgevenBij(1000)).toBeNull()
  })
})

describe('de status als de app stopt met proberen (#783)', () => {
  it('heeft een eigen status, en offline gaat voor', () => {
    expect(connectionStatus({ online: true, connected: false, opgegeven: 'weg' })).toBe('opgegeven')
    expect(connectionStatus({ online: true, connected: false, opgegeven: 'te_veel' })).toBe('te_veel')
    expect(connectionStatus({ online: false, connected: false, opgegeven: 'weg' })).toBe('offline')
    expect(connectionStatus({ online: true, connected: false })).toBe('reconnecting')
    expect(connectionStatusText('opgegeven')).toBe('Geen verbinding.')
  })

  it('toont een knop "Opnieuw verbinden" die met het toetsenbord te bedienen is', async () => {
    const onOpnieuw = vi.fn()
    const div = document.createElement('div')
    document.body.appendChild(div)
    root = createRoot(div)
    await act(async () => { root.render(createElement(ConnectionStatus, { connected: false, opgegeven: 'weg', onOpnieuw })) })

    const knop = div.querySelector('button.ws-opnieuw')
    expect(div.querySelector('[role="status"]').textContent).toBe('Geen verbinding.Opnieuw verbinden')
    expect(knop.tagName).toBe('BUTTON')
    knop.focus()
    expect(document.activeElement).toBe(knop)
    await act(async () => { knop.click() })
    expect(onOpnieuw).toHaveBeenCalledOnce()

    await act(async () => { root.render(createElement(ConnectionStatus, { connected: false, onOpnieuw })) })
    expect(div.querySelector('button')).toBeNull()
    div.remove()
  })
})

describe.each([
  ['chat', useChat],
  ['dashboardchat', useDashboardChat],
])('herverbinden in de %s (#783)', (_, useHook) => {
  it('1013: één poging, één foutmelding, dan wacht hij op de gebruiker', async () => {
    await mount(useHook)
    await weigerTeVeel(FakeWebSocket.last)

    await wacht(Math.max(...BACKOFF_DELAYS) * 10)

    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(fouten().map(m => m.content)).toEqual([TE_VEEL])
    expect(hook.opgegeven).toBe('te_veel')

    // De gebruiker sloot een ander venster en probeert het opnieuw.
    await act(async () => { hook.verbindOpnieuw() })
    expect(FakeWebSocket.instances).toHaveLength(2)
    expect(hook.opgegeven).toBeNull()
    await act(async () => { FakeWebSocket.last.open() })
    expect(hook.connected).toBe(true)
  })

  it('4003: geen nieuwe poging', async () => {
    await mount(useHook)
    await act(async () => { FakeWebSocket.last.finishClose(4003) })
    await wacht(Math.max(...BACKOFF_DELAYS) * 10)
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(hook.opgegeven).toBe('weg')
  })

  it('na de laatste poging zegt hij dat hij stopte; de knop en online beginnen opnieuw', async () => {
    await mount(useHook)
    await act(async () => { FakeWebSocket.last.finishClose() })
    for (let i = 0; i < MAX_RETRIES; i++) {
      expect(hook.opgegeven).toBeNull()
      await wacht(BACKOFF_DELAYS[i])
      await act(async () => { FakeWebSocket.last.finishClose() })
    }
    expect(FakeWebSocket.instances).toHaveLength(MAX_RETRIES + 1)
    expect(hook.opgegeven).toBe('weg')

    await act(async () => { hook.verbindOpnieuw() })
    expect(FakeWebSocket.instances).toHaveLength(MAX_RETRIES + 2)
    // Een nieuwe volle reeks: weer MAX_RETRIES pogingen voordat hij opgeeft.
    await act(async () => { FakeWebSocket.last.finishClose() })
    await wacht(BACKOFF_DELAYS[0])
    expect(FakeWebSocket.instances).toHaveLength(MAX_RETRIES + 3)
    expect(hook.opgegeven).toBeNull()
  })

  it('een socket die opent en meteen sluit, laat de pauze groeien in plaats van elke seconde te proberen', async () => {
    await mount(useHook)
    await act(async () => { FakeWebSocket.last.open(); FakeWebSocket.last.finishClose() })
    await wacht(BACKOFF_DELAYS[0])
    await act(async () => { FakeWebSocket.last.open(); FakeWebSocket.last.finishClose() })
    // Met de oude reset bij onopen kwam hier na 1 s weer een poging; nu pas na 2 s.
    await wacht(BACKOFF_DELAYS[0])
    expect(FakeWebSocket.instances).toHaveLength(2)
    await wacht(BACKOFF_DELAYS[1] - BACKOFF_DELAYS[0])
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it('een socket die lang genoeg open bleef, telt als hersteld', async () => {
    await mount(useHook)
    await act(async () => { FakeWebSocket.last.open() })
    await wacht(STABIEL_MS)
    await act(async () => { FakeWebSocket.last.finishClose() })
    await wacht(BACKOFF_DELAYS[0])
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
