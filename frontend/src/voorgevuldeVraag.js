import { STORAGE_VOORGEVULDE_VRAAG } from './constants'

// A link into the app can carry a question (#709): /chat#vraag=…, for example from the catalogue MCP server (#707).
// In the fragment, not the query: a browser never sends '#…' to a server or proxy, so the question, often words from
// what the user asked elsewhere, stays out of their access logs (#103, #475). It goes into the input box of a new
// conversation and is never sent by itself: the user reads it first.
export const VRAAG_PARAM = 'vraag'
export const MAX_VOORGEVULDE_VRAAG = 500

// Control and format characters (zero-width, bidi overrides: a link can make text read otherwise than it is) and angle
// brackets go; a line break becomes a space. The question stays one line of plain text.
const WEG = /[\p{Cc}\p{Cf}<>]/gu

export function schoonVraag(ruw) {
  if (typeof ruw !== 'string') return null
  const tekst = ruw.replace(WEG, teken => (/\s/.test(teken) ? ' ' : '')).replace(/\s+/g, ' ').trim()
  // Per code point, so a cut never splits an emoji or another surrogate pair.
  return Array.from(tekst).slice(0, MAX_VOORGEVULDE_VRAAG).join('').trim() || null
}

// At startup, before the router and the login screen: the parameter leaves the address bar and history, and the
// question waits in sessionStorage. That survives the round trip via SRAM in this tab, which lands back on /.
export function bewaarVraagUitUrl() {
  const params = new URLSearchParams(window.location.hash.slice(1))
  if (!params.has(VRAAG_PARAM)) return
  const vraag = schoonVraag(params.get(VRAAG_PARAM))
  params.delete(VRAAG_PARAM)
  const rest = params.toString()
  window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search + (rest ? `#${rest}` : ''))
  try {
    if (vraag) sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, vraag)
    else sessionStorage.removeItem(STORAGE_VOORGEVULDE_VRAAG)
  } catch { /* storage blocked: the link opens the app without the question */ }
}

export function wachtVoorgevuldeVraag() {
  try { return sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG) !== null } catch { return false }
}

// Once: the chat takes the question out, so a reload or a later visit does not fill the box again.
export function neemVoorgevuldeVraag() {
  try {
    const vraag = sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)
    sessionStorage.removeItem(STORAGE_VOORGEVULDE_VRAAG)
    return schoonVraag(vraag)
  } catch {
    return null
  }
}
