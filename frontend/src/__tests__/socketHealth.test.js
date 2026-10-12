// #489: a silently dead connection fires onclose only after the TCP timeout. The
// heartbeat pings the server, closes the socket itself when nothing comes back and
// reports it dead at once (#522), without waiting for the closing handshake.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { BACKOFF_DELAYS, createHeartbeat, createRetry, HEARTBEAT_INTERVAL_MS, PONG_TIMEOUT_MS } from '../socketHealth'
import { FakeWebSocket } from './fakeWebSocket'

let ws
let heartbeat
let onDead

beforeEach(() => {
  vi.useFakeTimers()
  globalThis.WebSocket = FakeWebSocket
  ws = new FakeWebSocket()
  ws.open()
  onDead = vi.fn()
  heartbeat = createHeartbeat(() => ws, onDead)
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

  it('closes the socket and reports it dead when nothing comes back in time', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS + PONG_TIMEOUT_MS)
    expect(ws.readyState).toBe(FakeWebSocket.CLOSING)
    expect(onDead).toHaveBeenCalledExactlyOnceWith(ws)
  })

  it('reports a dead socket only once', () => {
    heartbeat.start()
    vi.advanceTimersByTime((HEARTBEAT_INTERVAL_MS + PONG_TIMEOUT_MS) * 3)
    expect(onDead).toHaveBeenCalledTimes(1)
  })

  it('keeps the socket open while messages keep arriving', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS)
    heartbeat.alive() // the pong, or any other server message
    vi.advanceTimersByTime(PONG_TIMEOUT_MS)
    expect(ws.readyState).toBe(FakeWebSocket.OPEN)
    expect(onDead).not.toHaveBeenCalled()
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

  it('reports nothing once stopped while a ping is unanswered', () => {
    heartbeat.start()
    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS)
    heartbeat.stop()
    vi.advanceTimersByTime(PONG_TIMEOUT_MS)
    expect(ws.readyState).toBe(FakeWebSocket.OPEN)
    expect(onDead).not.toHaveBeenCalled()
  })
})

describe('createRetry', () => {
  let connect
  let retry

  beforeEach(() => {
    connect = vi.fn()
    retry = createRetry(connect)
  })

  it('tries again after 1, 2, 4 and 8 s, then stops', () => {
    for (const [i, pause] of [1000, 2000, 4000, 8000].entries()) {
      retry.schedule()
      vi.advanceTimersByTime(pause - 1)
      expect(connect).toHaveBeenCalledTimes(i)
      vi.advanceTimersByTime(1)
      expect(connect).toHaveBeenCalledTimes(i + 1)
    }
    retry.schedule()
    vi.advanceTimersByTime(Math.max(...BACKOFF_DELAYS) * 2)
    expect(connect).toHaveBeenCalledTimes(4)
  })

  it('reset cancels the pending attempt and starts at the first pause again', () => {
    retry.schedule()
    vi.advanceTimersByTime(BACKOFF_DELAYS[0])
    retry.schedule()
    retry.reset()
    vi.advanceTimersByTime(Math.max(...BACKOFF_DELAYS))
    expect(connect).toHaveBeenCalledTimes(1)

    retry.schedule()
    vi.advanceTimersByTime(BACKOFF_DELAYS[0])
    expect(connect).toHaveBeenCalledTimes(2)
  })
})
