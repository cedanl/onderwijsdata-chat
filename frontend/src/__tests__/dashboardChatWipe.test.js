// @vitest-environment jsdom
// #498: a dashboard chat that was open at logout must not write the previous user's
// messages and figures back after the wipe.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import useDashboardChat from '../hooks/useDashboardChat'
import { clearLocalSessionData } from '../sessionData'
import { STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'

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

  // Documents why the wipe must go with unmounting the chat, as logout and session end do:
  // a chat that stays mounted persists its in-memory messages again on its next change.
  it('is written again by a chat that stays mounted and gets a message', async () => {
    const ws = await openChat()

    clearLocalSessionData()
    await act(async () => { ws.emit({ type: 'message_start' }) })

    expect(JSON.parse(localStorage.getItem(STORAGE_DC_MESSAGES))).toEqual([
      { id: 1, role: 'user', content: 'vorige gebruiker', done: true },
    ])
  })
})
