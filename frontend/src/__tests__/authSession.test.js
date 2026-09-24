// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { getToken, clearToken, sessionEndedSince, tokenExpiresAt } from '../auth'
import { STORAGE_TOKEN } from '../constants'

describe('sessionEndedSince', () => {
  beforeEach(() => localStorage.clear())

  it('is true after logging out', () => {
    localStorage.setItem(STORAGE_TOKEN, 'abc')
    const tokenAtMount = getToken()
    clearToken()
    expect(sessionEndedSince(tokenAtMount)).toBe(true)
  })

  it('is false while still logged in', () => {
    localStorage.setItem(STORAGE_TOKEN, 'abc')
    expect(sessionEndedSince(getToken())).toBe(false)
  })

  it('is false when auth is off and there never was a token', () => {
    expect(sessionEndedSince(getToken())).toBe(false)
  })
})

// Same shape as core.auth.make_token: base64url without padding, then a signature.
const serverToken = (username, exp) =>
  btoa(`${username}|${exp}`).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '') + '.sig'

describe('tokenExpiresAt', () => {
  it('reads the expiry from a server token', () => {
    expect(tokenExpiresAt(serverToken('demo', 1790000000))).toBe(1790000000 * 1000)
  })

  it('copes with url-safe characters and a | in the username', () => {
    const token = serverToken('??>|x', 1790000000)
    expect(token).toContain('-')
    expect(tokenExpiresAt(token)).toBe(1790000000 * 1000)
  })

  it('returns null for anything else', () => {
    expect(tokenExpiresAt('')).toBeNull()
    expect(tokenExpiresAt('not a token')).toBeNull()
  })
})
