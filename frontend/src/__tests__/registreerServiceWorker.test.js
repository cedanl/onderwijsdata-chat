import { describe, expect, it, vi } from 'vitest'
import { registreerServiceWorker } from '../registreerServiceWorker'

const maak = (readyState = 'complete', register = vi.fn().mockResolvedValue()) => {
  const luisteraars = []
  const win = { document: { readyState }, addEventListener: (type, fn) => luisteraars.push([type, fn]) }
  return { win, nav: { serviceWorker: { register } }, register, luisteraars }
}

describe('registreerServiceWorker', () => {
  it('registreert /sw.js meteen als de pagina al geladen is', () => {
    const { win, nav, register } = maak('complete')
    registreerServiceWorker({ nav, win, productie: true })
    expect(register).toHaveBeenCalledWith('/sw.js')
  })

  it('wacht met registreren tot de pagina geladen is', () => {
    const { win, nav, register, luisteraars } = maak('loading')
    registreerServiceWorker({ nav, win, productie: true })
    expect(register).not.toHaveBeenCalled()
    expect(luisteraars.map(([type]) => type)).toEqual(['load'])
    luisteraars[0][1]()
    expect(register).toHaveBeenCalledWith('/sw.js')
  })

  it('doet niets in dev, zonder ondersteuning of zonder window', () => {
    const { win, nav, register } = maak()
    registreerServiceWorker({ nav, win, productie: false })
    registreerServiceWorker({ nav: {}, win, productie: true })
    registreerServiceWorker({ nav, win: null, productie: true })
    expect(register).not.toHaveBeenCalled()
  })

  it('laat een mislukte registratie de app niet raken', async () => {
    const { win, nav } = maak('complete', vi.fn().mockRejectedValue(new Error('geblokkeerd')))
    expect(() => registreerServiceWorker({ nav, win, productie: true })).not.toThrow()
    await Promise.resolve()
  })
})
