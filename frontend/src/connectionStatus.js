// One connection status from three signals (#532, #783): the browser's network state, the chat socket, and whether
// the hook stopped trying (`opgegeven`: 'weg' after the last attempt, 'te_veel' when the server refused another
// window). navigator.onLine can stay true on a dead link, so the socket still drives 'reconnecting';
// offline wins even while the socket has not noticed yet.
export function connectionStatus({ online, connected, opgegeven = null }) {
  if (!online) return 'offline'
  if (opgegeven === 'te_veel') return 'te_veel'
  if (opgegeven) return 'opgegeven'
  if (!connected) return 'reconnecting'
  return 'ok'
}

// The statuses in which the app no longer tries by itself: the footer then offers to reconnect.
export const wachtOpGebruiker = (status) => status === 'opgegeven' || status === 'te_veel'

const TEXT = {
  offline: 'Je bent offline. Verbinding herstelt zodra je weer online bent.',
  reconnecting: 'Verbinding herstellen...',
  opgegeven: 'Geen verbinding.',
  te_veel: 'Geen verbinding: er staan te veel vensters open. Sluit er een.',
  ok: '',
}

// What the footer says for a status; empty when all is well.
export function connectionStatusText(status) {
  return TEXT[status] ?? ''
}
