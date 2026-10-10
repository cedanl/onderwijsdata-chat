// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { logout, tokenExpiresAt } from '../auth'

describe('logout', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('asks the server to revoke the token with a Bearer header', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    logout('abc.def')

    expect(fetchMock).toHaveBeenCalledWith('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: 'Bearer abc.def' },
    })
  })

  it('swallows a failed request: logging out locally never depends on the server', async () => {
    const rejection = Promise.reject(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', vi.fn(() => rejection))
    const unhandled = vi.fn()
    process.on('unhandledRejection', unhandled)

    expect(() => logout('abc.def')).not.toThrow()
    await new Promise((resolve) => setTimeout(resolve, 0))

    process.off('unhandledRejection', unhandled)
    expect(unhandled).not.toHaveBeenCalled()
  })

  it('does not call the server without a token', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    logout(null)

    expect(fetchMock).not.toHaveBeenCalled()
  })
})

// Same shape as core.auth.make_token since #479: the session start sits before the expiry.
const serverToken = (payload) =>
  btoa(payload).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '') + '.sig'

describe('tokenExpiresAt with a session start', () => {
  it('reads the expiry, not the session start', () => {
    expect(tokenExpiresAt(serverToken('demo|1789971200|1790000000'))).toBe(1790000000 * 1000)
  })
})
