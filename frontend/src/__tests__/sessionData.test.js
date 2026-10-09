// @vitest-environment jsdom
// #498: one list of user-bound localStorage keys, so a new key cannot be left out of the wipe.
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import * as constants from '../constants'
import { SESSION_DATA_KEYS, NOT_SESSION_DATA_KEYS } from '../constants'
import { clearLocalSessionData } from '../sessionData'

const storageExports = Object.entries(constants).filter(([name]) => name.startsWith('STORAGE_'))

const SRC = join(__dirname, '..')

function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    if (e.name === '__tests__') return []
    const path = join(dir, e.name)
    return e.isDirectory() ? sources(path) : /\.jsx?$/.test(e.name) ? [path] : []
  })
}

describe('storage key registry', () => {
  it('holds the conversations, current chat, workbooks and dashboard chat as session data', () => {
    expect(SESSION_DATA_KEYS).toEqual(expect.arrayContaining([
      constants.STORAGE_CONVERSATIONS,
      constants.STORAGE_CURRENT_CHAT,
      constants.STORAGE_WORKBOOKS,
      constants.STORAGE_DC_MESSAGES,
      constants.STORAGE_DC_FIGURES,
    ]))
  })

  it('keeps settings, onboarded, token, model and user info out of the session data on purpose', () => {
    expect(NOT_SESSION_DATA_KEYS).toEqual(expect.arrayContaining([
      constants.STORAGE_SETTINGS,
      constants.STORAGE_ONBOARDED,
      constants.STORAGE_TOKEN,
      constants.STORAGE_MODEL,
      constants.STORAGE_USERINFO,
    ]))
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

  // The guard above only sees STORAGE_* exports: a key written as a literal or a local constant
  // would slip past it. sessionData.js loops over the registry with `key`.
  it('reads and writes browser storage only through a STORAGE_* key from constants.js', () => {
    const offenders = sources(SRC).flatMap(path => {
      const file = relative(SRC, path)
      return [...readFileSync(path, 'utf8').matchAll(/(?:local|session)Storage\.(?:get|set|remove)Item\(\s*([^,)]*)/g)]
        .map(m => m[1].trim())
        .filter(arg => !(arg in constants && arg.startsWith('STORAGE_')) && !(file === 'sessionData.js' && arg === 'key'))
        .map(arg => `${file}: ${arg}`)
    })
    expect(offenders, `use a STORAGE_* key from constants.js: ${offenders.join(', ')}`).toEqual([])
  })
})

describe('clearLocalSessionData', () => {
  beforeEach(() => localStorage.clear())

  it('leaves exactly the keys that are not session data', () => {
    for (const [, key] of storageExports) localStorage.setItem(key, 'x')

    clearLocalSessionData()

    const left = Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).sort()
    expect(left).toEqual([...NOT_SESSION_DATA_KEYS].sort())
  })
})
