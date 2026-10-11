// Detects a silently dead WebSocket (#489). A dropped wifi link fires onclose only
// after the TCP timeout, so `connected` stayed true while the progress pill kept
// counting. Two signals close that gap: the browser's offline/online events, and an
// app-level ping the server answers with pong.

export const HEARTBEAT_INTERVAL_MS = 15000
export const PONG_TIMEOUT_MS = 5000

// The heartbeat pings over the open socket and closes it when nothing comes back in
// time; any incoming message counts as proof of life. Closing hands the dead
// connection to the hook's own onclose path: melding, interrupted turn, reconnect.
export function createHeartbeat(getWs) {
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

  const start = () => {
    stop()
    interval = setInterval(() => {
      const ws = getWs()
      if (!ws || ws.readyState !== WebSocket.OPEN) return
      ws.send(JSON.stringify({ action: 'ping' }))
      if (pongTimeout === null) {
        pongTimeout = setTimeout(() => getWs()?.close(), PONG_TIMEOUT_MS)
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  return { start, alive, stop }
}

// offline/online from the browser arrive seconds before any socket error does.
export function watchNetwork(onOffline, onOnline) {
  window.addEventListener('offline', onOffline)
  window.addEventListener('online', onOnline)
  return () => {
    window.removeEventListener('offline', onOffline)
    window.removeEventListener('online', onOnline)
  }
}
