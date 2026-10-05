// @vitest-environment jsdom
// #103: het auth-token staat nooit in een URL; query-strings belanden in proxy- en serverlogs.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { chatSocket, consumeTokenFromUrl, fetchUserInfo, getToken } from '../auth'
import { STORAGE_TOKEN } from '../constants'

beforeEach(() => {
  localStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('chatSocket', () => {
  it('sends the token as subprotocol, not in the URL', () => {
    const opened = []
    globalThis.WebSocket = function (url, protocols) { opened.push({ url, protocols }) }
    localStorage.setItem(STORAGE_TOKEN, 'abc.def')
    chatSocket()
    expect(opened[0].url).toMatch(/\/api\/chat$/)
    expect(opened[0].protocols).toEqual(['bearer', 'abc.def'])
  })

  it('opens without subprotocol when there is no token', () => {
    const opened = []
    globalThis.WebSocket = function (url, protocols) { opened.push({ url, protocols }) }
    chatSocket()
    expect(opened[0].protocols).toBeUndefined()
  })
})

describe('fetchUserInfo', () => {
  it('sends the token in the Authorization header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ username: 'a' }) })
    globalThis.fetch = fetchMock
    await fetchUserInfo('abc.def')
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/user')
    expect(options.headers.Authorization).toBe('Bearer abc.def')
  })
})

describe('consumeTokenFromUrl', () => {
  it('reads the token from the fragment and removes it from the address bar', () => {
    window.history.replaceState({}, '', '/chat#token=abc.def&user_data=%7B%22name%22%3A%22A%22%7D')
    const { token, userData } = consumeTokenFromUrl()
    expect(token).toBe('abc.def')
    expect(getToken()).toBe('abc.def')
    expect(userData).toEqual({ name: 'A' })
    expect(window.location.href).not.toContain('abc.def')
  })

  it('does nothing without a token in the fragment', () => {
    window.history.replaceState({}, '', '/chat#sectie')
    expect(consumeTokenFromUrl()).toBeNull()
    expect(window.location.hash).toBe('#sectie')
  })
})
