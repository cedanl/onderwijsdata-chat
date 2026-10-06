// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import { loadCurrentChat, persistCurrentChat } from '../conversationStore'
import { clarificationAnswer, hasOpenClarification } from '../clarificationState'

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
let chat

function Harness() {
  chat = useChat()
  return null
}

async function openPage() {
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
  return FakeWebSocket.last
}

async function closePage() {
  await act(async () => root.unmount())
  root = null
}

const cards = messages => messages.flatMap((m, i) => (m.clarification ? [i] : []))

beforeEach(() => {
  localStorage.clear()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(() => root && act(() => root.unmount()))

// #109: question → two clarifications → reload → answer, as the chat page goes through it.
describe('two clarifications survive a reload', () => {
  it('keeps both choices, closes both cards and answers the follow-up with their context', async () => {
    let ws = await openPage()
    await act(async () => { chat.send('Hoeveel studenten zijn er?') })
    await act(async () => { ws.emit({ type: 'clarification', vraag: 'Welk onderwijstype?', opties: ['mbo', 'hbo'] }) })
    await act(async () => { chat.sendClarification('hbo') })
    await act(async () => { ws.emit({ type: 'clarification', vraag: 'Welk schooljaar?', opties: ['2023/24', 'Alle jaren'] }) })
    await act(async () => { chat.sendClarification('2023/24') })
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'In 2023/24 studeerden er … in het hbo.' })
    })
    persistCurrentChat('conv-a', chat.messages)
    await closePage()

    const { messages: restored } = loadCurrentChat()
    expect(cards(restored).map(i => clarificationAnswer(restored, i))).toEqual([
      { answered: true, choice: 'hbo' },
      { answered: true, choice: '2023/24' },
    ])
    expect(hasOpenClarification(restored)).toBe(false)

    ws = await openPage()
    await act(async () => { chat.sendHistory(restored) })
    const [history] = ws.sent.filter(m => m.action === 'history')
    expect(history.messages.map(m => m.content)).toEqual([
      'Hoeveel studenten zijn er?',
      'Welk onderwijstype?', 'hbo',
      'Welk schooljaar?', '2023/24',
      'In 2023/24 studeerden er … in het hbo.',
    ])

    await act(async () => { chat.send('En in het mbo?') })
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'In het mbo …' })
    })
    expect(chat.messages.at(-1)).toMatchObject({ role: 'assistant', content: 'In het mbo …', done: true })
  })

  it('reopens on the card that was still open, with its options free', async () => {
    const ws = await openPage()
    await act(async () => { chat.send('Hoeveel studenten zijn er?') })
    await act(async () => { ws.emit({ type: 'clarification', vraag: 'Welk onderwijstype?', opties: ['mbo', 'hbo'] }) })
    await act(async () => { chat.sendClarification('hbo') })
    await act(async () => { ws.emit({ type: 'clarification', vraag: 'Welk schooljaar?', opties: ['2023/24', 'Alle jaren'] }) })
    persistCurrentChat('conv-a', chat.messages)
    await closePage()

    const { messages: restored } = loadCurrentChat()
    const [first, second] = cards(restored)
    expect(clarificationAnswer(restored, first)).toEqual({ answered: true, choice: 'hbo' })
    expect(clarificationAnswer(restored, second)).toEqual({ answered: false, choice: null })
    expect(hasOpenClarification(restored)).toBe(true)
    expect(restored[second].clarification).toEqual(['2023/24', 'Alle jaren'])
  })
})
