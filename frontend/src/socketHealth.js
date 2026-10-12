// Detects a silently dead WebSocket (#489). A dropped wifi link fires onclose only
// after the TCP timeout, so `connected` stayed true while the progress pill kept
// counting. Two signals close that gap: the browser's offline/online events, and an
// app-level ping the server answers with pong.

export const HEARTBEAT_INTERVAL_MS = 15000
export const PONG_TIMEOUT_MS = 5000

export const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
const MAX_RETRIES = 4

// The heartbeat pings over the open socket; any incoming message counts as proof of life.
// When nothing comes back in time it closes the socket and calls onDead(ws) at once: a
// real close() is asynchronous, and its onclose only follows after the closing handshake.
export function createHeartbeat(getWs, onDead) {
  let interval = null
  let pongTimeout = null

  const alive = () => {
    clearTimeout(pongTimeout)
    pongTimeout = null
  }

  const stop = () => {
    clearInterval(interval)
    interval = null
    alive()
  }

  const die = (ws) => {
    stop()
    ws.close()
    onDead(ws)
  }

  const start = () => {
    stop()
    interval = setInterval(() => {
      const ws = getWs()
      if (!ws || ws.readyState !== WebSocket.OPEN) return
      ws.send(JSON.stringify({ action: 'ping' }))
      if (pongTimeout === null) {
        pongTimeout = setTimeout(() => die(ws), PONG_TIMEOUT_MS)
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  return { start, alive, stop }
}

// Reconnect attempts after a lost connection: a growing pause, MAX_RETRIES in a row at most.
// reset() cancels a pending attempt and starts the count over (a socket opened, the network
// came back, or the hook unmounts).
export function createRetry(connect) {
  let count = 0
  let timeout = null

  const reset = () => {
    clearTimeout(timeout)
    timeout = null
    count = 0
  }

  const schedule = () => {
    if (count >= MAX_RETRIES) return
    const delay = BACKOFF_DELAYS[count] ?? BACKOFF_DELAYS[BACKOFF_DELAYS.length - 1]
    count += 1
    timeout = setTimeout(connect, delay)
  }

  return { schedule, reset }
}

const isLive = (ws) => ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING

// offline/online from the browser arrive seconds before any socket error does. Offline closes
// the socket and hands it to the hook's lost path at once. Online reconnects without waiting
// for the backoff, unless a socket is already open or opening; a socket that is still closing
// gets its lost path first, so its turn has ended before a new socket takes over.
export function watchNetwork({ getWs, lost, retry, connect }) {
  const onOffline = () => {
    const ws = getWs()
    if (!ws) return
    ws.close()
    lost(ws)
  }

  const onOnline = () => {
    const ws = getWs()
    const live = isLive(ws)
    if (ws && !live) lost(ws)
    retry.reset()
    if (!live) connect()
  }

  window.addEventListener('offline', onOffline)
  window.addEventListener('online', onOnline)
  return () => {
    window.removeEventListener('offline', onOffline)
    window.removeEventListener('online', onOnline)
  }
}
