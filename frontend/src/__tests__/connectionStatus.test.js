import { describe, it, expect } from 'vitest'
import { connectionStatus, connectionStatusText } from '../connectionStatus'

// #532: één verbindingsstatus uit navigator.onLine en de WebSocket-staat.
describe('connectionStatus', () => {
  it('is offline zonder netwerk, ook als de socket nog open lijkt', () => {
    expect(connectionStatus({ online: false, connected: false })).toBe('offline')
    expect(connectionStatus({ online: false, connected: true })).toBe('offline')
  })

  it('herstelt de verbinding als er netwerk is maar geen socket', () => {
    expect(connectionStatus({ online: true, connected: false })).toBe('reconnecting')
  })

  it('is ok met netwerk en een open socket', () => {
    expect(connectionStatus({ online: true, connected: true })).toBe('ok')
  })
})

describe('connectionStatusText', () => {
  it('zegt offline waarom er niets doorkomt', () => {
    expect(connectionStatusText('offline')).toBe('Je bent offline. Verbinding herstelt zodra je weer online bent.')
  })

  it('meldt het herstel van de verbinding', () => {
    expect(connectionStatusText('reconnecting')).toBe('Verbinding herstellen...')
  })

  it('zegt niets als alles werkt', () => {
    expect(connectionStatusText('ok')).toBe('')
  })
})
