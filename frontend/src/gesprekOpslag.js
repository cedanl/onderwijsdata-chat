import { STORAGE_SAVED_CHAT } from './constants'

// Wat de server van het open gesprek heeft (#635). Na herladen telde het herstelde gesprek als opgeslagen, ook als
// de PUT nooit liep (herladen tijdens een vraag) of mislukte (offline): het stond dan alleen in deze browser, en
// uitloggen wist dat. Een geslaagde PUT laat een vingerafdruk achter; een hersteld gesprek zonder die afdruk gaat
// alsnog naar de server. Alleen het id en een hash, geen inhoud.

// FNV-1a, 32 bit: genoeg om te zien of het gesprek veranderde, en snel genoeg voor een groot gesprek.
export function vingerafdruk(tekst) {
  let h = 0x811c9dc5
  for (let i = 0; i < tekst.length; i++) {
    h ^= tekst.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0).toString(36)
}

export function noteerOpgeslagen(id, json) {
  try { localStorage.setItem(STORAGE_SAVED_CHAT, JSON.stringify({ id: String(id), afdruk: vingerafdruk(json) })) } catch { /* noop */ }
}

export function isOpgeslagen(id, json) {
  try {
    const opgeslagen = JSON.parse(localStorage.getItem(STORAGE_SAVED_CHAT) || 'null')
    return opgeslagen?.id === String(id) && opgeslagen.afdruk === vingerafdruk(json)
  } catch {
    return false
  }
}

// De PUT's en DELETE's die nog lopen. Uitloggen trekt het token pas in als ze klaar zijn: een PUT van een groot
// antwoord (360 kB) liep anders soms nog toen de server het token al niet meer aannam, en een verwijdering ging
// dan stil verloren (#778).
const lopend = new Set()

export function volgOpslag(opslag) {
  lopend.add(opslag)
  opslag.then(() => lopend.delete(opslag), () => lopend.delete(opslag))
  return opslag
}

export function wachtOpOpslag(maxMs = 10000) {
  if (!lopend.size) return Promise.resolve()
  return Promise.race([Promise.allSettled([...lopend]), new Promise(r => setTimeout(r, maxMs))])
}

// Wat vóór het uitloggen nog moet gebeuren, zolang het token er is: een verwijdering in haar bedenktijd gaat dan
// meteen (#778). Na het uitloggen zou ze zonder token gaan, een 401 krijgen en het gesprek op de server laten.
const voorUitloggen = new Set()

export function bijUitloggen(fn) {
  voorUitloggen.add(fn)
  return () => { voorUitloggen.delete(fn) }
}

export function rondAfVoorUitloggen() {
  voorUitloggen.forEach(fn => fn())
}
