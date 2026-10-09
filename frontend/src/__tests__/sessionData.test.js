// @vitest-environment jsdom
// #498: one list of user-bound localStorage keys, so a new key cannot be left out of the wipe.
import { describe, it, expect, beforeEach } from 'vitest'
import * as constants from '../constants'
import { SESSION_DATA_KEYS, NOT_SESSION_DATA_KEYS } from '../constants'
import { clearLocalSessionData } from '../sessionData'

const storageExports = Object.entries(constants).filter(([name]) => name.startsWith('STORAGE_'))

describe('storage key registry', () => {
  it('holds the conversations, current chat, workbooks and dashboard chat as session data', () => {
    expect(SESSION_DATA_KEYS).toEqual(expect.arrayContaining([
      constants.STORAGE_CONVERSATIONS,
      constants.STORAGE_CURRENT_CHAT,
      constants.STORAGE_WORKBOOKS,
      constants.STORAGE_DC_MESSAGES,
      constants.STORAGE_DC_FIGURES,
    ]))
    expect(SESSION_DATA_KEYS).toHaveLength(5)
  })

  it('keeps settings, onboarded, token and model out of the session data on purpose', () => {
    expect(NOT_SESSION_DATA_KEYS).toEqual(expect.arrayContaining([
      constants.STORAGE_SETTINGS,
      constants.STORAGE_ONBOARDED,
      constants.STORAGE_TOKEN,
      constants.STORAGE_MODEL,
    ]))
    expect(NOT_SESSION_DATA_KEYS).toHaveLength(4)
  })

  it('places every STORAGE_* key in exactly one of the two lists', () => {
    const unlisted = storageExports
      .filter(([, key]) => !SESSION_DATA_KEYS.includes(key) && !NOT_SESSION_DATA_KEYS.includes(key))
      .map(([name, key]) => `${name} (${key})`)
    const inBoth = storageExports
      .filter(([, key]) => SESSION_DATA_KEYS.includes(key) && NOT_SESSION_DATA_KEYS.includes(key))
      .map(([name, key]) => `${name} (${key})`)
    expect(unlisted, `add to SESSION_DATA_KEYS or NOT_SESSION_DATA_KEYS: ${unlisted.join(', ')}`).toEqual([])
    expect(inBoth, `in both SESSION_DATA_KEYS and NOT_SESSION_DATA_KEYS: ${inBoth.join(', ')}`).toEqual([])
  })
})

describe('clearLocalSessionData', () => {
  beforeEach(() => localStorage.clear())

  it('leaves exactly the keys that are not session data', () => {
    for (const [, key] of storageExports) localStorage.setItem(key, 'x')
    // Belongs to the token: auth.clearToken removes it, not the session-data wipe.
    localStorage.setItem('userInfo', '{}')

    clearLocalSessionData()

    const left = Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).sort()
    expect(left).toEqual([...NOT_SESSION_DATA_KEYS, 'userInfo'].sort())
  })
})
