// @vitest-environment jsdom
// #532: de dashboardmaker toont dezelfde verbindingsstatus als de chat, in een live region die
// altijd gemount is, zodat een schermlezer offline en herstel aankondigt.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'
import DashboardCreator from '../components/DashboardCreator'

vi.mock('../api', () => ({ fetchSettingsConfig: () => new Promise(() => {}) }))
vi.mock('../workbooks', () => ({ saveWorkbookWithSync: vi.fn() }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const OFFLINE = 'Je bent offline. Verbinding herstelt zodra je weer online bent.'

let root
let container

const setOnline = value => Object.defineProperty(navigator, 'onLine', { configurable: true, value })
const fire = type => act(async () => { window.dispatchEvent(new Event(type)) })
const status = () => container.querySelector('.dc-input-footer [role="status"][aria-live="polite"]')

beforeEach(async () => {
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  Element.prototype.scrollIntoView = () => {}
  setOnline(true)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(DashboardCreator, { onSaved: vi.fn() })) })
})

afterEach(() => {
  act(() => root.unmount())
  document.body.innerHTML = ''
  delete navigator.onLine
})

describe('DashboardCreator verbindingsstatus', () => {
  it('meldt het herstel van de verbinding zolang de socket niet open is', () => {
    expect(status().textContent).toBe('Verbinding herstellen...')
  })

  it('houdt de live region leeg gemount zodra de socket open is', async () => {
    const el = status()
    await act(async () => { FakeWebSocket.last.open() })
    expect(status()).toBe(el)
    expect(el.textContent).toBe('')
  })

  it('meldt offline en weer verbonden in hetzelfde element', async () => {
    await act(async () => { FakeWebSocket.last.open() })
    const el = status()

    setOnline(false)
    await fire('offline')
    expect(status()).toBe(el)
    expect(el.textContent).toBe(OFFLINE)

    setOnline(true)
    await fire('online')
    await act(async () => { FakeWebSocket.last.open() })
    expect(status()).toBe(el)
    expect(el.textContent).toBe('')
  })
})
