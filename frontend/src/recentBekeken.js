import { useSyncExternalStore } from 'react'
import { STORAGE_RECENT } from './constants'

// What this browser opened last and which reports it marked as favourite (#603). Only IDs, no titles: a
// list shows an ID only when it matches a conversation or report of the account that is logged in, so
// on a shared device or in a shared account nothing of someone else shows. Kept on logout for that reason.
const MAX = 10
const LEEG = { gesprekken: [], rapporten: [], favorieten: [] }

let cache = null
const luisteraars = new Set()

function lees() {
  if (cache) return cache
  try {
    const ruw = JSON.parse(localStorage.getItem(STORAGE_RECENT) || '{}')
    cache = Object.fromEntries(Object.keys(LEEG).map(k => [k, Array.isArray(ruw[k]) ? ruw[k].map(String) : []]))
  } catch {
    cache = LEEG
  }
  return cache
}

function schrijf(nieuw) {
  cache = nieuw
  try {
    localStorage.setItem(STORAGE_RECENT, JSON.stringify(nieuw))
  } catch {
    // Full or blocked storage: the lists still work until the page reloads.
  }
  luisteraars.forEach(f => f())
}

const vooraan = (lijst, id) => [String(id), ...lijst.filter(x => x !== String(id))].slice(0, MAX)

export function noteerGesprek(id) {
  if (id && lees().gesprekken[0] !== String(id)) schrijf({ ...lees(), gesprekken: vooraan(lees().gesprekken, id) })
}

export function noteerRapport(id) {
  if (id && lees().rapporten[0] !== String(id)) schrijf({ ...lees(), rapporten: vooraan(lees().rapporten, id) })
}

export function wisselFavoriet(id) {
  const { favorieten } = lees()
  const aan = favorieten.includes(String(id))
  schrijf({ ...lees(), favorieten: aan ? favorieten.filter(x => x !== String(id)) : [String(id), ...favorieten] })
}

// The items of `lijst` (conversations or reports of this account) in the order of `ids`; unknown IDs drop out.
export function inVolgorde(ids, lijst) {
  const perId = new Map(lijst.map(item => [String(item.id), item]))
  return ids.map(id => perId.get(id)).filter(Boolean)
}

function abonneer(f) {
  luisteraars.add(f)
  // Another tab of the same browser changed the lists.
  const opStorage = e => { if (e.key === STORAGE_RECENT) { cache = null; f() } }
  window.addEventListener('storage', opStorage)
  return () => { luisteraars.delete(f); window.removeEventListener('storage', opStorage) }
}

export function useRecent() {
  return useSyncExternalStore(abonneer, lees)
}

// For tests: forget the cached copy, so the next read comes from localStorage.
export function vergeetCache() {
  cache = null
}
