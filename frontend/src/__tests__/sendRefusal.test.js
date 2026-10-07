import { describe, it, expect } from 'vitest'
import { sendRefusalReason } from '../sendRefusal'

describe('sendRefusalReason (#241)', () => {
  it('noemt een lopende run', () => {
    expect(sendRefusalReason({ connected: true, busy: true, resetting: false })).toMatch(/loopt nog een vraag/)
  })

  it('noemt een rapport dat nog wordt gemaakt (#417)', () => {
    expect(sendRefusalReason({ connected: true, busy: false, resetting: false, reporting: true })).toMatch(/rapport/i)
  })

  it('noemt een gesprek dat nog wordt gestart', () => {
    expect(sendRefusalReason({ connected: true, busy: false, resetting: true })).toMatch(/nieuwe gesprek/)
  })

  it('noemt een verbroken verbinding en dat de vraag blijft staan', () => {
    expect(sendRefusalReason({ connected: false, busy: false, resetting: false })).toMatch(/Geen verbinding.*blijft staan/)
  })

  it('geeft altijd een melding, ook zonder bekende reden', () => {
    expect(sendRefusalReason({ connected: true, busy: false, resetting: false })).toBeTruthy()
  })
})
