// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { getToken, clearToken, sessionEndedSince } from '../auth'
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
