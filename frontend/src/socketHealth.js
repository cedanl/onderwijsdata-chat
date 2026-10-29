// Detects a silently dead WebSocket (#489). A dropped wifi link fires onclose only
// after the TCP timeout, so `connected` stayed true while the progress pill kept
// counting. Two signals close that gap: the browser's offline/online events, and an
// app-level ping the server answers with pong.

export const HEARTBEAT_INTERVAL_MS = 15000
// A ping that arrives behind a `reset` or `history` is answered only after the server has
// stopped the running task, which can take up to _STOP_TIMEOUT_S (5 s, routes/chat.py). Twice
// that wait, and still under the interval, so a healthy connection is never dropped (#522).
export const PONG_TIMEOUT_MS = 10000

export const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
export const MAX_RETRIES = 4
// Zo lang blijft een socket open voordat hij als herstelde verbinding telt en de teller opnieuw begint (#783). De
// server sluit een verbinding die hij niet wil direct na het openen (1013); een reset bij onopen liet de backoff dan
// nooit groeien, met elke seconde een nieuwe poging en een nieuwe foutmelding.
export const STABIEL_MS = 5000

// Sluitcodes waarbij opnieuw proberen niet helpt (#783), met de reden voor de status: te veel vensters open (1013,
// routes/chat.py _TE_VEEL_VERBINDINGEN), of een origin die de server weigert (4003). Die laatste sluit vóór accept en
// komt in de browser meestal als een kale 1006 aan; dan eindigt hij na MAX_RETRIES in 'weg'.
const OPGEVEN_BIJ = { 1013: 'te_veel', 4003: 'weg' }
export const opgevenBij = (code) => OPGEVEN_BIJ[code] ?? null

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

// Reconnect attempts after a lost connection: a growing pause, MAX_RETRIES in a row at most. After the last one
// `opgegeven` is called (#783): the status then says so, with a way to try again, instead of "herstellen" forever.
// opened() cancels a pending attempt; the count starts over only once the socket stayed open STABIEL_MS.
// reset() cancels everything and starts the count over (the network came back, the user asked, or the hook unmounts).
export function createRetry(connect, { opgegeven = () => {} } = {}) {
  let count = 0
  let timeout = null
  let stabiel = null

  const wachtNiet = () => {
    clearTimeout(stabiel)
    stabiel = null
  }

  const reset = () => {
    clearTimeout(timeout)
    timeout = null
    wachtNiet()
    count = 0
  }

  const opened = () => {
    clearTimeout(timeout)
    timeout = null
    wachtNiet()
    stabiel = setTimeout(() => { stabiel = null; count = 0 }, STABIEL_MS)
  }

  const schedule = () => {
    wachtNiet()
    if (count >= MAX_RETRIES) {
      opgegeven()
      return
    }
    const delay = BACKOFF_DELAYS[count] ?? BACKOFF_DELAYS[BACKOFF_DELAYS.length - 1]
    count += 1
    timeout = setTimeout(connect, delay)
  }

  return { schedule, reset, opened }
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
