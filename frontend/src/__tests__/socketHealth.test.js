// #489: a silently dead connection fires onclose only after the TCP timeout. The
// heartbeat pings the server and closes the socket itself when nothing comes back.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createHeartbeat, HEARTBEAT_INTERVAL_MS, PONG_TIMEOUT_MS } from '../socketHealth'

class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 3
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    this.sent = []
  }
  send(data) { this.sent.push(JSON.parse(data)) }
  close() { this.readyState = FakeWebSocket.CLOSED }
}

let ws
let heartbeat

beforeEach(() => {
  vi.useFakeTimers()
  globalThis.WebSocket = FakeWebSocket
  ws = new FakeWebSocket()
  heartbeat = createHeartbeat(() => ws)
})

afterEach(() => {
  heartbeat.stop()
  vi.useRealTimers()
})

describe('createHeartbeat', () => {
  it('pings over the open socket on each interval', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS)
    expect(ws.sent).toEqual([{ action: 'ping' }])
  })

  it('closes the socket when nothing comes back in time', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS + PONG_TIMEOUT_MS)
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED)
  })

  it('keeps the socket open while messages keep arriving', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS)
    heartbeat.alive() // the pong, or any other server message
    vi.advanceTimersByTime(PONG_TIMEOUT_MS)
    expect(ws.readyState).toBe(FakeWebSocket.OPEN)
  })

  it('does not ping a socket that is no longer open', () => {
    ws.readyState = FakeWebSocket.CLOSED
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 2)
    expect(ws.sent).toEqual([])
  })

  it('stops pinging after stop', () => {
    heartbeat.start()
    heartbeat.stop()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 2)
    expect(ws.sent).toEqual([])
  })
})
