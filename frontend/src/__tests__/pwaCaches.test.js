import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import { PWA_CACHE_VOORVOEGSEL, wisPwaCaches } from '../pwaCaches'

const maakStore = namen => {
  const over = new Set(namen)
  return { over, keys: vi.fn(async () => [...over]), delete: vi.fn(async n => over.delete(n)) }
}

describe('wisPwaCaches', () => {
  it('wist de caches van de service worker en laat die van anderen staan', async () => {
    const store = maakStore(['edudata-shell-v1', 'edudata-assets-v1', 'iets-anders'])
    await wisPwaCaches(store)
    expect([...store.over]).toEqual(['iets-anders'])
  })

  it('doet niets zonder Cache API (onveilige context, oude browser)', async () => {
    await expect(wisPwaCaches(null)).resolves.toBeUndefined()
  })

  it('laat een geblokkeerde Cache API het uitloggen niet raken', async () => {
    const store = { keys: vi.fn().mockRejectedValue(new Error('SecurityError')), delete: vi.fn() }
    await expect(wisPwaCaches(store)).resolves.toBeUndefined()
  })

  it('gebruikt hetzelfde voorvoegsel als de worker, anders wist hij niets', () => {
    const sw = readFileSync(new URL('../../public/sw.js', import.meta.url), 'utf8')
    expect(sw).toContain(`const CACHE_VOORVOEGSEL = '${PWA_CACHE_VOORVOEGSEL}'`)
  })
})
