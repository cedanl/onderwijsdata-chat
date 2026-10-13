// One connection status from two signals (#532): the browser's network state and the chat socket.
// navigator.onLine can stay true on a dead link, so the socket still drives 'reconnecting';
// offline wins even while the socket has not noticed yet.
export function connectionStatus({ online, connected }) {
  if (!online) return 'offline'
  if (!connected) return 'reconnecting'
  return 'ok'
}

const TEXT = {
  offline: 'Je bent offline. Verbinding herstelt zodra je weer online bent.',
  reconnecting: 'Verbinding herstellen...',
  ok: '',
}

// What the footer says for a status; empty when all is well.
export function connectionStatusText(status) {
  return TEXT[status] ?? ''
}
