// @vitest-environment jsdom
// #498: a dashboard chat that was open at logout must not write the previous user's
// messages and figures back after the wipe.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act, useLayoutEffect } from 'react'
import { createRoot } from 'react-dom/client'
import useDashboardChat from '../hooks/useDashboardChat'
import { clearLocalSessionData } from '../sessionData'
import { clearToken } from '../auth'
import { STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES, STORAGE_TOKEN } from '../constants'

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

function Harness() {
  useDashboardChat()
  return null
}

async function openChat() {
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
  return FakeWebSocket.last
}

async function closeChat() {
  await act(async () => root.unmount())
  root = null
}

const dcKeys = () => [STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES].filter(key => localStorage.getItem(key) !== null)

beforeEach(() => {
  localStorage.clear()
  globalThis.WebSocket = FakeWebSocket
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  localStorage.setItem(STORAGE_DC_MESSAGES, JSON.stringify([{ id: 1, role: 'user', content: 'vorige gebruiker', done: true }]))
  localStorage.setItem(STORAGE_DC_FIGURES, JSON.stringify([{ data: [], layout: {} }]))
})

afterEach(async () => { if (root) await closeChat() })

describe('dashboard chat after the session-data wipe', () => {
  it('stays wiped when the chat unmounts and its socket still delivers events', async () => {
    const ws = await openChat()

    clearLocalSessionData()
    await closeChat()
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'laat antwoord' })
      ws.emit({ type: 'figure', figure_json: { data: [], layout: {} } })
      ws.emit({ type: 'message_end' })
      ws.onclose({ code: 1000 })
    })

    expect(dcKeys()).toEqual([])
  })

  // Logout and session end clear the token before the wipe; the chat checks it before each save.
  it('stays wiped by a chat that stays mounted and gets a message after the session ended', async () => {
    const ws = await openChat()

    clearToken()
    clearLocalSessionData()
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'figure', figure_json: { data: [], layout: {} } })
    })

    expect(dcKeys()).toEqual([])
  })
})

// Without act, as in a browser: React commits a render and runs its passive effects (the two
// saves) later. A logout click can land in between; the save that then runs must be skipped.
describe('a save still pending when the session ends', () => {
  const settle = () => new Promise(resolve => setTimeout(resolve, 20))
  let logOutOnCommit = false

  // The layout effect runs in the commit, before React runs that commit's passive effects:
  // it plays the logout click (clearToken, then the wipe) that lands in that gap.
  function LoggingOutHarness() {
    const { messages, figures } = useDashboardChat()
    useLayoutEffect(() => {
      if (!logOutOnCommit) return
      logOutOnCommit = false
      clearToken()
      clearLocalSessionData()
    }, [messages, figures])
    return null
  }

  beforeEach(() => { globalThis.IS_REACT_ACT_ENVIRONMENT = false })
  afterEach(() => { globalThis.IS_REACT_ACT_ENVIRONMENT = true })

  it('does not write the previous user\'s chat back', async () => {
    const pending = createRoot(document.createElement('div'))
    pending.render(createElement(LoggingOutHarness))
    await settle()
    const ws = FakeWebSocket.last

    logOutOnCommit = true
    ws.emit({ type: 'message_start' })
    ws.emit({ type: 'text_delta', content: 'antwoord voor de vorige gebruiker' })
    ws.emit({ type: 'figure', figure_json: { data: [], layout: {} } })
    ws.emit({ type: 'message_end' })
    await settle()
    pending.unmount()
    await settle()

    expect(logOutOnCommit).toBe(false)
    expect(dcKeys()).toEqual([])
  })
})
